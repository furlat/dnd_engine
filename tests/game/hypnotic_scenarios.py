"""Real Hypnotic casts: square-edge coverage, mixed saves and independent recovery."""

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
from dnd.core.dice import fixed_dice_faces
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_BY_NAME
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def hypnotic_history(*, mode: str = 'clear') -> CapturedHistory:
    assert mode in ('clear', 'damage_one', 'recast')
    positions = (("caster", (3,7)), ("recipient", (9,7)),
                 ("second", (6,4)), ("saved", (10,8)), ("bystander", (14,7)))
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        for role, position in positions:
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction="heroes" if role == "caster" else "monsters",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    wisdom=AbilityConfig(ability_score=30 if role == "saved" else 1)),
                action_economy=ActionEconomyConfig(spell_slots={3: 3}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10,
                    hit_dice_count=12, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22")))
            actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, SPELL_CONTENT_IDENTITY_BY_NAME['Hypnotic Pattern'].spell_type, caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["recipient"]
        encounter = Encounter(name="Hypnotic actual square, target recovery and slot clear", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10, 10, 10, 10):
            encounter.start_encounter()
        encounter.start_turn()

        def perform(actor: Entity, behavior: str, destination: tuple[int, int]) -> None:
            while encounter.get_current_entity() is not actor:
                with fixed_dice_faces(*([1] * 40)):
                    encounter.next_turn()
            choices = [(action, selection) for action in get_available_actions(actor).all_actions
                if action.behavior_id == behavior for selection in action.valid_targets
                if selection.position == destination]
            assert choices, (behavior, destination)
            with fixed_dice_faces(*([10] * 40)):
                result = execute_available_action(actor, *choices[0])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION

        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Fear initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        perform(caster, 'spell.hypnotic_pattern', (9,7))
        assert {'Hypnotic Pattern', 'Charmed'} <= set(recipient.active_conditions)
        assert 'Hypnotic Pattern' in actors['second'].active_conditions
        assert 'Hypnotic Pattern' not in actors['saved'].active_conditions
        assert 'Hypnotic Pattern' not in actors['bystander'].active_conditions
        if mode == 'damage_one':
            recipient.receive_damage(1, DamageType.FORCE, source_entity_uuid=caster.uuid)
            assert 'Hypnotic Pattern' not in recipient.active_conditions
            assert 'Hypnotic Pattern' in actors['second'].active_conditions
            assert 'Concentrating' in caster.active_conditions
        perform(caster, 'action.move', (3,8))
        if mode == 'recast':
            with fixed_dice_faces(*([1] * 40)):
                encounter.next_turn()
            perform(caster, 'spell.hypnotic_pattern', (10,7))
            perform(caster, 'action.move', (3,7))
        caster.remove_condition('Concentrating')
        assert 'Hypnotic Pattern' not in recipient.active_conditions
        assert 'Hypnotic Pattern' not in actors['second'].active_conditions
        perform(recipient, 'action.move', (8,7))
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "recipient")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
