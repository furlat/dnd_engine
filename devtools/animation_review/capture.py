"""Generate native review inputs once, then render their saved public bytes."""

import json
from pathlib import Path

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from devtools.animation_review.cases import RecordedInput, ReviewCase, ReviewPerspective
from devtools.animation_review.cli import main as run_review, write_json
from devtools.animation_review.produce import produce
from game.player_projection import project_sequence
from game.player_reduction import encode_player_sequence
from game.replay import RecordedSequence


def capture_inputs(case: ReviewCase, output: Path, captured_at: str, sources: dict) -> tuple[RecordedInput, ...]:
    """Run one experiment, then persist each participant's public input separately."""
    generated = produce(case)
    views = generated.views or {"observer": RecordedSequence(
        initialization=generated.initialization, lineages=generated.lineages)}
    result = []
    for role, native in views.items():
        primary = native.initialization.observer_uuid == generated.before.observer_uuid
        identity = case.id if primary else f"{case.id}--{role}"
        view_case = case.model_copy(update={"id": identity, "title": f"{case.title} · {role}",
                                           "tags": (*case.tags, f"observer:{role}")})
        perspective = ReviewPerspective(experiment_id=case.id, role=role,
            observer_uuid=native.initialization.observer_uuid, generation=native.initialization.generation,
            start_cursor=native.initialization.end_cursor,
            end_cursor=max((lineage.end_cursor for lineage in native.lineages), default=native.initialization.end_cursor))
        recorded = RecordedInput(case=view_case, captured_at=captured_at, sources=sources,
            sequence=json.loads(encode_player_sequence(project_sequence(native))),
            sequence_format="player-v1", perspective=perspective)
        directory = output / "inputs" / identity
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "native.json").write_text(native.model_dump_json(), encoding="utf-8")
        (directory / "input.json").write_text(recorded.model_dump_json(), encoding="utf-8")
        result.append(RecordedInput.model_validate_json((directory / "input.json").read_bytes()))
    write_json(output / "inputs" / case.id / "perspectives.json", {
        "schema_version": 1, "experiment_id": case.id,
        "views": [recorded.case.id for recorded in result],
    })
    return tuple(result)



def main(argv: list[str] | None = None) -> int:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    return run_review(argv, capture=capture_inputs)


if __name__ == "__main__":
    raise SystemExit(main())
