"""Native gap-delivery captures shared with the standard visual review catalog."""

import random
from uuid import uuid4

from dnd.actions import AttackEvent, SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import ConeOfCold
from dnd.spells.wall_fields import WindWall
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.area_spell_scenarios import area_spell_history
from tests.game.assembly_scenarios import assembly_history
from tests.manual.spell_regression_support import force_save_result


CONE_DIRECTIONS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))


def cone_gap_history(*, heading: int = 0, oblique: bool = False) -> CapturedHistory:
    """Keep the native cone vector and failed/successful saves in detached bytes."""
    if not 0 <= heading < len(CONE_DIRECTIONS):
        raise ValueError("Cone heading must be one of the eight source headings")
    direction = (2, 1) if oblique else CONE_DIRECTIONS[heading]
    dx, dy = direction
    source = (14, 14)
    destination = (source[0]+3*dx, source[1]+3*dy)
    positions = {"caster": source, "outside": (source[0]-dx, source[1]-dy)}
    positions.update(recipient=destination, saved=(source[0]+2*dx, source[1]+2*dy))
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.weather_review"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors: dict[str, Entity] = {}
        for role, position in positions.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "caster" else "enemies",
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False),
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={5: 1}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode="maximums")]),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, ConeOfCold, caster_level=9)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            force_save_result(actor, "constitution", succeeds=role == "saved")
            actors[role] = actor
        caster = actors["caster"]
        encounter = Encounter(name="Native Cone delivery", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10]*len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Cone initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        choices = [(action, target) for action in get_available_actions(caster).all_actions
            if action.behavior_id == "spell.cone_of_cold" for target in action.valid_targets
            if target.position is not None
            and (target.position[0]-source[0])*dy == (target.position[1]-source[1])*dx
            and (target.position[0]-source[0])*dx+(target.position[1]-source[1])*dy > 0]
        assert choices, (direction, destination)
        with fixed_dice_faces(*([4]*100)):
            result = execute_available_action(caster, *choices[0])
        assert isinstance(result, SpellEvent) and not result.canceled and result.phase is EventPhase.COMPLETION
        assert actors["outside"].get_hp() == before.actors[actors["outside"].uuid].normal_hp
        assert caster.get_hp() == before.actors[caster.uuid].normal_hp
        losses = {role: before.actors[actors[role].uuid].normal_hp-actors[role].get_hp()
            for role in ("recipient", "saved")}
        assert losses == {"recipient": 32, "saved": 16}, losses
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)


def call_lightning_gap_history(*, moved_empty_repeat: bool = False) -> CapturedHistory:
    """The established paid cast, retained repeat and native concentration drop."""
    return area_spell_history(program="call_lightning",
        call_repeat_position=(9, 8) if moved_empty_repeat else None, move_before_repeat=moved_empty_repeat)


def thorns_ring_history() -> CapturedHistory:
    """The discovered native ring, real damage and ordinary concentration removal."""
    return assembly_history(program="thorns", form="ring")


def wind_interception_history(*, direction: tuple[int, int] = (0, 1), blocked: bool = True) -> CapturedHistory:
    """An ordinary longbow shot crosses, or misses, an actual discovered Wind Wall.

    Cardinal, diagonal and oblique paths pass through the same arrow crossing.
    The clear control retains its visible wall four cells north of the shot.
    """
    if direction not in ((0, 1), (1, 1), (1, 2)):
        raise ValueError("Wind review uses cardinal, diagonal and oblique paths")
    dx, dy = direction
    center = (8, 8 if blocked else 3)
    start, end = (center[0]-dx, center[1]-dy), (center[0]+dx, center[1]+dy)
    positions = {"caster": (3, 12), "archer": (5, 8), "recipient": (11, 8)}
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors: dict[str, Entity] = {}
        for role, position in positions.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="enemies" if role == "recipient" else "heroes",
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False),
                action_economy=ActionEconomyConfig(spell_slots={3: 1}),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=12, mode="maximums")]),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
                *((((build_authored_item("weapon.longbow", actor.uuid), WeaponSlot.RANGED_MAIN),)
                    if role == "archer" else ())),
            ))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, WindWall, caster_level=5)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, archer, recipient = (actors[role] for role in ("caster", "archer", "recipient"))
        encounter = Encounter(name="Native Wind missile interception", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(18, 12, 6):
            encounter.start_encounter()
        encounter.start_turn()
        assert encounter.get_current_entity() is caster
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Wind missile initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        choices = [(action, target) for action in get_available_actions(caster).all_actions
            if action.behavior_id == "spell.wind_wall" for target in action.valid_targets if target.position == start]
        assert choices, start
        with fixed_dice_faces(*([4]*100)):
            cast = execute_available_action(caster, *choices[0], extra_target_positions=[end])
        assert isinstance(cast, SpellEvent) and not cast.canceled
        while encounter.get_current_entity() is not archer:
            encounter.next_turn()
        before_shot = recipient.get_hp()
        attacks = [(action, target) for action in get_available_actions(archer).all_actions
            if action.behavior_id == "action.attack" and action.weapon_slot == WeaponSlot.RANGED_MAIN.value
            for target in action.valid_targets if target.position == recipient.position]
        assert attacks
        with fixed_dice_faces(20, *([4]*100)):
            shot = execute_available_action(archer, *attacks[0])
        assert isinstance(shot, AttackEvent) and not shot.canceled and shot.phase is EventPhase.COMPLETION
        assert (shot.intercepted_by_condition_uuid is not None) is blocked
        assert (shot.projectile_deflection_position is not None) is blocked
        assert (recipient.get_hp() == before_shot) is blocked
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
