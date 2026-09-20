"""Actual dread-demon injury followed by a discovered entry and paid retreat."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_by_index, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.content.recipes import ContentRecipe
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import MistyStep
from dnd.types.world import OccupancyLayer
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def dread_residue_history(*, entry: Literal["walk", "jump", "misty-step"] = "walk") -> CapturedHistory:
    """Retain incoming contact and ordinary reverse movement from both views.

    A witness wounds an authored dread demon, which leaves its pool. The
    traveler then fails the real entry save and pays for the native reverse
    step. Every actor action is selected through native action discovery.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        start = {"walk": (6, 3), "jump": (5, 3), "misty-step": (3, 3)}[entry]
        actors: dict[str, Entity] = {}
        for role, position in (("traveler", start), ("witness", (7, 4))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes",
                ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={2: 1} if role == "traveler" else {}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(
                    hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "traveler" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("weapon.dagger", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
            ))
            setup_standard_actions(actor)
            if role == "traveler":
                register_spell(actor, MistyStep, caster_level=3)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        declaration = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry.declarations[
            "content.neurodragon:creature:creature.dread_demon@1"]
        donor = materialize_creature(
            ContentRecipe.create(ref=declaration.ref, parameters={}), runtime_entity_uuid=uuid4(),
            display_name=declaration.descriptor.display_name, faction="enemies", position=(7, 3),
            deployment_role=CreatureDeploymentRole(role_id="scenario.dread_residue"),
            possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
        )
        donor.compose_entity()
        game.deploy_entity(donor, donor.position)
        actors["donor"] = donor
        traveler, witness = actors["traveler"], actors["witness"]
        encounter = Encounter(name="Paid dread-pool retreat", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()

        def perform(actor: Entity, behavior: str, *, destination: tuple[int, int] | None = None,
                    target: Entity | None = None) -> Event:
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()
            available = get_available_actions(actor)
            choices = [(row, option) for row in available.all_actions
                if row.behavior_id == behavior
                and (behavior != "action.attack" or row.weapon_slot == WeaponSlot.MELEE_MAIN.value)
                for option in row.valid_targets
                if (destination is None or option.position == destination)
                and (target is None or option.target_uuid == target.uuid)]
            if not choices:
                raise ValueError(f"No discovered {behavior}: {actor.name}, {destination}")
            row, option = choices[0]
            with fixed_dice_faces(*(18, 2) if behavior == "action.attack" else (1,)):
                result = execute_by_index(actor, row.template_name, option.index, available=available)
            assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
            return result

        while encounter.get_current_entity() is not witness:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Dread residue initialization", start_cursor=0,
            end_cursor=baseline, observer_uuid=traveler.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        perform(witness, "action.attack", target=donor)
        perform(donor, "action.move", destination=(8, 3))
        perform(traveler, {"walk": "action.move", "jump": "action.jump",
            "misty-step": "spell.misty_step"}[entry], destination=(7, 3))
        assert traveler.position == (6, 3) and traveler.occupancy_layer is OccupancyLayer.GROUND
        assert "Frightened" not in traveler.active_conditions
        assert traveler.action_economy.movement.normalized_score == {"walk": 20, "jump": 15, "misty-step": 25}[entry]
        if entry == "misty-step":
            assert traveler.action_economy.bonus_actions.normalized_score == 0
            assert traveler.action_economy.spell_slot_2.normalized_score == 0
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items() if role != "donor"))
        primary = captured.views["traveler"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
