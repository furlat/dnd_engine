"""Durable owner-scoped saved roster and encounter contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import pytest

from dnd.core.content.encounters import EncounterRecipe, EncounterRosterRecipe
from dnd.scenarios.encounter_catalog import (
    AUTHORED_ENCOUNTER_RECIPES,
    AUTHORED_ROSTER_RECIPES,
)
from server.game_directory.contracts import (
    PrincipalCreate,
    PrincipalKind,
    SavedEncounterCreate,
    SavedEncounterReplace,
    SavedEncounterRosterCreate,
    SavedEncounterRosterReplace,
)
from server.game_directory.errors import NotFoundError, StaleVersionError
from server.game_directory.repository import GameDirectoryRepository


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
PEPPER = b"saved-encounter-directory"


def _open(path: Path) -> GameDirectoryRepository:
    return GameDirectoryRepository(
        path,
        capability_pepper=PEPPER,
        clock=lambda: NOW,
    )


def _saved_roster(roster_id: str, title: str) -> EncounterRosterRecipe:
    source = AUTHORED_ROSTER_RECIPES[0]
    return EncounterRosterRecipe.create(
        roster_id=roster_id,
        title=title,
        members=source.members,
        tags=("saved",),
        required_battlefield_capabilities=(
            source.required_battlefield_capabilities
        ),
        forbidden_battlefield_capabilities=(
            source.forbidden_battlefield_capabilities
        ),
    )


def _saved_encounter(encounter_id: str, title: str) -> EncounterRecipe:
    source = AUTHORED_ENCOUNTER_RECIPES[0]
    return EncounterRecipe.create(
        encounter_id=encounter_id,
        title=title,
        roster_slots=source.roster_slots,
        battlefield_id=source.battlefield_id,
        deployment=source.deployment,
        opening_policy=source.opening_policy,
        notable_positions=source.notable_positions,
        tags=("saved",),
    )


def test_saved_roster_and_encounter_are_owner_scoped_cas_documents(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    owner = repository.create_principal(PrincipalCreate(
        principal_kind=PrincipalKind.HUMAN,
        display_name="Owner",
    ))
    other = repository.create_principal(PrincipalCreate(
        principal_kind=PrincipalKind.HUMAN,
        display_name="Other",
    ))

    roster = _saved_roster("roster.saved.party", "Saved Party")
    saved_roster_id = "saved.roster.party"
    created_roster = repository.create_saved_encounter_roster(
        SavedEncounterRosterCreate(
            saved_roster_id=saved_roster_id,
            owner_principal_id=owner.principal_id,
            title=roster.title,
            recipe=roster,
        ),
    )
    encounter = _saved_encounter(
        "encounter.saved.duel",
        "Saved Duel",
    )
    saved_encounter_id = "saved.encounter.duel"
    created_encounter = repository.create_saved_encounter(
        SavedEncounterCreate(
            saved_encounter_id=saved_encounter_id,
            owner_principal_id=owner.principal_id,
            title=encounter.title,
            recipe=encounter,
        ),
    )

    assert repository.list_saved_encounter_rosters(
        owner.principal_id,
    ) == (created_roster,)
    assert repository.list_saved_encounters(
        owner.principal_id,
    ) == (created_encounter,)
    with pytest.raises(NotFoundError):
        repository.get_saved_encounter_roster(
            other.principal_id,
            saved_roster_id,
        )
    with pytest.raises(NotFoundError):
        repository.get_saved_encounter(
            other.principal_id,
            saved_encounter_id,
        )

    replacement_roster = _saved_roster(
        "roster.saved.party.revision-2",
        "Renamed Party",
    )
    replaced_roster = repository.replace_saved_encounter_roster(
        owner.principal_id,
        saved_roster_id,
        SavedEncounterRosterReplace(
            title=replacement_roster.title,
            recipe=replacement_roster,
            expected_revision=created_roster.revision,
            expected_recipe_digest=created_roster.recipe_digest,
        ),
    )
    assert replaced_roster.saved_roster_id == saved_roster_id
    assert replaced_roster.recipe.roster_id != roster.roster_id
    assert replaced_roster.revision == 2
    with pytest.raises(StaleVersionError):
        repository.replace_saved_encounter_roster(
            owner.principal_id,
            saved_roster_id,
            SavedEncounterRosterReplace(
                title=replacement_roster.title,
                recipe=replacement_roster,
                expected_revision=1,
                expected_recipe_digest=created_roster.recipe_digest,
            ),
        )

    replacement_encounter = _saved_encounter(
        "encounter.saved.duel.revision-2",
        "Renamed Duel",
    )
    replaced_encounter = repository.replace_saved_encounter(
        owner.principal_id,
        saved_encounter_id,
        SavedEncounterReplace(
            title=replacement_encounter.title,
            recipe=replacement_encounter,
            expected_revision=created_encounter.revision,
            expected_recipe_digest=created_encounter.recipe_digest,
        ),
    )
    assert replaced_encounter.saved_encounter_id == saved_encounter_id
    assert replaced_encounter.recipe.encounter_id != encounter.encounter_id
    assert replaced_encounter.revision == 2
    repository.close()

    reopened = _open(database_path)
    assert reopened.get_saved_encounter_roster(
        owner.principal_id,
        saved_roster_id,
    ) == replaced_roster
    assert reopened.get_saved_encounter(
        owner.principal_id,
        saved_encounter_id,
    ) == replaced_encounter
    reopened.delete_saved_encounter_roster(
        owner.principal_id,
        saved_roster_id,
        expected_revision=replaced_roster.revision,
        expected_recipe_digest=replaced_roster.recipe_digest,
    )
    reopened.delete_saved_encounter(
        owner.principal_id,
        saved_encounter_id,
        expected_revision=replaced_encounter.revision,
        expected_recipe_digest=replaced_encounter.recipe_digest,
    )
    assert reopened.list_saved_encounter_rosters(owner.principal_id) == ()
    assert reopened.list_saved_encounters(owner.principal_id) == ()
    reopened.close()
