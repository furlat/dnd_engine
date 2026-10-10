"""Private four-controller acceptance compositions using normal creature recipes."""
from pathlib import Path
import secrets

from dnd.ai.policies.basic import BASIC_POLICY_ID
from dnd.core.content.encounters import (AuthoredCreatureRosterSource, EncounterDeploymentSpec,
    EncounterDeploymentZone, EncounterRecipe, EncounterRosterMember, EncounterRosterRecipe,
    EncounterRosterSlot, InitiativeOpeningPolicy, RosterControllerDefaults, RosterControllerKind,
    RosterMemberControllerOverride, RosterItemGrant, RosterItemPlacement)
from dnd.core.content.encounters import FixedRosterOpeningPolicy, RosterSpellGrant
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import get_content_declaration
from dnd.core.equipment_types import WeaponSlot
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.player.audience import SeatAssignment
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_BY_NAME
from server.config import SeatCredential, ServerConfig


def configuration(mode: str, directory: Path) -> ServerConfig:
    if mode == 'crypt':
        return ServerConfig(game_id='crypt', encounter_id='encounter.lantern_crypt',
            credentials=(SeatCredential(seat_id='Expedition', token=secrets.token_urlsafe(32)),),
            spool_directory=directory/'spool', test_seed=0)
    sides = ('amber', 'blue')
    slots = []
    assignments = []
    for side in sides:
        members = tuple(EncounterRosterMember(member_id=f'unit_{i}', display_name=f'{side.title()} scout {i}',
            deployment_role=f'unit_{i}', scenario_setup_effects=(RosterItemGrant(item_id='weapon.shortbow',
                placement=RosterItemPlacement.EQUIPPED, equipment_slot=WeaponSlot.RANGED_MAIN),), source=AuthoredCreatureRosterSource(recipe=BESTIARY_CREATURE_RECIPES_BY_ID['goblin']))
            for i in (1, 2))
        roster = EncounterRosterRecipe.create(roster_id=f'roster.acceptance_{side}', title=side.title(), members=members)
        ai_side = mode == 'human_vs_ai' and side == 'blue' or mode == 'ai_vs_human' and side == 'amber'
        overrides = (RosterMemberControllerOverride(member_id='unit_2', controller=RosterControllerKind.AI,
            policy_id=BASIC_POLICY_ID),) if mode == 'mixed' else ()
        controls = RosterControllerDefaults(controller=RosterControllerKind.AI if ai_side else RosterControllerKind.HUMAN,
            participant_name=side, policy_id=BASIC_POLICY_ID if ai_side else None, member_overrides=overrides)
        slots.append(EncounterRosterSlot(roster_slot_id=side, roster=roster, faction_id=side,
            deployment_zone_id=side, controller_defaults=controls))
        external = () if ai_side else ('unit_1',) if mode == 'mixed' else ('unit_1', 'unit_2')
        if mode == 'per_entity':
            assignments.extend(SeatAssignment(f'{side}_{member}', ((side, member),)) for member in external)
        elif external:
            assignments.append(SeatAssignment(side, tuple((side, member) for member in external)))
    battlefield = 'battlefield.open_floor_bright'
    deployment = EncounterDeploymentSpec.create(deployment_id='deployment.server_acceptance', title='Server acceptance',
        battlefield_id=battlefield, zones=tuple(EncounterDeploymentZone(zone_id=side,
            ordered_slots=((6 + index * 3, 6), (6 + index * 3, 8))) for index, side in enumerate(sides)))
    recipe = EncounterRecipe.create(encounter_id='encounter.server_acceptance', title='Server acceptance',
        battlefield_id=battlefield, deployment=deployment, roster_slots=tuple(slots), opening_policy=InitiativeOpeningPolicy())
    return ServerConfig(game_id='acceptance', encounter_id=None, recipe=recipe, assignments=tuple(assignments),
        credentials=tuple(SeatCredential(seat_id=seat.seat_id, token=secrets.token_urlsafe(32)) for seat in assignments),
        spool_directory=directory / 'spool', test_seed=2)


COMBAT_CASES = ('melee', 'ranged', 'magic_missile', 'scorching_ray', 'fireball_six_goblins',
    'hold_person', 'wall_of_fire', 'conjure_animals')


def combat_configuration(case: str, directory: Path, seed: int = 2) -> ServerConfig:
    """Finite fights using authored HP/slot progression and initial item/spell grants."""
    if case not in COMBAT_CASES:
        raise ValueError(case)
    weapon_case = case in ('melee', 'ranged')
    dense = case == 'fireball_six_goblins'
    spells = {'scorching_ray': 'Scorching Ray', 'hold_person': 'Hold Person',
        'wall_of_fire': 'Wall of Fire', 'conjure_animals': 'Conjure Animals'}
    slots, assignments, zones = [], [], []
    for side in ('amber', 'blue'):
        count = 2 if weapon_case or side == 'blue' and not dense else 6 if side == 'blue' else 1
        source = BESTIARY_CREATURE_RECIPES_BY_ID['goblin' if weapon_case or dense and side == 'blue' else 'generic_caster']
        if not weapon_case and not (dense and side == 'blue'):
            source = ContentRecipe.create(ref=source.ref, parameters={'level': 7 if side == 'amber' else 5})
        grants = [RosterItemGrant(item_id='weapon.shortbow', placement=RosterItemPlacement.EQUIPPED,
            equipment_slot=WeaponSlot.RANGED_MAIN, replace_existing=True)]
        if case == 'melee':
            grants.append(RosterItemGrant(item_id='weapon.shortsword', placement=RosterItemPlacement.EQUIPPED,
                equipment_slot=WeaponSlot.MELEE_MAIN, replace_existing=True))
        if side == 'amber' and case in spells:
            declaration = get_content_declaration(SPELL_CONTENT_IDENTITY_BY_NAME[spells[case]].spell_type)
            grants.append(RosterSpellGrant(spell_refs=(declaration.ref,), caster_level=7))
        members = tuple(EncounterRosterMember(member_id=f'unit_{i}', display_name=f'{side.title()} combatant {i}',
            deployment_role=f'{side}_{i}', source=AuthoredCreatureRosterSource(recipe=source),
            scenario_setup_effects=tuple(grants)) for i in range(1, count + 1))
        roster = EncounterRosterRecipe.create(roster_id=f'roster.combat_measurement_{side}', title=side.title(), members=members)
        slots.append(EncounterRosterSlot(roster_slot_id=side, roster=roster, faction_id=side,
            deployment_zone_id=side, controller_defaults=RosterControllerDefaults(
                controller=RosterControllerKind.HUMAN, participant_name=side)))
        assignments.append(SeatAssignment(side, tuple((side, member.member_id) for member in members)))
        positions = ((4, 6), (4, 8)) if weapon_case and side == 'amber' else ((9, 6), (9, 8)) if weapon_case else \
            ((3, 7),) if side == 'amber' else ((9, 6), (9, 7), (9, 8), (10, 6), (10, 7), (10, 8)) if dense else ((9, 7), (9, 8))
        zones.append(EncounterDeploymentZone(zone_id=side, ordered_slots=positions))
    battlefield = 'battlefield.open_floor_bright'
    deployment = EncounterDeploymentSpec.create(deployment_id='deployment.combat_measurement',
        title='Combat measurement', battlefield_id=battlefield, zones=tuple(zones))
    recipe = EncounterRecipe.create(encounter_id='encounter.combat_measurement', title='Combat measurement',
        battlefield_id=battlefield, deployment=deployment, roster_slots=tuple(slots),
        opening_policy=FixedRosterOpeningPolicy(roster_slot_id='amber'))
    return ServerConfig(game_id='combat_' + case, encounter_id=None, recipe=recipe, assignments=tuple(assignments),
        credentials=tuple(SeatCredential(seat_id=side, token=secrets.token_urlsafe(32)) for side in ('amber', 'blue')),
        spool_directory=directory / 'spool', test_seed=seed)
