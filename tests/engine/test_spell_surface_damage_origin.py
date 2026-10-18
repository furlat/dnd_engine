"""Owned spell origins survive native surface entry damage."""

from uuid import uuid4

import pytest

from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.dice import fixed_dice_faces
from dnd.core.effect_types import EffectOrigin
from dnd.core.events import DamageAppliedEvent, Event, EventPhase, EventQueue, EventType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import SpellDamageResistance
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import ElectrifiedWater, FireSurface


@pytest.fixture
def traveler():
    reset_engine_runtime(grid_size=(4, 3))
    game = Game()
    entity = Entity.create(uuid4(), "Surface traveler", config=EntityConfig(
        position=(0, 1), health=HealthConfig(hit_dices=[
            HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums"),
        ]),
    ))
    entity.compose_entity()
    game.deploy_entity(entity, entity.position)
    entity.add_condition(SpellDamageResistance(
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid,
    ))
    yield entity
    game.close()
    reset_engine_runtime()


@pytest.mark.parametrize("surface_type,spell_id", [
    (FireSurface, "spell.flaming_sphere"),
    (ElectrifiedWater, "spell.lightning_bolt"),
])
@pytest.mark.parametrize("from_spell", [False, True])
def test_surface_entry_retains_owned_spell_origin(traveler, surface_type, spell_id, from_spell):
    origin = EffectOrigin.spell(source_id=spell_id,
        source_event_lineage_uuid=None, base_spell_level=2, effective_spell_level=2,
    ) if from_spell else None
    cause = Event(source_entity_uuid=traveler.uuid, event_type=EventType.BASE_ACTION,
        phase=EventPhase.EFFECT)
    surface = surface_type(source_entity_uuid=traveler.uuid, position=(1, 1),
        affected_positions={(1, 1)}, effect_origin=origin)
    surface.activate(parent_event=cause)
    hp = traveler.get_normal_hp()

    with fixed_dice_faces(2, 2):
        Entity.update_entity_position(traveler, (1, 1), parent_event=cause.uuid)

    # Electrified water also applies native Wet vulnerability. Its one d4 and
    # the fire's two d4 both deal four before spell resistance in this case.
    assert traveler.get_normal_hp() == hp - (2 if from_spell else 4)
    fact = next(event for event in reversed(EventQueue.get_events_by_type(EventType.DAMAGE_APPLIED))
        if event.phase is EventPhase.COMPLETION and event.target_entity_uuid == traveler.uuid)
    assert isinstance(fact, DamageAppliedEvent)
    assert fact.damages[0].effect_origin == origin
