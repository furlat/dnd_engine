"""Native jump contact narratives shared by tests and paired recordings."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import GhoulClawsParalysisFeature
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.types.traps import TrapState
from dnd.types.world import OccupancyLayer
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def ground_contact_history(
    *, program: Literal["jump", "interrupted-jump"] = "jump",
) -> CapturedHistory:
    """Author the initial room, then record actual native jumps and turns."""
    previous_random = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        interrupted = program == "interrupted-jump"
        positions = {(5, 3)} if interrupted else {(4, 3), (6, 3)}
        trap = materialize_spike_trap_condition(positions)
        actors: dict[str, Entity] = {}
        for role, position in (("mover", (3, 3)), ("operator", (4, 2) if interrupted else (3, 5))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="enemies" if interrupted and role == "operator" else "heroes",
                ability_scores=AbilityScoresConfig(strength=AbilityConfig(
                    ability_score=10 if interrupted and role == "operator" else 18)),
                health=HealthConfig(hit_dices=[HitDiceConfig(
                    hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "mover" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            if role == "operator" and interrupted:
                actor.install_initial_items(((
                    build_authored_item("weapon.longsword", actor.uuid), WeaponSlot.MELEE_MAIN,
                ),))
                actor.add_condition(GhoulClawsParalysisFeature(
                    source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid,
                    weapon_names=("Longsword",),
                ))
                add_opportunity_attack_handler(actor)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        mover = actors["mover"]
        encounter = Encounter(name="Native floor contact", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()

        def turn(actor: Entity) -> None:
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()

        def perform(actor: Entity, behavior: str, *, destination: tuple[int, int],
                    dice_faces: tuple[int, ...] = ()) -> Event:
            turn(actor)
            available = get_available_actions(actor)
            choices = [(row, target) for row in available.all_actions
                if row.behavior_id == behavior
                for target in row.valid_targets if target.position == destination]
            if not choices:
                raise ValueError(f"No discovered {behavior} for {actor.name}: {destination}")
            row, target = choices[0]
            with fixed_dice_faces(*dice_faces):
                result = execute_by_index(actor, row.template_name, target.index, available=available)
            assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
            return result

        turn(mover)
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Ground contact initialization", start_cursor=0,
            end_cursor=baseline, observer_uuid=mover.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        hp = mover.get_hp()
        if interrupted:
            perform(mover, "action.jump", destination=(6, 3), dice_faces=(18, 2, 1, 1, 1))
            assert mover.position == (5, 3) and "Paralyzed" in mover.active_conditions
        else:
            perform(mover, "action.jump", destination=(5, 3))
            assert mover.position == (5, 3) and mover.occupancy_layer is OccupancyLayer.GROUND
            assert mover.get_hp() == hp and trap.trap_state is TrapState.READY
            encounter.next_turn()
            perform(mover, "action.jump", destination=(6, 3), dice_faces=(1, 1))
        assert mover.occupancy_layer is OccupancyLayer.GROUND
        assert mover.get_hp() == hp - (4 if interrupted else 2)
        assert trap.trap_state is TrapState.ACTIVATED

        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["mover"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
