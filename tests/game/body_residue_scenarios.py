"""Native injuries, departure and crossings saved for both participants."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import (
    BLOOD_BODY_RESPONSE, BONE_BODY_RESPONSE, CORROSIVE_BODY_RESPONSE, DREAD_BODY_RESPONSE, install_body_response,
)
from dnd.conditions import Blinded, Invisible
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_door, build_standing_torch
from dnd.types.world import CardinalDirection
from dnd.world_authoring import place_world_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.content.recipes import ContentRecipe
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.types.traps import TrapState
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


BODY_PROFILES = {"blood": BLOOD_BODY_RESPONSE, "bone": BONE_BODY_RESPONSE,
                 "corrosive": CORROSIVE_BODY_RESPONSE, "dread": DREAD_BODY_RESPONSE}


def body_residue_history(*, profile: Literal["blood", "bone", "corrosive", "dread"] = "blood",
                         mixed: bool = False, hits: int = 2,
                         weapon: str = "weapon.dagger", critical: bool = False,
                         layout: Literal["east", "north", "reverse", "closed-door", "open-door", "raised", "ledge"] = "east",
                         crossings: bool = True, fixed_skeleton: bool = False,
                         creature_identity: str | None = None) -> CapturedHistory:
    """Discovered attacks accumulate residue, then real movement crosses it.

    The mixed case adds a second authored body response and lowered spikes at
    the same support tile. Substance is composition data, independent of art.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.visual_vertical_seam" if layout in ("raised", "ledge") else "battlefield.open_floor_bright")
    game = Game()
    try:
        if layout in ("closed-door", "open-door"):
            door = build_directional_door(is_open=layout == "open-door")
            place_world_item(door, (5, 3), boundary_direction=CardinalDirection.EAST, author_uuid=uuid4())
        if layout in ("raised", "ledge"):
            build_standing_torch().mount((16, 20), lit=True)
        if mixed:
            materialize_spike_trap_condition({(5, 3)}, trap_state=TrapState.DEACTIVATED)
        actors: dict[str, Entity] = {}
        placements = (("donor", (5, 3)), ("walker", {"north": (5, 2), "reverse": (6, 3)}.get(layout, (4, 3))))
        if layout in ("raised", "ledge"):
            x = 16 if layout == "raised" else 18
            placements = (("donor", (x, 21)), ("walker", (x - 1, 21)))
        if mixed:
            placements += (("bone", (6, 4)),)
        for role, position in placements:
            creature_id = "skeleton_archer" if fixed_skeleton or role == "bone" else f"{profile}_demon"
            if role == "bone" or role == "donor" and (creature_identity or fixed_skeleton or profile in ("corrosive", "dread")):
                identity = (creature_identity if role == "donor" else None) or f"content.neurodragon:creature:creature.{creature_id}@1"
                declaration = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry.declarations[
                    identity]
                actor = materialize_creature(
                    ContentRecipe.create(ref=declaration.ref, parameters={}), runtime_entity_uuid=uuid4(),
                    display_name=declaration.descriptor.display_name, faction="enemies", position=position,
                    deployment_role=CreatureDeploymentRole(role_id="scenario.body_residue"),
                    possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
                )
                if role == "donor" and creature_identity is not None:
                    # Explicit review composition, before recording/deployment;
                    # the selected canonical creature definition is unchanged.
                    install_body_response(actor, BODY_PROFILES[profile])
                    actor.name = f"{declaration.descriptor.display_name} · {profile} review"
            else:
                actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                    position=position, faction="heroes" if role == "walker" else "enemies",
                    health=HealthConfig(hit_dices=[HitDiceConfig(
                        hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                    appearance=AppearanceConfig(body_category="NakedBody2" if role == "bone" or role == "donor" and profile == "bone" else "NakedBody",
                        has_beard=False, head_category="Head10" if role == "walker" else "Head22"),
                ))
                actor.install_initial_items((
                    (build_authored_item(weapon, actor.uuid), WeaponSlot.MELEE_MAIN),
                    (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                ))
                if role != "walker":
                    install_body_response(actor, BONE_BODY_RESPONSE if role == "bone" else BODY_PROFILES[profile])
                setup_standard_actions(actor)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        donor, walker = actors["donor"], actors["walker"]
        encounter = Encounter(name="Body residue history", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()

        def perform(actor: Entity, behavior: str, *, destination: tuple[int, int] | None = None,
                    target: Entity | None = None) -> Event:
            for attempt in range(2):
                while encounter.get_current_entity() is not actor:
                    encounter.next_turn()
                available = get_available_actions(actor)
                choices = [(row, option) for row in available.all_actions
                    if row.behavior_id == behavior
                    and (behavior != "action.attack" or row.weapon_slot == WeaponSlot.MELEE_MAIN.value)
                    for option in row.valid_targets
                    if (destination is None or option.position == destination)
                    and (target is None or option.target_uuid == target.uuid)]
                if choices:
                    break
                if attempt == 0:
                    encounter.next_turn()
            if not choices:
                raise ValueError(f"No discovered {behavior}: {actor.name}, {destination}")
            row, option = choices[0]
            faces = ((20, 2, 2) if critical else (18, 2)) if behavior == "action.attack" else (2,) if profile == "corrosive" else ()
            with fixed_dice_faces(*faces):
                result = execute_by_index(actor, row.template_name, option.index, available=available)
            assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
            return result

        while encounter.get_current_entity() is not walker:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Body residue initialization", start_cursor=0,
            end_cursor=baseline, observer_uuid=walker.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        for _ in range(hits):
            perform(walker, "action.attack", target=donor)
        if crossings:
            perform(donor, "action.move", destination=(6, 3))
            if mixed:
                bone = actors["bone"]
                perform(bone, "action.move", destination=(5, 3))
                perform(walker, "action.attack", target=bone)
                perform(bone, "action.move", destination=(6, 4))
            hp = walker.get_hp()
            perform(walker, "action.move", destination=(5, 3))
            perform(walker, "action.move", destination=(4, 3))
            perform(walker, "action.move", destination=(5, 3))
            assert walker.get_hp() == hp - (4 if profile == "corrosive" else 0)
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items() if role != "bone"))
        primary = captured.views["walker"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)


def hidden_residue_history(*, first_sight: bool = False) -> CapturedHistory:
    """An unseen body is injured on a visible support tile, without revealing it.

    Injury uses the native damage entry point because the witness cannot select
    the invisible donor as an attack target. Blindness controls when the witness
    can first observe the tile's new state; no snapshot is patched.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        actors: dict[str, Entity] = {}
        for role, position in (("donor", (5, 3)), ("witness", (4, 3))):
            actor = Entity.create(uuid4(), "Unseen donor" if role == "donor" else "Witness",
                config=EntityConfig(position=position, faction="enemies" if role == "donor" else "heroes",
                    health=HealthConfig(hit_dices=[HitDiceConfig(
                        hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                    appearance=AppearanceConfig(body_category="NakedBody", has_beard=False, head_category="Head10")))
            if role == "donor":
                install_body_response(actor, BLOOD_BODY_RESPONSE)
                actor.add_condition(Invisible(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        donor, witness = actors["donor"], actors["witness"]
        materialize_spike_trap_condition({(5, 3)}, stealth_dc=40, trap_state=TrapState.DEACTIVATED)
        encounter = Encounter(name="Unseen body residue", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        assert donor.uuid not in witness.senses.entities
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Unseen residue initialization", start_cursor=0,
            end_cursor=baseline, observer_uuid=witness.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        blinded = Blinded(source_entity_uuid=witness.uuid, target_entity_uuid=witness.uuid)
        if first_sight:
            witness.add_condition(blinded)
        donor.receive_damage(3, DamageType.PIERCING, source_entity_uuid=donor.uuid)
        if first_sight:
            witness.remove_condition_by_uuid(blinded.uuid)
        assert donor.uuid not in witness.senses.entities
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["witness"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
