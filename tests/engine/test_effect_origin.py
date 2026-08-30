"""Focused contracts for explicit persistent-effect provenance."""

from uuid import UUID, uuid4

from dnd.actions import SpellEvent
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionTag
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.effect_types import EffectOrigin, EffectOriginKind
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import AreaCondition
from dnd.types.spatial_effects import (
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
)


_TEST_AREA_CONTENT_REF = ContentRef(
    pack_id="test.effect_origin",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="condition.spatial.effect_origin",
    content_version=1,
    definition_contract_hash="0" * 64,
)


def _area(
    source_uuid: UUID,
    *,
    effect_origin: EffectOrigin | None = None,
) -> AreaCondition:
    return AreaCondition(
        source_entity_uuid=source_uuid,
        content_ref=_TEST_AREA_CONTENT_REF,
        position=(0, 0),
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        effect_origin=effect_origin,
    )


def test_spell_event_exports_frozen_base_and_effective_spell_provenance() -> None:
    """Persistent effects retain cast identity without walking event ancestry."""
    reset_engine_runtime()
    source_uuid = uuid4()
    event = SpellEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        spell_id="web",
        spell_level=2,
        cast_at_level=4,
    )

    origin = event.to_effect_origin()

    assert origin.kind is EffectOriginKind.SPELL
    assert origin.source_id == "web"
    assert origin.source_event_lineage_uuid == str(event.lineage_uuid)
    assert origin.base_spell_level == 2
    assert origin.effective_spell_level == 4
    assert origin.model_config["frozen"] is True


def test_zone_protection_uses_explicit_base_level_even_when_upcast() -> None:
    """Globe protection uses the spell's base level even when it is upcast."""
    reset_engine_runtime()
    source_uuid = uuid4()
    cast_event = SpellEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        spell_id="web",
        spell_level=2,
        cast_at_level=6,
    )
    zone = _area(source_uuid, effect_origin=cast_event.to_effect_origin())

    assert zone.effect_origin is not None
    assert zone.effect_origin.base_spell_level == 2
    assert zone._protection_spell_level() == 2


def test_non_spell_or_missing_provenance_disables_spell_level_filtering() -> None:
    """Protection filtering never guesses a level from registry ancestry."""
    reset_engine_runtime()
    source_uuid = uuid4()

    zone = _area(source_uuid)

    assert zone._protection_spell_level() is None


def test_condition_applications_inherit_spell_origin_without_event_ancestry_walks() -> None:
    """Direct and nested conditions inherit one immutable spell origin."""
    reset_engine_runtime()
    source_uuid = uuid4()
    spell_event = SpellEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        spell_id="hold_person",
        spell_level=2,
        cast_at_level=5,
        source_position=(1, 2),
    )
    parent = BaseCondition(
        name="Spell Wrapper",
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        tags={ConditionTag.MAGICAL},
    )

    parent_event = parent.declare_event(spell_event)
    child = BaseCondition(
        name="Nested Spell Effect",
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        tags={ConditionTag.MAGICAL},
    )
    child.declare_event(parent_event)

    expected = spell_event.to_effect_origin()
    assert parent.effect_origin == expected
    assert child.effect_origin == expected
    assert parent.effect_origin is not None
    assert parent.effect_origin.source_position == (1, 2)
