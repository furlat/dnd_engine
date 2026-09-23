"""Player commands for the fourteen maintained spell presentations."""

import random
from contextlib import nullcontext
from typing import Literal
from uuid import uuid4
from unittest.mock import patch

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.controller import HumanController
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.core.modifiers import NumericalModifier
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import MageArmor, ProtectionFromEnergy, Sanctuary, register_shield_reaction
from dnd.spells.conjuration import AcidSplash, Cloudkill, Darkness, FogCloud, Grease, IncendiaryCloud, InsectPlague, StinkingCloud
from dnd.spells.evocation import FireBolt, MagicMissile, RayOfFrost, Shatter, ShockingGrasp
from dnd.spells.illusion import Blur, MirrorImage
from dnd.spells.transmutation import EnlargeReduce, SpikeGrowth
from dnd.types.world import CardinalDirection
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


PersistentProgram = Literal['mage_armor', 'shield', 'grease', 'spike_growth', 'fog_cloud', 'cloudkill',
    'stinking_cloud', 'darkness', 'incendiary_cloud', 'insect_plague', 'blur', 'mirror_image',
    'enlarge_reduce', 'protection_from_energy', 'sanctuary']
SPELLS = {'mage_armor': MageArmor, 'grease': Grease, 'spike_growth': SpikeGrowth, 'fog_cloud': FogCloud,
    'cloudkill': Cloudkill, 'stinking_cloud': StinkingCloud, 'darkness': Darkness,
    'incendiary_cloud': IncendiaryCloud, 'insect_plague': InsectPlague, 'blur': Blur, 'mirror_image': MirrorImage,
    'sanctuary': Sanctuary}
AREAS = {'grease', 'spike_growth', 'fog_cloud', 'cloudkill', 'stinking_cloud', 'darkness', 'incendiary_cloud', 'insect_plague'}
ENERGY_ATTACKS = {'Acid': (AcidSplash, 'spell.acid_splash', (1, 4, 20)),
    'Cold': (RayOfFrost, 'spell.ray_of_frost', (15, 4, 20)),
    'Fire': (FireBolt, 'spell.fire_bolt', (15, 4, 20)),
    'Lightning': (ShockingGrasp, 'spell.shocking_grasp', (15, 4, 20)),
    'Thunder': (Shatter, 'spell.shatter', (20, 4, 4, 4, 20))}


def persistent_spell_history(*, program: PersistentProgram, mode: Literal['enlarge', 'reduce'] = 'enlarge',
        energy: Literal['Acid', 'Cold', 'Fire', 'Lightning', 'Thunder'] = 'Fire',
        saved: bool = True, jump: bool = False,
        shield_delivery: Literal['melee', 'ranged', 'missile'] = 'melee',
        environment: Literal['flat', 'raised', 'wall'] = 'flat', jump_across: bool = False,
        discovered: bool = True, cast_level: int | None = None,
        ward_expiry: bool = False, ward_retained: bool = False) -> CapturedHistory:
    """Keep the same actors; cast, exercise the condition, then end real ownership."""
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = 'battlefield.open_floor_bright'
    build_battlefield(battlefield)
    if environment == 'raised':
        for x in range(2, 15):
            for y in range(4, 14):
                assert get_map().set_tile_elevation((x, y), height=2,
                    surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    elif environment == 'wall':
        for y in range(6, 12):
            build_directional_wall().place_on_grid((11, y), boundary_direction=CardinalDirection.EAST)
    game = Game()
    try:
        positions = {'caster': (3, 6), 'target': (4, 6)}
        if program in AREAS:
            positions['target'] = (5, 8) if program != 'grease' else (5, 6)
            if jump_across:
                positions['target'] = (5, 6) if program == 'grease' else (9, 12)
        if program == 'shield' and shield_delivery != 'melee':
            positions['target'] = (6, 7)
        actors = {}
        for role, position in positions.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction='heroes' if role == 'caster' else 'enemies',
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    strength=AbilityConfig(ability_score=20 if jump_across else 10),
                    dexterity=AbilityConfig(ability_score=14), constitution=AbilityConfig(ability_score=14)),
                action_economy=ActionEconomyConfig(actions=4 if program == 'shield' and role == 'target' else 1,
                    spell_slots={level: 8 for level in range(1, 9)}),
                spellcasting=SpellcastingConfig(spellcasting_ability='intelligence'),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode='maximums')]),
                appearance=AppearanceConfig(body_category='NakedBody', has_beard=False,
                    head_category='Head10' if role == 'caster' else 'Head22')))
            actor.install_initial_items((
                (build_authored_item('weapon.shortsword', actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item('apparel.robes.red_mage', actor.uuid), BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red', actor.uuid), BodyPart.FEET)))
            if program == 'mage_armor' and role == 'caster':
                actor.install_initial_items(((build_authored_item('armor.chain_mail', actor.uuid), None),))
            if program == 'shield' and role == 'target':
                if shield_delivery == 'ranged':
                    actor.install_initial_items(((build_authored_item('weapon.shortbow', actor.uuid), WeaponSlot.RANGED_MAIN),))
            setup_standard_actions(actor)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            if program == 'shield' and role == 'target' and shield_delivery == 'missile':
                register_spell(actor, MagicMissile, caster_level=1)
            if program == 'enlarge_reduce' and role == 'target':
                register_spell(actor, FireBolt, caster_level=1)
            if program == 'protection_from_energy' and role == 'target':
                register_spell(actor, ENERGY_ATTACKS[energy][0], caster_level=1)
            if role == 'caster':
                if program == 'shield':
                    register_shield_reaction(actor)
                elif program == 'enlarge_reduce':
                    actor.register_action(EnlargeReduce(source_entity_uuid=actor.uuid, template=True,
                        caster_level=15, enlarge_mode=mode))
                elif program == 'protection_from_energy':
                    actor.register_action(ProtectionFromEnergy(source_entity_uuid=actor.uuid, template=True,
                        caster_level=15, chosen_energy_type=DamageType(energy)))
                else:
                    register_spell(actor, SPELLS[program], caster_level=15)
                register_spell(actor, FireBolt, caster_level=1)
            if program == 'spike_growth' and (discovered or role == 'caster'):
                actor.skill_set.get_skill('perception').skill_bonus.self_static.add_value_modifier(
                    NumericalModifier.create(name='Alert scout', value=20, source_entity_uuid=actor.uuid))
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, target = actors['caster'], actors['target']
        encounter = Encounter(name='Persistent spell gameplay', source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name='Persistent spell initialization', start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)

        def perform(actor: Entity, behavior: str, *, recipient: Entity | None = None,
                    position: tuple[int, int] | None = None, dice: tuple[int, ...] | None = None,
                    fresh: bool = False, canceled: bool = False) -> Event:
            def outcome(low: int, high: int) -> int:
                return (20 if saved else 1) if high == 20 else min(high, 4)
            with patch('dnd.core.dice.random.randint', side_effect=outcome):
                if fresh:
                    encounter.next_turn()
                while encounter.get_current_entity() is not actor:
                    encounter.next_turn()
            available = get_available_actions(actor)
            choices = [(action, choice) for action in available.all_actions if action.behavior_id == behavior
                and (cast_level is None or behavior != 'spell.' + program or action.cast_at_level == cast_level)
                for choice in action.valid_targets
                if (program != 'shield' or actor is caster or behavior != 'action.attack'
                    or shield_delivery != 'ranged' or action.weapon_slot == WeaponSlot.RANGED_MAIN.value)
                and (recipient is None or choice.target_uuid == recipient.uuid)
                and (position is None or choice.position == position)]
            assert choices, (program, actor.name, behavior, position,
                [(row.behavior_id, [(t.target_uuid, t.position) for t in row.valid_targets]) for row in available.all_actions])
            with patch('dnd.core.dice.random.randint', side_effect=outcome), (fixed_dice_faces(*dice) if dice is not None else nullcontext()):
                result = execute_available_action(actor, *choices[0])
            assert result is not None and result.canceled is canceled, (program, behavior, result)
            if not canceled:
                assert result.phase is EventPhase.COMPLETION, (program, behavior, result)
            return result

        if program == 'sanctuary':
            perform(caster, 'spell.sanctuary', recipient=caster)
            assert 'Sanctuary' in caster.active_conditions and 'Concentrating' not in caster.active_conditions
            perform(caster, 'action.move', position=(3, 7))
            hp = caster.get_hp()
            perform(target, 'action.attack', recipient=caster, dice=(1,), canceled=True)
            assert caster.get_hp() == hp and 'Sanctuary' in caster.active_conditions
            perform(target, 'action.attack', recipient=caster, dice=(20, 15, 4), fresh=True)
            assert caster.get_hp() < hp and 'Sanctuary' in caster.active_conditions
            if ward_expiry:
                # Let the native duration owner expire the ward through real turns.
                for _ in range(20):
                    if 'Sanctuary' not in caster.active_conditions:
                        break
                    encounter.next_turn()
                assert 'Sanctuary' not in caster.active_conditions
            elif not ward_retained:
                perform(caster, 'spell.fire_bolt', recipient=target, dice=(15, 15, 4))
                assert 'Sanctuary' not in caster.active_conditions
        elif program in AREAS:
            center = (7, 6) if program == 'grease' else (10, 8)
            perform(caster, 'spell.' + program, position=center)
            entrance = (6, 6) if program == 'grease' else (7, 8) if program == 'darkness' else (6, 8)
            tired_grease_entry = program == 'grease' and not saved and not jump and not jump_across
            if tired_grease_entry:
                # Spend real movement before entering: this fall cannot immediately
                # consume another half-speed to stand during the same turn.
                perform(target, 'action.move', position=(5, 8))
                perform(target, 'action.move', position=positions['target'])
            if jump_across:
                hp = target.get_hp()
                destination = (8, 6) if program == 'grease' else (11, 12)
                perform(target, 'action.jump', position=destination)
                assert target.position == destination and target.get_hp() == hp, (
                    program, target.position, destination, hp, target.get_hp())
                assert 'Prone' not in target.active_conditions
            else:
                perform(target, 'action.jump' if jump else 'action.move', position=entrance)
            if tired_grease_entry:
                assert 'Prone' in target.active_conditions
                assert target.action_economy.movement.normalized_score < 15
            elif 'Prone' in target.active_conditions:
                perform(target, 'action.stand_up')
            perform(target, 'action.jump' if jump_across else 'action.move', position=positions['target'], fresh=True)
            if tired_grease_entry:
                assert 'Prone' not in target.active_conditions
            perform(caster, 'action.drop_concentration')
        elif program == 'shield':
            if shield_delivery == 'missile':
                perform(target, 'spell.magic_missile', recipient=caster, dice=(3,) * 30)
                perform(target, 'spell.magic_missile', recipient=caster, dice=(3,) * 30)
            else:
                for faces in ((10,) * 30, (10,) * 30, (1,) * 30, (20, 4, 4)):
                    perform(target, 'action.attack', recipient=caster, dice=faces)
            assert 'Shield' in caster.active_conditions
            perform(caster, 'action.move', position=(3, 7))
            assert 'Shield' not in caster.active_conditions
        else:
            recipient = caster if program in ('mage_armor', 'enlarge_reduce', 'protection_from_energy') else None
            perform(caster, 'spell.' + program, recipient=recipient)
            if program == 'mirror_image':
                for index in range(3):
                    perform(target, 'action.attack', recipient=caster, dice=(1,) * 30, fresh=index > 0)
                assert 'Mirror Image' not in caster.active_conditions
            else:
                perform(caster, 'action.move', position=(3, 8))
                if program == 'protection_from_energy':
                    if energy == 'Lightning':
                        perform(target, 'action.move', position=(4, 8))
                    _, behavior, dice = ENERGY_ATTACKS[energy]
                    hp = caster.get_hp()
                    perform(target, behavior, recipient=None if energy == 'Thunder' else caster,
                        position=caster.position if energy == 'Thunder' else None, dice=dice)
                    resisted = hp - caster.get_hp()
                    assert resisted > 0 and 'Protection from Energy' in caster.active_conditions
                    perform(caster, 'action.drop_concentration')
                    hp = caster.get_hp()
                    perform(target, behavior, recipient=None if energy == 'Thunder' else caster,
                        position=caster.position if energy == 'Thunder' else None, dice=dice)
                    assert hp - caster.get_hp() == resisted * 2
                else:
                    perform(caster, 'spell.fire_bolt', recipient=target, fresh=True, dice=(15, 4, 4))
                    if program == 'enlarge_reduce':
                        perform(target, 'spell.fire_bolt', recipient=caster, dice=(15, 4, 20))
                    if program == 'mage_armor':
                        armor = next(item for item in caster.inventory.items.values() if item.item_id == 'armor.chain_mail')
                        robe = caster.equipment.get_item_by_slot(BodyPart.BODY)
                        assert robe is not None and 'Mage Armor' in caster.active_conditions
                        assert caster.ac_bonus().normalized_score == 15
                        assert caster.equip_item(armor.uuid, BodyPart.BODY)
                        assert 'Mage Armor' not in caster.active_conditions
                        assert caster.ac_bonus().normalized_score == 16
                        assert caster.equip_item(robe.uuid, BodyPart.BODY)
                        assert caster.ac_bonus().normalized_score == 12
                    elif 'Concentrating' in caster.active_conditions:
                        perform(caster, 'action.drop_concentration')
        history = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ('caster', 'target')))
        primary = history.views['caster']
        return CapturedHistory(primary.initialization, before, primary.lineages, history.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
