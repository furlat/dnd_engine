"""Determinism regressions for ActionSemantics content addresses."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import get_args, get_origin

from pydantic import BaseModel

from ai.protocol.semantics import (
    ActionSemantics,
    _UNORDERED_SEMANTIC_FIELDS,
    action_semantics_payload_ref,
)


def _reachable_models(annotation: object) -> tuple[type[BaseModel], ...]:
    """Return Pydantic models nested inside one field annotation."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return (annotation,)
    origin = get_origin(annotation)
    if origin is None:
        return ()
    models: list[type[BaseModel]] = []
    for argument in get_args(annotation):
        models.extend(_reachable_models(argument))
    return tuple(models)


def _unordered_fields_in_model_graph(root: type[BaseModel]) -> frozenset[str]:
    """Collect unordered field names from a nested Pydantic model graph."""
    pending = [root]
    visited: set[type[BaseModel]] = set()
    unordered: set[str] = set()
    while pending:
        model = pending.pop()
        if model in visited:
            continue
        visited.add(model)
        for field_name, field in model.model_fields.items():
            annotation = field.annotation
            if get_origin(annotation) in {set, frozenset}:
                unordered.add(field_name)
            pending.extend(_reachable_models(annotation))
    return frozenset(unordered)


def _payload_with_nested_field(
    field_name: str,
    values: list[str],
) -> dict[str, object]:
    """Build a JSON payload containing one nested semantic collection."""
    return {
        "semantic_id": "test.unordered_field",
        "semantic_version": 1,
        "tags": [],
        "nested": {field_name: values},
    }


def test_canonicalizer_covers_every_unordered_action_semantics_field() -> None:
    """The canonicalizer audit must follow the complete ActionSemantics graph."""
    assert _UNORDERED_SEMANTIC_FIELDS == _unordered_fields_in_model_graph(
        ActionSemantics
    )


def test_every_unordered_semantic_field_is_permutation_invariant() -> None:
    """JSON list order cannot change the hash of a schema-declared set field."""
    values = [
        "rules.conditions.HypnoticPattern",
        "rules.conditions.Charmed",
        "rules.conditions.Incapacitated",
    ]
    for field_name in _UNORDERED_SEMANTIC_FIELDS:
        forward = _payload_with_nested_field(field_name, values)
        reverse = _payload_with_nested_field(field_name, list(reversed(values)))

        assert action_semantics_payload_ref(forward) == action_semantics_payload_ref(
            reverse
        )


def test_ordered_effect_sequences_remain_order_sensitive() -> None:
    """Canonicalization must not erase meaningful action-effect ordering."""
    first = {
        "semantic_id": "test.ordered_effects",
        "semantic_version": 1,
        "tags": [],
        "guaranteed_effects": [
            {"fact_id": "target.hp", "operation": "decrease", "value": 1},
            {"fact_id": "target.dead", "operation": "set", "value": True},
        ],
    }
    guaranteed_effects = first["guaranteed_effects"]
    assert isinstance(guaranteed_effects, list)
    second = {
        **first,
        "guaranteed_effects": list(reversed(guaranteed_effects)),
    }

    assert action_semantics_payload_ref(first) != action_semantics_payload_ref(second)


def test_frozenset_semantics_hash_identically_across_processes() -> None:
    """Real model dumps must produce one reference under different hash seeds."""
    script = """
from ai.protocol.semantics import (
    ActionSemantics,
    ActionTag,
    EffectDisposition,
    FactExpression,
    OutcomeKind,
    SelfSetupDuration,
    SelfSetupSemantics,
    TargetEffectSemantics,
    action_semantics_ref,
)

condition_keys = frozenset({
    "rules.conditions.HypnoticPattern",
    "rules.conditions.Charmed",
    "rules.conditions.Incapacitated",
})
semantics = ActionSemantics(
    semantic_id="control.hypnotic_pattern",
    tags=frozenset({ActionTag.CONTROL_HARD, ActionTag.TARGET_MULTI}),
    target_effects=(TargetEffectSemantics(
        effect_id="control.hypnotic_pattern",
        disposition=EffectDisposition.HARMFUL,
        applicability=FactExpression.true(),
        outcome_kind=OutcomeKind.GUARANTEED,
        condition_semantic_keys=condition_keys,
    ),),
    self_setup=SelfSetupSemantics(
        duration=SelfSetupDuration.UNTIL_REMOVED,
        active_condition_semantic_keys=condition_keys,
        resistance_damage_types=frozenset({"cold", "fire", "lightning"}),
    ),
)
print(action_semantics_ref(semantics))
"""
    project_root = Path(__file__).resolve().parents[2]
    references = {
        subprocess.run(
            [sys.executable, "-c", script],
            cwd=project_root,
            env={**os.environ, "PYTHONHASHSEED": seed},
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        for seed in ("1", "2", "3", "11", "37")
    }

    assert len(references) == 1
