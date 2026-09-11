"""Native discovery after hidden equipment/damage, followed by a visible attack."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import AttackEvent, MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.characters.premades import FIGHTER_PREMADE_ID, create_premade_character
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue, SpatialChangeEvent
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.presentation import (
    capture_interval, capture_lineage,
    reduce_interval, reduce_lineage,
)

from game.replay import CapturedHistory, ObserverCapture, capture_history


def discovery_history(
    *, mode: Literal["enter_view", "deploy_later"] = "enter_view",
    existing_hidden: bool = False,
) -> CapturedHistory:
    """Birth is followed by unseen native mutations, then actual sensory admission.

    In enter_view, only the fourth committed walking Step discovers the target.
    In deploy_later, the target is first deployed after its equipment/HP changes.
    The subsequent discovered longbow attack binds against the admitted actor.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        observer = create_premade_character(FIGHTER_PREMADE_ID, faction="heroes", position=(0, 3))
        game.deploy_entity(observer, observer.position)
        encounter = Encounter(name="Discovery history", source_entity_uuid=observer.uuid)
        encounter.add_combatant(observer, HumanController(source_entity_uuid=observer.uuid))
        encounter.start_encounter()
        encounter.start_turn()
        observer.update_entity_senses()
        baseline_cursor = EventQueue.event_cursor()

        unseen = Entity.create(uuid4(), "Previously unseen", config=EntityConfig(
            position=(14, 3) if mode == "enter_view" else (4, 3), faction="enemies",
            appearance=AppearanceConfig(body_category="NakedBody", head_category="Head22", has_beard=False),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")]),
        ))
        setup_standard_actions(unseen)
        sword = build_authored_item("weapon.shortsword", unseen.uuid)
        dagger = build_authored_item("weapon.dagger", unseen.uuid)
        unseen.install_initial_items((
            (sword, WeaponSlot.MELEE_MAIN), (dagger, None),
            (build_authored_item("apparel.robes.red_mage", unseen.uuid), BodyPart.BODY),
            (build_authored_item("apparel.cloth_shoes.red", unseen.uuid), BodyPart.FEET),
        ))
        birth = unseen.compose_entity()
        assert birth.current_hit_points == 40
        if mode == "enter_view":
            game.deploy_entity(unseen, unseen.position)
        unseen_start = EventQueue.event_cursor()
        assert unseen.uuid not in observer.senses.entities
        private_start = EventQueue.event_cursor()
        assert unseen.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
        unseen.receive_damage(7, DamageType.FORCE, source_entity_uuid=unseen.uuid)
        private_ids = {event.uuid for _, event in EventQueue.iter_events_since(private_start)}
        assert unseen.uuid not in observer.senses.entities
        assert unseen.get_hp() == 33
        if existing_hidden:
            baseline_cursor = EventQueue.event_cursor()
        startup = capture_interval(name="discovery startup", start_cursor=0,
            end_cursor=baseline_cursor, observer_uuid=observer.uuid,
            battlefield_id="battlefield.open_floor_bright")
        before, _ = reduce_interval(None, startup)
        assert set(before.actors) == {observer.uuid}
        start = EventQueue.event_cursor()
        if mode == "enter_view":
            available = get_available_actions(observer)
            move = next(row for row in available.all_actions if row.behavior_id == "action.move" and row.valid_targets)
            destination = next(row for row in move.valid_targets if row.position == (4, 3))
            root = execute_by_index(observer, move.template_name, destination.index, available=available)
            assert isinstance(root, MovementEvent)
        else:
            game.deploy_entity(unseen, unseen.position)
            unseen_start = EventQueue.event_cursor()
            root, = (event for _, event in EventQueue.iter_events_since(start)
                     if isinstance(event, SpatialChangeEvent) and event.parent_lineage is None
                     and event.phase is EventPhase.COMPLETION)
        assert unseen.uuid in observer.senses.entities
        discovery = capture_lineage(root, observer_uuid=observer.uuid,
                                    known_actor_uuids=frozenset(before.actors))
        assert private_ids.isdisjoint(row.event_uuid for row in discovery.objective_rows)
        admitted = reduce_lineage(before, discovery)
        assert admitted.actors[unseen.uuid].normal_hp == unseen.get_hp() == 33
        assert dict(admitted.actors[unseen.uuid].equipment)[WeaponSlot.MELEE_MAIN.value] == dagger.uuid

        available = get_available_actions(observer)
        attack = next(row for row in available.all_actions if row.behavior_id == "action.attack"
                      and row.weapon_slot == WeaponSlot.RANGED_MAIN.value and row.valid_targets)
        target = next(row for row in attack.valid_targets if row.target_uuid == unseen.uuid)
        random.seed(0)
        later_root = execute_by_index(observer, attack.template_name, target.index, available=available)
        assert isinstance(later_root, AttackEvent) and later_root.phase is EventPhase.COMPLETION
        assert not later_root.canceled and unseen.get_hp() < 33
        later = capture_lineage(later_root, observer_uuid=observer.uuid,
                                known_actor_uuids=frozenset(admitted.actors))
        assert not later.admissions
        assert reduce_lineage(admitted, later).actors[unseen.uuid].normal_hp == unseen.get_hp()
        return capture_history(before, (discovery, later), observers=(
            ObserverCapture("observer", observer.uuid, before.reducer_cursor),
            ObserverCapture("discovered", unseen.uuid, unseen_start),
        ))
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
