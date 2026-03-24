from types import SimpleNamespace
from uuid import UUID

import anyio
import pytest

from pantry_server.contexts.pantry.application.pantry_service import PantryService
from pantry_server.core.exceptions import AppError


class _FakeQuery:
    def __init__(self, client: "_FakeSupabaseClient", table_name: str) -> None:
        self._client = client
        self._table_name = table_name
        self._op = "select"

    def select(self, _: str) -> "_FakeQuery":
        self._op = "select"
        return self

    def eq(self, _: str, __: str) -> "_FakeQuery":
        return self

    def limit(self, _: int) -> "_FakeQuery":
        return self

    def lte(self, _: str, __: str) -> "_FakeQuery":
        return self

    def insert(self, __: object) -> "_FakeQuery":
        self._op = "insert"
        return self

    def upsert(self, __: object, **___: object) -> "_FakeQuery":
        self._op = "upsert"
        return self

    def update(self, __: dict[str, object]) -> "_FakeQuery":
        self._op = "update"
        return self

    def delete(self) -> "_FakeQuery":
        self._op = "delete"
        return self

    def execute(self):
        self._client.record_call(self._table_name, self._op)
        return self._client.pop(self._table_name, self._op)


class _FakeSupabaseClient:
    def __init__(self, table_results: dict[tuple[str, str], list[object]] | None = None) -> None:
        self._table_results = table_results or {}
        self.calls: list[tuple[str, str]] = []

    def table(self, table_name: str) -> _FakeQuery:
        return _FakeQuery(self, table_name)

    def record_call(self, table_name: str, op: str) -> None:
        self.calls.append((table_name, op))

    def pop(self, table_name: str, op: str):
        key = (table_name, op)
        queue = self._table_results.get(key, [])
        if not queue:
            return SimpleNamespace(data=[])
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _item_row() -> dict[str, object]:
    return {
        "id": "17a336f0-eed2-4f5e-bf15-e4c4d89f9959",
        "household_id": "f8c2ce57-d0ac-4d8d-96f8-6c4a1844091a",
        "name": "Milk",
        "category": "dairy",
        "quantity": 1.0,
        "unit": "liter",
        "expiry_date": None,
    }


def test_add_single_item_returns_created_item() -> None:
    client = _FakeSupabaseClient(
        table_results={("pantry_items", "insert"): [SimpleNamespace(data=[_item_row()])]}
    )
    service = PantryService(client)

    result = anyio.run(
        lambda: service.add_single_item(
            owner_id=UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
            household_id=UUID("f8c2ce57-d0ac-4d8d-96f8-6c4a1844091a"),
            item_data={"name": "Milk", "category": "dairy", "quantity": 1, "unit": "liter"},
        )
    )

    assert result.name == "Milk"
    assert result.category == "dairy"


def test_add_single_item_sets_embedding_ready_when_inline_embedding_succeeds() -> None:
    class _CapturingQuery(_FakeQuery):
        def __init__(self, client: "_CapturingSupabaseClient", table_name: str) -> None:
            super().__init__(client, table_name)
            self._capturing_client = client

        def insert(self, payload: object) -> "_CapturingQuery":
            self._capturing_client.insert_payloads.append((self._table_name, payload))
            return super().insert(payload)

        def update(self, payload: dict[str, object]) -> "_CapturingQuery":
            self._capturing_client.update_payloads.append((self._table_name, payload))
            return super().update(payload)

    class _CapturingSupabaseClient(_FakeSupabaseClient):
        def __init__(self, table_results: dict[tuple[str, str], list[object]] | None = None) -> None:
            super().__init__(table_results=table_results)
            self.insert_payloads: list[tuple[str, object]] = []
            self.update_payloads: list[tuple[str, dict[str, object]]] = []

        def table(self, table_name: str) -> _CapturingQuery:
            return _CapturingQuery(self, table_name)

    client = _CapturingSupabaseClient(
        table_results={
            ("pantry_items", "insert"): [SimpleNamespace(data=[_item_row()])],
            ("pantry_items", "update"): [SimpleNamespace(data=[_item_row()])],
        }
    )
    service = PantryService(
        client,
        inline_embedding_timeout_seconds=1.0,
        embeddings_provider=lambda: SimpleNamespace(embed_query=lambda _: [0.1, 0.2, 0.3]),
    )

    result = anyio.run(
        lambda: service.add_single_item(
            owner_id=UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
            household_id=UUID("f8c2ce57-d0ac-4d8d-96f8-6c4a1844091a"),
            item_data={"name": "Milk", "category": "dairy", "quantity": 1, "unit": "liter"},
        )
    )

    assert result.name == "Milk"
    assert ("pantry_embedding_jobs", "insert") not in client.calls

    inserted_item_payload = next(payload for table, payload in client.insert_payloads if table == "pantry_items")
    assert isinstance(inserted_item_payload, dict)
    assert inserted_item_payload["embedding_status"] == "pending"

    updated_item_payload = next(payload for table, payload in client.update_payloads if table == "pantry_items")
    assert updated_item_payload["embedding"] == [0.1, 0.2, 0.3]
    assert updated_item_payload["embedding_status"] == "ready"
    assert updated_item_payload["embedding_error"] is None
    assert "embedding_updated_at" in updated_item_payload


def test_add_single_item_enqueues_job_when_inline_embedding_fails() -> None:
    class _CapturingQuery(_FakeQuery):
        def __init__(self, client: "_CapturingSupabaseClient", table_name: str) -> None:
            super().__init__(client, table_name)
            self._capturing_client = client

        def insert(self, payload: object) -> "_CapturingQuery":
            self._capturing_client.insert_payloads.append((self._table_name, payload))
            return super().insert(payload)

        def upsert(self, payload: object, **kwargs: object) -> "_CapturingQuery":
            self._capturing_client.upsert_payloads.append((self._table_name, payload, kwargs))
            return super().upsert(payload, **kwargs)

    class _CapturingSupabaseClient(_FakeSupabaseClient):
        def __init__(self, table_results: dict[tuple[str, str], list[object]] | None = None) -> None:
            super().__init__(table_results=table_results)
            self.insert_payloads: list[tuple[str, object]] = []
            self.upsert_payloads: list[tuple[str, object, dict[str, object]]] = []

        def table(self, table_name: str) -> _CapturingQuery:
            return _CapturingQuery(self, table_name)

    client = _CapturingSupabaseClient(
        table_results={
            ("pantry_items", "insert"): [SimpleNamespace(data=[_item_row()])],
            ("pantry_embedding_jobs", "upsert"): [SimpleNamespace(data=[{"id": "job-1"}])],
        }
    )
    service = PantryService(
        client,
        inline_embedding_timeout_seconds=0.1,
        embeddings_provider=lambda: SimpleNamespace(embed_query=lambda _: (_ for _ in ()).throw(RuntimeError("boom"))),
    )

    result = anyio.run(
        lambda: service.add_single_item(
            owner_id=UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
            household_id=UUID("f8c2ce57-d0ac-4d8d-96f8-6c4a1844091a"),
            item_data={"name": "Milk", "category": "dairy", "quantity": 1, "unit": "liter"},
        )
    )

    assert result.name == "Milk"
    assert ("pantry_items", "update") not in client.calls
    assert ("pantry_embedding_jobs", "upsert") in client.calls

    inserted_item_payload = next(payload for table, payload in client.insert_payloads if table == "pantry_items")
    assert isinstance(inserted_item_payload, dict)
    assert inserted_item_payload["embedding_status"] == "pending"

    queue_payload = next(payload for table, payload, _ in client.upsert_payloads if table == "pantry_embedding_jobs")
    assert isinstance(queue_payload, dict)
    assert queue_payload["pantry_item_id"] == "17a336f0-eed2-4f5e-bf15-e4c4d89f9959"


def test_add_bulk_items_inserts_pending_and_enqueues_jobs() -> None:
    class _CapturingQuery(_FakeQuery):
        def __init__(self, client: "_CapturingSupabaseClient", table_name: str) -> None:
            super().__init__(client, table_name)
            self._capturing_client = client

        def insert(self, payload: object) -> "_CapturingQuery":
            self._capturing_client.insert_payloads.append((self._table_name, payload))
            return super().insert(payload)

        def upsert(self, payload: object, **kwargs: object) -> "_CapturingQuery":
            self._capturing_client.upsert_payloads.append((self._table_name, payload, kwargs))
            return super().upsert(payload, **kwargs)

    class _CapturingSupabaseClient(_FakeSupabaseClient):
        def __init__(self, table_results: dict[tuple[str, str], list[object]] | None = None) -> None:
            super().__init__(table_results=table_results)
            self.insert_payloads: list[tuple[str, object]] = []
            self.upsert_payloads: list[tuple[str, object, dict[str, object]]] = []

        def table(self, table_name: str) -> _CapturingQuery:
            return _CapturingQuery(self, table_name)

    second_row = {**_item_row(), "id": "b7953263-8ecb-4f09-a67c-b31af7d5bbdb", "name": "Bread"}
    client = _CapturingSupabaseClient(
        table_results={
            ("pantry_items", "insert"): [SimpleNamespace(data=[_item_row(), second_row])],
            ("pantry_embedding_jobs", "upsert"): [SimpleNamespace(data=[{"id": 1}, {"id": 2}])],
        }
    )
    service = PantryService(client)

    result = anyio.run(
        lambda: service.add_bulk_items(
            owner_id=UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
            household_id=UUID("f8c2ce57-d0ac-4d8d-96f8-6c4a1844091a"),
            items_data=[
                {"name": "Milk", "category": "dairy", "quantity": 1, "unit": "liter"},
                {"name": "Bread", "category": "bakery", "quantity": 1, "unit": "piece"},
            ],
        )
    )

    assert len(result) == 2
    assert ("pantry_items", "insert") in client.calls
    assert ("pantry_embedding_jobs", "upsert") in client.calls
    assert ("pantry_items", "update") not in client.calls

    bulk_insert_payload = next(payload for table, payload in client.insert_payloads if table == "pantry_items")
    assert isinstance(bulk_insert_payload, list)
    assert bulk_insert_payload[0]["embedding_status"] == "pending"
    assert bulk_insert_payload[1]["embedding_status"] == "pending"

    jobs_payload = next(payload for table, payload, _ in client.upsert_payloads if table == "pantry_embedding_jobs")
    assert isinstance(jobs_payload, list)
    assert jobs_payload[0]["pantry_item_id"] == "17a336f0-eed2-4f5e-bf15-e4c4d89f9959"
    assert jobs_payload[1]["pantry_item_id"] == "b7953263-8ecb-4f09-a67c-b31af7d5bbdb"


def test_add_bulk_items_rejects_payload_larger_than_100() -> None:
    service = PantryService(_FakeSupabaseClient())

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            lambda: service.add_bulk_items(
                owner_id=UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
                household_id=UUID("f8c2ce57-d0ac-4d8d-96f8-6c4a1844091a"),
                items_data=[
                    {"name": f"item-{index}", "category": "misc", "quantity": 1, "unit": "pcs"}
                    for index in range(101)
                ],
            )
        )

    assert exc_info.value.status_code == 400


def test_process_embedding_jobs_completes_successfully() -> None:
    client = _FakeSupabaseClient(
        table_results={
            (
                "pantry_embedding_jobs",
                "select",
            ): [
                SimpleNamespace(
                    data=[
                        {
                            "id": 10,
                            "pantry_item_id": "17a336f0-eed2-4f5e-bf15-e4c4d89f9959",
                            "attempts": 0,
                            "status": "queued",
                            "next_attempt_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                )
            ],
            ("pantry_embedding_jobs", "update"): [
                SimpleNamespace(data=[{"id": 10}]),
                SimpleNamespace(data=[{"id": 10}]),
            ],
            ("pantry_items", "select"): [
                SimpleNamespace(
                    data=[
                        {
                            "id": "17a336f0-eed2-4f5e-bf15-e4c4d89f9959",
                            "name": "Milk",
                            "category": "dairy",
                            "quantity": 1.0,
                            "unit": "liter",
                        }
                    ]
                )
            ],
            ("pantry_items", "update"): [SimpleNamespace(data=[{"id": "17a336f0-eed2-4f5e-bf15-e4c4d89f9959"}])],
        }
    )
    service = PantryService(client, embeddings_provider=lambda: SimpleNamespace(embed_query=lambda _: [0.2, 0.4]))

    result = anyio.run(lambda: service.process_embedding_jobs(max_jobs=20))

    assert result["selected"] == 1
    assert result["processed"] == 1
    assert result["retried"] == 0
    assert result["failed"] == 0


def test_process_embedding_jobs_retries_then_fails_at_max_attempts() -> None:
    client = _FakeSupabaseClient(
        table_results={
            (
                "pantry_embedding_jobs",
                "select",
            ): [
                SimpleNamespace(
                    data=[
                        {
                            "id": 11,
                            "pantry_item_id": "17a336f0-eed2-4f5e-bf15-e4c4d89f9959",
                            "attempts": 4,
                            "status": "queued",
                            "next_attempt_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                )
            ],
            ("pantry_embedding_jobs", "update"): [
                SimpleNamespace(data=[{"id": 11}]),
                SimpleNamespace(data=[{"id": 11}]),
            ],
            ("pantry_items", "select"): [
                SimpleNamespace(
                    data=[
                        {
                            "id": "17a336f0-eed2-4f5e-bf15-e4c4d89f9959",
                            "name": "Milk",
                            "category": "dairy",
                            "quantity": 1.0,
                            "unit": "liter",
                        }
                    ]
                )
            ],
            ("pantry_items", "update"): [SimpleNamespace(data=[{"id": "17a336f0-eed2-4f5e-bf15-e4c4d89f9959"}])],
        }
    )
    service = PantryService(
        client,
        embeddings_provider=lambda: SimpleNamespace(
            embed_query=lambda _: (_ for _ in ()).throw(RuntimeError("embed failed"))
        ),
    )

    result = anyio.run(lambda: service.process_embedding_jobs(max_jobs=20, max_attempts=5))

    assert result["selected"] == 1
    assert result["processed"] == 0
    assert result["retried"] == 0
    assert result["failed"] == 1


def test_process_embedding_jobs_caps_selected_batch_to_20() -> None:
    class _LimitCapturingQuery(_FakeQuery):
        def __init__(self, client: "_LimitCapturingClient", table_name: str) -> None:
            super().__init__(client, table_name)
            self._capturing_client = client

        def limit(self, value: int) -> "_LimitCapturingQuery":
            self._capturing_client.selected_limit = value
            return super().limit(value)

    class _LimitCapturingClient(_FakeSupabaseClient):
        def __init__(self) -> None:
            super().__init__(
                table_results={
                    ("pantry_embedding_jobs", "select"): [SimpleNamespace(data=[])],
                }
            )
            self.selected_limit: int | None = None

        def table(self, table_name: str) -> _LimitCapturingQuery:
            return _LimitCapturingQuery(self, table_name)

    client = _LimitCapturingClient()
    service = PantryService(client)

    result = anyio.run(lambda: service.process_embedding_jobs(max_jobs=100))

    assert result["selected"] == 0
    assert client.selected_limit == 20


def test_get_my_items_returns_list() -> None:
    client = _FakeSupabaseClient(
        table_results={("pantry_items", "select"): [SimpleNamespace(data=[_item_row()])]}
    )
    service = PantryService(client)

    result = anyio.run(
        lambda: service.get_my_items(
            owner_id=UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
        )
    )

    assert len(result) == 1
    assert result[0].id == "17a336f0-eed2-4f5e-bf15-e4c4d89f9959"


def test_update_my_item_raises_not_found_when_no_rows_returned() -> None:
    client = _FakeSupabaseClient(table_results={("pantry_items", "update"): [SimpleNamespace(data=[])]})
    service = PantryService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            lambda: service.update_my_item(
                item_id=UUID("17a336f0-eed2-4f5e-bf15-e4c4d89f9959"),
                owner_id=UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
                updates={"quantity": 2},
            )
        )

    assert exc_info.value.status_code == 404


def test_delete_my_item_raises_not_found_when_item_missing() -> None:
    client = _FakeSupabaseClient(table_results={("pantry_items", "select"): [SimpleNamespace(data=[])]})
    service = PantryService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            lambda: service.delete_my_item(
                item_id=UUID("17a336f0-eed2-4f5e-bf15-e4c4d89f9959"),
                owner_id=UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
            )
        )

    assert exc_info.value.status_code == 404
