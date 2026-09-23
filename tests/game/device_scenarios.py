"""Real device grants, turn costs, aiming refusals and recipient allocations."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, execute_use_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.base_item import BaseItem
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_arcane_machine_gun, build_fireball_cannon, build_spell_device
from dnd.controller import HumanController
from dnd.core.base_actions import AvailableTarget
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.enchantment import Sleep
from dnd.spells.evocation import Fireball, FireBolt
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


DeviceProgram = Literal["mixed-spells", "sleep-area", "normal-sleep", "reposition", "break-cannon", "break-projector", "break-fireball"]


def device_history(*, program: DeviceProgram = "mixed-spells", wake_damage: int = 2) -> CapturedHistory:
    """Only setup and dice are authored; every later change is a native action."""
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        breaking = program in ("break-cannon", "break-projector", "break-fireball")
        sleeping = program not in ("reposition", "break-fireball")
        placements = {"operator": (3, 5), "target": (10, 5), "second": (10, 6)}
        if program in ("sleep-area", "normal-sleep", "break-cannon", "break-projector"):
            placements.update(target=(8, 5), second=(8, 7))
        elif program == "reposition":
            placements.update(target=(4, 11), second=(7, 11))
        actors: dict[str, Entity] = {}
        for role, position in placements.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "operator" else "enemies",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={1: 1}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(
                    hit_dice_value=10 if role == "operator" or program == "reposition" else 8,
                    hit_dice_count=20 if role == "operator" or program == "reposition" else
                    3 if program in ("mixed-spells", "break-fireball") else 1, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "operator" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            if role == "operator":
                if breaking:
                    actor.install_initial_items(((build_authored_item("weapon.longsword", actor.uuid), WeaponSlot.MELEE_MAIN),))
                register_spell(actor, FireBolt, caster_level=1)
                if program == "normal-sleep":
                    register_spell(actor, Sleep, caster_level=1)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        operator, target, second = actors["operator"], actors["target"], actors["second"]
        fireball = Fireball(source_entity_uuid=operator.uuid, template=True,
            caster_level=5, cast_at_level=3, cast_origin="source_item",
            alt_range=30 if program == "reposition" else 60, target_sector_degrees=45)
        sleep = Sleep(source_entity_uuid=operator.uuid, template=True,
            cast_at_level=1, cast_origin="source_item", target_sector_degrees=45)
        if breaking:
            # Exercise the actual body builders with independent spell grants.
            # HP is setup data; all subsequent damage is an action.
            device = (build_fireball_cannon(charges=1,
                          spell_templates=[fireball] if program == "break-fireball" else [sleep])
                      if program != "break-projector" else
                      build_arcane_machine_gun(operator.uuid, charges=1, spell_templates=[sleep]))
            device.health = device.create_item_health(device.uuid, 12)
        else:
            device = build_spell_device(
                item_id="environment.arcane_machine_gun" if program in ("sleep-area", "normal-sleep") else "environment.fireball_cannon",
                name="Sleep Projector" if program in ("sleep-area", "normal-sleep") else "Spell Cannon",
                spell_templates=[sleep] if program in ("sleep-area", "normal-sleep") else [fireball, sleep] if program == "mixed-spells" else [fireball],
                charges=2 if program == "mixed-spells" else 1,
                source_entity_uuid=operator.uuid,
            )
        if program != "normal-sleep":
            device.place_on_grid((4, 5))
        encounter = Encounter(name="Device spell grants", source_entity_uuid=operator.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not operator:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Device initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=operator.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)

        def perform(behavior: str, *, position: tuple[int, int] | None = None,
                    recipient: Entity | BaseItem | None = None, extras: tuple[Entity, ...] = (),
                    dice: tuple[int, ...] = ()) -> Event:
            available = get_available_actions(operator)
            choices = [(row, choice) for row in available.all_actions
                if row.behavior_id == behavior
                and (behavior in ("action.move", "spell.fire_bolt", "action.attack_object") or
                     row.source_item_uuid == (None if program == "normal-sleep" else device.uuid))
                for choice in row.valid_targets
                if (position is None or choice.position == position)
                and (recipient is None or choice.target_uuid == recipient.uuid)]
            if not choices:
                raise ValueError(f"No discovered device action {behavior} toward {position or (recipient.name if recipient else 'self')}")
            row, choice = choices[0]
            with fixed_dice_faces(*dice):
                result = execute_available_action(operator, row, choice,
                    extra_target_uuids=[str(actor.uuid) for actor in extras])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION
            return result

        hp = {role: actor.get_hp() for role, actor in actors.items()}
        if program == "reposition":
            available = get_available_actions(operator)
            assert not any(choice.position == target.position for row in available.all_actions
                if row.source_item_uuid == device.uuid for choice in row.valid_targets)
            template = device.get_use_actions(operator.uuid)[0]
            refused = execute_use_action(operator, device.uuid, template.get_discovery_template_name(),
                AvailableTarget(index=0, position=target.position))
            assert refused is not None and refused.canceled
            assert device.charges == 1 and operator.action_economy.actions.normalized_score == 1
            assert {role: actor.get_hp() for role, actor in actors.items()} == hp
            for destination in ((3, 4), (4, 4)):
                perform("action.move", position=destination)
            assert operator.position == (4, 4)

        if program in ("mixed-spells", "reposition", "break-fireball"):
            result = perform("spell.fireball", position=target.position, dice=(1, *([2] * 8)) * 2)
            assert isinstance(result, SpellEvent) and result.aoe_position == target.position
            assert target.get_hp() == hp["target"] - 16 and second.get_hp() == hp["second"] - 16
            assert result.resolved_area_positions is not None
            assert second.position in result.resolved_area_positions
            assert operator.get_hp() == hp["operator"]
            assert operator.action_economy.actions.normalized_score == 0
        if program == "mixed-spells":
            assert device.charges == 1
            encounter.next_turn()
            while encounter.get_current_entity() is not operator:
                encounter.next_turn()
        if sleeping:
            prior = (target.get_hp(), second.get_hp())
            # Sleep's actual native HP dice use random; seed the roll, never
            # author a condition, recipient allocation or reduced after-state.
            random.seed(0)
            result = perform("spell.sleep", position=target.position)
            assert isinstance(result, SpellEvent) and result.aoe_position == target.position
            assert (target.get_hp(), second.get_hp()) == prior
            assert "Sleep" in target.active_conditions and "Sleep" in second.active_conditions
            assert operator.action_economy.actions.normalized_score == 0
            encounter.next_turn()
            while encounter.get_current_entity() is not operator:
                encounter.next_turn()
            perform("spell.fire_bolt", recipient=target, dice=(15, wake_damage))
            assert "Sleep" not in target.active_conditions and "Sleep" in second.active_conditions
            assert target.get_hp() == prior[0] - wake_damage, (target.get_hp(), prior[0], wake_damage)
        if program != "normal-sleep":
            assert device.charges == 0 and device.get_position() == (4, 5)
        encounter.next_turn()
        while encounter.get_current_entity() is not operator:
            encounter.next_turn()
        assert operator.action_economy.actions.normalized_score == 1
        assert not any(row.source_item_uuid == device.uuid for row in get_available_actions(operator).all_actions)
        if breaking:
            perform("action.attack_object", recipient=device, dice=(4,))
            assert device.get_hp() == 8 and device.get_position() == (4, 5)
            encounter.next_turn()
            while encounter.get_current_entity() is not operator:
                encounter.next_turn()
            perform("action.attack_object", recipient=device, dice=(8,))
            assert device.get_hp() == 0 and device.get_position() == (4, 5)
            assert device.integrity is ItemIntegrity.DESTROYED
            # Sleep is not sustained by its launcher; breaking it does not wake
            # the untouched sleeper or reapply Sleep to the creature we woke.
            if sleeping:
                assert "Sleep" not in target.active_conditions and "Sleep" in second.active_conditions
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("operator", "target")))
        primary = captured.views["operator"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
