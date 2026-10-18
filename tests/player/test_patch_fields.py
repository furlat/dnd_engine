"""A body or item patch can carry every field of the value it patches.

A field added to `PlayerActor` or `ItemPresentationState` without its patch
field or item component would never reach a seat.
"""

from dataclasses import fields, replace
from typing import get_type_hints
from uuid import uuid4

from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.equipment_types import WeaponSet
from dnd.core.item_types import ItemPresentationState
from dnd.core.life_types import LifeState
from dnd.player.facts import (ActorBirth, ActorChanges, BodyRecord, BodyState, ItemLook, ItemProfile, ItemState,
    PlayerActor, PlayerCharacterSheet, PlayerObservation, PlayerState, PlayerWorld, SheetChanges, SpatialEffectContent,
    SpatialEffectSighting, VisualLoadout)
from dnd.player.audience import PlayerAudience
from dnd.types.item_parts import ItemStateChanges
from dnd.player.projection import _sighting, actor_changes
from dnd.player.reduction import enter_body, joined_effect, observed_actor
from dnd.types.appearance import AppearanceConfig
from dnd.types.senses import PerceivedSpatialEffect


def test_actor_changes_cover_every_body_field():
    assert set(get_type_hints(ActorChanges)) == {row.name for row in fields(PlayerActor)} - {"uuid"}
    body = PlayerActor(uuid=uuid4(), name="Witness", character_body_id=None, creature_content_ref=None,
        appearance=AppearanceConfig(), visual_loadout=VisualLoadout(active_weapon_set=WeaponSet.NONE, layers=()),
        normal_hp=7, maximum_hp=9, temporary_hp=0, life_state=LifeState.ALIVE, armor_class=12)
    first = actor_changes(None, body)
    assert set(first) == set(get_type_hints(ActorChanges))
    acquired = observed_actor(None, PlayerObservation(occurrence=0, actor_uuid=body.uuid, changes=first, contact=None))
    assert acquired == body
    hurt = replace(body, normal_hp=3)
    assert actor_changes(body, hurt) == {"normal_hp": 3}
    assert actor_changes(hurt, hurt) == {}


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
    components = [{row.name for row in fields(value)} for value in (ItemLook, ItemProfile, ItemState)]
    assert sum(len(names) for names in components) == len(set().union(*components))
    assert set().union(*components) == set(ItemPresentationState.model_fields) - {"item_uuid"}


def test_a_sighting_and_its_content_are_every_perceived_effect_field():
    sighting = set(SpatialEffectSighting.model_fields)
    content = {row.name for row in fields(SpatialEffectContent)}
    assert not sighting & content and sighting | content == set(PerceivedSpatialEffect.model_fields)


def test_sheet_changes_cover_every_sheet_field():
    assert set(get_type_hints(SheetChanges)) == {row.name for row in fields(PlayerCharacterSheet)} - {"actor_uuid"}


def test_a_sighting_split_and_joined_back_passes_every_field():
    effect = PerceivedSpatialEffect(content_ref=ContentRef(pack_id="test.patch",
        definition_kind=ContentDefinitionKind.CONDITION, content_id="condition.test.patch",
        content_version=1, definition_contract_hash="0" * 64), name="Fog", description="Thick.",
        positions=((1, 2), (1, 3), (4, 0)), visible_volume_positions=((2, 2),), owner_revision=3)
    sighting = _sighting(effect)
    content = SpatialEffectContent(content_ref=effect.content_ref, name=effect.name, description=effect.description)
    assert sighting.model_fields_set == set(SpatialEffectSighting.model_fields)
    joined = joined_effect(sighting, content)
    assert joined.model_fields_set == set(PerceivedSpatialEffect.model_fields) and joined == effect
