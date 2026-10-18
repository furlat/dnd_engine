"""A body or item record can carry every field of the value it sends.

A field added to `PlayerActor` or `ItemPresentationState` without its record
field or item component would never reach a seat.
"""

from dataclasses import fields
from typing import get_type_hints
from uuid import uuid4

from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.equipment_types import WeaponSet
from dnd.core.item_types import ItemPresentationState
from dnd.core.life_types import LifeState
from dnd.player.facts import (ActorBirth, BodyRecord, BodyState, ItemLook, ItemProfile, ItemState, LightChanges,
    LightRow, PlayerActor, PlayerCharacterSheet, PlayerItem, PlayerState, PlayerWorld, SheetChanges,
    SightingChanges, SpatialEffectContent, SpatialEffectSighting, VisualLoadout)
from dnd.player.audience import PlayerAudience
from dnd.types.item_parts import ItemStateChanges
from dnd.player.projection import _sighting
from dnd.player.reduction import _sighted_effect, enter_body
from dnd.types.appearance import AppearanceConfig
from dnd.types.senses import PerceivedSpatialEffect


def test_a_body_record_carries_every_body_field_once():
    birth = {row.name for row in fields(ActorBirth)}
    body = {row.name for row in fields(BodyState)}
    # The last visual position is perception (contacts set it); presence ends only with a lifetime.
    assert not birth & body and birth | body == {row.name for row in fields(PlayerActor)} - {
        "uuid", "last_visual_position", "present"}
    seat = PlayerState(generation=uuid4(), observer_uuid=uuid4(), world=PlayerWorld(battlefield_id="patch",
        battlefield_name="Patch", bounds=(0, 0, 1, 1), width=2, height=2))
    seat.audience = PlayerAudience(observers=(seat.observer_uuid,), controlled=(seat.observer_uuid,))
    record = BodyRecord(occurrence=0, actor_uuid=uuid4(), birth=ActorBirth(name="Witness", character_body_id=None,
        creature_content_ref=None, appearance=AppearanceConfig()), body=BodyState(
        visual_loadout=VisualLoadout(active_weapon_set=WeaponSet.NONE, layers=()), normal_hp=7, maximum_hp=9,
        temporary_hp=0, life_state=LifeState.ALIVE, armor_class=12))
    enter_body(seat, record)
    assert seat.actors[record.actor_uuid] == PlayerActor(uuid=record.actor_uuid, name="Witness",
        character_body_id=None, creature_content_ref=None, appearance=AppearanceConfig(),
        visual_loadout=VisualLoadout(active_weapon_set=WeaponSet.NONE, layers=()), normal_hp=7, maximum_hp=9,
        temporary_hp=0, life_state=LifeState.ALIVE, armor_class=12)


def test_item_state_changes_name_every_state_field():
    assert set(get_type_hints(ItemStateChanges)) == {row.name for row in fields(ItemState)}


def test_item_components_partition_every_item_field():
    # The static look and profile, the controller's state, and the effects the seat's item record holds.
    components = [{row.name for row in fields(value)} for value in (ItemLook, ItemProfile, ItemState)]
    components.append({"item_effects"})
    assert sum(len(names) for names in components) == len(set().union(*components))
    assert set().union(*components) == set(ItemPresentationState.model_fields) - {"item_uuid"}
    assert "effects" in {row.name for row in fields(PlayerItem)}


def test_a_sighting_and_its_content_are_every_perceived_effect_field():
    # The effect's native revision stays on the server: the seat is sent its changes, not their count.
    sighting = set(SpatialEffectSighting.model_fields)
    content = {row.name for row in fields(SpatialEffectContent)}
    assert not sighting & content and sighting | content == set(PerceivedSpatialEffect.model_fields) - {
        "owner_revision"}


def test_a_sighting_patch_can_change_every_sighting_field():
    # The cell sets and volume surfaces change through the patch's added and removed sets; the rest by value.
    assert set(get_type_hints(SightingChanges)) | {"positions", "visible_volume_positions",
        "upper_volume_surfaces"} == set(SpatialEffectSighting.model_fields)


def test_a_light_patch_can_change_every_light_row_field():
    assert set(get_type_hints(LightChanges)) | {"source"} == {row.name for row in fields(LightRow)}


def test_sheet_changes_cover_every_sheet_field():
    assert set(get_type_hints(SheetChanges)) == {row.name for row in fields(PlayerCharacterSheet)} - {"actor_uuid"}


def test_a_sighting_split_and_joined_back_passes_every_field():
    effect = PerceivedSpatialEffect(content_ref=ContentRef(pack_id="test.patch",
        definition_kind=ContentDefinitionKind.CONDITION, content_id="condition.test.patch",
        content_version=1, definition_contract_hash="0" * 64), name="Fog", description="Thick.",
        positions=((1, 2), (1, 3), (4, 0)), visible_volume_positions=((2, 2),), owner_revision=3)
    sighting = _sighting(effect, True)
    content = SpatialEffectContent(content_ref=effect.content_ref, name=effect.name, description=effect.description)
    assert sighting.model_fields_set == set(SpatialEffectSighting.model_fields)
    joined = _sighted_effect(sighting, content)
    assert joined.model_fields_set == set(PerceivedSpatialEffect.model_fields)
    assert joined == effect.model_copy(update={"owner_revision": None})
