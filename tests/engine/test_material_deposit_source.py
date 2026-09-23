"""Real spills retain their source geometry independently of the broken item."""

from uuid import UUID

import pytest

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.events import EventPhase, ItemDestructionEvent, SpatialEffectInteractionEvent, WorldTileState
from dnd.core.gridmap import get_map
from dnd.game import Game
from dnd.residues import BLOOD_RESIDUE, deposit_residue
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import SpatialCondition
from dnd.types.residues import ResidueContribution, ResidueEllipse
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from tests.engine.test_liquid_barrel_areas import AREA, barrel_and_attacker, break_barrel, world as world
from tests.engine.test_liquid_barrels import CONTENTS, actor, completed


@pytest.mark.parametrize("contents", CONTENTS)
def test_real_spill_retains_one_source_after_wreck_retirement_and_cold_roundtrip(world: Game, contents: str) -> None:
    barrel, attacker = barrel_and_attacker(world, contents)
    break_barrel(barrel, attacker)
    destruction, = [event for event in completed(0) if isinstance(event, ItemDestructionEvent)]
    barrel.retire()
    assert get_map().get_object_placement(barrel.uuid) is None
    if contents in {"oil", "water", "grease"}:
        owner, = get_map().get_spatial_conditions()
        assert isinstance(owner, SpatialCondition)
        observation = owner.get_spatial_observation(AREA, observer_uuid=attacker.uuid)
        assert observation is not None
        sources = [observation.deposit_source]
        encoded = [observation.model_dump_json()]
    else:
        tiles = [get_map().get_tile(*position) for position in sorted(AREA)]
        states = [tile.to_world_tile_state() for tile in tiles if tile is not None]
        assert len(states) == 9
        sources = [contribution.deposit_source for tile in states
                   for residue in tile.residues for contribution in residue.contributions]
        assert len(sources) == 9
        encoded = [state.model_dump_json() for state in states]
    assert all(source is not None for source in sources)
    assert all(source == sources[0] for source in sources)
    source = sources[0]
    assert source is not None
    assert source.deposit_uuid == destruction.lineage_uuid
    assert source.origin == (3, 3) and source.radius_cells == 1

    world.close()
    reset_engine_runtime()
    if contents in {"oil", "water", "grease"}:
        restored = PerceivedSpatialEffect.model_validate_json(encoded[0])
        assert restored.deposit_source == source and set(restored.positions) == AREA
    else:
        restored_tiles = [WorldTileState.model_validate_json(row) for row in encoded]
        assert {tile.position for tile in restored_tiles} == AREA
        assert all(contribution.deposit_source == source for tile in restored_tiles
                   for residue in tile.residues for contribution in residue.contributions)


@pytest.mark.parametrize("contents", CONTENTS)
def test_overlapping_spills_keep_sources_on_actual_retained_material(world: Game, contents: str) -> None:
    first, attacker = barrel_and_attacker(world, contents)
    break_barrel(first, attacker)
    first.retire()
    second = build_authored_item(f"environment.blocker.{contents}_barrel", attacker.uuid)
    second.place_on_grid((4, 3))
    attacker.action_economy.reset_all_costs()
    break_barrel(second, attacker)
    second.retire()
    destructions = [event for event in completed(0) if isinstance(event, ItemDestructionEvent)]
    assert len(destructions) == 2
    origins = {destructions[0].lineage_uuid: (3, 3), destructions[1].lineage_uuid: (4, 3)}
    second_cells = {(x + 1, y) for x, y in AREA}
    by_source: dict[UUID, set[tuple[int, int]]] = {}
    if contents in {"oil", "water", "grease"}:
        for owner in get_map().get_spatial_conditions():
            assert isinstance(owner, SpatialCondition) and owner.deposit_source is not None
            source = owner.deposit_source
            assert source.origin == origins[source.deposit_uuid]
            by_source[source.deposit_uuid] = set(owner.affected_positions)
        # Existing equal-ranked spatial material admits the newer owner.
        assert by_source == {destructions[0].lineage_uuid: AREA - second_cells,
                             destructions[1].lineage_uuid: second_cells}
    else:
        for position in AREA | second_cells:
            tile = get_map().get_tile(*position)
            assert tile is not None
            residue, = tile.to_world_tile_state().residues
            contribution, = residue.contributions
            source = contribution.deposit_source
            assert source is not None and source.origin == origins[source.deposit_uuid]
            assert contribution.amount == residue.amount == residue.max_amount
            by_source.setdefault(source.deposit_uuid, set()).add(position)
        # Saturated residue retains its first material; no fictitious new layer.
        assert by_source == {destructions[0].lineage_uuid: AREA,
                             destructions[1].lineage_uuid: second_cells - AREA}


def test_bulk_blood_keeps_injury_shape_and_only_its_actual_added_amount(world: Game) -> None:
    barrel, attacker = barrel_and_attacker(world, "blood")
    tile = get_map().get_tile(3, 3)
    assert tile is not None
    ellipse = ResidueEllipse(center=(0.2, 0.1), radius_x=0.4, radius_y=0.2)
    injury = deposit_residue(tile, BLOOD_RESIDUE, amount=2, ellipses=(ellipse,))
    assert injury is not None
    break_barrel(barrel, attacker)
    after, = tile.to_world_tile_state().residues
    assert after.condition_uuid == injury.condition_uuid and after.amount == 5
    assert after.contributions[0] == injury.contributions[0]
    assert after.contributions[1].ellipses == ()
    assert after.contributions[1].amount == 3
    assert after.contributions[1].deposit_source is not None
    # Neither another shaped hit nor a saturated deposit rewrites the survivors.
    capped = deposit_residue(tile, BLOOD_RESIDUE, amount=1, ellipses=(ellipse,))
    assert capped == after


@pytest.mark.parametrize("contents,operation,expected_name", (
    ("oil", SpatialEffectInteractionOperation.IGNITE, "Fire Surface"),
    ("water", SpatialEffectInteractionOperation.FREEZE, "Ice Surface"),
    ("water", SpatialEffectInteractionOperation.ELECTRIFY, "Electrified Water"),
    ("water", SpatialEffectInteractionOperation.VAPORIZE, "Steam Cloud"),
))
def test_partial_transform_and_removal_preserve_original_deposit_frame(
    world: Game, contents: str, operation: SpatialEffectInteractionOperation, expected_name: str,
) -> None:
    barrel, attacker = barrel_and_attacker(world, contents)
    cause = break_barrel(barrel, attacker)
    original, = get_map().get_spatial_conditions()
    assert isinstance(original, SpatialCondition) and original.deposit_source is not None
    source = original.deposit_source
    selected = {(4, 2), (4, 3), (4, 4)}
    event = SpatialEffectInteractionEvent(source_entity_uuid=attacker.uuid, operation=operation,
        positions=tuple(sorted(selected)))
    event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
    assert original.affected_positions == AREA - selected
    replacement, = [condition for condition in get_map().get_spatial_conditions() if condition.name == expected_name]
    assert isinstance(replacement, SpatialCondition)
    assert replacement.affected_positions == selected and replacement.position != source.origin
    assert replacement.deposit_source == original.deposit_source == source
    assert replacement.change_footprint({(4, 2), (4, 4)}, parent_event=cause)
    observed = replacement.get_spatial_observation({(4, 4)}, observer_uuid=attacker.uuid)
    assert observed is not None
    assert observed.positions == ((4, 4),) and observed.anchor_position is None
    assert observed.deposit_source == source
    replacement.deactivate(parent_event=cause)
    assert set(original.affected_positions) == AREA - selected
    assert original.deposit_source == source


@pytest.mark.parametrize("contents", ("oil", "water", "grease"))
def test_visible_fragment_keeps_source_geometry_without_discovering_anchor_or_hidden_cells(world: Game, contents: str) -> None:
    barrel, attacker = barrel_and_attacker(world, contents)
    observer = actor(world, (5, 3))
    observer.update_entity_senses(max_distance=1)
    break_barrel(barrel, attacker)
    observer.update_entity_senses(max_distance=1)
    owner, = get_map().get_spatial_conditions()
    observed = observer.senses.spatial_effects[owner.uuid]
    assert observed.anchor_position is None and (3, 3) not in observer.senses.visible
    assert observed.positions == ((4, 3),)
    assert observed.deposit_source is not None and observed.deposit_source.origin == (3, 3)
    assert barrel.uuid not in observer.senses.objects
    source = observed.deposit_source
    observer.update_entity_senses(max_distance=2)
    assert observer.senses.spatial_effects[owner.uuid].deposit_source == source
    assert observer.senses.spatial_effects[owner.uuid].anchor_position == (3, 3)


def test_older_material_records_leave_unknown_source_unspecified(world: Game) -> None:
    barrel, attacker = barrel_and_attacker(world, "water")
    break_barrel(barrel, attacker)
    owner, = get_map().get_spatial_conditions()
    observed = owner.get_spatial_observation(AREA, observer_uuid=attacker.uuid)
    assert observed is not None
    prior_record = observed.model_dump(mode="json")
    prior_record.pop("deposit_source")
    restored = PerceivedSpatialEffect.model_validate(prior_record)
    assert restored.deposit_source is None and restored.positions == observed.positions
    old_injury = ResidueContribution.model_validate({"ellipses": [], "amount": 1})
    assert old_injury.deposit_source is None
