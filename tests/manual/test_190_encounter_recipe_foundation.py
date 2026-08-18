"""Dependency-neutral authored encounter value validation."""

import pytest
from pydantic import ValidationError

from dnd.content.scenarios.scenario_definitions import (
    DirectEntitySource,
    EncounterDefinition,
    EncounterDeploymentDefinition,
    EncounterDeploymentZone,
    EncounterRosterDefinition,
    EncounterRosterMember,
    EncounterRosterSlot,
    FixedRosterOpeningPolicy,
    InitiativeOpeningPolicy,
)


def _roster(roster_id: str, member_id: str) -> EncounterRosterDefinition:
    return EncounterRosterDefinition(
        roster_id=roster_id,
        title=roster_id,
        members=(EncounterRosterMember(
            member_id=member_id,
            display_name=member_id,
            deployment_role=member_id,
            source=DirectEntitySource(entity_id="monster.goblin"),
        ),),
    )


def _deployment() -> EncounterDeploymentDefinition:
    return EncounterDeploymentDefinition(
        deployment_id="deployment.test_duel",
        title="Test Duel",
        battlefield_id="battlefield.test_room",
        zones=(
            EncounterDeploymentZone(zone_id="west", ordered_slots=((1, 1),)),
            EncounterDeploymentZone(zone_id="east", ordered_slots=((8, 8),)),
        ),
    )


def _slots() -> tuple[EncounterRosterSlot, EncounterRosterSlot]:
    return (
        EncounterRosterSlot(
            roster_slot_id="first_party",
            roster=_roster("roster.test_first", "first"),
            faction_id="first",
            deployment_zone_id="west",
            participant_name="First",
        ),
        EncounterRosterSlot(
            roster_slot_id="second_party",
            roster=_roster("roster.test_second", "second"),
            faction_id="second",
            deployment_zone_id="east",
            participant_name="Second",
        ),
    )


def test_authored_encounter_round_trip_contains_no_digest_or_content_ref() -> None:
    encounter = EncounterDefinition(
        encounter_id="encounter.test_duel",
        title="Test Duel",
        roster_slots=_slots(),
        battlefield_id="battlefield.test_room",
        deployment=_deployment(),
        opening_policy=FixedRosterOpeningPolicy(roster_slot_id="first_party"),
    )

    payload = encounter.model_dump(mode="json")
    assert EncounterDefinition.model_validate(payload) == encounter
    assert "digest" not in repr(payload)
    assert "content_ref" not in repr(payload)


def test_encounter_validates_slot_zone_and_opening_references() -> None:
    deployment = _deployment()
    slots = _slots()
    bad_zone = slots[0].model_copy(update={"deployment_zone_id": "missing"})

    with pytest.raises(ValidationError, match="deployment zone"):
        EncounterDefinition(
            encounter_id="encounter.bad_zone",
            title="Bad Zone",
            roster_slots=(bad_zone, slots[1]),
            battlefield_id=deployment.battlefield_id,
            deployment=deployment,
            opening_policy=InitiativeOpeningPolicy(),
        )

    with pytest.raises(ValidationError, match="opening roster slot"):
        EncounterDefinition(
            encounter_id="encounter.bad_opening",
            title="Bad Opening",
            roster_slots=slots,
            battlefield_id=deployment.battlefield_id,
            deployment=deployment,
            opening_policy=FixedRosterOpeningPolicy(roster_slot_id="missing"),
        )


def test_deployment_rejects_duplicate_coordinates_across_zones() -> None:
    with pytest.raises(ValidationError, match="coordinate"):
        EncounterDeploymentDefinition(
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
