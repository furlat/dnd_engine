"""Discovered ordered casts, exposure and removal saved for cold wall playback."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.walls import WallOfFire
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def wall_spell_history(*, axis: Literal["x", "y", "diagonal", "oblique"] = "x", raised: bool = False,
                       retain_field: bool = False, multiple_targets: bool = False,
                       formation_targets: bool = False,
                       ring_hot_side: Literal["inside", "outside"] | None = None) -> CapturedHistory:
    """Native endpoints retain flame contacts separately from the heated band."""
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    if raised:
        for position in get_map().get_all_tiles():
            assert get_map().set_tile_elevation(position, height=2,
                surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    game = Game()
    try:
        start, end = ((4, 6), (8, 6)) if axis == "x" else ((6, 4), (6, 8))
        positions = {"caster": (2, 7) if axis == "x" else (4, 3),
                     "target": (6, 7) if axis == "x" else (5, 6)}
        if axis in ("diagonal", "oblique"):
            start, end = (4, 4), (8, 8) if axis == "diagonal" else (8, 6)
            positions = {"caster": (2, 6), "target": (5, 7)}
            if axis == "oblique":
                positions["target"] = (5, 6)
        if multiple_targets:
            positions.update({"target": (5, 7) if axis == "x" else (5, 5),
                              "hot-far": (7, 8) if axis == "x" else (4, 7),
                              "safe": (6, 5) if axis == "x" else (7, 6)})
        if formation_targets:
            assert multiple_targets and axis == "x"
            positions.update({"target": (5, 6), "hot-far": (7, 6)})
        if ring_hot_side is not None:
            start, end = (6, 6), (6, 6)
            positions = {"caster": (6, 5), "target": (6, 7) if ring_hot_side == "inside" else (9, 6),
                         "safe": (9, 6) if ring_hot_side == "inside" else (6, 7),
                         "formation": (8, 6), "center": (6, 6)}
        actors = {}
        for role, position in positions.items():
            name = ("Hot near" if role == "target" else "Hot far" if role == "hot-far" else role.title()) if multiple_targets else role.title()
            actor = Entity.create(uuid4(), name, config=EntityConfig(
                position=position, faction="heroes" if role == "caster" else "enemies",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    constitution=AbilityConfig(ability_score=30 if ring_hot_side is not None and role == "caster" else 20)),
                action_economy=ActionEconomyConfig(spell_slots={4: 2}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=12, hit_dice_count=30, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22")))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            if role == "caster":
                register_spell(actor, WallOfFire, caster_level=7)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        encounter = Encounter(name="Wall of Fire native ordered cast", source_entity_uuid=actors["caster"].uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(18, 14, 10, 6, 5):
            encounter.start_encounter()
        encounter.start_turn()
        baseline = EventQueue.event_cursor()
        initialization = capture_interval(name="Wall initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=actors["caster"].uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initialization)

        def command(role: str, behavior: str, *, position: tuple[int, int] | None = None,
                    extra: tuple[tuple[int, int], ...] = ()):
            actor = actors[role]
            with fixed_dice_faces(*([4] * 100)):
                while encounter.get_current_entity() is not actor:
                    encounter.next_turn()
            options = [(action, target) for action in get_available_actions(actor).all_actions
                if action.behavior_id == behavior and (behavior != "spell.wall_of_fire"
                    or {facet.key:facet.value for facet in action.variant_facets} ==
                        ({"form":"ring","side":ring_hot_side} if ring_hot_side else {"form":"segment"}))
                for target in action.valid_targets if position is None or target.position == position]
            assert options, (role, behavior, position)
            with fixed_dice_faces(*([4] * 100)):
                result = execute_available_action(actor, *options[0], extra_target_positions=list(extra))
            assert result is not None and not result.canceled
            return result

        initial_hp = {role: actor.get_hp() for role, actor in actors.items()}
        cast = command("caster", "spell.wall_of_fire", position=start,
                       extra=() if ring_hot_side is not None else (end,))
        assert isinstance(cast, SpellEvent) and cast.area_geometry is not None
        if ring_hot_side is not None:
            assert actors["formation"].get_hp() < initial_hp["formation"]
            hot_hp, safe_hp = actors["target"].get_hp(), actors["safe"].get_hp()
            command("target", "action.dodge")
            command("safe", "action.dodge")
            command("caster", "action.dodge")
            assert actors["target"].get_hp() < hot_hp
            assert actors["safe"].get_hp() == safe_hp
            command("target", "action.move", position=(8, 7))
            command("target", "action.dodge")
            if not retain_field:
                command("caster", "action.drop_concentration")
            captured = capture_history(before, (), observers=tuple(
                ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
            primary = captured.views["caster"]
            return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
        if formation_targets:
            assert all(actors[role].get_hp() < initial_hp[role] for role in ("target", "hot-far"))
            assert actors["safe"].get_hp() == initial_hp["safe"]
        hp = actors["target"].get_hp()
        command("target", "action.dodge")
        if multiple_targets:
            far_hp, safe_hp = actors["hot-far"].get_hp(), actors["safe"].get_hp()
            command("hot-far", "action.dodge")
            command("safe", "action.dodge")
            command("caster", "action.dodge")
            assert actors["target"].get_hp() < hp
            assert actors["hot-far"].get_hp() < far_hp
            assert actors["safe"].get_hp() == safe_hp
        else:
            # Cardinal fixtures cross into the cold side. Angled fixtures hold
            # their positions to expose module width and seams.
            command("caster", "action.dodge")
            assert actors["target"].get_hp() < hp
            if axis in ("x", "y"):
                command("target", "action.move", position=(6, 6))
                command("target", "action.move", position=(6, 5) if axis == "x" else (7, 6))
            command("target", "action.dodge")
        if not retain_field:
            command("caster", "action.drop_concentration")
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
