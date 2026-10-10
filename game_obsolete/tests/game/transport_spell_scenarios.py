"""Recorded ordinary spell transfers, absence and actual returns."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.conditions import Blinded, Deafened
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import Banishment
from dnd.spells.conjuration import DimensionDoor
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history
from tests.manual.spell_regression_support import force_save_result

TransportProgram = Literal['door', 'door_passenger', 'door_mishap', 'banish_return', 'banish_saved',
                           'banish_foreign_return', 'banish_permanent', 'banish_pending', 'banish_hidden_return']


def transport_spell_history(*, program: TransportProgram) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = 'battlefield.open_floor_bright'
    build_battlefield(battlefield)
    game = Game()
    try:
        is_door = program.startswith('door')
        actors = {}
        placements = [('caster', (3, 5)), ('recipient', (4, 5) if is_door else (7, 5))]
        if program == 'banish_pending':
            placements.append(('blocker', (3, 6)))
        for role, position in placements:
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction='heroes' if is_door or role == 'caster' else 'enemies',
                action_economy=ActionEconomyConfig(spell_slots={4: 1}),
                health=HealthConfig(max_hit_points_bonus=60),
                appearance=AppearanceConfig(body_category='NakedBody', has_beard=False)))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage', actor.uuid), BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red', actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors['caster'], actors['recipient']
        if program in ('banish_foreign_return', 'banish_permanent'):
            recipient.native_plane_id = 'abyss'
        spell = DimensionDoor if is_door else Banishment
        register_spell(caster, spell, caster_level=11)
        force_save_result(recipient, 'charisma', succeeds=program == 'banish_saved')
        if program == 'door_mishap':
            get_map().set_tile(9, 7, walking_cost=0)
        encounter = Encounter(name='Transport spell', source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10]*len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name='Transport initialization', start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        template = caster.get_action_template(spell.model_fields['name'].default)
        assert template is not None
        selection = ({'target_entity_uuid': recipient.uuid if program != 'door' else caster.uuid,
                      'end_position': (9, 7)} if is_door else {'target_entity_uuid': recipient.uuid})
        with fixed_dice_faces(*([3]*80)):
            result = template.instantiate(**selection).apply()
        assert result is not None and not result.canceled, result
        if program in ('banish_return', 'banish_foreign_return'):
            encounter.next_turn()
            caster.remove_condition('Concentrating')
        elif program == 'banish_hidden_return':
            caster.add_condition(Blinded(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
            caster.add_condition(Deafened(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
            caster.remove_condition('Concentrating')
            assert recipient.is_deployed
            assert not caster.senses.entities.get(recipient.uuid)
            caster.remove_condition('Blinded')
            caster.remove_condition('Deafened')
        elif program == 'banish_permanent':
            for _ in range(10):
                recipient.on_turn_start()
        elif program == 'banish_pending':
            for point in get_map().get_all_tiles():
                if point not in (caster.position, actors['blocker'].position):
                    get_map().set_tile(*point, walking_cost=0)
            caster.remove_condition('Concentrating')
            assert recipient.pending_spatial_return is not None
            encounter.next_turn()
            actors['blocker'].suspend_spatial_presence()
            assert recipient.is_deployed
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views['caster']
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
