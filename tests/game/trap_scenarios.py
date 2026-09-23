"""Real turn-based trap entry, re-entry, lowering and occupied activation."""

import random
from typing import Literal
from uuid import UUID, uuid4

from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_trap_lever
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.core.item_types import ItemLocation
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.environmental_conditions import (
    PLAIN_SPIKE_PAYLOAD, POISON_DAMAGE_SPIKE_PAYLOAD, SICKENING_SPIKE_PAYLOAD,
    SPIKE_TRAP_CONTENT_REF, POISON_DAMAGE_SPIKE_CONTENT_REF, SICKENING_SPIKE_CONTENT_REF,
    materialize_spike_trap_condition,
)
from dnd.types.traps import TrapState
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


TRAP_PAYLOADS = {"plain": PLAIN_SPIKE_PAYLOAD, "poison-damage": POISON_DAMAGE_SPIKE_PAYLOAD,
                 "poisoned": SICKENING_SPIKE_PAYLOAD}
TRAP_CONTENT = {"plain": SPIKE_TRAP_CONTENT_REF, "poison-damage": POISON_DAMAGE_SPIKE_CONTENT_REF,
                "poisoned": SICKENING_SPIKE_CONTENT_REF}


def trap_history(
    *, detected: bool = False,
    payload: Literal["plain", "poison-damage", "poisoned"] = "plain",
    save_face: Literal[1, 20] = 1,
    bloodied: bool = False,
) -> CapturedHistory:
    """Only initial actors/fixtures and reproducible dice are authored.

    From the baseline onward, every move and lever use is selected through real
    action discovery and executed on the actor's native encounter turn.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        trap = materialize_spike_trap_condition({(5, 3)}, stealth_dc=11,
            payload=TRAP_PAYLOADS[payload], content_ref=TRAP_CONTENT[payload])
        lever = build_trap_lever(trap.uuid, charges=-1, allow_activation=True)
        lever.place_on_grid((3, 4))
        lever.publish_location_state(ItemLocation.FLOOR)
        actors: dict[str, Entity] = {}
        for role, position in (("walker", (4, 3)), ("operator", (3, 5))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes",
                ability_scores=AbilityScoresConfig(wisdom=AbilityConfig(
                    ability_score=18 if role == "walker" and detected else 10)),
                health=HealthConfig(hit_dices=[HitDiceConfig(
                    hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "walker" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        walker, operator = actors["walker"], actors["operator"]
        assert (trap.uuid in walker.senses.spatial_effects) is detected
        assert trap.uuid not in operator.senses.spatial_effects
        encounter = Encounter(name="Spike trap lifecycle", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()

        def turn(actor: Entity) -> None:
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()

        def perform(actor: Entity, *, destination: tuple[int, int] | None = None,
                    item_uuid: UUID | None = None, damage: bool = False) -> Event:
            turn(actor)
            available = get_available_actions(actor)
            choices = [(row, target) for row in available.all_actions
                if (row.source_item_uuid == item_uuid if item_uuid is not None else row.behavior_id == "action.move")
                for target in row.valid_targets
                if destination is None or target.position == destination]
            if not choices:
                raise ValueError(f"No discovered action for {actor.name}: {destination or item_uuid}")
            row, target = choices[0]
            faces = (2, 2, 2) if payload == "poison-damage" else (2, 2, save_face) if payload == "poisoned" else (2, 2)
            with fixed_dice_faces(*(faces if damage else ())):
                result = execute_by_index(actor, row.template_name, target.index, available=available)
            assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
            return result

        turn(walker)
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Trap lifecycle initialization", start_cursor=0,
            end_cursor=baseline, observer_uuid=walker.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        hp = walker.get_hp()
        hit = 6 if payload == "poison-damage" else 4
        perform(walker, destination=(5, 3), damage=True)
        assert walker.get_hp() == hp - hit and trap.trap_state is TrapState.ACTIVATED
        perform(walker, destination=(6, 3))
        perform(walker, destination=(5, 3), damage=True)
        assert walker.get_hp() == hp - 2 * hit
        perform(walker, destination=(4, 3))

        perform(operator, item_uuid=lever.uuid)
        assert trap.trap_state is TrapState.DEACTIVATED and trap.applied
        for destination in ((5, 3), (6, 3), (5, 3)):
            perform(walker, destination=destination)
            assert walker.get_hp() == hp - 2 * hit
        assert walker.position == (5, 3)
        perform(operator, item_uuid=lever.uuid, damage=True)
        assert trap.trap_state is TrapState.ACTIVATED and walker.position == (5, 3)
        assert walker.get_hp() == hp - 3 * hit
        perform(walker, destination=(6, 3))
        assert walker.get_hp() == hp - 3 * hit

        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["walker"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
