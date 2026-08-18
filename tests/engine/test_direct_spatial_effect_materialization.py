"""In-process authored spatial-condition construction contracts."""

from uuid import uuid4

import pytest

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.content.spatial_effect_recipes import SPIKE_TRAP_EFFECT_RECIPE
from dnd.spatial.environmental_conditions import SpikeTrap
from dnd.types.spatial_effects import SpatialEffectTriggerKind
from dnd.core.content.recipes import ContentRecipe


def test_spike_trap_recipe_materializes_without_a_global_content_runtime() -> None:
    """A built-in recipe directly produces its authenticated condition."""
    source_uuid = uuid4()
    recipe = SPIKE_TRAP_EFFECT_RECIPE

    condition = materialize_spatial_condition(
        recipe,
        source_uuid,
        position=(2, 3),
        faction=None,
        condition_type=SpikeTrap,
        condition_fields={
            "affected_positions": {(2, 3)},
            "condition_stealth_dc": 12,
        },
    )

    assert condition.source_entity_uuid == source_uuid
    assert condition.position == (2, 3)
    assert condition.condition_stealth_dc == 12
    assert condition.content_ref == recipe.ref
    assert condition.trigger_kinds == frozenset({SpatialEffectTriggerKind.ENTER})


def test_spatial_recipe_parameters_are_rejected_at_the_direct_boundary() -> None:
    """Runtime state is explicit condition data, not a generic recipe payload."""
    recipe = ContentRecipe.create(
        ref=SPIKE_TRAP_EFFECT_RECIPE.ref,
        parameters={"stealth_dc": 12},
    )

    with pytest.raises(ValueError, match="does not accept construction parameters"):
        materialize_spatial_condition(
            recipe,
            uuid4(),
            position=(2, 3),
            faction=None,
            condition_type=SpikeTrap,
            condition_fields={
                "affected_positions": {(2, 3)},
                "condition_stealth_dc": 12,
            },
        )
