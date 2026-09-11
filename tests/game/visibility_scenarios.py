"""Finite native sight experiments, captured once for both participating actors."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


VisibilityRole = Literal["observer", "subject"]


def visibility_history(
    *, battlefield_id: str = "battlefield.visibility_doorway_open",
    observer_position: tuple[int, int] = (5, 7),
    subject_position: tuple[int, int] = (8, 4),
    route: tuple[tuple[VisibilityRole, tuple[int, int]], ...] = (("subject", (8, 10)),),
    hidden_change_after: int | None = None,
    dash_before: bool = False,
) -> CapturedHistory:
    """Execute authored movement choices; native senses determine every sighting.

    Both actors exist at the shared baseline. A selected hidden mutation changes
    actual equipment and HP after the indexed movement operation; reacquisition
    must use those facts without displaying the unseen operation to the observer.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    built = build_battlefield(battlefield_id)
    game = Game()
    try:
        actors: dict[VisibilityRole, Entity] = {}
        placements: tuple[tuple[VisibilityRole, tuple[int, int]], ...] = (
            ("observer", observer_position), ("subject", subject_position))
        for role, position in placements:
            name = "Observer" if role == "observer" else "Subject"
            actor = Entity.create(uuid4(), name, config=EntityConfig(
                position=position, faction="heroes" if role == "observer" else "enemies",
                appearance=AppearanceConfig(body_category="NakedBody",
                    head_category="Head10" if role == "observer" else "Head22", has_beard=False),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")]),
            ))
            actor.install_initial_items((
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("weapon.dagger", actor.uuid), None),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            actor.compose_entity()
            actors[role] = actor
        for actor in actors.values():
            game.deploy_entity(actor, actor.position)
        encounter = Encounter(name="Paired visibility experiment", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        first = actors[route[0][0]] if route else actors["observer"]
        while encounter.get_current_entity() is not first:
            encounter.next_turn()
        baseline_cursor = EventQueue.event_cursor()
        startup = capture_interval(name="visibility experiment", start_cursor=0, end_cursor=baseline_cursor,
            observer_uuid=actors["observer"].uuid, battlefield_id=battlefield_id,
            door_uuid=built.object_uuids.get("door"))
        before, _ = reduce_interval(None, startup)
        for operation, (role, destination) in enumerate(route):
            actor = actors[role]
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()
            if dash_before and operation == 0:
                available = get_available_actions(actor)
                dash = next(row for row in available.all_actions
                            if row.behavior_id == "action.dash" and row.valid_targets)
                execute_by_index(actor, dash.template_name, dash.valid_targets[0].index, available=available)
            available = get_available_actions(actor)
            choices = [row for row in available.all_actions if row.behavior_id == "action.move"]
            chosen = next(((row, target) for row in choices for target in row.valid_targets
                           if target.position == destination), None)
            if chosen is None:
                # A subsequent route may need the actor's next actual turn.
                encounter.next_turn()
                while encounter.get_current_entity() is not actor:
                    encounter.next_turn()
                available = get_available_actions(actor)
                chosen = next(((row, target) for row in available.all_actions if row.behavior_id == "action.move"
                               for target in row.valid_targets if target.position == destination), None)
            if chosen is None:
                raise ValueError(f"{role} has no native move from {actor.position} to {destination}")
            action, target = chosen
            event = execute_by_index(actor, action.template_name, target.index, available=available)
            assert isinstance(event, MovementEvent) and event.phase is EventPhase.COMPLETION
            assert not event.canceled and actor.position == destination
            if operation == hidden_change_after:
                subject, observer = actors["subject"], actors["observer"]
                contact = observer.senses.entities.get(subject.uuid)
                assert contact is None or not contact.visual, "hidden-change case requires native loss of sight"
                dagger = next(item for item in subject.inventory.items.values() if item.item_id == "weapon.dagger")
                assert subject.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
                subject.receive_damage(7, DamageType.FORCE, source_entity_uuid=subject.uuid)
                assert subject.get_hp() == 33
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline_cursor) for role, actor in actors.items()))
        primary = captured.views["observer"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
