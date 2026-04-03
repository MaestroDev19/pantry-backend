from __future__ import annotations

import io
import json
import logging

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from pantry_server.core.config import Settings, get_settings
from pantry_server.main import app
from pantry_server.observability.logging_setup import JsonFormatter
from pantry_server.observability.metrics import record_auth_failure
from pantry_server.observability.redact import redact_for_log
from pantry_server.shared.dependencies import get_supabase_client


def _sample_value(metric_name: str, labels: dict[str, str]) -> float:
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name != metric_name:
                continue
            if all(sample.labels.get(k) == v for k, v in labels.items()):
                return float(sample.value)
    return 0.0


def test_metrics_endpoint_exposes_household_and_auth_counters() -> None:
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "household_operations_total" in body
    assert "auth_failures_total" in body


def test_record_auth_failure_increments_prometheus_counter() -> None:
    before = _sample_value("auth_failures_total", {"reason": "missing_credentials"})
    record_auth_failure(reason="missing_credentials")
    after = _sample_value("auth_failures_total", {"reason": "missing_credentials"})
    assert after == before + 1.0


def test_redact_for_log_scrubs_sensitive_keys() -> None:
    payload = {
        "invite_code": "SECRET1",
        "nested": {"authorization": "Bearer x", "safe": "ok"},
        "list": [{"token": "t"}],
    }
    out = redact_for_log(payload)
    assert out["invite_code"] == "[REDACTED]"
    assert out["nested"]["authorization"] == "[REDACTED]"
    assert out["nested"]["safe"] == "ok"
    assert out["list"][0]["token"] == "[REDACTED]"


def test_redact_for_log_scrubs_jwt_shaped_strings() -> None:
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    out = redact_for_log({"msg": jwt_like})
    assert out["msg"] == "[REDACTED]"


def test_missing_credentials_increments_auth_metric_with_supabase_configured() -> None:
    def fake_supabase(settings: Settings = Depends(get_settings)) -> object:
        return object()

    app.dependency_overrides[get_supabase_client] = fake_supabase
    try:
        before = _sample_value("auth_failures_total", {"reason": "missing_credentials"})
        client = TestClient(app)
        response = client.post(
            "/api/households/join",
            json={"invite_code": "ABCD12"},
        )
        assert response.status_code == 401
        after = _sample_value("auth_failures_total", {"reason": "missing_credentials"})
        assert after == before + 1.0
    finally:
        app.dependency_overrides.clear()


def test_json_formatter_emits_extra_fields_as_json() -> None:
    from pantry_server.observability.logging_events import log_household_event

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("pantry_server.observability.test_json")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_household_event(logger, operation="join", outcome="failure", reason="invalid_invite")
    payload = json.loads(stream.getvalue().strip())
    assert payload["event"] == "household_operation"
    assert payload["operation"] == "join"
    assert payload["outcome"] == "failure"
    assert payload["reason"] == "invalid_invite"
