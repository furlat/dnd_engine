"""Accepted weather and solar media driven by native encounter histories."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.conditions import Invisible
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import SleetStorm
from dnd.spells.abjuration import register_counterspell_reaction
from dnd.spells.evocation import IceStorm, Sunbeam, Sunburst
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.manual.spell_regression_support import force_save_result

WeatherSolarProgram = Literal['ice_storm', 'sleet_storm', 'sunbeam', 'sunburst']


def weather_solar_history(*, program: WeatherSolarProgram, empty: bool = False,
                          expire: bool = False, heading: int = 0, hidden: bool = False,
                          countered: bool = False, repeat: bool = False) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = 'battlefield.open_floor_bright' if program == 'ice_storm' else 'battlefield.weather_review'
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        direction = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))[heading]
        center = (7, 7) if program == 'ice_storm' else (14, 14)
        source = center if program == 'sunbeam' else (1, 7) if program == 'ice_storm' else (4, 14)
        destination = (center[0] + direction[0]*4, center[1] + direction[1]*4) if program == 'sunbeam' else center
        positions = [('caster', source)]
        if not empty:
            positions += [('recipient', destination), ('second', (destination[0], destination[1]+2))]
        spell = {'ice_storm': IceStorm, 'sleet_storm': SleetStorm, 'sunbeam': Sunbeam, 'sunburst': Sunburst}[program]
        for role, position in positions:
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction='heroes' if role == 'caster' else 'enemies',
                appearance=AppearanceConfig(body_category='NakedBody', has_beard=False),
                action_economy=ActionEconomyConfig(spell_slots={3: 2, 4: 2, 6: 2, 8: 2}),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode='maximums')])))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage', actor.uuid), BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red', actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            if role == 'caster':
                register_spell(actor, spell, caster_level=17)
            elif role == 'recipient' and countered:
                register_counterspell_reaction(actor)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
            for ability in ('dexterity', 'constitution'):
                force_save_result(actor, ability, succeeds=role == 'second')
        caster = actors['caster']
        encounter = Encounter(name='Weather and solar', source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10]*len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        if hidden and not empty:
            recipient = actors['recipient']
            recipient.add_condition(Invisible(source_entity_uuid=recipient.uuid, target_entity_uuid=recipient.uuid))
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name='Weather initialization', start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        template = caster.get_action_template(spell.model_fields['name'].default)
        assert template is not None
        with fixed_dice_faces(*([20 if countered else 3]*300)):
            result = template.instantiate(end_position=destination).apply()
        assert result is not None and result.canceled == countered, result
        if repeat and not countered:
            assert program == 'sunbeam'
            while encounter.get_current_entity() is not caster or caster.action_economy.actions.normalized_score == 0:
                encounter.next_turn()
            activated = caster.get_action_template('Sunbeam Strike')
            assert activated is not None
            repeat_direction = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))[(heading+2)%8]
            endpoint = (center[0]+repeat_direction[0]*4, center[1]+repeat_direction[1]*4)
            with fixed_dice_faces(*([3]*300)):
                result = activated.instantiate(end_position=endpoint).apply()
            assert result is not None and not result.canceled, result
        if expire and not countered:
            if program == 'ice_storm':
                while encounter.get_current_entity() is not caster or caster.action_economy.actions.normalized_score == 0:
                    encounter.next_turn()
                encounter.next_turn()
                assert not any(zone.name == 'Ice Storm Terrain' for zone in get_map().get_spatial_conditions())
            elif program in ('sleet_storm', 'sunbeam'):
                caster.remove_condition('Concentrating')
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views['caster']
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
