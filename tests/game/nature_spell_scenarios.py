"""Native nature spells, movement, exact item ownership and retaliation."""
import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import ProduceFlame
from dnd.spells.evocation import FireShield
from dnd.spells.transmutation import Barkskin, Shillelagh
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history

NatureProgram = Literal['shillelagh', 'barkskin', 'warm', 'chill', 'produce_hit', 'produce_miss', 'produce_initial', 'produce_recast', 'coexist']


def nature_spell_history(*, program: NatureProgram, immune: bool = False) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = 'battlefield.open_floor_bright'
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        for role, position in (('caster', (4, 6)), ('recipient', (5, 6))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction=role, ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10,hit_dice_count=12,mode='maximums')]),
                appearance=AppearanceConfig(body_category='NakedBody',head_category='Head22',has_beard=False)))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage',actor.uuid),BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red',actor.uuid),BodyPart.FEET),
                (build_authored_item('weapon.quarterstaff' if role=='caster' else 'weapon.dagger',actor.uuid),WeaponSlot.MELEE_MAIN)))
            setup_standard_actions(actor)
            if role == "caster":
                for spell in (Shillelagh, Barkskin, FireShield, ProduceFlame):
                    register_spell(actor, spell)
            actor.compose_entity()
            game.deploy_entity(actor,position)
            actors[role]=actor
        caster, recipient = actors['caster'], actors['recipient']
        if immune:
            recipient.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
                name='Native immunity',value=ResistanceStatus.IMMUNITY,
                damage_type=DamageType.FIRE if program=='warm' else DamageType.COLD,
                source_entity_uuid=recipient.uuid,target_entity_uuid=recipient.uuid))
        encounter=Encounter(name='Nature spells',source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10,10):
            encounter.start_encounter()
        encounter.start_turn()

        def turn(actor):
            while encounter.get_current_entity() is not actor or actor.action_economy.actions.normalized_score == 0:
                with fixed_dice_faces(*([12]*25)):
                    encounter.next_turn()

        def apply(actor, name, **selection):
            template = actor.get_action_template(name)
            assert template is not None, name
            result=template.instantiate(**selection).apply()
            assert result is not None and not result.canceled,result
            return result

        baseline=EventQueue.event_cursor()
        initial=capture_interval(name='Nature initialization',start_cursor=0,end_cursor=baseline,
            observer_uuid=caster.uuid,battlefield_id=battlefield)
        before,_=reduce_interval(None,initial)
        turn(caster)
        if program == 'coexist':
            for name in ('Barkskin', 'Fire Shield', 'Shillelagh'):
                turn(caster)
                apply(caster, name, target_entity_uuid=caster.uuid, alt_skip_slot=True)
        elif program in ('warm','chill'):
            apply(caster, "Fire Shield", target_entity_uuid=caster.uuid, shield_kind=program, alt_skip_slot=True)
            turn(recipient)
            with fixed_dice_faces(19,4,4,4,4,4,4):
                apply(recipient, "Attack_" + WeaponSlot.MELEE_MAIN.value, target_entity_uuid=caster.uuid)
            turn(caster)
            apply(caster, "Dodge")
            caster.remove_condition('Fire Shield')
        elif program in ('shillelagh','barkskin'):
            spell = "Shillelagh" if program == "shillelagh" else "Barkskin"
            apply(caster, spell, target_entity_uuid=caster.uuid, alt_skip_slot=True)
            apply(caster, "Move", end_position=(4,7), path=[(4,6),(4,7)])
            turn(recipient)
            with fixed_dice_faces(19,4,4,4):
                apply(recipient, "Attack_" + WeaponSlot.MELEE_MAIN.value, target_entity_uuid=caster.uuid)
            turn(caster)
            apply(caster, "Dodge")
            if program=='shillelagh':
                caster.equipment.unequip(WeaponSlot.MELEE_MAIN)
            else:
                caster.remove_condition('Concentrating')
        else:
            # Separate actors before casting, so ranged disadvantage does not hide hit/miss intent.
            apply(caster, "Move", end_position=(2,6), path=[(4,6),(3,6),(2,6)])
            with fixed_dice_faces(*([1] if program == 'produce_miss' else [19,4,4,4])):
                apply(caster, "Produce Flame", target_entity_uuid=recipient.uuid)
            if program == 'produce_recast':
                turn(recipient)
                apply(recipient, "Dodge")
                turn(caster)
                with fixed_dice_faces(19,19,4,4,4):
                    apply(caster, "Produce Flame", target_entity_uuid=recipient.uuid)
        captured=capture_history(before,(),observers=tuple(ObserverCapture(role,a.uuid,baseline) for role,a in actors.items()))
        primary=captured.views['caster']
        return CapturedHistory(primary.initialization,before,primary.lineages,captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
