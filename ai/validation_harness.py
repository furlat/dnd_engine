"""Typed harness for rotating AI validation arenas."""

from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any, Literal, Optional, Sequence

import httpx
import typer
from pydantic import BaseModel, Field


ValidationMode = Literal["human_hero", "codex_monsters"]

DEFAULT_FOCUS_CYCLE: tuple[str, ...] = (
    "sorcerer_hero",
    "skeleton_side",
    "barbarian_hero",
    "skeleton_side",
    "skirmish_hero",
    "skeleton_side",
    "resource_hero",
    "environment_hero",
)


class ValidationArenaInfo(BaseModel):
    """Validation view derived from the canonical game-creation catalog.

    Attributes:
        arena_id: Stable preset id accepted by `/game-creation/start`.
        title: Human-readable arena title.
        hero_role: Player-side role under test.
        tags: Mechanical pressure tags exposed by the fixture.
        expected_pressure: Behaviors the arena is meant to exercise.
        map_notes: Notable terrain and object facts.
    """

    arena_id: str = Field(description="Stable preset id accepted by canonical game creation.")
    title: str = Field(description="Human-readable arena title.")
    hero_role: str = Field(description="Player-side role under test.")
    tags: list[str] = Field(default_factory=list, description="Mechanical pressure tags exposed by the fixture.")
    expected_pressure: list[str] = Field(
        default_factory=list,
        description="Behaviors the arena is meant to exercise.",
    )
    map_notes: list[str] = Field(default_factory=list, description="Notable terrain and object facts.")


class _CatalogHeroConfiguration(BaseModel):
    """Hero configuration fields used to label validation presets."""

    configuration_id: str
    title: str


class _CatalogRecipe(BaseModel):
    """Recipe fields needed to resolve one preset's hero label."""

    hero_configuration_id: str


class _CatalogPreset(BaseModel):
    """Canonical preset fields consumed by the validation schedule."""

    arena_id: str
    title: str
    tags: list[str]
    expected_pressure: list[str]
    map_notes: list[str]
    recipe: _CatalogRecipe


class _GameCreationCatalogPayload(BaseModel):
    """Closed subset of the canonical game-creation catalog."""

    hero_configurations: list[_CatalogHeroConfiguration]
    presets: list[_CatalogPreset]


class _PreparedEntityAssignment(BaseModel):
    """One entity identity returned by prepared game creation."""

    entity_uuid: str


class _PreparedSide(BaseModel):
    """Prepared side fields needed for joining and Codex provenance."""

    entity_assignments: list[_PreparedEntityAssignment]
    codex_session_id: Optional[str] = None
    takeover_claim_id: Optional[str] = None


class _PreparedGame(BaseModel):
    """Closed startup subset returned by canonical game creation."""

    status: Literal["prepared"]
    preset_arena_id: Optional[str] = None
    encounter_uuid: str
    side_a: _PreparedSide
    side_b: _PreparedSide


class _CreatedSession(BaseModel):
    """Session identity used to join a human validation side."""

    session_id: str


class _JoinedGame(BaseModel):
    """Canonical join acknowledgement used before replication bootstrap."""

    session_id: str
    controlled_entities: list[str]


class _ReplicationProtocol(BaseModel):
    """Source identities required by the activation barrier."""

    source_stream_id: str
    generation_id: str


class _ReplicationPerspective(BaseModel):
    """Perspective identity required by the activation barrier."""

    perspective_epoch_id: str


class _ReplicationBootstrap(BaseModel):
    """Exact activation identities from the canonical player bootstrap."""

    protocol: _ReplicationProtocol
    perspective: _ReplicationPerspective


class _ActivationResult(BaseModel):
    """Prepared-to-active acknowledgement."""

    status: Literal["activated", "already_active"]


class ValidationScheduleEntry(BaseModel):
    """One planned validation run.

    Attributes:
        sequence: Zero-based index in the generated run schedule.
        focus: High-level role or pressure focus selected from the focus cycle.
        mode: Server validation mode for the run.
        arena_id: Stable arena id to start.
        arena_title: Human-readable arena title.
        hero_role: Player-side role inside the arena.
        tags: Arena tags copied into the schedule for dashboard logging.
        rationale: Short reason this arena was selected for this schedule slot.
    """

    sequence: int = Field(description="Zero-based index in the generated run schedule.")
    focus: str = Field(description="High-level role or pressure focus selected from the focus cycle.")
    mode: ValidationMode = Field(description="Server validation mode for the run.")
    arena_id: str = Field(description="Stable arena id to start.")
    arena_title: str = Field(description="Human-readable arena title.")
    hero_role: str = Field(description="Player-side role inside the arena.")
    tags: list[str] = Field(default_factory=list, description="Arena tags copied into the schedule.")
    rationale: str = Field(description="Short reason this arena was selected for this schedule slot.")


class ValidationStartResult(BaseModel):
    """Typed result for one started validation run.

    Attributes:
        schedule_entry: Schedule row used to start the run.
        status: Status reported by canonical game activation.
        arena_id: Arena id reported by the server.
        mode: Validation mode reported by the server.
        codex_session_id: Codex session id when mode claims monsters.
        takeover_claim_id: Takeover claim id when mode claims monsters.
        encounter_uuid: Active encounter UUID.
        hero_uuid: Hero entity UUID.
        raw_response: Canonical preparation/join/activation responses.
    """

    schedule_entry: ValidationScheduleEntry = Field(description="Schedule row used to start the run.")
    status: str = Field(description="Status reported by canonical game activation.")
    arena_id: str = Field(description="Arena id reported by the server.")
    mode: ValidationMode = Field(description="Validation mode reported by the server.")
    codex_session_id: Optional[str] = Field(default=None, description="Codex session id when mode claims monsters.")
    takeover_claim_id: Optional[str] = Field(default=None, description="Takeover claim id when mode claims monsters.")
    encounter_uuid: Optional[str] = Field(default=None, description="Active encounter UUID.")
    hero_uuid: Optional[str] = Field(default=None, description="Hero entity UUID.")
    raw_response: dict[str, Any] = Field(default_factory=dict, description="Full server response.")


class ValidationSessionRow(BaseModel):
    """One session row from `/game/status`.

    Attributes:
        session_id: Session UUID.
        player_type: Session player/controller type.
        name: Human-readable session name.
        connection_status: Current connection state.
        controlled_entities: Entity UUIDs controlled by this session.
        is_their_turn: Whether the active actor belongs to this session.
    """

    session_id: str = Field(description="Session UUID.")
    player_type: str = Field(description="Session player/controller type.")
    name: str = Field(description="Human-readable session name.")
    connection_status: str = Field(description="Current connection state.")
    controlled_entities: list[str] = Field(default_factory=list, description="Entity UUIDs controlled by this session.")
    is_their_turn: bool = Field(default=False, description="Whether the active actor belongs to this session.")


class ValidationGameStatus(BaseModel):
    """Typed subset of `/game/status` used by validation probes."""

    active: bool = Field(default=False, description="Whether a game is currently active.")
    game_id: Optional[str] = Field(default=None, description="Active game UUID.")
    encounter_active: bool = Field(default=False, description="Whether the encounter is still active.")
    active_entity_uuid: Optional[str] = Field(default=None, description="Active entity UUID when an encounter is waiting.")
    sessions: list[ValidationSessionRow] = Field(default_factory=list, description="Current joined sessions.")


class ValidationSessionPing(BaseModel):
    """Typed subset of `/session/{session_id}/ping` used by validation probes."""

    status: str = Field(description="Ping result status.")
    session_id: str = Field(description="Session UUID.")
    connection_status: str = Field(description="Current connection status.")
    is_my_turn: bool = Field(description="Whether this session controls the active actor.")
    active_entity_uuid: Optional[str] = Field(default=None, description="Active entity UUID.")
    active_entity_name: Optional[str] = Field(default=None, description="Active entity name.")
    controlled_entities: list[str] = Field(default_factory=list, description="Controlled entity UUIDs.")


class ValidationBoundaryResult(BaseModel):
    """Result from waiting for a validation control boundary."""

    status: Literal["session_turn", "encounter_ended", "inactive", "timeout"] = Field(
        description="Boundary outcome.",
    )
    elapsed_ms: float = Field(description="Milliseconds spent waiting.")
    active_entity_uuid: Optional[str] = Field(default=None, description="Active entity UUID at the boundary.")
    active_entity_name: Optional[str] = Field(default=None, description="Active entity name at the boundary.")
    samples: int = Field(default=0, description="Number of poll samples taken.")


class ValidationHarnessHTTPError(RuntimeError):
    """Raised when the validation harness receives a bad HTTP response."""

    def __init__(self, response: httpx.Response) -> None:
        """Create an error from an HTTP response.

        Args:
            response: Failed HTTP response.
        """
        try:
            detail: Any = response.json()
        except json.JSONDecodeError:
            detail = response.text
        super().__init__(f"HTTP {response.status_code}: {detail}")
        self.response = response
        self.detail = detail


class ValidationHarnessClient:
    """Small HTTP client for validation arena schedule and startup."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", client: Optional[httpx.Client] = None) -> None:
        """Create a validation harness client.

        Args:
            base_url: Server base URL.
            client: Optional preconfigured HTTPX client for tests.
        """
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(base_url=self.base_url, timeout=httpx.Timeout(30.0))
        self._owns_client = client is None

    def close(self) -> None:
        """Close the underlying HTTP client when owned by this harness."""
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "ValidationHarnessClient":
        """Return this client for `with` statement use."""
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        """Close the owned HTTP client and allow exceptions to propagate."""
        self.close()
        return False

    def list_arenas(self) -> list[ValidationArenaInfo]:
        """Derive validation rows from the canonical game-creation catalog.

        Returns:
            Typed validation arena catalog rows.
        """
        response = self.client.get("/game-creation/catalog")
        _raise_for_status(response)
        payload = _GameCreationCatalogPayload.model_validate(response.json())
        hero_titles = {
            row.configuration_id: row.title
            for row in payload.hero_configurations
        }
        return [
            ValidationArenaInfo(
                arena_id=preset.arena_id,
                title=preset.title,
                hero_role=hero_titles.get(
                    preset.recipe.hero_configuration_id,
                    preset.recipe.hero_configuration_id,
                ),
                tags=preset.tags,
                expected_pressure=preset.expected_pressure,
                map_notes=preset.map_notes,
            )
            for preset in payload.presets
        ]

    def build_schedule(
        self,
        rounds: int,
        *,
        start_index: int = 0,
        focus_cycle: Sequence[str] = DEFAULT_FOCUS_CYCLE,
    ) -> list[ValidationScheduleEntry]:
        """Build a validation run schedule from the live server catalog.

        Args:
            rounds: Number of schedule rows to generate.
            start_index: Offset into the focus cycle.
            focus_cycle: Ordered validation focus labels.

        Returns:
            Planned validation runs.
        """
        return build_validation_schedule(
            self.list_arenas(),
            rounds=rounds,
            start_index=start_index,
            focus_cycle=focus_cycle,
        )

    def start_entry(self, entry: ValidationScheduleEntry) -> ValidationStartResult:
        """Start one scheduled validation run.

        Args:
            entry: Schedule row to start.

        Returns:
            Typed startup result with the raw server payload attached.
        """
        side_a_controller = "human" if entry.mode == "human_hero" else "ai"
        side_b_controller = "ai" if entry.mode == "human_hero" else "codex"
        response = self.client.post(
            "/game-creation/start",
            json={
                "scenario": {"kind": "preset", "arena_id": entry.arena_id},
                "side_a": {
                    "controller": side_a_controller,
                    "name": "Validation Hero",
                },
                "side_b": {
                    "controller": side_b_controller,
                    "name": (
                        "Validation Native Monsters"
                        if entry.mode == "human_hero"
                        else "Validation Codex Monsters"
                    ),
                },
                "opening_side": "side_a",
            },
        )
        _raise_for_status(response)
        prepared_payload = response.json()
        prepared = _PreparedGame.model_validate(prepared_payload)
        if prepared.preset_arena_id != entry.arena_id:
            raise ValueError("game creation returned a different validation preset")

        created_session_payload: dict[str, Any] | None = None
        if entry.mode == "human_hero":
            session_response = self.client.post(
                "/session/create",
                json={"player_type": "human", "name": "Validation Hero"},
            )
            _raise_for_status(session_response)
            created_session_payload = session_response.json()
            session_id = _CreatedSession.model_validate(
                created_session_payload
            ).session_id
            controlled_side = prepared.side_a
        else:
            session_id = prepared.side_b.codex_session_id
            if session_id is None:
                raise ValueError(
                    "codex_monsters game creation did not return a Codex session"
                )
            controlled_side = prepared.side_b

        entity_uuids = [
            assignment.entity_uuid
            for assignment in controlled_side.entity_assignments
        ]
        join_response = self.client.post(
            "/game/join",
            json={
                "session_id": session_id,
                "entity_uuids": entity_uuids,
            },
        )
        _raise_for_status(join_response)
        join_payload = join_response.json()
        joined = _JoinedGame.model_validate(join_payload)
        if joined.session_id != session_id:
            raise ValueError("game join returned a different validation session")
        if set(joined.controlled_entities) != set(entity_uuids):
            raise ValueError("game join did not preserve validation side ownership")

        bootstrap_response = self.client.get(
            "/replication/bootstrap",
            params={"session_id": session_id},
        )
        _raise_for_status(bootstrap_response)
        bootstrap = _ReplicationBootstrap.model_validate(
            bootstrap_response.json()
        )
        activation_response = self.client.post(
            "/game-creation/activate",
            json={
                "session_id": session_id,
                "expected_source_stream_id": bootstrap.protocol.source_stream_id,
                "expected_generation_id": bootstrap.protocol.generation_id,
                "expected_perspective_epoch_id": (
                    bootstrap.perspective.perspective_epoch_id
                ),
            },
        )
        _raise_for_status(activation_response)
        activation_payload = activation_response.json()
        activation = _ActivationResult.model_validate(activation_payload)
        hero_uuid = (
            prepared.side_a.entity_assignments[0].entity_uuid
            if prepared.side_a.entity_assignments
            else None
        )
        return ValidationStartResult(
            schedule_entry=entry,
            status=activation.status,
            arena_id=entry.arena_id,
            mode=entry.mode,
            codex_session_id=prepared.side_b.codex_session_id,
            takeover_claim_id=prepared.side_b.takeover_claim_id,
            encounter_uuid=prepared.encounter_uuid,
            hero_uuid=hero_uuid,
            raw_response={
                "prepared": prepared_payload,
                "created_session": created_session_payload,
                "joined": join_payload,
                "activation": activation_payload,
            },
        )

    def game_status(self) -> ValidationGameStatus:
        """Fetch typed validation game status.

        Returns:
            Current game status from `/game/status`.
        """
        response = self.client.get("/game/status")
        _raise_for_status(response)
        return ValidationGameStatus.model_validate(response.json())

    def ping_session(self, session_id: str) -> ValidationSessionPing:
        """Ping one session and return typed turn state.

        Args:
            session_id: Session UUID to ping.

        Returns:
            Current session turn status.
        """
        response = self.client.post(f"/session/{session_id}/ping")
        _raise_for_status(response)
        return ValidationSessionPing.model_validate(response.json())

    def wait_for_session_boundary(
        self,
        session_id: str,
        *,
        timeout_s: float = 45.0,
        poll_interval_s: float = 0.2,
    ) -> ValidationBoundaryResult:
        """Wait until a session can act or the encounter ends.

        Args:
            session_id: Session UUID whose boundary is expected.
            timeout_s: Maximum seconds to wait.
            poll_interval_s: Delay between polls.

        Returns:
            Boundary status. Finished encounters are reported as
            `encounter_ended`, not as timeouts.
        """
        started = time.perf_counter()
        samples = 0
        last_ping: Optional[ValidationSessionPing] = None
        while True:
            samples += 1
            game = self.game_status()
            ping = self.ping_session(session_id)
            last_ping = ping
            elapsed_ms = (time.perf_counter() - started) * 1000
            if not game.active:
                return ValidationBoundaryResult(
                    status="inactive",
                    elapsed_ms=round(elapsed_ms, 3),
                    active_entity_uuid=ping.active_entity_uuid,
                    active_entity_name=ping.active_entity_name,
                    samples=samples,
                )
            if not game.encounter_active:
                return ValidationBoundaryResult(
                    status="encounter_ended",
                    elapsed_ms=round(elapsed_ms, 3),
                    active_entity_uuid=game.active_entity_uuid or ping.active_entity_uuid,
                    active_entity_name=ping.active_entity_name,
                    samples=samples,
                )
            if ping.is_my_turn:
                return ValidationBoundaryResult(
                    status="session_turn",
                    elapsed_ms=round(elapsed_ms, 3),
                    active_entity_uuid=ping.active_entity_uuid,
                    active_entity_name=ping.active_entity_name,
                    samples=samples,
                )
            if elapsed_ms >= timeout_s * 1000:
                return ValidationBoundaryResult(
                    status="timeout",
                    elapsed_ms=round(elapsed_ms, 3),
                    active_entity_uuid=last_ping.active_entity_uuid if last_ping else None,
                    active_entity_name=last_ping.active_entity_name if last_ping else None,
                    samples=samples,
                )
            if poll_interval_s > 0:
                time.sleep(poll_interval_s)


def build_validation_schedule(
    arenas: Sequence[ValidationArenaInfo | dict[str, Any]],
    *,
    rounds: int,
    start_index: int = 0,
    focus_cycle: Sequence[str] = DEFAULT_FOCUS_CYCLE,
) -> list[ValidationScheduleEntry]:
    """Build a deterministic role-rotating validation schedule.

    The schedule intentionally alternates ordinary hero-side validation with
    `codex_monsters` slots so the iteration loop keeps touching Barbarian,
    Sorcerer, and monster-side decision surfaces.

    Args:
        arenas: Validation catalog rows.
        rounds: Number of schedule rows to return.
        start_index: Offset into the focus cycle.
        focus_cycle: Ordered focus labels.

    Returns:
        Schedule entries suitable for startup or dashboard logging.

    Raises:
        ValueError: If rounds is negative, no arenas are supplied, or the focus
            cycle is empty.
    """
    if rounds < 0:
        raise ValueError("rounds must be non-negative")
    if not focus_cycle:
        raise ValueError("focus_cycle must not be empty")

    parsed = [arena if isinstance(arena, ValidationArenaInfo) else ValidationArenaInfo.model_validate(arena) for arena in arenas]
    if not parsed and rounds:
        raise ValueError("at least one arena is required to build a non-empty schedule")

    usage: Counter[str] = Counter()
    schedule: list[ValidationScheduleEntry] = []
    previous_arena_id: Optional[str] = None
    for sequence in range(rounds):
        focus = focus_cycle[(start_index + sequence) % len(focus_cycle)]
        mode = mode_for_focus(focus)
        candidates = [arena for arena in parsed if arena_matches_focus(arena, focus)]
        if not candidates:
            candidates = list(parsed)
        arena = _choose_least_used(candidates, usage, previous_arena_id)
        usage[arena.arena_id] += 1
        previous_arena_id = arena.arena_id
        schedule.append(_schedule_entry(sequence, focus, mode, arena))
    return schedule


def mode_for_focus(focus: str) -> ValidationMode:
    """Return the validation mode implied by a focus label.

    Args:
        focus: Schedule focus label.

    Returns:
        `codex_monsters` for monster-side slots, otherwise `human_hero`.
    """
    return "codex_monsters" if focus == "skeleton_side" else "human_hero"


def arena_matches_focus(arena: ValidationArenaInfo, focus: str) -> bool:
    """Return whether an arena fits a schedule focus label.

    Args:
        arena: Arena metadata row.
        focus: Schedule focus label.

    Returns:
        True when the arena is a suitable representative for the focus.
    """
    tags = set(arena.tags)
    hero_role = arena.hero_role.lower()
    title = arena.title.lower()
    if focus == "sorcerer_hero":
        return "sorcerer" in hero_role
    if focus == "barbarian_hero":
        return "barbarian" in hero_role
    if focus == "skeleton_side":
        return "skeletons" in tags or "skeleton" in title
    if focus == "skirmish_hero":
        return bool(tags & {"goblins", "water", "difficult-terrain", "ranged", "nimble-escape", "gear-loadout", "weapon-choice"})
    if focus == "resource_hero":
        return bool(tags & {"items", "scrolls", "wands", "resource-economy", "support", "healing", "damage-affinity", "resistance", "vulnerability"})
    if focus == "environment_hero":
        return bool(tags & {"environment-object", "fireball-cannon", "zone-control", "summon-object"})
    return True


def _choose_least_used(
    candidates: Sequence[ValidationArenaInfo],
    usage: Counter[str],
    previous_arena_id: Optional[str],
) -> ValidationArenaInfo:
    """Choose the least-used candidate while avoiding immediate repetition."""
    non_repeating = [arena for arena in candidates if arena.arena_id != previous_arena_id]
    pool = non_repeating or list(candidates)
    indexed = list(enumerate(pool))
    return min(indexed, key=lambda item: (usage[item[1].arena_id], item[0]))[1]


def _schedule_entry(
    sequence: int,
    focus: str,
    mode: ValidationMode,
    arena: ValidationArenaInfo,
) -> ValidationScheduleEntry:
    """Create one schedule entry from selected metadata."""
    return ValidationScheduleEntry(
        sequence=sequence,
        focus=focus,
        mode=mode,
        arena_id=arena.arena_id,
        arena_title=arena.title,
        hero_role=arena.hero_role,
        tags=list(arena.tags),
        rationale=_rationale(focus, mode, arena),
    )


def _rationale(focus: str, mode: ValidationMode, arena: ValidationArenaInfo) -> str:
    """Build a short schedule rationale."""
    if mode == "codex_monsters":
        return f"monster-side validation through {arena.title}"
    return f"{focus.replace('_', ' ')} validation through {arena.hero_role}"


def _raise_for_status(response: httpx.Response) -> None:
    """Raise a structured harness error on non-success responses."""
    if response.status_code >= 400:
        raise ValidationHarnessHTTPError(response)


app = typer.Typer(help="AI validation arena rotation harness.")


@app.command()
def schedule(
    rounds: int = typer.Option(8, "--rounds", min=0),
    start_index: int = typer.Option(0, "--start-index", min=0),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
) -> None:
    """Print a role-rotating validation arena schedule."""
    with _client(base_url) as client:
        _emit([entry.model_dump(mode="json") for entry in client.build_schedule(rounds, start_index=start_index)])


@app.command("start")
def start_entry(
    arena_id: str = typer.Option(..., "--arena-id"),
    mode: ValidationMode = typer.Option("human_hero", "--mode"),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
) -> None:
    """Start one explicit validation arena."""
    with _client(base_url) as client:
        arenas = {arena.arena_id: arena for arena in client.list_arenas()}
        arena = arenas.get(arena_id)
        if arena is None:
            raise typer.BadParameter(f"Unknown validation arena: {arena_id}")
        entry = _schedule_entry(0, "explicit", mode, arena)
        _emit(client.start_entry(entry).model_dump(mode="json"))


@app.command("start-scheduled")
def start_scheduled(
    sequence: int = typer.Option(0, "--sequence", min=0),
    rounds: int = typer.Option(8, "--rounds", min=1),
    start_index: int = typer.Option(0, "--start-index", min=0),
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url"),
) -> None:
    """Start one row from the generated validation schedule."""
    with _client(base_url) as client:
        plan = client.build_schedule(rounds, start_index=start_index)
        if sequence >= len(plan):
            raise typer.BadParameter(f"sequence must be < {len(plan)}")
        _emit(client.start_entry(plan[sequence]).model_dump(mode="json"))


class _client:
    """Context manager for validation harness clients."""

    def __init__(self, base_url: str) -> None:
        """Create the context manager."""
        self.client = ValidationHarnessClient(base_url)

    def __enter__(self) -> ValidationHarnessClient:
        """Return the managed client."""
        return self.client

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        """Close the client and allow exceptions to propagate."""
        self.client.close()
        return False


def _emit(payload: object) -> None:
    """Print a JSON payload."""
    typer.echo(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    app()
