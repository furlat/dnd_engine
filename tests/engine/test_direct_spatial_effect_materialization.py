"""In-process authored spatial-effect construction contracts."""

from uuid import uuid4

from dnd.content.spatial_effect_materialization import materialize_spatial_effect
from dnd.content.spatial_effect_recipes import spike_trap_effect_recipe
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.spatial.environmental_effects import SpikeTrapGroundEffect
from dnd.types.spatial_effects import SpatialEffectTriggerKind


def test_spike_trap_recipe_materializes_without_a_global_content_runtime() -> None:
    """A built-in recipe directly produces its authenticated runtime effect."""
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    source_uuid = uuid4()
    recipe = spike_trap_effect_recipe(stealth_dc=12)

    try:
        effect = materialize_spatial_effect(
            recipe,
            source_uuid,
            position=(2, 3),
            faction=None,
            expected_type=SpikeTrapGroundEffect,
        )

        assert effect.source_entity_uuid == source_uuid
        assert effect.position == (2, 3)
        assert effect.stealth_dc == 12
        assert effect.content_ref == recipe.ref
        assert effect.trigger_kinds == frozenset({SpatialEffectTriggerKind.ENTER})
    finally:
        BaseObject._registry.clear()
        BaseBlock._registry.clear()
