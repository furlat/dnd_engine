"""Native directed spell commands, captured before clearing the live engine."""
import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.base_item import BaseItem
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.conditions import Prone
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_BY_NAME
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.manual.spell_regression_support import force_save_result


def disintegrate_history(*, saved: bool = False, lethal: bool = True,
                         prone: bool = False, magical_weapon: bool = False) -> CapturedHistory:
    return directed_spell_history(program="Disintegrate", saved=saved, lethal=lethal,
        prone=prone, magical_weapon=magical_weapon)


def directed_spell_history(*, program: Literal["Disintegrate", "Eyebite", "Finger of Death"] = "Eyebite",
                         saved: bool = False, lethal: bool = False, prone: bool = False,
                         magical_weapon: bool = False,
                         mode: Literal["sickened", "panicked", "asleep"] = "sickened",
                         repeat: bool = False, cleanup: bool = False,
                         target_position: tuple[int,int] = (8,6),
                         target_item_id: str | None = None) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = 'battlefield.open_floor_bright'
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        positions = [('caster', (3, 6)), ('recipient', (8,8) if target_item_id else target_position)]
        if repeat:
            positions.append(('second',(6,9)))
        for role, position in positions:
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction='heroes' if role == 'caster' else 'enemies',
                appearance=AppearanceConfig(body_category='NakedBody', has_beard=False),
                action_economy=ActionEconomyConfig(spell_slots={6: 2,7: 2}),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10,
                    hit_dice_count=2 if role == 'recipient' and lethal else 20, mode='maximums')])))
            items: list[tuple[BaseItem, BodyPart | WeaponSlot]] = [(build_authored_item('apparel.robes.red_mage', actor.uuid), BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red', actor.uuid), BodyPart.FEET)]
            if role == 'recipient' and magical_weapon:
                items.append((build_authored_item('weapon.circus.longsword_plus_one', actor.uuid), WeaponSlot.MELEE_MAIN))
            actor.install_initial_items(tuple(items))
            setup_standard_actions(actor)
            if role == 'caster':
                register_spell(actor, SPELL_CONTENT_IDENTITY_BY_NAME[program].spell_type, caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
            force_save_result(actor, 'dexterity' if program=='Disintegrate' else 'constitution' if program=='Finger of Death' else 'wisdom', succeeds=saved)
        caster, target = actors['caster'], actors['recipient']
        if target_item_id is not None:
            target = build_authored_item(target_item_id,caster.uuid)
            target.place_on_grid(target_position)
            Entity.update_all_entities_senses()
        encounter = Encounter(name='Directed spell outcomes', source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10]*len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        if prone:
            fallen = actors["recipient"]
            fallen.add_condition(Prone(source_entity_uuid=fallen.uuid,target_entity_uuid=fallen.uuid))
            assert "Prone" in fallen.active_conditions
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name='Directed initialization', start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        template = caster.get_action_template(program)
        assert template is not None
        with fixed_dice_faces(*([3] * 100)):
            action = (template.instantiate(target_entity_uuid=target.uuid, effect_choice=mode)
                      if program == "Eyebite" else template.instantiate(target_entity_uuid=target.uuid))
            result = action.apply()
        assert result is not None and not result.canceled, result
        if repeat:
            encounter.next_turn()
            while encounter.get_current_entity() is not caster:
                encounter.next_turn()
            strike = caster.get_action_template("Eyebite Strike")
            assert strike is not None
            result = strike.instantiate(target_entity_uuid=actors['second'].uuid,effect_choice=mode).apply()
            assert result is not None and not result.canceled, result
        if cleanup:
            drop = caster.get_action_template("Drop Concentration")
            assert drop is not None
            result = drop.instantiate().apply()
            assert result is not None and not result.canceled, result
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views['caster']
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
