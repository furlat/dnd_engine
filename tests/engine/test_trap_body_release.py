"""Real grounded trap injury reaches the existing material-response handler."""

from uuid import uuid4

import pytest

from dnd.actions import Move
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.gas_traps import GasCloudSpec, materialize_gas_vent
from dnd.spatial.mechanisms import (
    AreaGeometry, CRUSHER_CONTENT_REF, DART_LAUNCHER_CONTENT_REF, LaneGeometry, SWINGING_BLADE_CONTENT_REF,
    materialize_finite_trap,
)
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.types.controls import ActivationLink
from dnd.types.traps import TrapDamage, TrapPayload


@pytest.mark.parametrize("damage_type", (
    DamageType.PIERCING, DamageType.SLASHING, DamageType.BLUDGEONING, DamageType.POISON,
))
@pytest.mark.parametrize("outcome", ("injury", "saved", "immune", "temporary-hp"))
def test_trap_damage_releases_blood_only_when_normal_hp_is_lost(damage_type, outcome):
    reset_engine_runtime(grid_size=(6, 4))
    game = Game()
    try:
        target = Entity.create(uuid4(), "Humanoid traveler", config=EntityConfig(position=(1, 1),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")],
                immunities=[damage_type] if outcome == "immune" else [],
                temporary_hit_points=8 if outcome == "temporary-hp" else 0)))
        setup_standard_actions(target)
        install_body_response(target, BLOOD_BODY_RESPONSE)
        target.compose_entity()
        game.deploy_entity(target, target.position)
        if damage_type is DamageType.POISON:
            trap = materialize_gas_vent((2, 1), gas=GasCloudSpec(radius_feet=0,
                half_damage_on_success=False, poisoned_duration_rounds=None))
        else:
            reference = {DamageType.PIERCING: DART_LAUNCHER_CONTENT_REF,
                         DamageType.SLASHING: SWINGING_BLADE_CONTENT_REF,
                         DamageType.BLUDGEONING: CRUSHER_CONTENT_REF}[damage_type]
            ranged = damage_type is DamageType.PIERCING
            trap = materialize_finite_trap((2, 3) if ranged else (2, 1),
                geometry=LaneGeometry(range_feet=10) if ranged else AreaGeometry(),
                direction=(0, -1) if ranged else (1, 0), content_ref=reference,
                payload=TrapPayload(damages=(TrapDamage(dice_count=1, dice_sides=6, damage_type=damage_type),)))
        materialize_pressure_plate({(2, 1)}, ActivationLink(target_condition_uuid=trap.uuid))
        target.update_entity_senses()
        cursor = EventQueue.event_cursor()
        with fixed_dice_faces(20 if outcome == "saved" else 1, 4):
            command = Move(source_entity_uuid=target.uuid, end_position=(2, 1),
                path=[(1, 1), (2, 1)], prefer_safe=False).apply()
        assert command is not None and not command.canceled and target.position == (2, 1)
        injuries = [event for _, event in EventQueue.iter_events_since(cursor)
                    if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION]
        assert len(injuries) == int(outcome in ("injury", "temporary-hp"))
        assert target.get_normal_hp() == (76 if outcome == "injury" else 80)
        for injury in injuries:
            assert injury.damage_type is damage_type and injury.resolution is not None
            assert {component.damage_type for component in injury.resolution.components} == {damage_type}
            assert (injury.body_release is not None) is (outcome == "injury")
            if injury.body_release is not None:
                assert injury.body_release.release_id == "body.blood"
                assert injury.body_release.position == injury.body_release.deposited_position == (2, 1)
                assert any((2, 1) in region.positions for region in injury.body_release.regions)
            ancestor = injury
            while ancestor.parent_event is not None:
                parent = EventQueue.get_event_by_uuid(ancestor.parent_event)
                assert parent is not None
                ancestor = parent
            assert ancestor.lineage_uuid == command.lineage_uuid
        tile = get_map().get_tile(2, 1)
        assert tile is not None
        assert any(residue.residue_id == "residue.blood" for residue in tile.to_world_tile_state().residues) is (
            outcome == "injury")
    finally:
        game.close()
        reset_engine_runtime()
