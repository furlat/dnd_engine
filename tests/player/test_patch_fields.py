"""A body or item patch can carry every field of the value it patches.

A field added to `PlayerActor` or `ItemPresentationState` without its patch
field or item component would never reach a seat.
"""

from dataclasses import fields, replace
from typing import get_type_hints
from uuid import uuid4

from dnd.core.equipment_types import WeaponSet
from dnd.core.item_types import ItemPresentationState
from dnd.core.life_types import LifeState
from dnd.player.facts import ActorChanges, ItemLook, ItemProfile, ItemState, PlayerActor, PlayerObservation, VisualLoadout
from dnd.player.projection import actor_changes
from dnd.player.reduction import observed_actor
from dnd.types.appearance import AppearanceConfig


def test_actor_changes_cover_every_body_field():
    assert set(get_type_hints(ActorChanges)) == {row.name for row in fields(PlayerActor)} - {"uuid"}
    body = PlayerActor(uuid=uuid4(), name="Witness", character_body_id=None, creature_content_ref=None,
        appearance=AppearanceConfig(), visual_loadout=VisualLoadout(active_weapon_set=WeaponSet.NONE, layers=()),
        normal_hp=7, maximum_hp=9, temporary_hp=0, life_state=LifeState.ALIVE, armor_class=12)
    first = actor_changes(None, body)
    assert set(first) == set(get_type_hints(ActorChanges))
    acquired = observed_actor(None, PlayerObservation(event_uuid=uuid4(), actor_uuid=body.uuid, changes=first, contact=None))
    assert acquired == body
    hurt = replace(body, normal_hp=3)
    assert actor_changes(body, hurt) == {"normal_hp": 3}
    assert actor_changes(hurt, hurt) == {}


def test_item_components_partition_every_item_field():
    components = [{row.name for row in fields(value)} for value in (ItemLook, ItemProfile, ItemState)]
    assert sum(len(names) for names in components) == len(set().union(*components))
    assert set().union(*components) == set(ItemPresentationState.model_fields) - {"item_uuid"}
