"""Native portal stories with independent witnesses at the two endpoints."""

from typing import Literal
from uuid import uuid4

from dnd.actions import Jump, Move
from dnd.actions_functional import execute_use_action, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_trap_lever
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue, PortalTransferEvent
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.portals import PORTAL_CONTENT_REF, PORTAL_HATCH_CONTENT_REF, materialize_portal
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.types.traps import TrapState, TrapDamage, TrapPayload
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def portal_history(*, program: Literal["hatch-walk", "hatch-jump", "bare-walk", "blocked-exit",
                                       "occupied-activation", "hatch-open", "hatch-visible",
                                       "hatch-open-jump"] = "hatch-walk",
                   arrival_spikes: bool = False) -> CapturedHistory:
    """Run commands once; each replay receives its own observed endpoint facts."""
    reset_engine_runtime()
    built = build_battlefield("battlefield.visibility_open_range")
    grid = get_map()
    for y in range(built.definition.height):
        grid.set_tile(10, y, name="Wall", walking_cost=0, blocks_optics=True)
    if program == "blocked-exit":
        grid.set_tile(17, 2, name="Wall", walking_cost=0, blocks_optics=True)
    game = Game()
    try:
        actors: dict[str, Entity] = {}
        for role, position in (("traveler", (2, 2)), ("departure", (2, 3)), ("arrival", (17, 3))):
            config = EntityConfig(position=position,
                faction="heroes", ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)))
            if arrival_spikes:
                config = config.model_copy(update={"health": HealthConfig(hit_dices=[
                    HitDiceConfig(hit_dice_value=10, hit_dice_count=2, mode="maximums")])})
            actor = Entity.create(uuid4(), role.title(), config=config)
            setup_standard_actions(actor)
            actor.install_initial_items((
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        initial_state = (TrapState.DEACTIVATED if program == "occupied-activation" else
                         TrapState.ACTIVATED if program in ("bare-walk", "hatch-open", "hatch-open-jump") else TrapState.READY)
        concealed = initial_state is TrapState.READY and program != "hatch-visible"
        portal = materialize_portal({(3, 2)}, (17, 2), trap_state=initial_state,
            content_ref=PORTAL_CONTENT_REF if program == "bare-walk" else PORTAL_HATCH_CONTENT_REF,
            stealth_dc=40 if concealed else None)
        if arrival_spikes:
            materialize_spike_trap_condition({(17, 2)}, payload=TrapPayload(damages=(
                TrapDamage(dice_count=1, dice_sides=4, damage_type=DamageType.PIERCING),)))
        lever = None
        if program == "occupied-activation":
            lever = build_trap_lever(portal.uuid, charges=-1, allow_activation=True)
            # Authored initial handle agrees with the initially disabled entrance.
            lever.is_engaged = True
            lever.place_on_grid((3, 3))
        encounter = Encounter(name="Two portal rooms", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 10, 1):
            encounter.start_encounter()
        encounter.start_turn()
        Entity.update_all_entities_senses()
        if concealed:
            assert all(portal.uuid not in actor.senses.spatial_effects for actor in actors.values())
        else:
            assert portal.uuid in actors["traveler"].senses.spatial_effects
            assert portal.uuid in actors["departure"].senses.spatial_effects
        assert portal.uuid not in actors["arrival"].senses.spatial_effects
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Two portal rooms", start_cursor=0, end_cursor=baseline,
            observer_uuid=actors["traveler"].uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        traveler = actors["traveler"]
        while encounter.get_current_entity() is not traveler:
            encounter.next_turn()
        with fixed_dice_faces(1):
            if program in ("hatch-jump", "hatch-open-jump"):
                result = Jump(source_entity_uuid=traveler.uuid, end_position=(3, 2)).apply()
            else:
                route = [(2, 2), (3, 2)]
                if program in ("hatch-walk", "bare-walk", "hatch-open", "hatch-visible"):
                    route.append((4, 2))  # Transfer must abandon the old remaining route.
                result = Move(source_entity_uuid=traveler.uuid, end_position=route[-1],
                    path=route, prefer_safe=False).apply()
        assert result is not None and not result.canceled
        if program == "occupied-activation":
            assert traveler.position == (3, 2) and portal.trap_state is TrapState.DEACTIVATED
            operator = actors["departure"]
            while encounter.get_current_entity() is not operator:
                encounter.next_turn()
            operator.update_entity_senses()
            assert lever is not None
            result = execute_use_action(operator, lever.uuid, "Activate Trap")
            assert result is not None and not result.canceled
        assert traveler.position == ((3, 2) if program == "blocked-exit" else (17, 2))
        assert portal.trap_state is TrapState.ACTIVATED
        transfers = [event for _, event in EventQueue.iter_events_since(baseline)
                     if isinstance(event, PortalTransferEvent)
                     and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)]
        transfer, = transfers
        assert transfer.committed is (program != "blocked-exit")
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["traveler"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
