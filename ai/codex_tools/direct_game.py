"""Canonical game startup transport for direct Codex artifact capture."""

from __future__ import annotations

from typing import Literal, Optional

import httpx
from pydantic import BaseModel, ConfigDict

from dnd.core.content.encounters import EncounterRecipe


class _GameCreationCatalog(BaseModel):
    """Catalog fields required to select one authored encounter."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    schema_version: Literal[3]
    encounter_recipes: tuple[EncounterRecipe, ...]


class _ComposedGame(BaseModel):
    """Normalized recipe identity required by exact game startup."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    schema_version: Literal[1]
    content_set_digest: str
    ruleset_digest: str
    recipe: EncounterRecipe


class _PreparedEntityAssignment(BaseModel):
    """Prepared controller identity required to join a Codex session."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    entity_uuid: str
    controller: Literal["human", "ai", "codex"]
    codex_session_id: Optional[str] = None
    takeover_claim_id: Optional[str] = None


class _PreparedRoster(BaseModel):
    """Prepared roster fields needed to find the direct Codex assignment."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    roster_slot_id: str
    entity_assignments: tuple[_PreparedEntityAssignment, ...]


class _PreparedGame(BaseModel):
    """Prepared game fields required by the join and activation sequence."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    schema_version: Literal[2]
    status: Literal["prepared"]
    recipe_digest: str
    encounter_uuid: str
    game_id: str
    rosters: tuple[_PreparedRoster, ...]


class _JoinedGame(BaseModel):
    """Join acknowledgement used to verify subjective ownership."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    success: Literal[True]
    game_id: str
    session_id: str
    controlled_entities: tuple[str, ...]


class _ReplicationProtocol(BaseModel):
    """Source identities required by the activation barrier."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    source_stream_id: str
    generation_id: str


class _ReplicationPerspective(BaseModel):
    """Subjective authority identity required by the activation barrier."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    perspective_epoch_id: str


class _ReplicationBootstrap(BaseModel):
    """Exact activation identities returned by replication bootstrap."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    protocol: _ReplicationProtocol
    perspective: _ReplicationPerspective


class _ActivationResult(BaseModel):
    """Prepared-to-active acknowledgement."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    status: Literal["activated", "already_active"]
    game_id: str
    encounter_uuid: str


class DirectCodexGameStart(BaseModel):
    """Activated game and Codex authority identities used by artifact capture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    activation_status: Literal["activated", "already_active"]
    encounter_id: str
    encounter_uuid: str
    game_id: str
    session_id: str
    takeover_claim_id: str
    controlled_entity_uuids: tuple[str, ...]


class DirectCodexGameClient:
    """Prepare, join, bootstrap, and activate one Codex-controlled game."""

    def __init__(
        self,
        base_url: str,
        *,
        client: Optional[httpx.Client] = None,
        timeout: float = 30.0,
    ) -> None:
        """Create a transport bound to one running game server."""
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "DirectCodexGameClient":
        """Return this context-managed transport."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Release the internally owned HTTP client."""
        self.close()

    def prepare_join_bootstrap_activate(
        self,
        encounter_id: str,
    ) -> DirectCodexGameStart:
        """Start one exact authored encounter with its second roster on Codex."""
        catalog = _GameCreationCatalog.model_validate(
            self._get_json("/game-creation/catalog"),
        )
        selected = next(
            (
                recipe
                for recipe in catalog.encounter_recipes
                if recipe.encounter_id == encounter_id
            ),
            None,
        )
        if selected is None:
            raise ValueError(f"Unknown encounter: {encounter_id}")

        composed = _ComposedGame.model_validate(
            self._post_json(
                "/game-creation/compose",
                _direct_codex_composition(selected),
            ),
        )
        if composed.recipe.encounter_id != encounter_id:
            raise ValueError("game composition returned a different encounter")
        prepared = _PreparedGame.model_validate(
            self._post_json(
                "/game-creation/start",
                {
                    "expected_content_set_digest": (
                        composed.content_set_digest
                    ),
                    "expected_ruleset_digest": composed.ruleset_digest,
                    "recipe": composed.recipe.model_dump(mode="json"),
                },
            ),
        )
        if prepared.recipe_digest != composed.recipe.recipe_digest:
            raise ValueError("game creation returned a different recipe")

        codex_slot_id = composed.recipe.roster_slots[1].roster_slot_id
        prepared_by_slot = {
            roster.roster_slot_id: roster
            for roster in prepared.rosters
        }
        codex_roster = prepared_by_slot.get(codex_slot_id)
        if codex_roster is None:
            raise ValueError("game creation omitted the direct Codex roster")
        assignment = next(
            (
                row
                for row in codex_roster.entity_assignments
                if row.controller == "codex"
                and row.codex_session_id is not None
                and row.takeover_claim_id is not None
            ),
            None,
        )
        if assignment is None:
            raise ValueError(
                "game creation did not return a complete Codex assignment",
            )
        assert assignment.codex_session_id is not None
        assert assignment.takeover_claim_id is not None
        session_id = assignment.codex_session_id
        controlled_entity_uuids = (assignment.entity_uuid,)

        joined = _JoinedGame.model_validate(
            self._post_json(
                "/game/join",
                {
                    "session_id": session_id,
                    "entity_uuids": list(controlled_entity_uuids),
                },
            ),
        )
        if joined.session_id != session_id:
            raise ValueError("game join returned a different Codex session")
        if joined.game_id != prepared.game_id:
            raise ValueError("game join returned a different game")
        if set(joined.controlled_entities) != set(
            controlled_entity_uuids,
        ):
            raise ValueError(
                "game join did not preserve Codex entity ownership",
            )

        bootstrap = _ReplicationBootstrap.model_validate(
            self._get_json(
                "/replication/bootstrap",
                params={"session_id": session_id},
            ),
        )
        activation = _ActivationResult.model_validate(
            self._post_json(
                "/game-creation/activate",
                {
                    "session_id": session_id,
                    "expected_source_stream_id": (
                        bootstrap.protocol.source_stream_id
                    ),
                    "expected_generation_id": (
                        bootstrap.protocol.generation_id
                    ),
                    "expected_perspective_epoch_id": (
                        bootstrap.perspective.perspective_epoch_id
                    ),
                },
            ),
        )
        if (
            activation.game_id != prepared.game_id
            or activation.encounter_uuid != prepared.encounter_uuid
        ):
            raise ValueError(
                "game activation returned different prepared identities",
            )
        return DirectCodexGameStart(
            activation_status=activation.status,
            encounter_id=encounter_id,
            encounter_uuid=prepared.encounter_uuid,
            game_id=prepared.game_id,
            session_id=session_id,
            takeover_claim_id=assignment.takeover_claim_id,
            controlled_entity_uuids=controlled_entity_uuids,
        )

    def _get_json(
        self,
        path: str,
        *,
        params: Optional[dict[str, str]] = None,
    ) -> object:
        """GET one direct-start route and return its JSON payload."""
        response = self._client.get(
            f"{self.base_url}{path}",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def _post_json(
        self,
        path: str,
        payload: dict[str, object],
    ) -> object:
        """POST one direct-start route and return its JSON payload."""
        response = self._client.post(
            f"{self.base_url}{path}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def _direct_codex_composition(
    recipe: EncounterRecipe,
) -> dict[str, object]:
    """Compose authored rosters with the second roster controlled by Codex."""
    slots: list[dict[str, object]] = []
    for index, roster_slot in enumerate(recipe.roster_slots):
        controller = "codex" if index == 1 else "ai"
        slots.append({
            "roster_slot_id": roster_slot.roster_slot_id,
            "roster": {
                "kind": "authored_roster",
                "roster_id": roster_slot.roster.roster_id,
            },
            "faction_id": roster_slot.faction_id,
            "deployment_zone_id": roster_slot.deployment_zone_id,
            "controller_defaults": {
                "controller": controller,
                "participant_name": f"Direct Codex {roster_slot.roster.title}",
                "policy_id": (
                    "builtin.basic" if controller == "ai" else None
                ),
                "member_overrides": [],
            },
        })
    return {
        "title": recipe.title,
        "roster_slots": slots,
        "battlefield_id": recipe.battlefield_id,
        "deployment_id": recipe.deployment.deployment_id,
        "opening_policy": {
            "kind": "fixed_roster",
            "roster_slot_id": recipe.roster_slots[0].roster_slot_id,
        },
    }
