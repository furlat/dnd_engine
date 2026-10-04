"""Native moving field suppresses and restores the same visible spell owner."""

import random
from uuid import uuid4

from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig
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
from dnd.spells.abjuration import AntimagicField
from dnd.spells.transmutation import Barkskin
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def antimagic_history() -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = 'battlefield.open_floor_bright'
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        for role, position, spell in (('caster', (3, 6), AntimagicField), ('recipient', (7, 6), Barkskin)):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction='heroes', action_economy=ActionEconomyConfig(spell_slots={2: 1, 8: 1}),
                health=HealthConfig(max_hit_points_bonus=60),
                appearance=AppearanceConfig(body_category='NakedBody', has_beard=False)))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage', actor.uuid), BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red', actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            register_spell(actor, spell)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors['caster'], actors['recipient']
        encounter = Encounter(name='Moving Antimagic', source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()

        def turn(actor):
            while encounter.get_current_entity() is not actor or actor.action_economy.actions.normalized_score == 0:
                encounter.next_turn()

        def apply(actor, name, **selection):
            template = actor.get_action_template(name)
            assert template is not None, name
            result = template.instantiate(**selection).apply()
            assert result is not None and not result.canceled, name

        baseline = EventQueue.event_cursor()
        initial = capture_interval(name='Antimagic initialization', start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        turn(recipient)
        apply(recipient, 'Barkskin', target_entity_uuid=recipient.uuid)
        turn(caster)
        apply(caster, 'Antimagic Field')
        apply(caster, 'Move', end_position=(5, 6), path=[(3, 6), (4, 6), (5, 6)])
        turn(recipient)
        apply(recipient, 'Dodge')
        turn(caster)
        apply(caster, 'Move', end_position=(3, 6), path=[(5, 6), (4, 6), (3, 6)])
        apply(caster, 'Dodge')
        caster.remove_condition('Concentrating')
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views['caster']
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
