"""Real spell turns for registered Fireball and Globe review, saved once."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import GlobeOfInvulnerability
from dnd.spells.conjuration import Cloudkill, Darkness, FogCloud, IncendiaryCloud
from dnd.spells.evocation import Fireball, FireBolt
from dnd.spells.ice_knife import IceKnife
from dnd.types.world import CardinalDirection
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def globe_history(*, spell: Literal["fireball", "fire_bolt", "ice_knife", "fog_cloud", "darkness", "cloudkill", "incendiary_cloud"] = "fireball",
                  protection: bool = True, source_inside: bool = False,
                  impact_offset: tuple[int, int] = (3, 0),
                  walls: Literal["none", "wall", "door", "l-wall", "corridor"] = "none",
                  retain_field: bool = False) -> CapturedHistory:
    prior_random = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        center = (7, 7)
        impact = center[0] + impact_offset[0], center[1] + impact_offset[1]
        positions = {"owner": center, "caster": (6, 7) if source_inside else (1, 7),
                     "target": (8, 7), "outside": (11, 7)}
        if spell == "ice_knife":
            positions["target"], positions["outside"] = (9, 7), (10, 7)
        if walls != "none":
            positions = {"owner": (4, 5), "caster": (5, 8), "target": (7, 9), "outside": (11, 8)}
            impact = (8, 8)
            edges = []
            if walls in ("wall", "door"):
                edges = [((9, y), CardinalDirection.EAST) for y in range(4, 13)
                         if walls != "door" or y != 8]
            elif walls == "l-wall":
                edges = [((9, y), CardinalDirection.EAST) for y in range(4, 10)] + [
                    ((x, 9), CardinalDirection.NORTH) for x in range(4, 10)]
            else:
                edges = [((x, y), direction) for x, direction in ((7, CardinalDirection.WEST), (9, CardinalDirection.EAST))
                         for y in range(3, 14)]
                positions["caster"], positions["outside"] = (8, 4), (8, 11)
            for position, direction in edges:
                build_directional_wall().place_on_grid(position, boundary_direction=direction)
        actors = {}
        spell_type = {"fireball": Fireball, "fire_bolt": FireBolt, "ice_knife": IceKnife,
            "fog_cloud": FogCloud, "darkness": Darkness, "cloudkill": Cloudkill,
            "incendiary_cloud": IncendiaryCloud}[spell]
        targets_area = spell not in ("fire_bolt", "ice_knife")
        for role, position in positions.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="enemies" if role == "caster" else "heroes",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    constitution=AbilityConfig(ability_score=20)),
                action_economy=ActionEconomyConfig(spell_slots={level: 2 for level in range(1, 9)}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=12, hit_dice_count=20, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22")))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            if role == "owner":
                register_spell(actor, GlobeOfInvulnerability, caster_level=11)
            if role == "caster":
                register_spell(actor, spell_type, caster_level=5)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        encounter = Encounter(name="Globe and registered spell geometry", source_entity_uuid=actors["owner"].uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(18, 14, 10, 6):
            encounter.start_encounter()
        encounter.start_turn()
        baseline = EventQueue.event_cursor()
        initialization = capture_interval(name="Globe experiment initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=actors["caster"].uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initialization)

        def command(role, behavior, *, position=None, target_uuid=None):
            actor = actors[role]
            with fixed_dice_faces(*([10] * 100)):
                while encounter.get_current_entity() is not actor:
                    encounter.next_turn()
            options = [(action, target) for action in get_available_actions(actor).all_actions
                       if action.behavior_id == behavior for target in action.valid_targets
                       if (position is None or target.position == position)
                       and (target_uuid is None or target.target_uuid == target_uuid)]
            assert options, (role, behavior, position, target_uuid)
            with fixed_dice_faces(*([4] * 100)):
                return execute_available_action(actor, *options[0])

        if protection:
            result = command("owner", "spell.globe_of_invulnerability")
            assert result is not None and not result.canceled
        target = actors["outside"] if spell == "ice_knife" else actors["target"]
        hp = target.get_hp()
        result = command("caster", "spell." + spell, position=impact if targets_area else None,
                         target_uuid=None if targets_area else target.uuid)
        assert isinstance(result, SpellEvent)
        if protection and not source_inside and spell == "fire_bolt":
            assert result.canceled and result.suppressions and target.get_hp() == hp
        else:
            assert not result.canceled, result.status_message
        if protection and not retain_field and "Concentrating" in actors["owner"].active_conditions:
            result = command("owner", "action.drop_concentration")
            assert result is not None and not result.canceled
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "target")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(prior_random)
