"""An area effect resolves at once: one damage roll, every target, then reactions (plan §5.1; D6a, D7a)."""

from collections.abc import Iterator
from itertools import cycle, islice

import pytest

from dnd.conditions import Concentrating
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, Event, EventPhase, EventQueue, SavingThrowEvent
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import Fireball
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena

TARGET_CELLS = ((6, 6), (7, 6), (6, 7))


@pytest.fixture
def caster() -> Iterator[Entity]:
    reset_spell_regression_arena(13, 13)
    actor = create_spell_regression_actor("Caster", (0, 0), "heroes", spell_slots={3: 3})
    yield actor
    reset_engine_runtime()


def _targets() -> list[Entity]:
    return [create_spell_regression_actor(f"Target {index}", cell, "monsters", dexterity=1)
            for index, cell in enumerate(TARGET_CELLS)]


def _fireball(caster: Entity) -> list[tuple[int, Event]]:
    """Cast with varied dice faces: per-target rolls would give each target a different total."""
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()
    spell = Fireball(source_entity_uuid=caster.uuid, use_register=False, caster_level=5, cast_at_level=3,
        end_position=(6, 6))
    with fixed_dice_faces(*islice(cycle((1, 2, 3, 4, 5, 6)), 400)):
        result = spell.apply()
    assert result is not None and not result.canceled
    return [(index, event) for index, event in EventQueue.iter_events_since(cursor)
            if event.phase is EventPhase.COMPLETION]


def _damage_by_target(events: list[tuple[int, Event]], targets: list[Entity]) -> dict[str, list[int]]:
    names = {target.uuid: target.name for target in targets}
    damage: dict[str, list[int]] = {}
    for _, event in events:
        target_uuid = event.target_entity_uuid
        if isinstance(event, DamageAppliedEvent) and target_uuid is not None and target_uuid in names:
            damage.setdefault(names[target_uuid], []).append(event.applied_damage)
    return damage


def test_one_fireball_damage_roll_is_shared_by_every_target(caster: Entity) -> None:
    targets = _targets()
    damage = _damage_by_target(_fireball(caster), targets)
    assert sorted(damage) == sorted(target.name for target in targets)
    assert len({amount for amounts in damage.values() for amount in amounts}) == 1, damage


def test_concentration_is_tested_only_after_every_target_took_the_damage(caster: Entity) -> None:
    targets = _targets()
    concentrator = targets[1]
    concentrator.add_condition(Concentrating(source_entity_uuid=concentrator.uuid,
        target_entity_uuid=concentrator.uuid, spell_name="Held spell"))
    events = _fireball(caster)
    last_damage = max(index for index, event in events if isinstance(event, DamageAppliedEvent)
        and event.target_entity_uuid in {target.uuid for target in targets})
    concentration_saves = [index for index, event in events if isinstance(event, SavingThrowEvent)
        and event.target_entity_uuid == concentrator.uuid and event.ability_name == "constitution"]
    assert concentration_saves, "the concentrating target must make its concentration save"
    assert min(concentration_saves) > last_damage
