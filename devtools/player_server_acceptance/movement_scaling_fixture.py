"""Native setup for the opt-in movement scaling lane; no measured commands here."""
from pathlib import Path
import secrets
from uuid import uuid4

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.aoe import Cube, Sphere
from dnd.core.base_block import LightLevel
from dnd.core.content.encounters import (AuthoredCreatureRosterSource, EncounterDeploymentSpec,
    EncounterDeploymentZone, EncounterRecipe, EncounterRosterMember, EncounterRosterRecipe,
    EncounterRosterSlot, FixedRosterOpeningPolicy, RosterControllerDefaults, RosterControllerKind,
    RosterItemGrant, RosterItemPlacement)
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.player.audience import SeatAssignment
from dnd.reactions import add_opportunity_attack_handler
from dnd.spells.conjuration import FOG_CLOUD_AREA, FogCloudZone, GreaseZone
from dnd.types.world import CardinalDirection
from server.config import SeatCredential, ServerConfig


LEVELS = {
    'baseline': (0, 0, 0),
    'tiles': (100, 1000, 10000),
    'objects': (10, 100, 1000),
    'optical_conditions': (10, 100, 1000),
    'nonoptical_conditions': (10, 100, 1000),
    'observers': (2, 8, 32),
    'reaction_handlers': (2, 8, 32),
    'handlers': (10, 100, 1000),
    'memory': (100, 1000, 10000),
    'history': (100, 1000, 10000),
    'affected_observers': (2, 8, 32),
    'affected_contacts': (1, 10, 100),
    'sight_radius': (10, 20, 40),
    'light_radius': (15, 30, 60),
    'seats': (1, 2, 4),
}
SIZES = ('small', 'medium', 'large')
START = (4, 6)
END = (10, 6)
MOVER = 'Scaling mover'


def configuration(axis: str, amount: int, directory: Path) -> ServerConfig:
    """Four fixed native combatants; only seat partition varies for that axis."""
    source = AuthoredCreatureRosterSource(recipe=BESTIARY_CREATURE_RECIPES_BY_ID['goblin'])
    slots, zones = [], []
    addresses = []
    for index, position in enumerate((START, (2, 12), (12, 12), (13, 12))):
        name = f'unit_{index}'
        grants = (RosterItemGrant(item_id='equipment.portable_torch',
            placement=RosterItemPlacement.INVENTORY, on_grant='ignite'),) if index == 0 else ()
        member = EncounterRosterMember(member_id='actor',
            display_name=MOVER if index == 0 else f'Scaling companion {index}',
            deployment_role=name, source=source, scenario_setup_effects=grants)
        roster = EncounterRosterRecipe.create(roster_id=f'roster.scaling_{name}',
            title=name, members=(member,))
        slots.append(EncounterRosterSlot(roster_slot_id=name, roster=roster,
            faction_id='local' if index < 2 else 'opposing', deployment_zone_id=name,
            controller_defaults=RosterControllerDefaults(controller=RosterControllerKind.HUMAN,
                participant_name=name)))
        zones.append(EncounterDeploymentZone(zone_id=name, ordered_slots=(position,)))
        addresses.append((name, 'actor'))
    seat_count = amount if axis == 'seats' else 2
    assignments = tuple(SeatAssignment(f'seat_{index}',
        tuple(address for order, address in enumerate(addresses) if order % seat_count == index),
        observers=(addresses[0],) if axis == 'seats' else None)
        for index in range(seat_count))
    battlefield = 'battlefield.open_floor_bright'
    deployment = EncounterDeploymentSpec.create(deployment_id='deployment.movement_scaling',
        title='Movement scaling', battlefield_id=battlefield, zones=tuple(zones))
    recipe = EncounterRecipe.create(encounter_id='encounter.movement_scaling',
        title='Movement scaling', battlefield_id=battlefield, deployment=deployment,
        roster_slots=tuple(slots), opening_policy=FixedRosterOpeningPolicy(roster_slot_id='unit_0'))
    return ServerConfig(game_id='movement_scaling', encounter_id=None, recipe=recipe,
        assignments=assignments, credentials=tuple(SeatCredential(seat_id=seat.seat_id,
            token=secrets.token_urlsafe(32)) for seat in assignments),
        spool_directory=directory / 'spool', test_seed=2)


def add_observer(session, position, index, *, reaction=False):
    actor = materialize_creature(BESTIARY_CREATURE_RECIPES_BY_ID['goblin'],
        runtime_entity_uuid=uuid4(), display_name=f'Scaling observer {index}',
        faction='opposing' if reaction else 'local', position=position,
        deployment_role=CreatureDeploymentRole(role_id=f'scaling.observer_{index}'),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS)
    actor.compose_entity()
    if reaction:
        add_opportunity_attack_handler(actor)
    session.game.deploy_entity(actor, position)
    actor.update_entity_senses()
    if reaction:
        adjacent = position[0] + 1, position[1]
        assert actor.action_economy.reactions.normalized_score >= 1
        assert adjacent in actor.senses.get_threathened_positions(candidate_positions=(adjacent,))
    return actor


def prepare(session, axis: str, amount: int):
    """Use the existing world owners before the initial audience capture.

    The remote 100x100 support and one native source creature are fixed for every
    variant. Conditions own their real registrations; no dummy handlers are used.
    Memory/history are deliberately left to the SDK warm-up phase.
    """
    grid = get_map()
    grid.create_rectangle(1000, 1000, 100, 100)
    source = add_observer(session, (1000, 1000), 0)
    mover = next(actor for actor in session.game.entities.values() if actor.name == MOVER)
    if axis == 'tiles':
        grid.create_rectangle(4000, 4000, 100, amount // 100)
    if axis in ('objects', 'optical_conditions', 'nonoptical_conditions', 'handlers'):
        for index in range(amount):
            # Grease occupies more than one cell; spaced supports keep native
            # exclusive-layer replacement from silently reducing the owner count.
            position = (1010 + index % 25 * 2, 1010 + index // 25 * 2)
            if axis == 'objects':
                item = build_authored_item('weapon.dagger', source.uuid)
                grid.place_object(item.uuid, position)
            else:
                zone_type = FogCloudZone if axis == 'optical_conditions' else GreaseZone
                zone = zone_type(source_entity_uuid=source.uuid, position=position,
                    area=(Sphere(radius_feet=0, propagation=FOG_CLOUD_AREA.propagation) if axis == 'optical_conditions'
                          else Cube(size_feet=5, centered=True)))
                zone.activate(parent_event=None)
    if axis in ('observers', 'affected_observers', 'reaction_handlers'):
        for index in range(amount):
            position = (1010 + index % 16, 1010 + index // 16) if axis != 'affected_observers' else \
                (index % 12 + 1, 8 + index // 12)
            add_observer(session, position, index + 1, reaction=axis == 'reaction_handlers')
    if axis == 'affected_contacts':
        # Both sizes share support for all 100 possible contact positions.
        grid.create_rectangle(0, 15, 15, 3)
        for index in range(amount):
            item = build_authored_item('weapon.dagger', source.uuid)
            grid.place_object(item.uuid, (index % 12 + 1, 8 + index // 12))
    if axis == 'memory':
        # All sizes share the same remote corridor and object population. Only
        # the distance actually explored through ordinary commands will differ.
        grid.create_rectangle(4, 15, 7, 1500)
        for index in range(1000):
            item = build_authored_item('weapon.dagger', source.uuid)
            grid.place_object(item.uuid, (4 + index % 7, 20 + index // 7 * 10))
    if axis in ('sight_radius', 'light_radius'):
        # The geometry is fixed across each radius cohort; it exceeds every
        # tested radius so required cell work can actually grow.
        grid.create_rectangle(15, 0, 66, 81)
        grid.create_rectangle(0, 15, 15, 66)
    if axis == 'light_radius':
        torch = next(item for item in mover.inventory.items.values()
            if item.item_id == 'equipment.portable_torch')
        torch.extinguish()
        torch.very_bright_radius_feet = amount // 3
        torch.bright_radius_feet = amount * 2 // 3
        torch.dim_radius_feet = amount
        torch.ignite(mover.uuid)
    # Establish all local fields before the optional native remote mutation.
    # Ordinary SDK discovery and movement run only after these events settle.
    for actor in session.game.entities.values():
        actor.update_entity_senses(amount if axis == 'sight_radius' and actor is mover else 10)
    return session


def mutate_remote():
    """A real local-to-remote world change after the opening fields are current."""
    grid = get_map()
    grid.set_tile_base_light((1050, 1050), LightLevel.DIM_LIGHT)
    wall = build_directional_wall(display_name='Remote mutation wall')
    grid.place_object(wall.uuid, (1050, 1050), boundary_direction=CardinalDirection.EAST)
