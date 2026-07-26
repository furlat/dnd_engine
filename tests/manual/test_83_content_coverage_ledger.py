"""General rules-content identity and lifecycle coverage contracts."""

from uuid import uuid4

from ai.evaluation.config_ladder.experiment import (
    RetainedContentCoverage,
    RetainedExperimentEvidence,
    build_content_coverage_report,
    build_default_catalog,
)
from ai.evaluation.content_catalog import build_implemented_content_catalog
from ai.evaluation.content_coverage import MatchContentCoverageCollector
from dnd.blocks.base_item import ItemChargeConsumptionEvent
from dnd.conditions import Prone
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.content.runtime import HandlerDispatchOutcome, RuntimeBehaviorKind
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger


def test_handler_dispatch_observer_distinguishes_opportunity_from_effect() -> None:
    """Matched handlers are opportunities; only observable mutations are effects."""
    EventQueue.reset()
    evidence = []
    source_uuid = uuid4()

    def no_effect(event: Event, _source_uuid):
        return None

    def modify(event: Event, _source_uuid):
        return event.model_copy(update={"modified": True})

    EventQueue.add_on_handler_dispatch_callback(evidence.append)
    for semantic_key, processor in (
        ("reaction.test.no_effect", no_effect),
        ("reaction.test.modify", modify),
    ):
        EventQueue.add_event_handler(EventHandler(
            name=semantic_key,
            semantic_key=semantic_key,
            content_kind=RuntimeBehaviorKind.REACTION,
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EXECUTION)],
            event_processor=processor,
        ))

    EventQueue.register(Event(
        event_type=EventType.ATTACK,
        phase=EventPhase.EXECUTION,
        source_entity_uuid=uuid4(),
        use_register=False,
    ))

    assert [row.handler_semantic_key for row in evidence] == [
        "reaction.test.no_effect",
        "reaction.test.modify",
    ]
    assert evidence[0].outcome == HandlerDispatchOutcome.NO_EFFECT
    assert evidence[1].outcome == HandlerDispatchOutcome.MODIFIED_EVENT
    EventQueue.reset()


def test_match_collector_records_condition_item_and_handler_lifecycles() -> None:
    """The evaluator collector retains typed effects without becoming an engine handler."""
    EventQueue.reset()
    collector = MatchContentCoverageCollector()
    collector.attach()
    source_uuid = uuid4()
    target_uuid = uuid4()
    condition = Prone(source_entity_uuid=source_uuid, target_entity_uuid=target_uuid)

    for event_type in (ConditionApplicationEvent, ConditionRemovalEvent):
        EventQueue.register(event_type(
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            condition=condition,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ))
    EventQueue.register(ItemChargeConsumptionEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        item_uuid=target_uuid,
        item_semantic_key="item.test.potion",
        item_name="Test Potion",
        amount=1,
        charges_before=1,
        charges_after=0,
        stack_count_before=1,
        stack_count_after=1,
        item_destroyed=True,
        phase=EventPhase.COMPLETION,
        use_register=False,
    ))
    collector.detach()
    retained = collector.build()

    condition_key = condition.get_semantic_key()
    assert retained.condition_application_counts == {condition_key: 1}
    assert retained.condition_removal_counts == {condition_key: 1}
    assert retained.item_consumption_counts == {"item.test.potion": 1}
    assert retained.event_lifecycle_counts["condition_application:completion"] == 1
    EventQueue.reset()


def test_implemented_catalog_and_general_report_keep_content_families_distinct() -> None:
    """Actions, reactions, feats, traits, conditions, and items keep separate denominators."""
    implemented = build_implemented_content_catalog()
    assert (
        implemented["reaction.opportunity_attack"].content_kind
        == RuntimeBehaviorKind.REACTION
    )
    assert implemented["reaction.spell.counterspell"].evidence_lifecycle == "handler_dispatch"
    assert any(
        row.content_kind == RuntimeBehaviorKind.FEAT
        for row in implemented.values()
    )
    assert any(
        row.content_kind == RuntimeBehaviorKind.TRAIT
        for row in implemented.values()
    )
    assert any(
        row.content_kind == RuntimeBehaviorKind.ITEM
        for row in implemented.values()
    )

    retained = RetainedContentCoverage(manifest_match_count=2, lifecycle_evidence_match_count=2)
    retained.metadata["reaction.opportunity_attack"] = {
        "display_name": "Opportunity Attack",
        "content_kind": "reaction",
        "subtype": "movement_reaction",
        "identity_quality": "typed",
    }
    retained.configured_by_key["reaction.opportunity_attack"].add("monsters.test")
    retained.handler_opportunity_counts["reaction.opportunity_attack"] = 4
    retained.handler_effect_counts["reaction.opportunity_attack"] = 2
    report = build_content_coverage_report(
        build_default_catalog(generated_at="2026-07-18T16:00:00+00:00"),
        RetainedExperimentEvidence(
            evidences={},
            responses={},
            infrastructure_failures={},
            artifact_bytes=0,
            content_coverage=retained,
        ),
    )

    content_rows = report["content"]
    assert isinstance(content_rows, list)
    row = next(
        value for value in content_rows
        if value["semantic_key"] == "reaction.opportunity_attack"
    )
    assert row["status"] == "effected"
    assert row["handler_opportunity_count"] == 4
    assert row["handler_effect_count"] == 2
    assert report["lifecycle_evidence_match_count"] == 2
