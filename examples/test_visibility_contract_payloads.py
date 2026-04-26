#!/usr/bin/env python
"""
Test visibility/sensory payload contract fields consumed by clients.

This is intentionally focused on API/event payload shape:
- /visibility includes visible_objects from backend Senses.objects.
- SENSORY_UPDATE carries replacement sense_modes when sense modes change.
- SENSORY_UPDATE carries replacement passive_perception when passive perception changes.
"""

import sys
from typing import List, Optional, Tuple
from uuid import UUID

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

from dnd.core.base_conditions import BaseCondition
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity
from dnd.monsters.bestiary import create_caster, create_goblin, create_skeleton
from dnd.conditions import Invisible
from dnd.spells.divination import SeeInvisibility
from dnd.utils import reset_combat_state
from server.event_server import app, setup_arena_combat


class PerceptionBoostCondition(BaseCondition):
    """Test condition that increases passive perception."""

    name: str = "Contract Perception Boost"
    boost_amount: int = 5

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        skill = target.skill_set.get_skill("perception")
        mod_uuid = skill.skill_bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name="Contract Perception Boost",
                value=self.boost_amount,
            )
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
        )
        return [(skill.skill_bonus.uuid, mod_uuid)], [], [], [], effect_event


def setup_bright_arena(size: int = 10):
    reset_combat_state()
    reset_map()
    grid = get_map()
    grid.create_rectangle(0, 0, size, size)
    return grid


def completed_sensory_updates(observer_uuid: UUID):
    return [
        event for event in EventQueue._all_events
        if event.event_type == EventType.SENSORY_UPDATE
        and event.phase == EventPhase.COMPLETION
        and getattr(event, "observer_uuid", None) == observer_uuid
    ]


def test_visibility_endpoint_includes_visible_objects():
    print("=" * 60)
    print("TEST: /visibility includes visible_objects")
    print("=" * 60)

    setup_arena_combat(character_class="fighter")
    Entity.update_all_entities_senses(max_distance=20)

    with TestClient(app) as client:
        response = client.get("/visibility")

    assert response.status_code == 200
    data = response.json()

    checked = 0
    for entity in Entity.get_all_entities():
        payload = data[str(entity.uuid)]
        assert "visible_objects" in payload, f"{entity.name} payload missing visible_objects"

        expected = sorted(str(uuid) for uuid in entity.senses.objects.keys())
        actual = sorted(payload["visible_objects"])
        print(f"  {entity.name}: {len(actual)} visible objects")
        assert actual == expected, \
            f"{entity.name} visible_objects mismatch: expected {expected}, got {actual}"
        checked += 1

    assert checked > 0, "Expected at least one entity visibility payload"
    print("  PASS: /visibility visible_objects mirrors backend senses")


def test_sensory_update_includes_replacement_sense_modes():
    print("\n" + "=" * 60)
    print("TEST: SENSORY_UPDATE includes replacement sense_modes")
    print("=" * 60)

    setup_bright_arena()

    observer = create_caster(name="Wizard", position=(2, 2), level=5, faction="heroes")
    enemy = create_goblin(name="Invisible Goblin", position=(5, 2), faction="monsters")
    Entity.update_all_entities_senses()

    invis = Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    enemy.add_condition(invis)
    assert enemy.uuid not in observer.senses.entities, "Enemy should be hidden while invisible"

    spell = SeeInvisibility(
        source_entity_uuid=observer.uuid,
        cast_at_level=2,
        template=False,
        costs=SeeInvisibility(source_entity_uuid=observer.uuid)._get_costs_for_level(2),
    )
    result = spell.apply()
    assert result is not None and not result.canceled, "See Invisibility should succeed"

    updates = [
        event for event in completed_sensory_updates(observer.uuid)
        if event.sense_modes_changed
    ]
    assert updates, "Expected sensory update for See Invisibility sense-mode change"

    payload = updates[-1].model_dump(mode="json")
    print(f"  sense_modes payload: {payload['sense_modes']}")
    assert payload["sense_modes"] == [
        {"sense_type": "See Invisible", "range_feet": 0}
    ], "Expected full replacement sense mode payload"

    for _ in range(10):
        observer.advance_duration("See Invisibility")

    removal_updates = [
        event for event in completed_sensory_updates(observer.uuid)
        if event.sense_modes_changed and event.model_dump(mode="json")["sense_modes"] == []
    ]
    assert removal_updates, "Expected empty replacement sense_modes when buff expires"
    print("  PASS: sense mode additions/removals carry replacement payloads")


def test_sensory_update_includes_replacement_passive_perception():
    print("\n" + "=" * 60)
    print("TEST: SENSORY_UPDATE includes replacement passive_perception")
    print("=" * 60)

    setup_bright_arena()

    observer = create_skeleton(name="Observer", position=(2, 2))
    Entity.update_all_entities_senses()

    before = observer.get_passive_perception()
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=5,
    )
    observer.add_condition(boost)
    after = observer.get_passive_perception()

    updates = [
        event for event in completed_sensory_updates(observer.uuid)
        if event.passive_perception_changed
    ]
    assert updates, "Expected sensory update for passive perception change"

    payload = updates[-1].model_dump(mode="json")
    print(f"  passive_perception: {before} -> {payload['passive_perception']}")
    assert payload["passive_perception"] == after, \
        f"Expected passive_perception {after}, got {payload['passive_perception']}"

    print("  PASS: passive perception changes carry replacement payload")


if __name__ == "__main__":
    test_visibility_endpoint_includes_visible_objects()
    test_sensory_update_includes_replacement_sense_modes()
    test_sensory_update_includes_replacement_passive_perception()

    print("\n" + "=" * 60)
    print("ALL VISIBILITY CONTRACT PAYLOAD TESTS PASSED")
    print("=" * 60)
