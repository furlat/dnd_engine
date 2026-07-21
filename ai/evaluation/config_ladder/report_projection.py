"""Deterministic JSON projection for connected-rating HTML reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
import math
from pathlib import Path
from typing import Any, TypeAlias

from pydantic import BaseModel


ReportSource: TypeAlias = BaseModel | Mapping[str, Any]

REPORT_SCHEMA_VERSION = 1
REPORT_KIND = "connected_configuration_rating_report"


def build_report_projection(payload: ReportSource) -> dict[str, Any]:
    """Normalize typed or mapping report data into compact versioned JSON.

    The projection only rearranges retained report slices. It does not estimate
    missing ratings, intervals, matchup probabilities, performance values, or
    scaling results.

    Args:
        payload: Pydantic model or mapping containing retained report data.

    Returns:
        JSON-compatible report projection consumed by the offline renderer.

    Raises:
        TypeError: If the payload or one of its values is not JSON-compatible.
        ValueError: If report identity is missing or numeric data is non-finite.
    """
    normalized = _json_value(payload, path="report")
    if not isinstance(normalized, dict):
        raise TypeError("Connected-rating report payload must be a mapping or Pydantic model.")

    schema_version = normalized.get("schema_version", REPORT_SCHEMA_VERSION)
    if schema_version != REPORT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported connected-rating report schema version: {schema_version!r}")

    source = _mapping(normalized.get("source"), field="source")
    experiment_id = source.get("experiment_id") or normalized.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ValueError("Connected-rating report source.experiment_id is required.")
    source["experiment_id"] = experiment_id

    strength_value = normalized.get("strength")
    if strength_value is None:
        strength_value = normalized.get("strength_result")
    strength = _mapping(strength_value, field="strength")

    matchup_value = normalized.get("matchups")
    matchups = _mapping(matchup_value, field="matchups")
    if "predicted" not in matchups and "predicted_matchups" in normalized:
        matchups["predicted"] = normalized["predicted_matchups"]
    if "empirical" not in matchups and "empirical_matchups" in normalized:
        matchups["empirical"] = normalized["empirical_matchups"]

    specialization = normalized.get("specialization")
    if specialization is None:
        specialization = strength.get("specialization", [])
    calibration = normalized.get("calibration")
    if calibration is None:
        calibration = strength.get("calibration", [])
    rank_uncertainty = normalized.get("rank_uncertainty")
    if rank_uncertainty is None:
        rank_uncertainty = strength.get("rank_uncertainty", [])

    projection = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "source": source,
        "status": _mapping(normalized.get("status"), field="status"),
        "method": _mapping(normalized.get("method"), field="method"),
        "quality": _mapping_or_list(normalized.get("quality"), field="quality"),
        "participants": _mapping_or_list(normalized.get("participants"), field="participants"),
        "strength": strength,
        "matchups": matchups,
        "specialization": _sequence(specialization, field="specialization"),
        "rank_uncertainty": _sequence(rank_uncertainty, field="rank_uncertainty"),
        "calibration": _sequence(calibration, field="calibration"),
        "spell_coverage": _mapping(normalized.get("spell_coverage"), field="spell_coverage"),
        "content_coverage": _mapping(normalized.get("content_coverage"), field="content_coverage"),
        "connectivity": _mapping(normalized.get("connectivity"), field="connectivity"),
        "performance": _mapping(normalized.get("performance"), field="performance"),
        "scaling": _mapping(normalized.get("scaling"), field="scaling"),
        "artifacts": _sequence(normalized.get("artifacts"), field="artifacts"),
        "explanations": _mapping(normalized.get("explanations"), field="explanations"),
        "live": _mapping(normalized.get("live"), field="live"),
        "secondary_estimators": _mapping(normalized.get("secondary_estimators"), field="secondary_estimators"),
        "excluded_pairs": _mapping(normalized.get("excluded_pairs"), field="excluded_pairs"),
        "infrastructure_failures": _mapping(
            normalized.get("infrastructure_failures"),
            field="infrastructure_failures",
        ),
    }
    _assert_strict_json(projection)
    return projection


def project_connected_rating_report(payload: ReportSource) -> dict[str, Any]:
    """Alias with an experiment-specific name for public callers."""
    return build_report_projection(payload)


def project_report(payload: ReportSource) -> dict[str, Any]:
    """Short alias used by report generation commands."""
    return build_report_projection(payload)


def load_report_projection(path: Path | str) -> dict[str, Any]:
    """Load and normalize one retained report JSON file.

    Args:
        path: Path to versioned report JSON.

    Returns:
        Normalized report projection.
    """
    source_path = Path(path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    return build_report_projection(payload)


def _json_value(value: Any, *, path: str) -> Any:
    """Convert supported typed values into strict JSON-compatible values."""
    if isinstance(value, BaseModel):
        return _json_value(value.model_dump(mode="json"), path=path)
    if is_dataclass(value) and not isinstance(value, type):
        return _json_value(asdict(value), path=path)
    if isinstance(value, Enum):
        return _json_value(value.value, path=path)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Non-finite report number at {path}.")
        return value
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"Report mapping key at {path} must be a string.")
            output[key] = _json_value(child, path=f"{path}.{key}")
        return output
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(child, path=f"{path}[{index}]") for index, child in enumerate(value)]
    raise TypeError(f"Unsupported report value at {path}: {type(value).__name__}")


def _mapping(value: Any, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"Connected-rating report {field} must be an object.")
    return dict(value)


def _mapping_or_list(value: Any, *, field: str) -> dict[str, Any] | list[Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    raise TypeError(f"Connected-rating report {field} must be an object or array.")


def _sequence(value: Any, *, field: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"Connected-rating report {field} must be an array.")
    return list(value)


def _assert_strict_json(payload: dict[str, Any]) -> None:
    try:
        json.dumps(payload, ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Connected-rating report projection is not strict JSON: {exc}") from exc
