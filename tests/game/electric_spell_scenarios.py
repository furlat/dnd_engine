"""Actual directed electric spell outcomes recorded through ordinary encounter actions."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import LightningBolt, ChainLightning
from dnd.spells.abjuration import AntimagicField
from dnd.spells.divination import SeeInvisibilityEffect
from dnd.conditions import Invisible
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.manual.spell_regression_support import force_save_result

ElectricProgram = Literal['lightning_bolt', 'chain_lightning']


def electric_spell_history(*, program: ElectricProgram, empty: bool = False, hidden_branch: bool = False, blocked_branch: bool = False) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = 'battlefield.visibility_open_range'
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        positions = [('caster', (3, 6)), ('recipient', (8, 6) if not empty else (8, 4))]
        if not empty:
            positions.extend((('second', (10, 6) if program == 'lightning_bolt' else (11, 5)),
                              ('third', (14, 6) if program == 'lightning_bolt' else (10, 3))))
        if blocked_branch:
            assert program == 'chain_lightning' and not empty
            positions.append(('field', (12, 6)))
        spell = {'lightning_bolt': LightningBolt, 'chain_lightning': ChainLightning}[program]
        for role, position in positions:
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction='heroes' if role == 'caster' else 'enemies',
                appearance=AppearanceConfig(body_category='NakedBody', has_beard=False),
                action_economy=ActionEconomyConfig(spell_slots={3: 2, 6: 2}),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode='maximums')])))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage', actor.uuid), BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red', actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            if role == 'caster':
                register_spell(actor, spell, caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
            force_save_result(actor, 'dexterity', succeeds=(role == 'second'))
        caster, target = actors['caster'], actors['recipient']
        if hidden_branch:
            assert program == 'chain_lightning' and not empty
            hidden = actors['second']
            hidden.add_condition(Invisible(source_entity_uuid=hidden.uuid, target_entity_uuid=hidden.uuid))
            caster.add_condition(SeeInvisibilityEffect(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
            Entity.update_all_entities_senses()
        if blocked_branch:
            field = AntimagicField(source_entity_uuid=actors['field'].uuid, alt_skip_slot=True).apply()
            assert field is not None and not field.canceled
        encounter = Encounter(name='Directed electric spells', source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10] * len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name='Electric initialization', start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        template = caster.get_action_template(spell.model_fields['name'].default)
        assert template is not None
        selection = ({'end_position': (23, 6)} if program == 'lightning_bolt' else
            {'target_entity_uuid': target.uuid, 'extra_target_entity_uuids': [actors[role].uuid for role in ('second', 'third')]})
        with fixed_dice_faces(*([3] * 100)):
            result = template.instantiate(**selection).apply()
        assert result is not None and not result.canceled, result
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views['caster']
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
