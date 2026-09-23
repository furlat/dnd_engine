"""Retained elemental state chooses one pair, including its removal tail."""

from dataclasses import replace

import pytest

from dnd.core.creature_types import DamageType
from dnd.core.events import EventQueue
from dnd.spells.abjuration import ProtectionFromEnergy
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.condition_animation import resolve_condition_appearance
from game.condition_media_lifetime import register_condition_lifetimes, sample_condition_lifetimes
from game.condition_types import ConditionRecipe
from game.player_reduction import decode_player_sequence, reduce_lineage
from tests.game.test_spell14_native_facts import actors, saved_views


ELEMENTS = (DamageType.ACID, DamageType.COLD, DamageType.FIRE, DamageType.LIGHTNING, DamageType.THUNDER)
PROTECTION = "condition.spell.protection_from_energy"


@pytest.fixture(scope="module")
def authored_selection_fixture():
    # Known exported media exercise selection/lifetime before Protection's new
    # art arrives. Ten unique logical IDs share these two explicit test donors.
    data = load_animation_data()
    donor = data.condition_recipes["condition.spell.bless"]
    definition = data.condition_recipes[PROTECTION].definitionRef
    media = dict(data.condition_media)
    layers = []
    for element in ELEMENTS:
        for side, layer in zip(("back", "front"), donor.persistent.layers, strict=True):
            identity = f"test.protection.{element.value}.{side}"
            layers.append(layer.model_copy(update={
                "id": identity, "assetId": identity, "whenEnergyType": element}))
            media[identity] = replace(data.condition_media[layer.assetId], removal_fade_ms=400)
    recipe = ConditionRecipe.model_validate({**donor.model_dump(), "definitionRef": definition,
        "persistent": donor.persistent.model_copy(update={"layers": tuple(layers)}),
        "application": donor.application.model_copy(update={"effects": ()}),
        "removal": donor.removal.model_copy(update={"effects": ()})})
    return replace(data, condition_recipes={**data.condition_recipes, PROTECTION: recipe}, condition_media=media)


def resolved(state, data):
    return {str(actor.uuid): resolve_condition_appearance(actor.conditions, data.condition_recipes,
        data.condition_media) for actor in state.actors.values()}


@pytest.mark.parametrize("element", ELEMENTS)
def test_native_saved_energy_selects_and_removes_only_its_registered_pair(authored_selection_fixture, element):
    data = authored_selection_fixture
    caster, target = actors()
    start = EventQueue.event_cursor()
    cast = ProtectionFromEnergy(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        chosen_energy_type=element, template=False).apply()
    assert cast is not None and not cast.canceled
    owner = target.active_conditions["Protection from Energy"].uuid
    caster.remove_condition("Concentrating")
    assert "Protection from Energy" not in target.active_conditions
    identity = str(target.uuid)
    expected = {f"test.protection.{element.value}.{side}" for side in ("back", "front")}
    for payload in saved_views((caster, target), start).values():
        state, heads = decode_player_sequence(payload)
        records, clock, witnessed_application, witnessed_removal = {}, 100., False, False
        for head in heads:
            group = bind_choreography(state, head, data)
            records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                lineage=head, choreography=group)
            after = reduce_lineage(state, head)
            active = any(member.condition_uuid == owner for member in after.actors[target.uuid].conditions)
            if active:
                selected = resolved(after, data)[identity].layers
                assert {layer.layer.assetId for layer in selected} == expected
                assert {layer.owner_uuid for layer in selected} == {owner}
                assert {layer.layer.whenEnergyType for layer in selected} == {element}
                # Cold observation must select the same pair without replaying application.
                cold_dates = register_condition_lifetimes({}, after, data, absolute_start_ms=clock + 1)
                cold = sample_condition_lifetimes(resolved(after, data), cold_dates, data, clock + 2)[identity]
                assert {layer.layer.assetId for layer in cold.layers} == expected
                assert not any(layer.application for layer in cold.layers)
                witnessed_application = True
            record = records.get(owner)
            if record is not None and record.removed_ms is not None:
                assert set(record.removed_layers) == expected
                at = record.removed_ms
                fading = sample_condition_lifetimes(resolved(after, data), records, data, at + 200)[identity]
                assert {layer.layer.assetId for layer in fading.layers} == expected
                assert all(layer.alpha == .5 for layer in fading.layers)
                assert not sample_condition_lifetimes(resolved(after, data), records, data, at + 400)[identity].layers
                witnessed_removal = True
            state = after
            clock += group.complete_ms + 25
        assert witnessed_application and witnessed_removal
