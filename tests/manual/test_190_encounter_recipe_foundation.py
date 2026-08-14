"""Dependency-neutral encounter recipe contracts and integrity regressions."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.core.content.encounters import (
    AuthoredCreatureRosterSource,
    EncounterDeploymentSpec,
    EncounterDeploymentZone,
    EncounterRecipe,
    EncounterRosterMember,
    EncounterRosterRecipe,
    EncounterRosterSlot,
    FixedRosterOpeningPolicy,
    InitiativeOpeningPolicy,
    OwnedCharacterRosterSource,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.recipes import ContentRecipe


def _creature_recipe(content_id: str = "creature.test_dummy") -> ContentRecipe:
    ref = ContentRef(
        pack_id="test.encounters",
        definition_kind=ContentDefinitionKind.CREATURE,
        content_id=content_id,
        content_version=1,
        definition_contract_hash="a" * 64,
    )
    return ContentRecipe.create(ref=ref, parameters={"variant": "base"})


def _roster(
    roster_id: str,
    member_id: str,
    *,
    character: bool = False,
) -> EncounterRosterRecipe:
    source = (
        OwnedCharacterRosterSource(
            character_id=uuid4(),
            expected_character_row_version=1,
            expected_definition_revision=1,
            expected_definition_digest="b" * 64,
            expected_holdings_revision=1,
            expected_holdings_digest="c" * 64,
            expected_loadout_revision=1,
            expected_loadout_digest="d" * 64,
            expected_ruleset_digest="e" * 64,
        )
        if character
        else AuthoredCreatureRosterSource(recipe=_creature_recipe())
    )
    return EncounterRosterRecipe.create(
        roster_id=roster_id,
        title=roster_id,
        members=(
            EncounterRosterMember(
                member_id=member_id,
                display_name=member_id,
                deployment_role=member_id,
                source=source,
            ),
        ),
    )


def _deployment() -> EncounterDeploymentSpec:
    return EncounterDeploymentSpec.create(
        deployment_id="deployment.test_duel",
        title="Test Duel",
        battlefield_id="battlefield.test_room",
        zones=(
            EncounterDeploymentZone(
                zone_id="west",
                ordered_slots=((1, 1),),
            ),
            EncounterDeploymentZone(
                zone_id="east",
                ordered_slots=((8, 8),),
            ),
        ),
    )


def test_roster_and_encounter_digests_authenticate_every_nested_fact() -> None:
    first = _roster("roster.test_first", "first")
    second = _roster("roster.test_second", "second")
    deployment = _deployment()
    encounter = EncounterRecipe.create(
        encounter_id="encounter.test_duel",
        title="Test Duel",
        roster_slots=(
            EncounterRosterSlot(
                roster_slot_id="first_party",
                roster=first,
                faction_id="first",
                deployment_zone_id="west",
                participant_name="First",
            ),
            EncounterRosterSlot(
                roster_slot_id="second_party",
                roster=second,
                faction_id="second",
                deployment_zone_id="east",
                participant_name="Second",
            ),
        ),
        battlefield_id="battlefield.test_room",
        deployment=deployment,
        opening_policy=FixedRosterOpeningPolicy(
            roster_slot_id="first_party",
        ),
    )

    round_trip = EncounterRecipe.model_validate(
        encounter.model_dump(mode="json"),
    )
    assert round_trip == encounter

    tampered = encounter.model_dump(mode="json")
    tampered["roster_slots"][0]["faction_id"] = "other"
    with pytest.raises(ValidationError, match="recipe_digest"):
        EncounterRecipe.model_validate(tampered)


def test_owned_character_is_a_roster_source_not_a_hero_configuration() -> None:
    roster = _roster("roster.test_owned", "owned", character=True)

    assert isinstance(roster.members[0].source, OwnedCharacterRosterSource)
    payload = roster.model_dump(mode="json")
    serialized = repr(payload)
    assert "hero_configuration" not in serialized
    assert "monster_configuration" not in serialized
    assert "side_a" not in serialized
    assert "side_b" not in serialized


def test_encounter_validates_slot_zone_and_opening_references() -> None:
    first = _roster("roster.test_first", "first")
    second = _roster("roster.test_second", "second")
    deployment = _deployment()

    with pytest.raises(ValidationError, match="deployment zone"):
        EncounterRecipe.create(
            encounter_id="encounter.bad_zone",
            title="Bad Zone",
            roster_slots=(
                EncounterRosterSlot(
                    roster_slot_id="party",
                    roster=first,
                    faction_id="first",
                    deployment_zone_id="missing",
                    participant_name="First",
                ),
                EncounterRosterSlot(
                    roster_slot_id="opposition",
                    roster=second,
                    faction_id="second",
                    deployment_zone_id="east",
                    participant_name="Second",
                ),
            ),
            battlefield_id=deployment.battlefield_id,
            deployment=deployment,
            opening_policy=InitiativeOpeningPolicy(),
        )

    with pytest.raises(ValidationError, match="opening roster slot"):
        EncounterRecipe.create(
            encounter_id="encounter.bad_opening",
            title="Bad Opening",
            roster_slots=(
                EncounterRosterSlot(
                    roster_slot_id="party",
                    roster=first,
                    faction_id="first",
                    deployment_zone_id="west",
                    participant_name="First",
                ),
                EncounterRosterSlot(
                    roster_slot_id="opposition",
                    roster=second,
                    faction_id="second",
                    deployment_zone_id="east",
                    participant_name="Second",
                ),
            ),
            battlefield_id=deployment.battlefield_id,
            deployment=deployment,
            opening_policy=FixedRosterOpeningPolicy(
                roster_slot_id="missing",
            ),
        )


def test_deployment_rejects_duplicate_coordinates_across_zones() -> None:
    with pytest.raises(ValidationError, match="coordinate"):
        EncounterDeploymentSpec.create(
            deployment_id="deployment.bad_overlap",
            title="Bad Overlap",
            battlefield_id="battlefield.test_room",
            zones=(
                EncounterDeploymentZone(
                    zone_id="west",
                    ordered_slots=((1, 1),),
                ),
                EncounterDeploymentZone(
                    zone_id="east",
                    ordered_slots=((1, 1),),
                ),
            ),
        )
