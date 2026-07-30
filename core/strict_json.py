"""Small strict-JSON boundary shared by durable scientific records.

Python's standard decoder accepts duplicate object fields and non-finite
numbers.  Both are ambiguous in records whose bytes determine provenance.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Any


class StrictJsonError(ValueError):
    """Raised when a payload is not one unambiguous JSON object."""


def parse_json_object(
    payload: bytes | str,
    *,
    label: str,
) -> dict[str, Any]:
    """Decode one JSON object while rejecting ambiguous JSON extensions."""

    if isinstance(payload, bytes):
        try:
            source = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StrictJsonError(f"{label} is not valid UTF-8") from exc
    elif isinstance(payload, str):
        source = payload
    else:
        raise StrictJsonError(f"{label} must be bytes or text")

    def unique_object(
        pairs: Sequence[tuple[str, Any]],
    ) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise StrictJsonError(
                    f"{label} contains duplicate field {key!r}"
                )
            value[key] = item
        return value

    def reject_constant(constant: str) -> None:
        raise StrictJsonError(
            f"{label} contains invalid numeric value {constant!r}"
        )

    def parse_finite_float(number: str) -> float:
        value = float(number)
        if not math.isfinite(value):
            raise StrictJsonError(
                f"{label} contains invalid numeric value {number!r}"
            )
        return value

    try:
        value = json.loads(
            source,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=parse_finite_float,
        )
    except StrictJsonError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictJsonError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise StrictJsonError(f"{label} must contain one JSON object")
    return value
