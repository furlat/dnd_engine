"""Native Fly grant, supported travel and concentration release review cases."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.window_builders import place_window
from dnd.content.items.window_definitions import WINDOW_DEFINITIONS
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.content.recipes import ContentRecipe
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment import DirectionalWall
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.transmutation import Fly
from dnd.types.world import CardinalDirection, MovementMode
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history


def fly_lifetime_history(*, recipient: Literal["modular-backpack", "huntsman", "wolf"],
                         geometry: bool = False) -> CapturedHistory:
    """Record real public Fly ownership without replacing a summon concentration."""
    previous = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        origin = (5, 4) if geometry else (5, 6)
        caster_position = (4, 4) if geometry else (4, 6)
        destination = (5, 8) if geometry else (8, 6)
        if geometry:
            family = "environment.window.fantasy_g7"
            assembly = place_window(family, (5, 6), CardinalDirection.EAST)
            for y in (5, 7):
                DirectionalWall(source_entity_uuid=assembly.wall.uuid,
                    item_id="environment.wall.fantasy_g1", name="Matching solid wall",
                    material=WINDOW_DEFINITIONS[family].wall_material,
                    include_in_senses_objects=True).place_on_grid((5, y), boundary_direction=CardinalDirection.EAST)
        caster = Entity.create(uuid4(), "Fly caster", config=EntityConfig(
            position=caster_position, faction="heroes", action_economy=ActionEconomyConfig(spell_slots={3: 1}),
            spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
            appearance=AppearanceConfig(body_category="NakedBody", head_category="Head10", has_beard=False),
            health=HealthConfig(max_hit_points_bonus=80)))
        caster.install_initial_items(((build_authored_item("apparel.robes.red_mage", caster.uuid), BodyPart.BODY),))
        setup_standard_actions(caster)
        register_spell(caster, Fly, caster_level=7)
        if recipient == "modular-backpack":
            target = Entity.create(uuid4(), "Backpack wearer", config=EntityConfig(
                position=origin, faction="heroes",
                appearance=AppearanceConfig(body_category="NakedBody", head_category="Head22", has_beard=False),
                health=HealthConfig(max_hit_points_bonus=80)))
            target.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", target.uuid), BodyPart.BODY),
                (build_authored_item("gear.quiver", target.uuid), BodyPart.BACKPACK)))
            setup_standard_actions(target)
        else:
            identity = ("content.neurodragon:creature:creature.huntsman_wing_devil@1" if recipient == "huntsman"
                        else "content.srd_5_1_cc:creature:creature.wolf@1")
            declaration = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry.declarations[identity]
            target = materialize_creature(ContentRecipe.create(ref=declaration.ref, parameters={}),
                runtime_entity_uuid=uuid4(), display_name=declaration.descriptor.display_name,
                position=origin, faction="heroes",
                deployment_role=CreatureDeploymentRole(role_id="review.fly_recipient"),
                possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS)
        actors = {"caster": caster, "recipient": target}
        if geometry:
            neighbor = Entity.create(uuid4(), "Adjacent witness", config=EntityConfig(
                position=(4, 6), faction="heroes",
                appearance=AppearanceConfig(body_category="NakedBody", head_category="Head10", has_beard=False),
                health=HealthConfig(max_hit_points_bonus=80)))
            setup_standard_actions(neighbor)
            actors["neighbor"] = neighbor
        for actor in actors.values():
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Fly lifetime", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10, 10):
            encounter.start_encounter()
        encounter.start_turn()

        def turn(actor: Entity) -> None:
            for _ in range(4):
                if encounter.get_current_entity() is actor:
                    return
                encounter.next_turn()
            raise AssertionError(f"Native turn unavailable for {actor.name}")

        turn(caster)
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Before Fly grant", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        original_speed = target.action_economy.current_speed(MovementMode.FLYING)
        original_gear = tuple(item.uuid for item in target.equipment.get_all_equipped_items())
        choices = [(action, choice) for action in get_available_actions(caster, legal_only=True).all_actions
            if action.behavior_id == "spell.fly" for choice in action.valid_targets if choice.target_uuid == target.uuid]
        assert len(choices) == 1
        cast = execute_available_action(caster, *choices[0])
        assert cast is not None and not cast.canceled and cast.phase is EventPhase.COMPLETION
        assert "Fly" in target.active_conditions
        assert target.action_economy.current_speed(MovementMode.FLYING) >= 60
        turn(target)
        choices = [(action, choice) for action in get_available_actions(target, legal_only=True).all_actions
            if action.template_name == "Flying Movement" for choice in action.valid_targets if choice.position == destination]
        assert len(choices) == 1
        moved = execute_available_action(target, *choices[0])
        assert moved is not None and not moved.canceled and target.position == destination
        turn(caster)
        choices = [(action, choice) for action in get_available_actions(caster, legal_only=True).all_actions
            if action.behavior_id == "action.drop_concentration" for choice in action.valid_targets]
        assert len(choices) == 1
        released = execute_available_action(caster, *choices[0])
        assert released is not None and not released.canceled and "Fly" not in target.active_conditions
        assert target.action_economy.current_speed(MovementMode.FLYING) == original_speed
        assert tuple(item.uuid for item in target.equipment.get_all_equipped_items()) == original_gear
        return capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)
