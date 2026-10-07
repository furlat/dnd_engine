"""Canonical caster kits issuing real spell and reaction actions for review."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.base_actions import TargetType
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.content.recipes import ContentRecipe
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import Fireball
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history


def creature_spell_history(identity: str, *, spell: Literal["web", "fire_bolt"]) -> CapturedHistory:
    """Use the creature's existing spell/reaction kit, never a replacement rig."""
    previous = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        declaration = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry.declarations[identity]
        caster = materialize_creature(ContentRecipe.create(ref=declaration.ref, parameters={}),
            runtime_entity_uuid=uuid4(), display_name=declaration.descriptor.display_name,
            position=(3, 6), faction="monsters",
            deployment_role=CreatureDeploymentRole(role_id="review.creature_spell"),
            possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS)
        opponent = Entity.create(uuid4(), "Spell opponent", config=EntityConfig(
            position=(8, 6), faction="heroes", action_economy=ActionEconomyConfig(spell_slots={3: 1}),
            spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
            appearance=AppearanceConfig(body_category="NakedBody", head_category="Head22", has_beard=False),
            health=HealthConfig(max_hit_points_bonus=200)))
        opponent.install_initial_items((
            (build_authored_item("weapon.shortbow", opponent.uuid), WeaponSlot.RANGED_MAIN),
            (build_authored_item("apparel.robes.red_mage", opponent.uuid), BodyPart.BODY)))
        setup_standard_actions(opponent)
        install_body_response(opponent, BLOOD_BODY_RESPONSE)
        register_spell(opponent, Fireball, caster_level=5)
        actors = {"caster": caster, "opponent": opponent}
        for actor in actors.values():
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Canonical caster actions", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()

        def turn(actor: Entity, *, fresh: bool = False) -> None:
            if fresh:
                encounter.next_turn()
            for _ in range(4):
                if encounter.get_current_entity() is actor:
                    return
                encounter.next_turn()
            raise AssertionError(f"Native turn unavailable for {actor.name}")

        def perform(actor: Entity, behavior: str, target: Entity, *, level: int | None = None):
            choices = [(action, choice) for action in get_available_actions(actor, legal_only=True).all_actions
                if action.behavior_id == behavior and (level is None or action.cast_at_level == level)
                and (behavior != "action.attack" or action.weapon_slot == WeaponSlot.RANGED_MAIN.value)
                for choice in action.valid_targets
                if choice.target_uuid == target.uuid or choice.position == target.position
                or action.target_type is TargetType.SELF and target is actor]
            assert choices, (actor.name, behavior)
            with fixed_dice_faces(15, *([3] * 64)):
                result = execute_available_action(actor, *choices[0])
            assert result is not None
            return result

        turn(caster)
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Before canonical creature spell", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        hp_before = opponent.get_normal_hp()
        cast = perform(caster, "spell." + spell, opponent, level=2 if spell == "web" else None)
        assert not cast.canceled
        if spell == "web":
            assert "Concentrating" in caster.active_conditions
            released = perform(caster, "action.drop_concentration", caster)
            assert not released.canceled and "Concentrating" not in caster.active_conditions
        else:
            assert opponent.get_normal_hp() < hp_before
            turn(opponent)
            attack = perform(opponent, "action.attack", caster)
            assert not attack.canceled and "Shield" in caster.active_conditions
            turn(caster)
            assert "Shield" not in caster.active_conditions
            turn(opponent)
            counter_slot = caster.action_economy.spell_slot_3.normalized_score
            reply = perform(opponent, "spell.fireball", caster, level=3)
            assert reply.canceled
            assert caster.action_economy.spell_slot_3.normalized_score == counter_slot - 1
            assert caster.action_economy.reactions.normalized_score == 0
        return capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)
