"""Focused tests for unambiguous durable-record JSON parsing."""

from __future__ import annotations

import pytest

from core.strict_json import StrictJsonError, parse_json_object


def test_nested_duplicate_field_is_rejected() -> None:
    with pytest.raises(StrictJsonError, match="duplicate field 'value'"):
        parse_json_object(
            b'{"nested":{"value":1,"value":2}}',
            label="test record",
        )


@pytest.mark.parametrize(
    "constant",
    ["NaN", "Infinity", "-Infinity", "1e10000"],
)
def test_non_finite_number_is_rejected(constant: str) -> None:
    with pytest.raises(
        StrictJsonError,
        match="invalid numeric value",
    ):
        parse_json_object(
            f'{{"value":{constant}}}',
            label="test record",
        )
