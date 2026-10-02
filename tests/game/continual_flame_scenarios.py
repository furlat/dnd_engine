"""Native permanent light anchors, independent retirement and paired replay."""

import random
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.base_block import BaseBlock
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import ContinualFlame, ContinualFlameObject
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def continual_flame_history() -> CapturedHistory:
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        for role, position in (("caster", (3, 6)), ("recipient", (5, 6))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction="heroes",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={2: 3}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10,
                    hit_dice_count=12, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22")))
            actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, ContinualFlame, caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["recipient"]
        encounter = Encounter(name="Permanent native light anchors", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()

        def perform(actor: Entity, behavior: str, destination: tuple[int, int]) -> None:
            while encounter.get_current_entity() is not actor:
                with fixed_dice_faces(*([4] * 30)):
                    encounter.next_turn()
            choices = [(action, selection) for action in get_available_actions(actor).all_actions
                if action.behavior_id == behavior for selection in action.valid_targets
                if selection.position == destination]
            assert choices, (behavior, destination)
            with fixed_dice_faces(*([4] * 30)):
                result = execute_available_action(actor, *choices[0])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION

        initial_hp = {role: actor.get_normal_hp() for role, actor in actors.items()}
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Permanent light initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        perform(caster, "spell.continual_flame", (4, 6))
        perform(recipient, "action.move", (5, 7))
        perform(caster, "spell.continual_flame", (3, 7))
        perform(recipient, "action.move", (5, 8))
        assert len(get_map().get_spatial_conditions()) == 2
        assert "Concentrating" not in caster.active_conditions
        for position in ((4, 6), (3, 7)):
            flame, = (BaseBlock.get(identity) for identity in get_map().get_objects_at(position))
            assert isinstance(flame, ContinualFlameObject)
            flame.destroy()
            assert not get_map().get_objects_at(position)
        assert not get_map().get_spatial_conditions()
        assert {role: actor.get_normal_hp() for role, actor in actors.items()} == initial_hp
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
