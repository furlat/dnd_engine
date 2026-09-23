"""Native Web cast, saves, escape, movement and concentration cleanup."""

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
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_spell_device
from dnd.controller import HumanController
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.core.dice import fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import Web, WebZone
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


WebDelivery = Literal["mage", "cannon"]


def web_history(*, delivery: WebDelivery = "mage") -> CapturedHistory:
    """Record both witnesses; author actors and dice, never after-state.

    The low-Dexterity target fails the cast's save and uses a real action to
    escape. The agile second target saves, then walks out through the difficult
    terrain. The mage ends concentration with the ordinary available action.
    The cannon sustains two separate casts until a real object attack destroys
    it, ending both zones and the restraint created by its second shot.
    """
    if delivery not in ("mage", "cannon"):
        raise ValueError(f"Web delivery is not authored: {delivery}")
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        actors: dict[str, Entity] = {}
        for role, position in (("caster", (3, 5)), ("target", (10, 5)), ("second", (8, 5))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "caster" else "enemies",
                ability_scores=AbilityScoresConfig(
                    intelligence=AbilityConfig(ability_score=18),
                    strength=AbilityConfig(ability_score=18),
                    dexterity=AbilityConfig(ability_score=8 if role == "target" else 20 if role == "second" else 10),
                ),
                action_economy=ActionEconomyConfig(spell_slots={2: 1}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, Web, caster_level=3)
                if delivery == "cannon":
                    actor.install_initial_items(((build_authored_item("weapon.longsword", actor.uuid), WeaponSlot.MELEE_MAIN),))
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, target, second = (actors[role] for role in ("caster", "target", "second"))
        device = None
        if delivery == "cannon":
            device = build_spell_device(item_id="environment.arcane_machine_gun", name="Web Cannon",
                source_entity_uuid=caster.uuid, charges=2, hit_points=8, concentration_capacity=2,
                spell_templates=[Web(source_entity_uuid=caster.uuid, template=True,
                    cast_origin="source_item", target_sector_degrees=45)])
            device.place_on_grid((4, 5))
        encounter = Encounter(name="Web saves and escape", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Web initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)

        def perform(actor: Entity, identity: str, *, position: tuple[int, int] | None = None,
                    dice: tuple[int, ...] = ()) -> Event:
            available = get_available_actions(actor)
            choices = [(row, choice) for row in available.all_actions
                if row.behavior_id == identity or row.display_name == identity
                if identity != "spell.web" or row.source_item_uuid == (device.uuid if device is not None else None)
                for choice in row.valid_targets if position is None or choice.position == position]
            if not choices:
                raise ValueError(f"{actor.name} has no available {identity} toward {position}")
            row, choice = choices[0]
            with fixed_dice_faces(*dice):
                result = execute_available_action(actor, row, choice)
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION
            return result

        def advance_to(actor: Entity) -> None:
            with fixed_dice_faces(*([10] * 8)):
                encounter.next_turn()
                while encounter.get_current_entity() is not actor:
                    encounter.next_turn()

        hp_before = tuple(actor.get_hp() for actor in actors.values())
        spell = perform(caster, "spell.web", position=(9, 5), dice=(10, 10))
        assert isinstance(spell, SpellEvent) and spell.aoe_position == (9, 5)
        zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WebZone))
        assert target.position in zone.affected_positions and second.position in zone.affected_positions
        assert "Restrained" in target.active_conditions and "Restrained" not in second.active_conditions
        assert caster.action_economy.actions.normalized_score == 0
        assert caster.action_economy.spell_slot_2.normalized_score == (1 if device is not None else 0)
        assert ("Concentrating" in caster.active_conditions) == (device is None)
        advance_to(target)
        assert "Restrained" in target.active_conditions
        perform(target, "Escape Web", dice=(15,))
        assert "Restrained" not in target.active_conditions and target.action_economy.actions.normalized_score == 0
        assert (11, 5) not in zone.affected_positions
        perform(target, "action.move", position=(11, 5))
        advance_to(second)
        assert "Restrained" not in second.active_conditions
        perform(second, "action.move", position=(8, 7), dice=(10, 10))
        assert second.position == (8, 7) and second.position not in zone.affected_positions
        assert "Restrained" not in second.active_conditions
        advance_to(caster)
        assert get_map().get_spatial_condition(zone.uuid) is not None
        if device is None:
            perform(caster, "action.drop_concentration")
        else:
            perform(caster, "spell.web", position=(13, 5), dice=(10,))
            assert "Restrained" in target.active_conditions
            assert len(device.to_item_presentation_state().concentration_slots) == 2
            assert get_map().get_spatial_condition(zone.uuid) is not None
            assert device.charges == 0 and "Concentrating" not in caster.active_conditions
            advance_to(caster)
            perform(caster, "action.attack_object", dice=(8,))
            assert get_map().get_object_position(device.uuid) == device.get_position()
            assert device.get_position() is not None and device.integrity is ItemIntegrity.DESTROYED
            assert not device.to_item_presentation_state().concentration_slots
        assert "Concentrating" not in caster.active_conditions
        assert get_map().get_spatial_condition(zone.uuid) is None
        assert not any(isinstance(effect, WebZone) for effect in get_map().get_spatial_conditions())
        assert "Restrained" not in target.active_conditions
        assert all(zone.uuid not in actor.senses.spatial_effects for actor in actors.values())
        assert tuple(actor.get_hp() for actor in actors.values()) == hp_before
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "target")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
