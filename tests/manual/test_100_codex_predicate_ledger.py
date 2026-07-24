"""Contracts for revision-scoped Codex facts, predicates, and focus."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from ai.codex_tools.representation.predicates import (
    MAX_EXPRESSION_DEPTH,
    PredicateDefinition,
    PredicateFocusProfile,
    PredicateLedger,
    PredicateLedgerSnapshot,
)
from ai.knowledge.models import (
    ActorFacts,
    AffordanceIndex,
    AgentFacts,
    CapabilityIndex,
    CombatMemoryFacts,
    ContactFacts,
    ObjectFacts,
    ThreatFacts,
    TopologyFacts,
)
from server.agent_protocol.observation import (
    ObservationEncounterState,
    ObservationSessionState,
    SubjectiveWorldState,
)
from server.agent_protocol.control import (
    ActionAffordance,
    ActionCostProfile,
    ActionEconomyState,
    ActionSourceDefinition,
)
from server.agent_protocol.semantics import (
    ActionTag,
    ComparisonOperator,
    FactExpression,
    FactOperator,
    FactPredicate,
    TruthValue,
)


def test_builtin_facts_derive_from_aligned_subjective_world_and_agent_facts() -> None:
    """The first-delivery catalog exposes typed state without objective lookups."""
    world, facts = _state(cursor=7, hp=9, visible_hostiles=2)

    snapshot = PredicateLedger().evaluate(world, facts)

    assert snapshot.observation_cursor == 7
    assert snapshot.fact("actor.hp").value == 9
    assert snapshot.fact("actor.hp_fraction").value == pytest.approx(0.45)
    assert snapshot.fact("actor.is_wounded").truth is TruthValue.TRUE
    assert snapshot.fact("actor.action_available").value is True
    assert snapshot.fact("contacts.visible_hostile_count").value == 2
    assert snapshot.fact("contacts.remembered_hostile_count").value == 1
    assert snapshot.fact("contacts.unknown_relationship_count").value == 2
    assert snapshot.fact("objects.known_closed_door_count").value == 1
    assert snapshot.fact("topology.known_hazard_count").value == 1
    assert snapshot.fact("affordances.total_count").value == 2
    assert snapshot.fact("affordances.affordable_count").value == 1
    assert snapshot.fact("affordances.tag_count.damage.single_target").value == 1
    assert snapshot.fact("encounter.is_terminal").truth is TruthValue.FALSE
    assert snapshot.predicate("contacts.has_visible_hostile").truth is TruthValue.TRUE


def test_unknown_actor_values_remain_unknown_and_predicates_propagate_unknown() -> None:
    """An inactive session does not turn absent actor knowledge into false facts."""
    world, facts = _state(cursor=8, active=False, hp=None, max_hp=None)
    ledger = PredicateLedger(include_builtin_predicates=False)
    ledger.register_predicate(_predicate(
        "agent.actor_is_healthy",
        "actor.hp_fraction",
        ComparisonOperator.GREATER_OR_EQUAL,
        0.5,
    ))

    snapshot = ledger.evaluate(world, facts)

    assert snapshot.fact("actor.is_active").truth is TruthValue.FALSE
    assert snapshot.fact("actor.hp").truth is TruthValue.UNKNOWN
    assert snapshot.fact("actor.hp_fraction").truth is TruthValue.UNKNOWN
    assert snapshot.predicate("agent.actor_is_healthy").truth is TruthValue.UNKNOWN
    assert "actor.hp_fraction" not in snapshot.known_fact_values()


def test_world_and_agent_fact_revisions_must_match() -> None:
    """Facts from one subjective revision cannot be evaluated against another."""
    world, facts = _state(cursor=9)

    with pytest.raises(ValueError, match="same observation cursor"):
        PredicateLedger().evaluate(
            world,
            facts.model_copy(update={"observation_cursor": 8}),
        )


def test_declarative_registration_validates_fact_ids_duplicates_and_payload_shape() -> None:
    """Session predicates accept expressions, never executable evaluator payloads."""
    ledger = PredicateLedger(include_builtin_predicates=False)
    definition = _predicate(
        "agent.has_mobility",
        "actor.movement_remaining",
        ComparisonOperator.GREATER_THAN,
        0,
    )

    assert ledger.register_predicate(definition) == definition
    with pytest.raises(ValueError, match="already registered"):
        ledger.register_predicate(definition)
    with pytest.raises(ValueError, match="unregistered facts"):
        ledger.register_predicate(_predicate(
            "agent.knows_secret",
            "objective.secret",
            ComparisonOperator.EQUALS,
            True,
        ))
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ledger.register_predicate({
            **definition.model_dump(mode="python"),
            "predicate_id": "agent.executable",
            "evaluator": lambda: True,
        })


def test_declarative_registration_rejects_oversized_expression_depth() -> None:
    """Bounded declarative logic cannot become an unbounded evaluation program."""
    expression = FactExpression(
        operator=FactOperator.PREDICATE,
        predicate=FactPredicate(fact_id="actor.is_active"),
    )
    for _ in range(MAX_EXPRESSION_DEPTH):
        expression = FactExpression(operator=FactOperator.NOT, operands=(expression,))

    with pytest.raises(ValueError, match="depth"):
        PredicateLedger(include_builtin_predicates=False).register_predicate(
            PredicateDefinition(
                predicate_id="agent.too_deep",
                description="A deliberately oversized declaration.",
                semantic_intent="test_bound",
                expression=expression,
            )
        )


def test_focus_selects_truth_modes_and_never_removes_complete_evaluations() -> None:
    """Focus is a bounded attention view over an unchanged complete ledger."""
    ledger = PredicateLedger(include_builtin_predicates=False)
    ledger.register_predicate(_predicate(
        "agent.visible_contact",
        "contacts.visible_hostile_count",
        ComparisonOperator.GREATER_THAN,
        0,
    ))
    ledger.register_predicate(_predicate(
        "agent.remembers_contact",
        "contacts.remembered_hostile_count",
        ComparisonOperator.GREATER_THAN,
        2,
    ))
    ledger.register_predicate(_predicate(
        "agent.actor_healthy",
        "actor.hp_fraction",
        ComparisonOperator.GREATER_THAN,
        0.5,
    ))
    ledger.register_predicate(_predicate(
        "agent.has_movement",
        "actor.movement_remaining",
        ComparisonOperator.GREATER_THAN,
        0,
    ))
    world, facts = _state(cursor=10, active=True, hp=None, max_hp=None)
    base = ledger.evaluate(world, facts)
    profile = PredicateFocusProfile(
        profile_id="codex.focus_test",
        always_include=("agent.visible_contact",),
        include_when_true=("agent.has_movement",),
        include_when_false=("agent.remembers_contact",),
        include_when_unknown=("agent.actor_healthy",),
        query_only=("agent.visible_contact",),
        max_automatic_items=3,
    )

    focused = ledger.apply_focus(base, profile)

    assert focused.predicates == base.predicates
    assert focused.facts == base.facts
    assert focused.focus is not None
    assert tuple(row.predicate_id for row in focused.focus.selected) == (
        "agent.has_movement",
        "agent.remembers_contact",
        "agent.actor_healthy",
    )
    assert focused.focus.query_only_count == 1


def test_focus_changed_mode_uses_revision_history_and_is_deterministic() -> None:
    """Input changes become focusable even while predicate truth remains true."""
    ledger = PredicateLedger(include_builtin_predicates=False)
    ledger.register_predicate(_predicate(
        "agent.is_alive",
        "actor.hp",
        ComparisonOperator.GREATER_THAN,
        0,
    ))
    first_world, first_facts = _state(cursor=11, hp=12)
    ledger.evaluate(first_world, first_facts)
    second_world, second_facts = _state(cursor=12, hp=11)
    profile = PredicateFocusProfile(
        profile_id="codex.changed",
        include_when_changed=("agent.is_alive",),
        max_automatic_items=1,
    )

    second = ledger.evaluate(second_world, second_facts, focus_profile=profile)

    assert second.predicate("agent.is_alive").truth is TruthValue.TRUE
    assert second.predicate("agent.is_alive").previous_truth is TruthValue.TRUE
    assert second.predicate("agent.is_alive").changed is True
    assert second.focus is not None
    assert [row.predicate_id for row in second.focus.selected] == ["agent.is_alive"]


def test_predicate_snapshot_json_round_trips_exactly() -> None:
    """Ledgers are directly retainable as deterministic experiment artifacts."""
    world, facts = _state(cursor=13)
    snapshot = PredicateLedger().evaluate(world, facts)

    restored = PredicateLedgerSnapshot.model_validate_json(snapshot.model_dump_json())

    assert restored == snapshot


def _predicate(
    predicate_id: str,
    fact_id: str,
    comparison: ComparisonOperator,
    expected_value: Any,
) -> PredicateDefinition:
    return PredicateDefinition(
        predicate_id=predicate_id,
        description=f"Test predicate over {fact_id}.",
        semantic_intent="test_subjective_state",
        expression=FactExpression(
            operator=FactOperator.PREDICATE,
            predicate=FactPredicate(
                fact_id=fact_id,
                comparison=comparison,
                expected_value=expected_value,
            ),
        ),
    )


def _state(
    *,
    cursor: int,
    active: bool = True,
    hp: int | None = 9,
    max_hp: int | None = 20,
    visible_hostiles: int = 1,
) -> tuple[SubjectiveWorldState, AgentFacts]:
    rows = (_row("strike", True, ActionTag.DAMAGE_SINGLE_TARGET), _row("dash", False, ActionTag.MOBILITY_EXTEND))
    actor_uuid = "actor" if active else None
    economy = ActionEconomyState(
        actor_uuid="actor",
        actions=1,
        bonus_actions=0,
        reactions=1,
        movement_remaining=25,
    ) if active else None
    world = SubjectiveWorldState(
        observation_cursor=cursor,
        session=ObservationSessionState(
            session_id="session",
            player_type="codex",
            name="Codex",
            connection_status="connected",
            controlled_entity_uuids=["actor"],
            active_entity_uuid=actor_uuid,
            active_entity_name="Actor" if active else None,
            is_my_turn=active,
        ),
        encounter=ObservationEncounterState(
            uuid="encounter",
            name="Arena",
            state="active",
            round_number=2,
            current_turn_index=0,
            current_entity_uuid=actor_uuid,
            current_entity_name="Actor" if active else None,
        ),
    )
    facts = AgentFacts(
        observation_cursor=cursor,
        epoch_id=None,
        actor=ActorFacts(
            session_id="session",
            controlled_entity_uuids=("actor",),
            active_entity_uuid=actor_uuid,
            actor_uuid=actor_uuid,
            is_my_turn=active,
            position=(2, 2) if active else None,
            hp=hp,
            normal_hp=hp,
            max_hp=max_hp,
            is_concentrating=active,
            economy=economy,
        ),
        contacts=ContactFacts(
            visible_hostile_uuids=tuple(f"enemy-{index}" for index in range(visible_hostiles)),
            remembered_hostile_uuids=("remembered-enemy",),
            visible_ally_uuids=("ally",),
            visible_unknown_relationship_uuids=("unknown-visible",),
            remembered_unknown_relationship_uuids=("unknown-remembered",),
        ),
        threat=ThreatFacts(actor_uuid=actor_uuid),
        objects=ObjectFacts(
            known_object_uuids=("door",),
            closed_door_uuids=("door",),
        ),
        topology=TopologyFacts(
            known_tile_keys=("2,2", "3,2"),
            hazardous_positions=frozenset({(3, 2)}),
            slow_positions=frozenset({(4, 2), (5, 2)}),
        ),
        combat_memory=CombatMemoryFacts(source_log_count=0),
        affordances=AffordanceIndex(
            rows=rows,
            by_id={row.row_id: row for row in rows},
            row_ids_by_tag={
                ActionTag.DAMAGE_SINGLE_TARGET: ("strike",),
                ActionTag.MOBILITY_EXTEND: ("dash",),
            },
        ),
        capabilities=CapabilityIndex(),
    )
    return world, facts


def _row(row_id: str, affordable: bool, tag: ActionTag) -> ActionAffordance:
    return ActionAffordance(
        row_id=row_id,
        source=ActionSourceDefinition(
            source_action_id=row_id,
            bucket="self_actions",
            template_name=row_id.title(),
            semantic_key=f"test.{row_id}",
            display_name=row_id.title(),
            action_category="ability",
            target_type="self",
            can_afford=affordable,
            cost=ActionCostProfile(
                action_cost=1,
                affordability="affordable" if affordable else "unaffordable",
            ),
            semantic_id=f"test.{row_id}",
            tags=(tag.value,),
        ),
    )
