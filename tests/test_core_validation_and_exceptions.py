from pantry_server.core.exceptions import AppError
from pantry_server.core.validation import (
    ValidationResult,
    normalize_title_case,
    normalize_trim,
    validate_in_set,
)


def test_normalize_title_case_strips_and_capitalizes_words() -> None:
    assert normalize_title_case(value="  hELLo wORld  ") == "Hello World"


def test_normalize_trim_strips_whitespace() -> None:
    assert normalize_trim(value="  a value  ") == "a value"


def test_validate_in_set_returns_valid_result_for_allowed_value() -> None:
    result = validate_in_set(value="  member ", allowed_values={"member", "admin"}, field_name="role")

    assert isinstance(result, ValidationResult)
    assert result.is_valid is True
    assert result.value == "member"
    assert result.error_message is None


def test_validate_in_set_returns_error_for_disallowed_value() -> None:
    result = validate_in_set(value="owner", allowed_values={"member", "admin"}, field_name="role")

    assert result.is_valid is False
    assert result.value is None
    assert result.error_message == "Invalid role"


def test_app_error_stores_all_fields() -> None:
    error = AppError(
        "Something failed",
        status_code=409,
        error_code="conflict",
        headers={"X-Test": "1"},
    )

    assert str(error) == "Something failed"
    assert error.message == "Something failed"
    assert error.status_code == 409
    assert error.error_code == "conflict"
    assert error.headers == {"X-Test": "1"}
