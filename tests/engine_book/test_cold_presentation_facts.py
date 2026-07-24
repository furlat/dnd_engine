"""Focused contracts for cold engine presentation facts."""

from uuid import uuid4, uuid5

import pytest
from pydantic import ValidationError

from dnd.actions import SpellEvent
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.action_types import ActionPresentationKind
from dnd.core.aoe import (
    Cone,
    Cube,
    Cylinder,
    Line,
    Sphere,
    snapshot_aoe_presentation_geometry,
)
from dnd.core.base_actions import ActionEvent
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.item_types import ItemPresentationKind
from dnd.core.presentation_geometry import (
    ConePresentationGeometry,
    CubePresentationGeometry,
    CylinderPresentationGeometry,
    LinePresentationGeometry,
    SpherePresentationGeometry,
)
from dnd.entity import Entity, EntityConfig
from dnd.items.test_items import create_healing_potion, create_scroll_of_fireball
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells import Fireball, MagicMissile
from dnd.core.gridmap import get_map


def _create_actor(
    name: str,
    position: tuple[int, int],
    faction: str,
    *,
    spell_slots: dict[int, int] | None = None,
) -> Entity:
    """Create one durable spell-capable actor for event integration checks."""
    return Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=12),
                constitution=AbilityConfig(ability_score=14),
                intelligence=AbilityConfig(ability_score=18),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(
                spell_slots=spell_slots or {},
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=8,
                        mode="maximums",
                    )
                ],
            ),
            spellcasting=SpellcastingConfig(
                spellcasting_ability="intelligence",
            ),
            proficiency_bonus=3,
            position=position,
            faction=faction,
        ),
    )


def _reset_grid() -> None:
    """Reset engine registries and create a small deterministic arena."""
    reset_engine_runtime()
    get_map().create_rectangle(0, 0, 10, 6)


def test_shape_snapshots_preserve_every_runtime_geometry_parameter() -> None:
    """Every concrete AoE shape has one exact immutable cold representation."""
    _reset_grid()
    source_uuid = uuid4()
    caster_position = (2, 2)
    target = (5, 4)

    sphere = snapshot_aoe_presentation_geometry(
        Sphere(source_entity_uuid=source_uuid, radius_feet=20),
        caster_position,
        target_override=target,
    )
    cone = snapshot_aoe_presentation_geometry(
        Cone(
            source_entity_uuid=source_uuid,
            length_feet=30,
            angle_degrees=70,
        ),
        caster_position,
        target_override=target,
    )
    line = snapshot_aoe_presentation_geometry(
        Line(
            source_entity_uuid=source_uuid,
            length_feet=100,
            width_feet=10,
        ),
        caster_position,
        target_override=target,
    )
    centered_cube = snapshot_aoe_presentation_geometry(
        Cube(
            source_entity_uuid=source_uuid,
            size_feet=30,
            centered=True,
        ),
        caster_position,
        target_override=target,
    )
    directional_cube = snapshot_aoe_presentation_geometry(
        Cube(
            source_entity_uuid=source_uuid,
            size_feet=15,
            centered=False,
        ),
        caster_position,
        target_override=target,
    )
    cylinder = snapshot_aoe_presentation_geometry(
        Cylinder(
            source_entity_uuid=source_uuid,
            radius_feet=20,
            height_feet=40,
        ),
        caster_position,
        target_override=target,
    )

    assert sphere == SpherePresentationGeometry(center=target, radius_feet=20)
    assert cone == ConePresentationGeometry(
        origin=caster_position,
        direction=(3, 2),
        length_feet=30,
        angle_degrees=70,
    )
    assert line == LinePresentationGeometry(
        origin=caster_position,
        direction=(3, 2),
        length_feet=100,
        width_feet=10,
    )
    assert centered_cube == CubePresentationGeometry(
        origin=target,
        direction=None,
        size_feet=30,
        centered=True,
    )
    assert directional_cube == CubePresentationGeometry(
        origin=caster_position,
        direction=(3, 2),
        size_feet=15,
        centered=False,
    )
    assert cylinder == CylinderPresentationGeometry(
        center=target,
        radius_feet=20,
        height_feet=40,
    )
    assert isinstance(sphere, SpherePresentationGeometry)
    with pytest.raises(ValidationError):
        sphere.radius_feet = 10


def test_spell_event_keeps_declaration_geometry_through_completion() -> None:
    """A completed spell never needs its live action to recover area geometry."""
    _reset_grid()
    caster = _create_actor("Geometry Mage", (1, 1), "heroes")
    spell = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(4, 2),
        template=False,
    )

    declaration = spell._create_declaration_event(use_register=False)

    assert isinstance(declaration, SpellEvent)
    assert declaration.area_geometry == SpherePresentationGeometry(
        center=(4, 2),
        radius_feet=20,
    )
    execution = declaration.phase_to(EventPhase.EXECUTION)
    effect = execution.phase_to(EventPhase.EFFECT)
    completion = effect.phase_to(EventPhase.COMPLETION)
    assert completion.area_geometry == declaration.area_geometry
    assert completion.model_dump(mode="json")["area_geometry"] == {
        "shape": "sphere",
        "center": [4, 2],
        "radius_feet": 20,
    }


def test_duplicate_spell_targets_receive_stable_ordered_application_ids() -> None:
    """Repeated target UUIDs remain distinct applications in source order."""
    _reset_grid()
    caster = _create_actor(
        "Missile Mage",
        (1, 1),
        "heroes",
        spell_slots={1: 1},
    )
    target = _create_actor("Training Target", (2, 1), "monsters")
    Entity.update_all_entities_senses(max_distance=30)
    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        extra_target_entity_uuids=[target.uuid, target.uuid],
        template=False,
    )

    completion = spell.apply()

    assert isinstance(completion, SpellEvent)
    applications = [
        event
        for event in EventQueue.get_events_by_type(EventType.CAST_SPELL)
        if isinstance(event, SpellEvent)
        and event.phase is EventPhase.COMPLETION
        and event.parent_lineage == completion.lineage_uuid
        and event.application_index is not None
    ]
    assert [event.application_index for event in applications] == [0, 1, 2]
    assert [event.target_entity_uuid for event in applications] == [
        target.uuid,
        target.uuid,
        target.uuid,
    ]
    assert [event.application_id for event in applications] == [
        uuid5(completion.lineage_uuid, f"target-application:{index}")
        for index in range(3)
    ]
    assert len({event.application_id for event in applications}) == 3


def test_drink_event_carries_immutable_declaration_time_item_state() -> None:
    """Item-use presentation survives consumption without a registry lookup."""
    _reset_grid()
    user_uuid = uuid4()
    potion = create_healing_potion(owner_uuid=user_uuid)
    action = potion.get_use_actions(user_uuid)[0]

    declaration = action._create_declaration_event(use_register=False)

    assert isinstance(declaration, ActionEvent)
    assert declaration.presentation_kind is ActionPresentationKind.DRINK
    assert declaration.source_item_uuid == potion.uuid
    assert declaration.source_item_presentation is not None
    assert declaration.source_item_presentation.item_uuid == potion.uuid
    assert (
        declaration.source_item_presentation.item_kind
        is ItemPresentationKind.USABLE
    )
    assert declaration.source_item_presentation.name == "Potion of Healing"
    assert declaration.source_item_presentation.charges == 1

    potion.name = "Mutated after declaration"
    potion.charges = 0
    completion = declaration.phase_to(EventPhase.EXECUTION).phase_to(
        EventPhase.EFFECT
    ).phase_to(EventPhase.COMPLETION)

    assert completion.source_item_presentation == declaration.source_item_presentation
    assert completion.source_item_presentation is not None
    assert completion.source_item_presentation.name == "Potion of Healing"
    assert completion.source_item_presentation.charges == 1


def test_drink_event_rejects_missing_or_mismatched_item_snapshot() -> None:
    """The presentation-bearing action cannot silently fall back to live state."""
    _reset_grid()
    with pytest.raises(ValidationError, match="declaration-time item presentation"):
        ActionEvent(
            source_entity_uuid=uuid4(),
            source_item_uuid=uuid4(),
            presentation_kind=ActionPresentationKind.DRINK,
            use_register=False,
        )

    potion = create_healing_potion(owner_uuid=uuid4())
    with pytest.raises(ValidationError, match="must match source_item_uuid"):
        ActionEvent(
            source_entity_uuid=uuid4(),
            source_item_uuid=uuid4(),
            source_item_presentation=potion.to_item_presentation_state(),
            use_register=False,
        )


def test_item_backed_spell_variant_carries_its_scroll_snapshot() -> None:
    """Model-copy spell variants retain the same cold item-use guarantee."""
    _reset_grid()
    user = _create_actor("Scroll Reader", (1, 1), "heroes")
    scroll = create_scroll_of_fireball(owner_uuid=user.uuid)
    action = scroll.get_use_actions(user.uuid)[0]
    action.end_position = (4, 2)

    declaration = action._create_declaration_event(use_register=False)

    assert isinstance(declaration, SpellEvent)
    assert declaration.source_item_uuid == scroll.uuid
    assert declaration.source_item_presentation is not None
    assert declaration.source_item_presentation.item_uuid == scroll.uuid
    assert (
        declaration.source_item_presentation.item_kind
        is ItemPresentationKind.USABLE
    )
    assert declaration.source_item_presentation.name == "Scroll of Fireball"
