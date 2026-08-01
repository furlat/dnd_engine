"""Server-owned normalization of catalog selections into exact recipes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from uuid import UUID

from dnd.content_system.builtin_character_builds import (
    DEFAULT_CHARACTER_RULESET_DIGEST,
)
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from dnd.core.content.encounters import (
    EncounterCompatibilityReport,
    EncounterRecipe,
    EncounterRosterMember,
    EncounterRosterRecipe,
    EncounterRosterSlot,
    OwnedCharacterRosterSource,
    RosterControllerKind,
    RosterMemberControllerOverride,
)
from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS_BY_ID,
    AUTHORED_ROSTER_RECIPES_BY_ID,
)
from dnd.scenarios.encounter_compatibility import (
    check_encounter_compatibility,
)
from dnd.scenarios.battlefield_catalog import get_battlefield
from server.api_models import (
    GameCreationAuthoredRosterSelection,
    GameCreationComposeRequest,
    GameCreationOwnedCharacterRosterSelection,
    GameCreationSavedRosterSelection,
)
from server.game_directory.contracts import SavedEncounterRosterRecord


class GameCreationCompositionError(ValueError):
    """One exact normalization failure suitable for public route mapping."""


class CharacterRulesetMismatchError(GameCreationCompositionError):
    """Encounter characters were authored under incompatible rulesets."""


def shared_deployment_ruleset_digest(
    deployments: Mapping[UUID, CharacterDeploymentSnapshot],
) -> str:
    """Return the already-authored ruleset identity shared by deployments.

    This does not derive or hash character rules.  The dependency-neutral
    progression layer owns that operation; encounter composition only verifies
    that the selected durable characters agree on its stored result.
    """
    ruleset_digests = {
        deployment.expected_ruleset_digest
        for deployment in deployments.values()
    }
    if len(ruleset_digests) > 1:
        raise CharacterRulesetMismatchError(
            "One encounter cannot mix character ruleset digests",
        )
    return next(iter(ruleset_digests), DEFAULT_CHARACTER_RULESET_DIGEST)


def required_character_ids(
    request_or_recipe: GameCreationComposeRequest | EncounterRecipe,
    *,
    saved_rosters: Mapping[str, SavedEncounterRosterRecord] | None = None,
) -> tuple[UUID, ...]:
    """Return each durable character in stable recipe/request order."""
    if isinstance(request_or_recipe, GameCreationComposeRequest):
        requested_saved = saved_rosters or {}
        rows: list[UUID] = []
        for slot in request_or_recipe.roster_slots:
            selection = slot.roster
            if isinstance(
                selection,
                GameCreationOwnedCharacterRosterSelection,
            ):
                rows.extend(selection.character_ids)
            elif isinstance(selection, GameCreationSavedRosterSelection):
                record = _require_saved_roster(
                    selection,
                    requested_saved,
                )
                rows.extend(
                    member.source.character_id
                    for member in record.recipe.members
                    if isinstance(
                        member.source,
                        OwnedCharacterRosterSource,
                    )
                )
    else:
        rows = [
            member.source.character_id
            for slot in request_or_recipe.roster_slots
            for member in slot.roster.members
            if isinstance(member.source, OwnedCharacterRosterSource)
        ]
    ordered = tuple(rows)
    if len(ordered) != len(set(ordered)):
        raise GameCreationCompositionError(
            "an owned character cannot appear more than once in an encounter",
        )
    return ordered


def required_saved_roster_ids(
    request: GameCreationComposeRequest,
) -> tuple[str, ...]:
    """Return selected saved-roster ids once in request order."""
    roster_ids = tuple(
        slot.roster.saved_roster_id
        for slot in request.roster_slots
        if isinstance(slot.roster, GameCreationSavedRosterSelection)
    )
    if len(roster_ids) != len(set(roster_ids)):
        raise GameCreationCompositionError(
            "a saved roster cannot appear more than once in an encounter",
        )
    return roster_ids


def _require_saved_roster(
    selection: GameCreationSavedRosterSelection,
    saved_rosters: Mapping[str, SavedEncounterRosterRecord],
) -> SavedEncounterRosterRecord:
    record = saved_rosters.get(selection.saved_roster_id)
    if record is None:
        raise GameCreationCompositionError(
            f"saved roster {selection.saved_roster_id!r} was not resolved",
        )
    if (
        record.revision != selection.expected_revision
        or record.recipe_digest != selection.expected_recipe_digest
    ):
        raise GameCreationCompositionError(
            f"saved roster {selection.saved_roster_id!r} "
            "changed during composition",
        )
    return record


def owned_character_source(
    snapshot: CharacterDeploymentSnapshot,
) -> OwnedCharacterRosterSource:
    """Freeze one trusted directory snapshot into a recipe source identity."""
    return OwnedCharacterRosterSource(
        character_id=snapshot.character_id,
        expected_character_row_version=snapshot.character_row_version,
        expected_definition_revision=(
            snapshot.definition.definition_revision
        ),
        expected_definition_digest=snapshot.definition.definition_digest,
        expected_holdings_revision=snapshot.holdings.holdings_revision,
        expected_holdings_digest=snapshot.holdings.holdings_digest,
        expected_loadout_revision=snapshot.loadout.loadout_revision,
        expected_loadout_digest=snapshot.loadout.loadout_digest,
        expected_ruleset_digest=snapshot.expected_ruleset_digest,
    )


def character_source_matches_snapshot(
    source: OwnedCharacterRosterSource,
    snapshot: CharacterDeploymentSnapshot,
) -> bool:
    """Check exact optimistic heads before preview or runtime replacement."""
    return source == owned_character_source(snapshot)


def _owned_member_id(character_id: UUID) -> str:
    return f"character_{character_id.hex}"


def _owned_roster(
    selection: GameCreationOwnedCharacterRosterSelection,
    snapshots: Mapping[UUID, CharacterDeploymentSnapshot],
) -> tuple[EncounterRosterRecipe, tuple[RosterMemberControllerOverride, ...]]:
    members: list[EncounterRosterMember] = []
    member_ids: dict[UUID, str] = {}
    for character_id in selection.character_ids:
        snapshot = snapshots.get(character_id)
        if snapshot is None:
            raise GameCreationCompositionError(
                f"owned character {character_id} was not resolved",
            )
        member_id = _owned_member_id(character_id)
        member_ids[character_id] = member_id
        members.append(EncounterRosterMember(
            member_id=member_id,
            display_name=snapshot.display_name,
            deployment_role=member_id,
            source=owned_character_source(snapshot),
        ))
    overrides = tuple(
        RosterMemberControllerOverride(
            member_id=member_ids[override.character_id],
            controller=RosterControllerKind(override.controller),
            policy_id=override.policy_id,
        )
        for override in selection.member_controller_overrides
    )
    identity_payload = [
        member.source.model_dump(mode="json")
        for member in members
    ]
    identity_digest = hashlib.sha256(
        json.dumps(
            identity_payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    ).hexdigest()
    return (
        EncounterRosterRecipe.create(
            roster_id=f"roster.owned.{identity_digest[:24]}",
            title=selection.title,
            members=tuple(members),
            tags=("owned_characters",),
        ),
        overrides,
    )


def normalize_encounter_recipe(
    request: GameCreationComposeRequest,
    *,
    character_deployments: Mapping[
        UUID,
        CharacterDeploymentSnapshot,
    ] | None = None,
    saved_rosters: Mapping[str, SavedEncounterRosterRecord] | None = None,
) -> tuple[EncounterRecipe, EncounterCompatibilityReport]:
    """Resolve ids and durable heads exactly once into a launch recipe."""
    deployments = character_deployments or {}
    resolved_saved_rosters = saved_rosters or {}
    selected_saved_roster_ids = required_saved_roster_ids(request)
    if set(selected_saved_roster_ids) != set(resolved_saved_rosters):
        raise GameCreationCompositionError(
            "resolved saved rosters do not match the composition request",
        )
    selected_character_ids = required_character_ids(
        request,
        saved_rosters=resolved_saved_rosters,
    )
    if set(selected_character_ids) != set(deployments):
        raise GameCreationCompositionError(
            "resolved character snapshots do not match the requested roster",
        )
    try:
        deployment = AUTHORED_DEPLOYMENTS_BY_ID[request.deployment_id]
        battlefield = get_battlefield(request.battlefield_id)
    except (KeyError, ValueError) as exc:
        raise GameCreationCompositionError(str(exc)) from exc
    if deployment.battlefield_id != battlefield.battlefield_id:
        raise GameCreationCompositionError(
            "selected deployment belongs to another battlefield",
        )

    roster_slots: list[EncounterRosterSlot] = []
    for selection in request.roster_slots:
        roster_selection = selection.roster
        translated_overrides: tuple[
            RosterMemberControllerOverride,
            ...,
        ] = ()
        if isinstance(
            roster_selection,
            GameCreationAuthoredRosterSelection,
        ):
            try:
                roster = AUTHORED_ROSTER_RECIPES_BY_ID[
                    roster_selection.roster_id
                ]
            except KeyError as exc:
                raise GameCreationCompositionError(
                    f"unknown authored roster {roster_selection.roster_id!r}",
                ) from exc
        elif isinstance(
            roster_selection,
            GameCreationOwnedCharacterRosterSelection,
        ):
            if selection.controller_defaults.member_overrides:
                raise GameCreationCompositionError(
                    "owned rosters address controller overrides by "
                    "character_id, not generated member_id",
                )
            roster, translated_overrides = _owned_roster(
                roster_selection,
                deployments,
            )
        else:
            record = _require_saved_roster(
                roster_selection,
                resolved_saved_rosters,
            )
            roster = record.recipe
            for member in roster.members:
                if not isinstance(
                    member.source,
                    OwnedCharacterRosterSource,
                ):
                    continue
                snapshot = deployments.get(member.source.character_id)
                if (
                    snapshot is None
                    or not character_source_matches_snapshot(
                        member.source,
                        snapshot,
                    )
                ):
                    raise GameCreationCompositionError(
                        "saved roster character heads changed during "
                        "composition"
                    )
        defaults = selection.controller_defaults.model_copy(update={
            "member_overrides": (
                selection.controller_defaults.member_overrides
                or translated_overrides
            ),
        })
        roster_slots.append(EncounterRosterSlot(
            roster_slot_id=selection.roster_slot_id,
            roster=roster,
            faction_id=selection.faction_id,
            deployment_zone_id=selection.deployment_zone_id,
            controller_defaults=defaults,
        ))

    request_identity = request.model_dump(mode="json")
    request_identity["roster_slots"] = [
        slot.model_dump(mode="json") for slot in roster_slots
    ]
    recipe_seed = hashlib.sha256(
        json.dumps(
            request_identity,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    ).hexdigest()
    recipe = EncounterRecipe.create(
        encounter_id=f"encounter.composed.{recipe_seed[:24]}",
        title=request.title,
        roster_slots=tuple(roster_slots),
        battlefield_id=request.battlefield_id,
        deployment=deployment,
        opening_policy=request.opening_policy,
        tags=("composed",),
    )
    compatibility = check_encounter_compatibility(
        recipe,
        battlefield,
        available_character_ids=frozenset(
            str(character_id)
            for character_id in deployments
        ),
    )
    return recipe, compatibility


__all__ = [
    "CharacterRulesetMismatchError",
    "GameCreationCompositionError",
    "character_source_matches_snapshot",
    "normalize_encounter_recipe",
    "owned_character_source",
    "required_character_ids",
    "required_saved_roster_ids",
    "shared_deployment_ruleset_digest",
]
