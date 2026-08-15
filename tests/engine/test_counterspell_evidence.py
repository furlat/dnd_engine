"""Closed objective evidence for Counterspell resolution."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.core.combat_log import SpellInterruptionLogData
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.events.action_events import (
    CounterspellReactionEvent,
)
from dnd.core.events.action_events import (
    COUNTERSPELL_FAILURE_OUTCOME_CODE,
    COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
)


REACTION_REF = ContentRef(
    pack_id="fixture.counterspell",
    definition_kind=ContentDefinitionKind.REACTION,
    content_id="reaction.spell.counterspell",
    content_version=1,
    definition_contract_hash="a" * 64,
)
REACTION_IDENTITY = REACTION_REF.identity_key
INCOMING_IDENTITY = (
    "fixture.counterspell:spell:spell.fireball@1"
)


def _binding(owner_uuid: UUID) -> BehaviorBinding:
    """Bind the synthetic reaction to its exact authored definition."""
    return BehaviorBinding(
        definition_ref=REACTION_REF,
        provided_by_ref=REACTION_REF,
        runtime_owner_uuid=owner_uuid,
    )


def _event(**updates: Any) -> CounterspellReactionEvent:
    """Construct one otherwise-valid automatic reaction event."""
    source_uuid = uuid4()
    values: dict[str, Any] = {
        "source_entity_uuid": source_uuid,
        "target_entity_uuid": uuid4(),
        "triggered_event_uuid": uuid4(),
        "triggered_lineage_uuid": uuid4(),
        "incoming_spell_name": "Fireball",
        "incoming_spell_level": 3,
        "counterspell_slot_level": 3,
        "automatic": True,
        "check_total": None,
        "check_dc": None,
        "succeeded": True,
        "outcome_code": COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
        "behavior_binding": _binding(source_uuid),
        "reaction_content_identity": REACTION_IDENTITY,
        "incoming_spell_content_identity": INCOMING_IDENTITY,
        "use_register": False,
    }
    values.update(updates)
    return CounterspellReactionEvent(**values)


def _log(**updates: Any) -> SpellInterruptionLogData:
    """Construct equivalent otherwise-valid typed log data."""
    values: dict[str, Any] = {
        "outcome_code": COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
        "counterspeller_name": "Abjurer",
        "counterspeller_uuid": str(uuid4()),
        "original_caster_name": "Evoker",
        "original_caster_uuid": str(uuid4()),
        "spell_name": "Fireball",
        "incoming_spell_level": 3,
        "counterspell_slot_level": 3,
        "automatic": True,
        "check_total": None,
        "check_dc": None,
        "succeeded": True,
        "reaction_content_identity": REACTION_IDENTITY,
        "incoming_spell_content_identity": INCOMING_IDENTITY,
    }
    values.update(updates)
    return SpellInterruptionLogData(**values)


class Builder(Protocol):
    """Shared constructor shape for event and log validation tests."""

    def __call__(self, **updates: Any) -> Any:
        ...


@pytest.mark.parametrize("builder", (_event, _log))
def test_automatic_counterspell_is_closed(builder: Builder) -> None:
    """Automatic evidence has a sufficient slot and no check fields."""
    result = builder()
    assert result.automatic is True
    assert result.succeeded is True
    assert result.check_total is None
    assert result.check_dc is None


@pytest.mark.parametrize("builder", (_event, _log))
@pytest.mark.parametrize(
    ("check_total", "succeeded", "outcome_code"),
    (
        (15, True, COUNTERSPELL_INTERRUPTION_OUTCOME_CODE),
        (14, False, COUNTERSPELL_FAILURE_OUTCOME_CODE),
    ),
)
def test_checked_counterspell_success_and_failure_are_closed(
    builder: Builder,
    check_total: int,
    succeeded: bool,
    outcome_code: str,
) -> None:
    """Checked evidence derives success from total against exact DC."""
    result = builder(
        incoming_spell_level=5,
        counterspell_slot_level=3,
        automatic=False,
        check_total=check_total,
        check_dc=15,
        succeeded=succeeded,
        outcome_code=outcome_code,
    )
    assert result.succeeded is succeeded
    assert result.check_total == check_total
    assert result.check_dc == 15


@pytest.mark.parametrize("builder", (_event, _log))
@pytest.mark.parametrize(
    "updates",
    (
        {"incoming_spell_level": 10},
        {"counterspell_slot_level": 2},
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 3,
        },
        {"succeeded": False},
        {"check_total": 20},
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 5,
            "automatic": False,
            "check_total": 20,
            "check_dc": 15,
        },
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 3,
            "automatic": False,
            "check_total": None,
            "check_dc": 15,
        },
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 3,
            "automatic": False,
            "check_total": 15,
            "check_dc": 14,
        },
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 3,
            "automatic": False,
            "check_total": 14,
            "check_dc": 15,
            "succeeded": True,
        },
    ),
)
def test_impossible_counterspell_resolution_is_rejected(
    builder: Builder,
    updates: dict[str, Any],
) -> None:
    """Neither objective event nor typed log accepts contradictions."""
    with pytest.raises(ValidationError):
        builder(**updates)


def test_event_rejects_outcome_code_that_contradicts_success() -> None:
    """The spell-specific event closes code/result consistency."""
    with pytest.raises(
        ValidationError,
        match="outcome code contradicts",
    ):
        _event(outcome_code=COUNTERSPELL_FAILURE_OUTCOME_CODE)


@pytest.mark.parametrize(
    "reaction_content_identity",
    (None, "fixture.counterspell:reaction:reaction.forged@1"),
)
def test_event_rejects_missing_or_mismatched_reaction_identity(
    reaction_content_identity: str | None,
) -> None:
    """Attached binding and scalar reaction identity cannot diverge."""
    with pytest.raises(ValidationError, match="reaction content identity"):
        _event(reaction_content_identity=reaction_content_identity)


def test_event_log_is_an_exact_typed_copy_of_both_content_roles() -> None:
    """Completion projection copies validated event facts without inference."""
    event = _event(
        incoming_spell_level=5,
        counterspell_slot_level=3,
        automatic=False,
        check_total=15,
        check_dc=15,
        succeeded=True,
        outcome_code=COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
    )

    entry = event.generate_combat_log()
    data = SpellInterruptionLogData.model_validate(entry.data)

    assert entry.success is True
    assert data.outcome_code == event.outcome_code
    assert data.incoming_spell_level == event.incoming_spell_level
    assert data.counterspell_slot_level == event.counterspell_slot_level
    assert data.automatic is event.automatic
    assert data.check_total == event.check_total
    assert data.check_dc == event.check_dc
    assert data.succeeded is event.succeeded
    assert (
        data.reaction_content_identity
        == event.reaction_content_identity
        == REACTION_IDENTITY
    )
    assert (
        data.incoming_spell_content_identity
        == event.incoming_spell_content_identity
        == INCOMING_IDENTITY
    )
    assert data.reaction_content_identity != (
        data.incoming_spell_content_identity
    )


def test_legacy_unbound_content_roles_remain_explicit_none() -> None:
    """Diagnostic events stay representable without invented identities."""
    event = _event(
        behavior_binding=None,
        reaction_content_identity=None,
        incoming_spell_content_identity=None,
    )

    entry = event.generate_combat_log()
    data = SpellInterruptionLogData.model_validate(entry.data)

    assert event.reaction_content_identity is None
    assert event.incoming_spell_content_identity is None
    assert data.reaction_content_identity is None
    assert data.incoming_spell_content_identity is None
