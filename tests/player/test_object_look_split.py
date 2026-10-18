"""A floor item travels as its look (once per uuid) and its state: joining them gives the item back (world codec)."""

from dataclasses import fields
from uuid import uuid4

from dnd.core.item_types import DoorMechanism, DoorSwing, ItemIntegrity, ItemRemnantState
from dnd.player.facts import FloorItem
from dnd.player.world_columns import join_floor_item, split_floor_item
from dnd.player.facts import ObjectLook, ObjectState
from dnd.types.physical_access import ContactPassage
from dnd.types.residues import ObjectResidueState
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.world import CardinalDirection


def check(item: FloorItem) -> None:
    look, state = split_floor_item(item)
    assert join_floor_item(look, state) == item


def test_a_plain_item_round_trips():
    check(FloorItem(item_uuid=uuid4(), item_id="item.box", name="Box", visual_item_name="box", visual_variant_id=None,
        map_char="b", boundary_structure=None, is_open=None, is_lit=None))


def test_an_item_with_every_field_set_round_trips():
    check(FloorItem(item_uuid=uuid4(), item_id="item.door", name="Door", visual_item_name="door",
        visual_variant_id="oak", map_char="+", boundary_structure=None, is_open=True, is_lit=False,
        very_bright_radius_feet=5, bright_radius_feet=10, dim_radius_feet=20, stack_count=3, is_pickable=False,
        blocks_propagation=True, contact_passage=ContactPassage.STRUCTURAL, supported_by_uuid=uuid4(),
        is_engaged=True, surface_residues=(ObjectResidueState(condition_uuid=uuid4(), residue_id="residue.blood",
            description="Blood", faces=(CardinalDirection.NORTH,)),),
        current_hit_points=4, maximum_hit_points=9, concentration_capacity=1,
        door_mechanism=next(iter(DoorMechanism)),
        door_swing=next(iter(DoorSwing)), remnant_state=ItemRemnantState(door_open=True),
        integrity=ItemIntegrity.DESTROYED, destruction_outcome="splintered", construction_owner_uuid=uuid4(),
        construction_suppressions=(SpellSuppression(provider_uuid=uuid4(), positions=((1, 2),)),),
        known_to_creator=True))


def test_look_and_state_cover_every_floor_item_field_once():
    look = {row.name for row in fields(ObjectLook)}
    state = {row.name for row in fields(ObjectState)}
    assert not look & state
    assert look | state == {row.name for row in fields(FloorItem)}
