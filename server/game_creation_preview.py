"""Parent-safe access to cold-process normalized encounter previews."""

from __future__ import annotations

import atexit
import json
import queue
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Mapping
from functools import lru_cache
from uuid import UUID

from pydantic import ValidationError

from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from dnd.core.content.encounters import EncounterRecipe
from server.game_creation_preview_contracts import (
    GameCreationEncounterVisualPreviewResponse,
)


class GameCreationPreviewError(ValueError):
    """Typed route-safe failure while materializing an exact preview."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        recipe_digest: str,
        status_code: int,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recipe_digest = recipe_digest
        self.status_code = status_code

    def detail(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "recipe_digest": self.recipe_digest,
        }


class _RetainedPreviewWorker:
    """Own one serialized isolated preview child for a server generation."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._stdout: queue.Queue[str | None] = queue.Queue()
        self._stderr: deque[str] = deque(maxlen=32)

    def prewarm(self, *, timeout: float = 90.0) -> None:
        """Start the child and wait until its content imports are complete."""
        with self._lock:
            self._ensure_started_locked(timeout=timeout)

    def request(self, request_json: str, *, timeout: float = 90.0) -> object:
        """Send one exact request through the retained serialized worker."""
        with self._lock:
            process = self._ensure_started_locked(timeout=timeout)
            if process.stdin is None:
                self._discard_locked()
                raise RuntimeError("preview worker stdin is unavailable")
            try:
                process.stdin.write(request_json + "\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self._discard_locked()
                raise RuntimeError("preview worker request pipe closed") from exc
            response_line = self._read_line_locked(timeout=timeout)
            try:
                envelope = json.loads(response_line)
            except json.JSONDecodeError as exc:
                self._discard_locked()
                raise RuntimeError(
                    "preview worker returned invalid JSON",
                ) from exc
            if not isinstance(envelope, dict):
                self._discard_locked()
                raise RuntimeError(
                    "preview worker returned a non-object envelope",
                )
            kind = envelope.get("kind")
            if kind == "preview":
                return envelope.get("payload")
            if kind == "error":
                error_type = envelope.get("error_type", "Error")
                message = envelope.get("message", "unknown worker error")
                raise RuntimeError(f"{error_type}: {message}")
            self._discard_locked()
            raise RuntimeError(
                f"preview worker returned unexpected envelope kind {kind!r}",
            )

    def close(self) -> None:
        """Terminate the child owned by this parent generation."""
        with self._lock:
            self._discard_locked()

    def pid(self) -> int | None:
        """Return the live worker PID for deterministic lifecycle tests."""
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None:
                return None
            return process.pid

    def _ensure_started_locked(
        self,
        *,
        timeout: float,
    ) -> subprocess.Popen[str]:
        process = self._process
        if process is not None and process.poll() is None:
            return process
        self._discard_locked()
        stdout_lines: queue.Queue[str | None] = queue.Queue()
        stderr_lines: deque[str] = deque(maxlen=32)
        self._stdout = stdout_lines
        self._stderr = stderr_lines
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "server.game_creation_preview_worker",
                "--serve",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._process = process
        threading.Thread(
            target=self._capture_stdout,
            args=(process, stdout_lines),
            daemon=True,
            name="game-creation-preview-stdout",
        ).start()
        threading.Thread(
            target=self._capture_stderr,
            args=(process, stderr_lines),
            daemon=True,
            name="game-creation-preview-stderr",
        ).start()
        try:
            ready_line = self._read_line_locked(timeout=timeout)
            ready = json.loads(ready_line)
            if ready != {"kind": "ready", "protocol_version": 1}:
                raise RuntimeError(
                    f"preview worker returned invalid readiness {ready!r}",
                )
        except Exception:
            self._discard_locked()
            raise
        return process

    def _read_line_locked(self, *, timeout: float) -> str:
        try:
            line = self._stdout.get(timeout=timeout)
        except queue.Empty as exc:
            suffix = self._last_diagnostic()
            self._discard_locked()
            raise TimeoutError(
                f"preview worker timed out{suffix}",
            ) from exc
        if line is None:
            suffix = self._last_diagnostic()
            self._discard_locked()
            raise RuntimeError(
                f"preview worker exited before responding{suffix}",
            )
        return line

    def _last_diagnostic(self) -> str:
        if not self._stderr:
            return ""
        return f": {self._stderr[-1]}"

    def _discard_locked(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    @staticmethod
    def _capture_stdout(
        process: subprocess.Popen[str],
        output: queue.Queue[str | None],
    ) -> None:
        stdout = process.stdout
        if stdout is None:
            output.put(None)
            return
        for line in stdout:
            output.put(line.rstrip("\n"))
        output.put(None)

    @staticmethod
    def _capture_stderr(
        process: subprocess.Popen[str],
        diagnostics: deque[str],
    ) -> None:
        stderr = process.stderr
        if stderr is None:
            return
        for line in stderr:
            diagnostics.append(line.rstrip("\n"))


_RETAINED_PREVIEW_WORKER = _RetainedPreviewWorker()


def prewarm_game_creation_preview_worker() -> None:
    """Pay preview interpreter/import startup once with the server lifespan."""
    _RETAINED_PREVIEW_WORKER.prewarm()


def close_game_creation_preview_worker() -> None:
    """Close the preview child owned by the current server generation."""
    _RETAINED_PREVIEW_WORKER.close()


def game_creation_preview_worker_pid() -> int | None:
    """Return the retained worker PID for lifecycle verification."""
    return _RETAINED_PREVIEW_WORKER.pid()


def clear_game_creation_preview_cache() -> None:
    """Clear memoized responses without replacing the retained worker."""
    _build_cached_preview.cache_clear()


atexit.register(close_game_creation_preview_worker)


@lru_cache(maxsize=256)
def _build_cached_preview(
    recipe_json: str,
    deployments_json: str,
    content_set_digest: str,
    ruleset_digest: str,
) -> GameCreationEncounterVisualPreviewResponse:
    recipe = EncounterRecipe.model_validate_json(recipe_json)
    request_json = json.dumps(
        {
            "expected_content_set_digest": content_set_digest,
            "expected_ruleset_digest": ruleset_digest,
            "recipe": json.loads(recipe_json),
            "character_deployments": json.loads(deployments_json),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        payload = _RETAINED_PREVIEW_WORKER.request(
            request_json,
            timeout=90,
        )
    except TimeoutError as exc:
        raise GameCreationPreviewError(
            "game_creation_preview_timeout",
            "Encounter preview materialization timed out.",
            recipe_digest=recipe.recipe_digest,
            status_code=504,
        ) from exc
    except RuntimeError as exc:
        raise GameCreationPreviewError(
            "game_creation_preview_failed",
            f"Encounter preview materialization failed: {exc}",
            recipe_digest=recipe.recipe_digest,
            status_code=500,
        ) from exc
    try:
        response = (
            GameCreationEncounterVisualPreviewResponse.model_validate(
                payload,
            )
        )
    except ValidationError as exc:
        raise GameCreationPreviewError(
            "invalid_game_creation_preview",
            "Preview worker returned an invalid payload.",
            recipe_digest=recipe.recipe_digest,
            status_code=500,
        ) from exc
    if (
        response.encounter_recipe_digest != recipe.recipe_digest
        or response.content_set_digest != content_set_digest
        or response.ruleset_digest != ruleset_digest
    ):
        raise GameCreationPreviewError(
            "game_creation_preview_identity_mismatch",
            "Preview worker returned another recipe or protocol identity.",
            recipe_digest=recipe.recipe_digest,
            status_code=500,
        )
    return response


def build_game_creation_encounter_visual_preview(
    recipe: EncounterRecipe,
    *,
    character_deployments: Mapping[
        UUID,
        CharacterDeploymentSnapshot,
    ] | None = None,
    expected_content_set_digest: str,
    expected_ruleset_digest: str,
) -> GameCreationEncounterVisualPreviewResponse:
    """Return one cached exact preview without touching parent engine state."""
    deployments = character_deployments or {}
    ordered_deployments = tuple(
        deployments[character_id]
        for character_id in sorted(deployments, key=lambda value: value.hex)
    )
    return _build_cached_preview(
        recipe.model_dump_json(),
        json.dumps(
            [
                deployment.model_dump(mode="json")
                for deployment in ordered_deployments
            ],
            sort_keys=True,
            separators=(",", ":"),
        ),
        expected_content_set_digest,
        expected_ruleset_digest,
    )


__all__ = [
    "GameCreationPreviewError",
    "build_game_creation_encounter_visual_preview",
    "clear_game_creation_preview_cache",
    "close_game_creation_preview_worker",
    "game_creation_preview_worker_pid",
    "prewarm_game_creation_preview_worker",
]
