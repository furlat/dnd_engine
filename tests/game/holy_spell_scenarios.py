"""Holy presentation records made by actual cast, movement and item-use commands."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import SpiritGuardians, GuardianOfFaith, HeroesFeast, HeroesFeastObject
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.manual.spell_regression_support import force_save_result

HolyProgram = Literal['spirit_radiant','spirit_necrotic','guardian','feast']


def holy_spell_history(*, program: HolyProgram, immune: bool = False, expire: bool = False) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = 'battlefield.open_floor_bright'
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        positions = [('caster',(4,6)),('recipient',(5,6) if program == 'feast' else (9,6)),('observer',(3,8))]
        spell = {'spirit_radiant':SpiritGuardians,'spirit_necrotic':SpiritGuardians,
            'guardian':GuardianOfFaith,'feast':HeroesFeast}[program]
        for role,position in positions:
            actor = Entity.create(uuid4(),role.title(),config=EntityConfig(position=position,
                faction='foes' if role == 'recipient' and program != 'feast' else 'heroes',
                appearance=AppearanceConfig(body_category='NakedBody',has_beard=False),
                action_economy=ActionEconomyConfig(spell_slots={3:2,4:2,6:2}),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10,hit_dice_count=20,mode='maximums')])))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage',actor.uuid),BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red',actor.uuid),BodyPart.FEET)))
            setup_standard_actions(actor)
            if role == 'caster':
                register_spell(actor,spell,caster_level=17)
            actor.compose_entity();game.deploy_entity(actor,position);actors[role]=actor
            for ability in ('wisdom','dexterity'):
                force_save_result(actor,ability,succeeds=False)
            if role == 'recipient' and immune:
                actor.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
                    name='Native radiant immunity',value=ResistanceStatus.IMMUNITY,damage_type=DamageType.RADIANT,
                    source_entity_uuid=actor.uuid,target_entity_uuid=actor.uuid))
        caster,target = actors['caster'],actors['recipient']
        encounter=Encounter(name='Holy spells',source_entity_uuid=caster.uuid)
        for actor in actors.values():encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10,10,10):encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:encounter.next_turn()
        baseline=EventQueue.event_cursor()
        initial=capture_interval(name='Holy initialization',start_cursor=0,end_cursor=baseline,
            observer_uuid=caster.uuid,battlefield_id=battlefield)
        before,_=reduce_interval(None,initial)

        def move(actor: Entity, end: tuple[int,int], path: list[tuple[int,int]]) -> None:
            actor.action_economy.reset_all_costs()
            template=actor.get_action_template('Move');assert template is not None
            result=template.instantiate(end_position=end,path=path).apply()
            assert result is not None and not result.canceled,result

        template = caster.get_action_template(spell.model_fields['name'].default)
        assert template is not None
        with fixed_dice_faces(*([3]*150)):
            if program.startswith('spirit_'):
                result=template.instantiate(
                    damage_type=DamageType.RADIANT if program == 'spirit_radiant' else DamageType.NECROTIC,
                    excluded_entity_uuids=frozenset({actors['observer'].uuid})).apply()
                assert result is not None and not result.canceled,result
                move(caster,(6,6),[(4,6),(5,6),(6,6)])
                target.on_turn_start(round_number=1)
                move(target,(9,7),[(9,6),(9,7)])
                caster.remove_condition('Concentrating')
            elif program == 'guardian':
                result=template.instantiate(end_position=(6,6)).apply()
                assert result is not None and not result.canceled,result
                for end in ((8,6),(8,7),(8,6)):
                    # The native first-per-turn admission reads the encounter's
                    # turn identity, not a manually invoked actor callback.
                    encounter.next_turn()
                    while encounter.get_current_entity() is not target:
                        encounter.next_turn()
                    move(target,end,[target.position,end])
            else:
                result=template.instantiate(end_position=(5,7)).apply()
                assert result is not None and not result.canceled,result
                feast=next(obj for identity in get_map().get_objects_at((5,7))
                    if isinstance(obj:=HeroesFeastObject.get(identity),HeroesFeastObject))
                result=feast.get_use_actions(target.uuid)[0].apply()
                assert result is not None and not result.canceled,result
                move(target,(6,6),[(5,6),(6,6)])
                if expire:
                    for round_number in range(1,11):target.on_turn_start(round_number=round_number)
                    feast.retire()
        captured=capture_history(before,(),observers=tuple(ObserverCapture(role,actor.uuid,baseline) for role,actor in actors.items()))
        primary=captured.views['caster']
        return CapturedHistory(primary.initialization,before,primary.lineages,captured.views)
    finally:
        game.close();reset_engine_runtime();random.setstate(previous_random)
