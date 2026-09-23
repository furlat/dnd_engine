"""Actual spell state remains sufficient in saved subjective playback."""

import pytest

from dnd.actions import Attack, Jump, Move
from dnd.actions_functional import execute_available_action, get_available_actions, setup_standard_actions
from dnd.core.base_block import LightLevel
from dnd.core.base_conditions import ConditionStateChangedEvent
from dnd.controller import HumanController
from dnd.encounter import Encounter
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.modifiers import NumericalModifier
from dnd.core.creature_types import DamageType, Size
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (DamageAppliedEvent, EventPhase, EventQueue, EventType,
                             SavingThrowEvent, SpatialChangeEvent, SpatialChangeType)
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import CubePresentationGeometry, SpherePresentationGeometry
from dnd.entity import Entity
from dnd.items.environment import DirectionalWall
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import AreaCondition
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import ProtectionFromEnergy, register_shield_reaction
from dnd.spells.evocation import MagicMissile
from dnd.spells.conjuration import (
    Cloudkill, Darkness, FogCloud, Grease, IncendiaryCloud,
    InsectPlague, StinkingCloud,
)
from dnd.spells.illusion import MirrorImage
from dnd.spells.transmutation import EnlargeReduce, SpikeGrowth
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.world import CardinalDirection, OccupancyLayer, WorldEdgeChannel
from game.player_facts import AttackFact, ConditionChangeFact, DamageFact, SpatialEffectStateFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, capture_lineages
from game.presentation_coverage import lineage_coverage
from game.replay import RecordedSequence
from tests.engine.support import force_attack_miss, get_hp
from tests.engine.test_spell_families import create_family_caster, create_family_target


BATTLEFIELD = "battlefield.open_floor_bright"


def actors(*, witness_position=(3,4)):
    reset_engine_runtime()
    build_battlefield(BATTLEFIELD)
    caster = create_family_caster(position=(2, 4), spell_slots={1:9,2:9,3:9,5:9,8:9})
    witness = create_family_target(position=witness_position, faction="heroes")
    encounter = Encounter(name="Spell values", source_entity_uuid=caster.uuid)
    for actor in (caster,witness):
        encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
    with fixed_dice_faces(20,1):
        encounter.start_encounter()
    encounter.start_turn()
    Entity.update_all_entities_senses()
    return caster, witness


def saved_views(observers, start):
    roots = tuple(event for _, event in EventQueue.iter_events_since(start)
                  if event.parent_lineage is None and event.phase is EventPhase.COMPLETION)
    result = {}
    for observer in observers:
        initial = capture_interval(name="Spell state", start_cursor=0, end_cursor=start,
            observer_uuid=observer.uuid, battlefield_id=BATTLEFIELD)
        native = RecordedSequence(initialization=initial,
            lineages=capture_lineages(roots, observer_uuid=observer.uuid))
        result[observer.uuid] = encode_player_sequence(project_sequence(native))
    reset_engine_runtime()
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    return result


def test_mirror_count_and_ac_update_under_real_attacks_without_reapplication():
    caster, witness = actors()
    force_attack_miss(witness)
    start = EventQueue.event_cursor()
    base_ac = caster.ac_bonus().normalized_score
    cast = MirrorImage(source_entity_uuid=caster.uuid, template=False).apply()
    assert cast is not None and not cast.canceled
    owner = caster.active_conditions["Mirror Image"].uuid
    applied_cursor = caster.active_conditions["Mirror Image"].applied_source_event_cursor
    for remaining in (2,1,0):
        witness.action_economy.reset_all_costs()
        attack = Attack(source_entity_uuid=witness.uuid, target_entity_uuid=caster.uuid,
                        weapon_slot=WeaponSlot.MELEE_MAIN).apply()
        assert attack is not None and not attack.canceled
        assert caster.ac_bonus().normalized_score == base_ac + remaining * 3
    updates = [event for _, event in EventQueue.iter_events_since(start)
               if isinstance(event, ConditionStateChangedEvent)]
    assert [event.condition_state.duplicate_count for event in updates] == [2,1]
    assert all(event.parent_lineage is not None for event in updates)
    assert all(event.condition_state.applied_source_event_cursor == applied_cursor for event in updates)
    views = saved_views((caster,witness),start)
    for payload in views.values():
        state, heads = decode_player_sequence(payload)
        observed_counts = []
        applications = 0
        for head in heads:
            update_ids = {str(node.uuid) for node in head.events
                          if isinstance(node.fact,ConditionChangeFact)
                          and node.fact.event_type is EventType.CONDITION_STATE_CHANGED}
            assert all(row["observed"] == "state_only" and not row["issues"]
                       for row in lineage_coverage(head) if row["event_uuid"] in update_ids)
            for node in head.events:
                if isinstance(node.fact, ConditionChangeFact) and node.fact.condition.condition_uuid == owner:
                    applications += node.fact.event_type is EventType.CONDITION_APPLICATION
            state = reduce_lineage(state,head)
            membership = next((row for row in state.actors[caster.uuid].conditions if row.condition_uuid == owner),None)
            if membership is not None:
                assert membership.state is not None and membership.state.duplicate_count is not None
                observed_counts.append(membership.state.duplicate_count)
                assert state.actors[caster.uuid].armor_class == base_ac + membership.state.duplicate_count * 3
        assert applications == 1 and observed_counts == [3,2,1]
        assert not any(row.condition_uuid == owner for row in state.actors[caster.uuid].conditions)
        assert state.actors[caster.uuid].armor_class == base_ac
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("mode,size", (("enlarge",Size.LARGE),("reduce",Size.SMALL)))
def test_size_mode_and_resolved_size_survive_saved_application_and_removal(mode,size):
    caster,witness=actors()
    start=EventQueue.event_cursor()
    event=EnlargeReduce(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid,
                       enlarge_mode=mode,template=False).apply()
    assert event is not None and not event.canceled and caster.size is size
    owner=caster.active_conditions["Enlarge/Reduce"].uuid
    caster.remove_condition("Concentrating")
    assert caster.size is Size.MEDIUM
    for payload in saved_views((caster,witness),start).values():
        state,heads=decode_player_sequence(payload)
        assert state.actors[caster.uuid].resolved_size is Size.MEDIUM
        assert state.actors[caster.uuid].structural_base_size is Size.MEDIUM
        during=reduce_lineage(state,heads[0]).actors[caster.uuid]
        assert during.resolved_size is size
        condition=next(row for row in during.conditions if row.condition_uuid==owner)
        assert condition.state is not None and condition.state.size_change==mode
        for head in heads:
            state=reduce_lineage(state,head)
        assert state.actors[caster.uuid].resolved_size is Size.MEDIUM


@pytest.mark.parametrize("element",(DamageType.ACID,DamageType.COLD,DamageType.FIRE,DamageType.LIGHTNING,DamageType.THUNDER))
def test_protection_selection_is_a_retained_condition_value(element):
    caster,witness=actors()
    start=EventQueue.event_cursor()
    event=ProtectionFromEnergy(source_entity_uuid=caster.uuid,target_entity_uuid=witness.uuid,
                              chosen_energy_type=element,template=False).apply()
    assert event is not None and not event.canceled
    owner=witness.active_conditions["Protection from Energy"].uuid
    for payload in saved_views((caster,witness),start).values():
        state,heads=decode_player_sequence(payload)
        for head in heads:
            state=reduce_lineage(state,head)
        condition=next(row for row in state.actors[witness.uuid].conditions if row.condition_uuid==owner)
        assert condition.state is not None and condition.state.energy_type is element
        assert condition.resulting_stats is not None
        assert (element.value,"Resistance") in condition.resulting_stats.damage_affinities


@pytest.mark.parametrize("spell",(Grease,SpikeGrowth,FogCloud,Cloudkill,StinkingCloud,Darkness,IncendiaryCloud,InsectPlague))
def test_actual_area_cast_discloses_only_observed_geometry(spell):
    caster,witness=actors()
    # Existing perception rule is intentionally strict: observer > spell DC.
    for actor in (caster,witness):
        actor.skill_set.get_skill("perception").skill_bonus.self_static.add_value_modifier(
            NumericalModifier.create(name="Observant",value=50,source_entity_uuid=actor.uuid))
    Entity.update_all_entities_senses()
    start=EventQueue.event_cursor()
    event=spell(source_entity_uuid=caster.uuid,end_position=(6,4),template=False).apply()
    assert event is not None
    assert not event.canceled,event.status_message
    zones=[zone for zone in get_map().get_spatial_conditions() if isinstance(zone,AreaCondition) and zone.source_entity_uuid==caster.uuid]
    assert len(zones)==1
    zone=zones[0]
    # Registration does not grant sight of the center or hidden occupied cells.
    for observer in (caster,witness):
        observed=observer.senses.spatial_effects.get(zone.uuid)
        if observed is not None:
            assert set(observed.positions)<=zone.affected_positions
            if observed.anchor_position is not None:
                assert observed.anchor_position==(6,4)
                assert isinstance(observed.area_geometry,(CubePresentationGeometry,SpherePresentationGeometry))
    observation=zone.get_spatial_observation({(6,4)},observer_uuid=caster.uuid,discovered=True)
    assert observation is not None and observation.anchor_position==(6,4)
    assert observation.area_geometry is not None
    assert observation.positions==((6,4),)
    views=saved_views((caster,witness),start)
    for payload in views.values():
        state,heads=decode_player_sequence(payload)
        for head in heads:
            state=reduce_lineage(state,head)
        assert state.senses is not None
        for observed in state.senses.spatial_effects.values():
            assert set(observed.positions)<=zone.affected_positions


def test_mirror_cold_acquisition_retains_remaining_count_without_live_owner():
    caster,witness=actors()
    force_attack_miss(witness)
    MirrorImage(source_entity_uuid=caster.uuid,template=False).apply()
    Attack(source_entity_uuid=witness.uuid,target_entity_uuid=caster.uuid,
           weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    owner=caster.active_conditions["Mirror Image"].uuid
    for payload in saved_views((caster,witness),EventQueue.event_cursor()).values():
        state,heads=decode_player_sequence(payload)
        assert not heads
        condition=next(row for row in state.actors[caster.uuid].conditions if row.condition_uuid==owner)
        assert condition.state is not None and condition.state.duplicate_count==2


def test_spike_discovery_gate_is_not_bypassed_by_authored_visibility():
    caster,witness=actors()
    event=SpikeGrowth(source_entity_uuid=caster.uuid,end_position=(6,4),template=False).apply()
    assert event is not None and not event.canceled
    zone,=get_map().get_spatial_conditions()
    assert isinstance(zone,AreaCondition)
    assert witness.get_passive_perception() <= caster.spell_save_dc()
    assert zone.get_spatial_observation({(6,4)},observer_uuid=witness.uuid) is None
    assert zone.uuid not in witness.senses.spatial_effects
    observed=zone.get_spatial_observation({(6,4)},observer_uuid=witness.uuid,discovered=True)
    assert observed is not None and observed.positions==((6,4),)
    reset_engine_runtime()


def test_observed_cloud_edge_carries_intrinsic_geometry_without_granting_center_sight():
    caster,witness=actors()
    start=EventQueue.event_cursor()
    event=FogCloud(source_entity_uuid=caster.uuid,end_position=(7,4),template=False).apply()
    assert event is not None and not event.canceled
    zone,=get_map().get_spatial_conditions()
    assert isinstance(zone,AreaCondition)
    assert (7,4) not in witness.senses.visible
    observed=witness.senses.spatial_effects[zone.uuid]
    assert observed.visible_volume_positions
    assert set(observed.visible_volume_positions) == zone.affected_positions
    assert observed.anchor_position is None
    assert observed.area_geometry==SpherePresentationGeometry(center=(7,4),radius_feet=20)
    for payload in saved_views((caster,witness),start).values():
        state,heads=decode_player_sequence(payload)
        for head in heads:
            state=reduce_lineage(state,head)
        assert state.senses is not None
        retained=state.senses.spatial_effects[zone.uuid]
        assert retained.area_geometry==observed.area_geometry
        assert retained.anchor_position is None
        assert (7,4) not in state.senses.visible and (7,4) in retained.visible_volume_positions


def test_fixed_ground_frame_survives_repeated_fragment_observation():
    caster,witness=actors()
    start=EventQueue.event_cursor()
    event=Grease(source_entity_uuid=caster.uuid,end_position=(6,4),template=False).apply()
    assert event is not None and not event.canceled
    zone,=get_map().get_spatial_conditions()
    original=witness.senses.spatial_effects[zone.uuid]
    assert original.anchor_position==(6,4) and original.area_geometry is not None
    for _ in range(3):
        witness.update_entity_senses(max_distance=2)
        observed=witness.senses.spatial_effects[zone.uuid]
        assert (6,4) not in witness.senses.visible
        assert set(observed.positions) & set(witness.senses.visible)
        assert observed.anchor_position is None
        assert observed.area_geometry==original.area_geometry
        assert observed.anchor_elevation_steps==original.anchor_elevation_steps
    payload,=saved_views((witness,),start).values()
    state,heads=decode_player_sequence(payload)
    for head in heads:
        state=reduce_lineage(state,head)
    assert state.senses is not None
    observed=state.senses.spatial_effects[zone.uuid]
    assert observed.anchor_position is None and observed.area_geometry==original.area_geometry


def test_native_cloud_turn_movement_changes_same_observed_owner_frame():
    caster,witness=actors()
    start=EventQueue.event_cursor()
    event=Cloudkill(source_entity_uuid=caster.uuid,end_position=(7,4),template=False).apply()
    assert event is not None and not event.canceled
    zone,=get_map().get_spatial_conditions()
    assert isinstance(zone,AreaCondition)
    identity=zone.uuid
    assert zone.position==(7,4)
    caster.on_turn_start(round_number=2,turn_index=0)
    assert zone.position==(9,4) and zone.uuid==identity
    views=saved_views((caster,witness),start)
    for payload in views.values():
        state,heads=decode_player_sequence(payload)
        centers=[]
        for head in heads:
            state=reduce_lineage(state,head)
            assert state.senses is not None
            observed=state.senses.spatial_effects.get(identity)
            if observed is not None:
                assert isinstance(observed.area_geometry,SpherePresentationGeometry)
                centers.append(observed.area_geometry.center)
        assert centers==[(7,4),(9,4)]


@pytest.mark.parametrize("boundary", ("wall", "dark", "range"))
def test_cloud_surface_observation_respects_physical_light_and_range_boundaries(boundary):
    caster, _ = actors()
    event = FogCloud(source_entity_uuid=caster.uuid, end_position=(7,4), template=False).apply()
    assert event is not None and not event.canceled
    zone, = get_map().get_spatial_conditions()
    if boundary == "wall":
        for y in range(get_map().height):
            wall = DirectionalWall(source_entity_uuid=caster.uuid, item_id="test.optical_wall",
                                   blocked_channels=(WorldEdgeChannel.OPTICAL,))
            wall.place_on_grid((2,y), boundary_direction=CardinalDirection.EAST)
    elif boundary == "dark":
        for position in get_map().get_all_tiles():
            get_map().set_tile_base_light(position, LightLevel.DARKNESS)
    observer = create_family_target(name="Cold observer", position=(0,4), faction="heroes")
    observer.update_entity_senses(max_distance=1 if boundary == "range" else 20)
    observed = observer.senses.spatial_effects.get(zone.uuid)
    if boundary == "range":
        # Deployment saw the field before this observer reduced its active range;
        # remembered geometry remains, but no surface is currently witnessed.
        assert observed is not None and not observed.visible_volume_positions
    else:
        assert observed is None
    reset_engine_runtime()


def test_cloud_skin_never_discloses_actor_or_ground_contents_and_clear_is_retained():
    caster, witness = actors()
    start = EventQueue.event_cursor()
    event = FogCloud(source_entity_uuid=caster.uuid, end_position=(7,4), template=False).apply()
    assert event is not None and not event.canceled
    zone, = get_map().get_spatial_conditions()
    hidden = create_family_target(name="Hidden inside cloud", position=(7,4))
    for observer in (caster,witness):
        observed = observer.senses.spatial_effects[zone.uuid]
        assert observed.visible_volume_positions
        assert not set(observed.visible_volume_positions) & observer.senses.visible.keys()
        assert hidden.uuid not in observer.senses.entities and (7,4) not in observer.senses.visible
    # A cold saved view observes the skin without replaying the cast or consulting owners.
    cold_cursor = EventQueue.event_cursor()
    cold = capture_interval(name="Cloud already active", start_cursor=0, end_cursor=cold_cursor,
                            observer_uuid=caster.uuid, battlefield_id=BATTLEFIELD)
    cold_payload = encode_player_sequence(project_sequence(RecordedSequence(initialization=cold,lineages=())))
    assert caster.remove_condition("Concentrating")
    for payload in saved_views((caster,witness),start).values():
        state, heads = decode_player_sequence(payload)
        witnessed_removals = []
        for head in heads:
            witnessed_removals.extend(node.fact for node in head.events
                if isinstance(node.fact,SpatialEffectStateFact)
                and node.fact.spatial_effect_uuid==zone.uuid
                and node.fact.operation is SpatialEffectChangeOperation.REMOVED)
            state=reduce_lineage(state,head)
        assert witnessed_removals
        assert state.senses is not None and zone.uuid not in state.senses.spatial_effects
    cold_state, _ = decode_player_sequence(cold_payload)
    assert cold_state.senses is not None
    assert cold_state.senses.spatial_effects[zone.uuid].visible_volume_positions
    assert hidden.uuid not in cold_state.actors and (7,4) not in cold_state.senses.visible


@pytest.mark.parametrize("blocker", ("wall", "other_fog", "other_darkness"))
def test_volume_geometry_excludes_other_owners_and_walls(blocker):
    caster, _ = actors()
    cast = FogCloud(source_entity_uuid=caster.uuid,end_position=(6,4),template=False).apply()
    assert cast is not None and not cast.canceled
    zone = next(owner for owner in get_map().get_spatial_conditions()
                if isinstance(owner,AreaCondition) and owner.source_entity_uuid==caster.uuid)
    if blocker in ("other_fog", "other_darkness"):
        other = create_family_caster(name="Other volume caster",position=(11,0))
        spell = FogCloud if blocker == "other_fog" else Darkness
        cast = spell(source_entity_uuid=other.uuid,end_position=(11,4),template=False).apply()
        assert cast is not None and not cast.canceled
    else:
        for y in range(get_map().height):
            wall=DirectionalWall(source_entity_uuid=caster.uuid,item_id="test.volume_wall",
                                 blocked_channels=(WorldEdgeChannel.OPTICAL,))
            wall.place_on_grid((6,y),boundary_direction=CardinalDirection.EAST)
    observer=create_family_target(name="Outside observer",position=(0,4))
    observed=observer.senses.spatial_effects[zone.uuid]
    assert (6,4) in observed.visible_volume_positions and (8,4) not in observed.visible_volume_positions
    assert (6,4) not in observer.senses.visible
    reset_engine_runtime()


def test_magical_darkness_geometry_uses_visible_exterior_light_without_granting_contents():
    caster, _ = actors()
    cast=Darkness(source_entity_uuid=caster.uuid,end_position=(7,4),template=False).apply()
    assert cast is not None and not cast.canceled
    zone,=get_map().get_spatial_conditions()
    assert isinstance(zone,AreaCondition)
    observed=caster.senses.spatial_effects[zone.uuid]
    assert (7,4) in observed.visible_volume_positions and (7,4) not in caster.senses.visible
    tile = get_map().get_tile(7,4)
    assert tile is not None and tile.resolved_light_level is LightLevel.DARKNESS
    reset_engine_runtime()


@pytest.mark.parametrize("spell", (FogCloud, Cloudkill))
def test_actual_discovered_walk_command_can_enter_previously_seen_obscured_ground(spell):
    caster, witness = actors(witness_position=(3,7))
    setup_standard_actions(caster)
    setup_standard_actions(witness)
    destination = (3,4)
    assert destination in caster.senses.seen
    event = spell(source_entity_uuid=caster.uuid, end_position=(7,4), template=False).apply()
    assert event is not None and not event.canceled
    assert destination not in caster.senses.visible
    available = get_available_actions(caster)
    choices = [(action,target) for action in available.all_actions
               if action.behavior_id=="action.move" for target in action.valid_targets
               if target.position==destination]
    assert choices
    with fixed_dice_faces(*([4]*30)):
        moved = execute_available_action(caster,*choices[0])
    assert moved is not None and not moved.canceled, moved.status_message if moved else "No event"
    assert caster.position==destination
    # Jump keeps its independent visible landing rule.
    jumps = [target.position for action in get_available_actions(witness).all_actions
             if action.behavior_id=="action.jump" for target in action.valid_targets]
    assert (7,4) not in jumps
    reset_engine_runtime()


def test_shield_interception_attribution_distinguishes_real_blocks_from_misses_and_hits():
    defender, attacker = actors()
    register_shield_reaction(defender)
    start = EventQueue.event_cursor()
    outcomes = []
    for roll in (10,10,3,1,17,20):
        attacker.action_economy.reset_all_costs()
        with fixed_dice_faces(roll,*([4]*30)):
            event = Attack(source_entity_uuid=attacker.uuid,target_entity_uuid=defender.uuid,
                           weapon_slot=WeaponSlot.MELEE_MAIN).apply()
        assert event is not None and not event.canceled
        outcomes.append(event)
    owner = defender.active_conditions["Shield"].uuid
    assert [row.attack_outcome for row in outcomes] == [
        AttackOutcome.MISS,AttackOutcome.MISS,AttackOutcome.MISS,AttackOutcome.CRIT_MISS,
        AttackOutcome.HIT,AttackOutcome.CRIT]
    assert [row.intercepted_by_condition_uuid for row in outcomes] == [owner,owner,None,None,None,None]
    for payload in saved_views((defender,attacker),start).values():
        _, heads = decode_player_sequence(payload)
        attacks = [node.fact for head in heads for node in head.events if isinstance(node.fact,AttackFact)]
        assert [row.intercepted_by_condition_uuid for row in attacks] == [owner,owner,None,None,None,None]


def test_shield_magic_missile_block_attribution_survives_canceled_damage_replay():
    defender, _ = actors()
    attacker = create_family_caster(name="Missile attacker",position=(2,7),faction="monsters")
    register_shield_reaction(defender)
    start = EventQueue.event_cursor()
    hp_before = get_hp(defender)
    event = MagicMissile(source_entity_uuid=attacker.uuid,target_entity_uuid=defender.uuid,template=False).apply()
    assert event is not None and not event.canceled
    assert get_hp(defender) == hp_before
    owner = defender.active_conditions["Shield"].uuid
    for payload in saved_views((defender,attacker),start).values():
        _,heads = decode_player_sequence(payload)
        blocks = [node for head in heads for node in head.events
                  if isinstance(node.fact,DamageFact) and node.fact.intercepted_by_condition_uuid==owner]
        assert blocks and all(node.canceled for node in blocks)


@pytest.mark.parametrize("spell", (SpikeGrowth, Grease))
@pytest.mark.parametrize("motion", ("jump_across", "jump_land", "walk"))
def test_ground_spell_contact_requires_landing_or_walking(spell, motion):
    origin = (9,12) if spell is SpikeGrowth else (5,6)
    caster, traveler = actors(witness_position=origin)
    center = (10,8) if spell is SpikeGrowth else (7,6)
    inside = (10,12) if spell is SpikeGrowth else (6,6)
    beyond = (11,12) if spell is SpikeGrowth else (8,6)
    cast = spell(source_entity_uuid=caster.uuid,end_position=center,template=False).apply()
    assert cast is not None and not cast.canceled
    zone, = get_map().get_spatial_conditions()
    footprint = get_map().get_spatial_condition_positions(zone.uuid)
    assert origin not in footprint and beyond not in footprint
    assert inside in footprint
    start = EventQueue.event_cursor()
    hp = traveler.get_hp()
    endpoint = beyond if motion == "jump_across" else inside
    with fixed_dice_faces(1,1):
        action = (Move(source_entity_uuid=traveler.uuid,end_position=endpoint,
                       path=[origin, endpoint],prefer_safe=False) if motion == "walk"
                  else Jump(source_entity_uuid=traveler.uuid,end_position=endpoint))
        result = action.apply()
    assert result is not None and not result.canceled
    assert traveler.position == endpoint and traveler.occupancy_layer is OccupancyLayer.GROUND
    events = [event for _, event in EventQueue.iter_events_since(start)
              if event.phase is EventPhase.COMPLETION]
    entries = [event for event in events if isinstance(event,SpatialChangeEvent)
               and event.change_type is SpatialChangeType.ENTITY_ENTERED
               and event.entity_uuid == traveler.uuid and event.position in footprint]
    if motion == "jump_across":
        assert entries and all(event.occupancy_layer is OccupancyLayer.AIR for event in entries)
    ground = [event for event in entries if event.occupancy_layer is OccupancyLayer.GROUND]
    assert len(ground) == (0 if motion == "jump_across" else 1)
    damage = [event for event in events if isinstance(event,DamageAppliedEvent)
              and event.target_entity_uuid == traveler.uuid]
    saves = [event for event in events if isinstance(event,SavingThrowEvent)
             and event.target_entity_uuid == traveler.uuid]
    if spell is SpikeGrowth:
        assert len(damage) == len(ground) and not saves
        assert traveler.get_hp() == hp - 2*len(ground)
        effects = damage
    else:
        assert len(saves) == len(ground) and not damage
        assert ("Prone" in traveler.active_conditions) is bool(ground)
        effects = saves
    for effect in effects:
        ancestor = effect
        seen_ground = False
        while ancestor.parent_event is not None:
            parent = EventQueue.get_event_by_uuid(ancestor.parent_event)
            assert parent is not None
            seen_ground |= any(parent.lineage_uuid == event.lineage_uuid for event in ground)
            ancestor = parent
        assert seen_ground and ancestor.lineage_uuid == result.lineage_uuid
