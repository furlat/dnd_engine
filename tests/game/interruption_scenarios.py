"""Real blocked casts, with unchanged actors and paired subjective recordings."""

import random
from typing import Literal
from unittest.mock import patch
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.actions import TargetType
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.base_actions import ActionEvent
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import Sanctuary, register_counterspell_reaction
from dnd.spells.conjuration import MistyStep
from dnd.spells.enchantment import HoldPerson
from dnd.spells.evocation import FireBolt, Fireball, MagicMissile, SacredFlame
from dnd.spells.illusion import Blur
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def interruption_history(*, blocker: Literal['sanctuary', 'counterspell'] = 'sanctuary',
        spell: Literal['fire_bolt', 'magic_missile', 'sacred_flame', 'hold_person', 'fireball', 'blur', 'misty_step'] = 'fire_bolt',
        blocked: bool = True) -> CapturedHistory:
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = 'battlefield.open_floor_bright'
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        for role, position in (('caster', (3, 6)), ('defender', (7, 7))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction=role,
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots=({1: 2, 2: 2, 4: 2}
                    if role == 'caster' else {1: 2, 3: 2})),
                spellcasting=SpellcastingConfig(spellcasting_ability='intelligence'),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode='maximums')]),
                appearance=AppearanceConfig(body_category='NakedBody', has_beard=False,
                    head_category='Head10' if role == 'caster' else 'Head22')))
            actor.install_initial_items((
                (build_authored_item('apparel.robes.red_mage', actor.uuid), BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red', actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            if role == 'caster':
                register_spell(actor, {'fire_bolt': FireBolt, 'magic_missile': MagicMissile,
                    'sacred_flame': SacredFlame, 'hold_person': HoldPerson, 'fireball': Fireball,
                    'blur': Blur, 'misty_step': MistyStep}[spell], caster_level=1)
            elif blocker == 'sanctuary':
                register_spell(actor, Sanctuary, caster_level=1)
            else:
                register_counterspell_reaction(actor)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, defender = actors['caster'], actors['defender']
        encounter = Encounter(name='Blocked spell attempts', source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        first_actor = defender if blocker == 'sanctuary' else caster
        while encounter.get_current_entity() is not first_actor:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name='Interruption initialization', start_cursor=0,
            end_cursor=baseline, observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)

        if blocker == 'sanctuary':
            choice = next((action, target) for action in get_available_actions(defender).all_actions
                if action.behavior_id == 'spell.sanctuary' and action.cast_at_level == 1
                for target in action.valid_targets if target.target_uuid == defender.uuid)
            result = execute_available_action(defender, *choice)
            assert result is not None and not result.canceled
            while encounter.get_current_entity() is not caster:
                encounter.next_turn()
        choice = next((action, target) for action in get_available_actions(caster).all_actions
            if action.behavior_id == 'spell.' + spell
            and (spell != 'fireball' or action.cast_at_level == 4)
            for target in action.valid_targets
            if action.target_type is TargetType.SELF
            or (target.position == (6, 6) if spell == 'misty_step'
                else target.position == defender.position if spell == 'fireball'
                else target.target_uuid == defender.uuid))
        hp = defender.get_hp()
        economy = caster.action_economy.bonus_actions if spell == 'misty_step' else caster.action_economy.actions
        actions = economy.normalized_score
        # Explicit deterministic dice, with actual handlers still resolving saves.
        d20 = (1 if blocked else 20) if blocker == 'sanctuary' else (20 if blocked else 1)
        with patch('dnd.core.dice.random.randint', side_effect=lambda low, high: d20 if high == 20 else min(high, 4)):
            result = execute_available_action(caster, *choice)
        assert isinstance(result, ActionEvent) and result.canceled == blocked
        assert result.action_economy_spent == (blocker == 'counterspell' or not blocked)
        assert economy.normalized_score == actions - int(result.action_economy_spent)
        if blocker == 'counterspell':
            assert defender.action_economy.reactions.normalized_score == 0
            assert defender.action_economy.spell_slot_3.normalized_score == 1
        if blocked:
            assert defender.get_hp() == hp
        history = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = history.views['caster']
        return CapturedHistory(primary.initialization, before, primary.lineages, history.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
