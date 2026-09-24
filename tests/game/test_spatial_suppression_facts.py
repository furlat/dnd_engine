"""Maintained protection outcomes survive the actual subjective wire boundary."""

import pytest

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import SpherePresentationGeometry
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.residues import ASHEN_RESIDUE, deposit_residue
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import GlobeOfInvulnerability, GlobeZone
from dnd.spells.conjuration import Cloudkill, CloudkillZone, FogCloud, FogCloudZone, InsectPlague, InsectPlagueZone
from dnd.types.world import CardinalDirection
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval
from game.replay import RecordedSequence
from tests.engine.test_spell_families import create_family_caster, create_family_target
from tests.game.globe_scenarios import globe_history
from tests.game.player_helpers import player_history


@pytest.mark.parametrize("spell", ("fog_cloud", "darkness", "cloudkill"))
def test_saved_cloud_retains_actual_disclosed_spherical_suppression(spell):
    history = globe_history(spell=spell, impact_offset=(0, 0), retain_field=True)
    for role in ("caster", "target"):
        state, heads = player_history(history, role=role)
        for head in heads:
            state = reduce_lineage(state, head)
        assert state.senses is not None
        effects = state.senses.spatial_effects
        provider, globe = next((owner, effect) for owner, effect in effects.items()
            if effect.content_ref.content_id == "spatial_effect.spell.globe_of_invulnerability")
        cloud = next(effect for effect in effects.values()
            if effect.content_ref.content_id == "spatial_effect.spell." + spell)
        suppression, = cloud.suppressions
        assert suppression.provider_uuid == provider
        assert suppression.provider_content_ref == globe.content_ref
        assert suppression.area_geometry == SpherePresentationGeometry(center=(7, 7), radius_feet=10)
        assert suppression.anchor_elevation_steps == 0
        assert suppression.positions
        assert set(suppression.positions) <= set(globe.positions)
        assert set(suppression.positions).isdisjoint(cloud.positions)
        # This adds geometry admission, never ground or actor visibility.
        if role == "caster" and spell in ("fog_cloud", "cloudkill"):
            assert not set(suppression.positions) & state.senses.visible


@pytest.fixture
def arena():
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    caster = create_family_caster(position=(1, 7), spell_slots={1: 2, 5: 2})
    owner = create_family_caster("Globe owner", position=(7, 7), spell_slots={6: 1})
    Entity.update_all_entities_senses(max_distance=120)
    result = GlobeOfInvulnerability(source_entity_uuid=owner.uuid, template=False).apply()
    assert result and not result.canceled
    globe = next(effect for effect in get_map().get_spatial_conditions() if isinstance(effect, GlobeZone))
    yield caster, owner, globe
    reset_engine_runtime()


def cloud(caster, *, movable=False):
    spell = Cloudkill if movable else FogCloud
    result = spell(source_entity_uuid=caster.uuid, end_position=(7, 7), template=False).apply()
    assert result and not result.canceled
    effect = next(effect for effect in get_map().get_spatial_conditions()
        if isinstance(effect, (CloudkillZone, FogCloudZone)))
    return effect, result


def cold_bytes(observer):
    initialization = capture_interval(name="Disclosed cloud protection", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=observer.uuid,
        battlefield_id="battlefield.open_floor_bright")
    return encode_player_sequence(project_sequence(RecordedSequence(initialization=initialization, lineages=())))


@pytest.mark.parametrize("position", ((7, 7), (7, 6), (6, 7), (8, 7)))
def test_simultaneous_cold_observation_discovers_relation_without_cast_history(arena, position):
    caster, _, globe = arena
    zone, _ = cloud(caster)
    witness = create_family_target("Late witness", position=position)
    witness.update_entity_senses(max_distance=120)
    relation, = witness.senses.spatial_effects[zone.uuid].suppressions
    assert relation.provider_uuid == globe.uuid and relation.positions
    assert relation.area_geometry == SpherePresentationGeometry(center=(7, 7), radius_feet=10)
    payload = cold_bytes(witness)
    reset_engine_runtime()
    state, heads = decode_player_sequence(payload)
    assert not heads and state.senses is not None
    assert state.senses.spatial_effects[zone.uuid].suppressions == (relation,)


def test_new_observer_cannot_discover_a_globe_hidden_inside_the_cloud(arena):
    caster, _, globe = arena
    zone, _ = cloud(caster)
    assert zone.spatial_suppressions and zone.spatial_suppressions[0].provider_uuid == globe.uuid
    witness = create_family_target("Uninformed outside witness", position=(1, 6))
    witness.update_entity_senses(max_distance=120)
    assert globe.uuid not in witness.senses.spatial_effects
    assert not witness.senses.spatial_effects[zone.uuid].suppressions
    payload = cold_bytes(witness)
    reset_engine_runtime()
    state, _ = decode_player_sequence(payload)
    assert state.senses is not None
    assert globe.uuid not in state.senses.spatial_effects
    assert not state.senses.spatial_effects[zone.uuid].suppressions


def test_current_cloud_interaction_keeps_known_protection_surface_without_ground_sight(arena):
    caster, owner, globe = arena
    zone, _ = cloud(caster)
    assert globe.uuid in caster.senses.spatial_effects
    protection = caster.senses.spatial_effects[globe.uuid]
    suppression, = caster.senses.spatial_effects[zone.uuid].suppressions
    assert protection.visible_volume_positions
    assert set(protection.visible_volume_positions) <= set(suppression.positions)
    assert not set(protection.visible_volume_positions) & caster.senses.visible.keys()
    assert owner.uuid not in caster.senses.entities
    payload = cold_bytes(caster)
    reset_engine_runtime()
    state, _ = decode_player_sequence(payload)
    assert state.senses is not None
    assert state.senses.spatial_effects[globe.uuid].visible_volume_positions == protection.visible_volume_positions
    assert owner.uuid not in state.senses.entities and (7, 7) not in state.senses.visible


def test_another_unblocked_cloud_still_hides_the_protection_surface(arena):
    caster, _, globe = arena
    cloud(caster)
    assert caster.senses.spatial_effects[globe.uuid].visible_volume_positions
    inside = create_family_caster("Inside caster", position=(8, 7), spell_slots={1: 1})
    result = FogCloud(source_entity_uuid=inside.uuid, end_position=(7, 7), template=False).apply()
    assert result and not result.canceled, result.status_message if result else "No cast"
    caster.update_entity_senses(max_distance=120)
    remembered = caster.senses.spatial_effects.get(globe.uuid)
    assert remembered is None or not remembered.visible_volume_positions
    assert not set(globe.affected_positions) & caster.senses.visible.keys()


def test_provider_removal_preserves_disclosed_registration_until_cloud_resolves_again(arena):
    caster, owner, globe = arena
    zone, cast = cloud(caster, movable=True)
    observed = caster.senses.spatial_effects[zone.uuid].suppressions
    assert len(observed) == 1
    prior_positions = set(zone.affected_positions)
    assert owner.remove_condition("Concentrating")
    assert get_map().get_spatial_condition(globe.uuid) is None
    assert set(zone.affected_positions) == prior_positions
    retained, = caster.senses.spatial_effects[zone.uuid].suppressions
    remembered = caster.senses.spatial_effects.get(globe.uuid)
    assert remembered is None or not remembered.visible_volume_positions
    assert retained.area_geometry == observed[0].area_geometry
    assert retained.provider_content_ref == observed[0].provider_content_ref
    payload = cold_bytes(caster)
    assert zone.move_zone((8, 7), parent_event=cast)
    assert not zone.spatial_suppressions
    assert not caster.senses.spatial_effects[zone.uuid].suppressions
    reset_engine_runtime()
    state, _ = decode_player_sequence(payload)
    assert state.senses is not None
    assert state.senses.spatial_effects[zone.uuid].suppressions == (retained,)


def test_moving_cloud_replaces_its_resolved_overlap_instead_of_accumulating_holes(arena):
    caster, owner, globe = arena
    zone, cast = cloud(caster, movable=True)
    original, = zone.spatial_suppressions
    assert len(original.positions) == 13
    assert zone.move_zone((10, 7), parent_event=cast)
    changed, = zone.spatial_suppressions
    expected = {position for position in globe.affected_positions
        if (position[0] - 10) ** 2 + (position[1] - 7) ** 2 <= 16}
    assert set(changed.positions) == expected < set(original.positions)
    assert set(changed.positions).isdisjoint(zone.affected_positions)
    observed, = owner.senses.spatial_effects[zone.uuid].suppressions
    assert set(observed.positions) <= expected
    assert observed.area_geometry == SpherePresentationGeometry(center=(7, 7), radius_feet=10)


def test_protected_volume_admission_stops_at_a_real_wall_and_does_not_reveal_ground(arena):
    caster, _, globe = arena
    zone, _ = cloud(caster)
    assert caster.senses.spatial_effects[zone.uuid].suppressions[0].positions
    for y in range(get_map().height):
        build_directional_wall().place_on_grid((4, y), boundary_direction=CardinalDirection.EAST)
    caster.update_entity_senses(max_distance=120)
    observed = caster.senses.spatial_effects[zone.uuid]
    suppression, = observed.suppressions
    assert not suppression.positions
    assert not set(globe.affected_positions) & caster.senses.visible.keys()
    assert observed.visible_volume_positions
    assert all(position[0] <= 4 for position in observed.visible_volume_positions)
    assert not caster.senses.spatial_effects[globe.uuid].visible_volume_positions


def test_unrelated_local_sensory_refresh_retains_visible_insect_protection(arena):
    caster, _, globe = arena
    result = InsectPlague(source_entity_uuid=caster.uuid, end_position=(7, 7), template=False).apply()
    assert result and not result.canceled
    zone = next(effect for effect in get_map().get_spatial_conditions() if isinstance(effect, InsectPlagueZone))
    before, = caster.senses.spatial_effects[zone.uuid].suppressions
    assert set(before.positions) == globe.affected_positions
    tile = get_map().get_tile(*caster.position)
    assert tile is not None
    deposit_residue(tile, ASHEN_RESIDUE)
    assert caster.senses.spatial_effects[zone.uuid].suppressions == (before,)


@pytest.mark.parametrize("spell,source_inside", (("incendiary_cloud", False), ("fog_cloud", True)))
def test_unsuppressed_clouds_never_gain_protection_exclusions(spell, source_inside):
    history = globe_history(spell=spell, source_inside=source_inside, impact_offset=(0, 0), retain_field=True)
    for role in ("caster", "target"):
        state, heads = player_history(history, role=role)
        for head in heads:
            state = reduce_lineage(state, head)
        assert state.senses is not None
        effect = next(effect for effect in state.senses.spatial_effects.values()
            if effect.content_ref.content_id == "spatial_effect.spell." + spell)
        assert not effect.suppressions
