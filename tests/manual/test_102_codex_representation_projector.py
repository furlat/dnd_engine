"""Focused tests for typed profile-driven Codex representation projection."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai.codex_tools.representation.components import (
    ActionFamilyBlock,
    AdviceBlock,
    AdvicePayload,
    CodexTurnRepresentation,
    ContactLedgerBlock,
    ComponentErrorBlock,
    DecisionDeltaBlock,
    EncounterSummaryBlock,
    OracleAdviceBasis,
    OracleProposalSummary,
    PredicateFocusBlock,
    RecentCombatLogsBlock,
    RuntimeTelemetryInput,
    SpatialSceneBlock,
)
from ai.codex_tools.representation.models import ExposureTiming
from ai.codex_tools.representation.predicates import (
    PredicateFocusProfile,
    PredicateLedger,
)
from ai.codex_tools.representation.profiles import (
    BALANCED_V2_PROFILE_ID,
    CURRENT_V1_PROFILE_ID,
    build_builtin_representation_registry,
)
from ai.codex_tools.representation.projector import (
    ComponentProjectionEvent,
    CodexRepresentationProjector,
    RequiredRepresentationComponentError,
    RepresentationProjectionInput,
)
from ai.knowledge.deriver import derive_agent_facts
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationSessionState,
    ObservationTileFact,
    SubjectiveWorldState,
)
from dnd.ai.contracts.control import (
    ActionBucket,
    ActionAffordance,
    ActionCapability,
    ActionCostProfile,
    ActionEconomyState,
    ActionSourceDefinition,
    ActionTarget,
    AffordanceSet,
    DecisionEpoch,
    DecisionEpochReason,
)
from dnd.core.item_types import ItemObservationState
from ai.subjective.models import AgentState


def test_current_v1_projects_ordered_compatible_blocks_and_complete_actions() -> None:
    """Compatibility projection preserves its bounded views and every legal row."""
    world = _world()
    inputs = _inputs(world)
    manifest = _manifest(CURRENT_V1_PROFILE_ID)

    representation = CodexRepresentationProjector().project(manifest, inputs)

    expected_ids = tuple(
        component.spec.component_id
        for component in manifest.components
        if component.enabled and component.exposure is ExposureTiming.DECISION_EPOCH
    )
    assert tuple(block.component_id for block in representation.blocks) == expected_ids
    assert representation.observation_cursor == world.observation_cursor
    assert representation.epoch_id == "epoch-7"
    assert all(block.observation_cursor == world.observation_cursor for block in representation.blocks)
    assert all(block.timing_ms >= 0 for block in representation.blocks)
    assert all(block.payload_bytes > 0 for block in representation.blocks)

    actions = _block(representation, "actions.index", ActionFamilyBlock)
    assert actions.payload.total_rows == 3
    assert actions.payload.semantic_coverage.source_action_count == 3
    assert actions.payload.semantic_coverage.unknown_count == 3
    assert actions.payload.semantic_coverage.unknown_semantic_keys
    assert actions.payload.families[0].source_action_id == "strike-enemy"
    assert actions.payload.families[0].direct_row_id == "strike-enemy"
    assert actions.payload.families[0].row_count == 1
    assert not hasattr(actions.payload.families[0], "row_ids")
    assert world.current_epoch is not None
    assert actions.payload.complete_affordances is world.current_epoch.affordances
    assert actions.payload.complete_affordances is not None
    assert tuple(
        row.row_id for row in actions.payload.complete_affordances.all_rows
    ) == ("strike-enemy", "missiles-enemy", "end-turn")
    assert tuple(
        row.row_id for row in actions.payload.automatically_expanded_rows
    ) == ("strike-enemy", "missiles-enemy", "end-turn")
    assert actions.omitted_item_count == 0
    assert actions.recovery_hints
    assert actions.payload.multi_target_rows[0].row_id == "missiles-enemy"
    assert actions.payload.multi_target_rows[0].extra_target_slots == 2

    logs = _block(representation, "events.recent_logs", RecentCombatLogsBlock)
    assert len(logs.payload.logs) == 3
    assert logs.omitted_item_count == 1
    assert len(logs.payload.logs[-1].sub_entries) == 8
    assert logs.payload.logs[-1].omitted_sub_entry_count == 1

    advice = _block(representation, "oracle.policy", AdviceBlock)
    assert advice.payload.available is False
    assert advice.payload.selected is None
    assert "did not invoke" in advice.warnings[0]

    encoded = representation.model_dump_json()
    assert "objective-hidden-enemy" not in encoded
    assert CodexTurnRepresentation.model_validate_json(encoded).model_dump(
        mode="json"
    ) == representation.model_dump(mode="json")


def test_balanced_v2_is_neutral_delta_aware_and_keeps_oracle_on_demand() -> None:
    """Balanced automatic context adds neutral tools and excludes pre-action advice."""
    previous = _world(cursor=6, enemy_hp=9)
    world = _world(cursor=7, enemy_hp=5)
    inputs = _inputs(world, previous_world=previous)
    manifest = _manifest(BALANCED_V2_PROFILE_ID)
    projector = CodexRepresentationProjector()

    representation = projector.project(manifest, inputs)
    component_ids = tuple(block.component_id for block in representation.blocks)

    assert "spatial.scene" in component_ids
    assert "events.decision_delta" in component_ids
    assert "predicates.focused" in component_ids
    assert "oracle.policy" not in component_ids
    assert "telemetry.runtime" not in component_ids
    assert "events.recent_logs" in component_ids
    assert any(
        omission.component_id == "oracle.policy"
        and omission.configured_exposure is ExposureTiming.ON_DEMAND
        for omission in representation.exposure_omissions
    )

    contacts = _block(representation, "contacts.partition", ContactLedgerBlock)
    assert tuple(entity.uuid for entity in contacts.payload.remembered_allies) == (
        "remembered-ally",
    )
    assert contacts.payload.knowledge_detail_preserved is True

    scene = _block(representation, "spatial.scene", SpatialSceneBlock)
    assert scene.payload.radius == 12
    assert (99, 99) not in scene.payload.anchor_positions
    assert all(entity.uuid != "objective-hidden-enemy" for entity in scene.payload.entities)
    assert scene.payload.unknown_positions

    delta = _block(representation, "events.decision_delta", DecisionDeltaBlock)
    assert delta.payload.baseline is False
    enemy_change = next(
        change for change in delta.payload.entities if change.entity_uuid == "enemy"
    )
    assert enemy_change.before is not None and enemy_change.before.hp == 9
    assert enemy_change.after is not None and enemy_change.after.hp == 5

    predicates = _block(representation, "predicates.focused", PredicateFocusBlock)
    assert predicates.payload.complete_fact_count > 0
    assert predicates.payload.complete_predicate_count > 0

    actions = _block(representation, "actions.index", ActionFamilyBlock)
    assert actions.payload.complete_affordances is None
    assert actions.payload.total_rows == 3
    assert any(
        hint.endpoint == "/v1/inspect/get"
        for hint in actions.recovery_hints
    )
    logs = _block(representation, "events.recent_logs", RecentCombatLogsBlock)
    assert [row.compact for row in logs.payload.logs] == [
        "visible log 1",
        "visible log 2",
        "visible log 3",
    ]

    on_demand_inputs = inputs.model_copy(update={
        "policy_advice": AdvicePayload(
            available=True,
            detail="ranked",
            basis=OracleAdviceBasis(
                session_id="session",
                observation_cursor=world.observation_cursor,
                epoch_id="epoch-7",
                actor_uuid="actor",
                policy_id="test.policy",
                policy_version="1.0.0",
            ),
            selected=OracleProposalSummary(
                intent_kind="execute",
                row_id="strike-enemy",
                goal="damage",
                source_node="test.oracle",
                reason="Supplied independently for the on-demand projection.",
                score=1.0,
            ),
        ),
    })
    on_demand = projector.project(
        manifest,
        on_demand_inputs,
        exposure=ExposureTiming.ON_DEMAND,
    )
    assert tuple(block.component_id for block in on_demand.blocks) == ("oracle.policy",)
    assert isinstance(on_demand.blocks[0], AdviceBlock)
    assert on_demand.blocks[0].payload.available is True
    assert on_demand.blocks[0].payload.selected is not None
    assert on_demand.blocks[0].payload.selected.row_id == "strike-enemy"
    assert on_demand.blocks[0].payload.candidates == ()


def test_action_families_group_by_discovered_source_without_dumping_rows() -> None:
    """One source capability remains compact even when it expands to many targets."""
    world = _world()
    assert world.current_epoch is not None
    first = _row(
        row_id="move|0,0",
        source_action_id="position_actions|source=move",
        bucket="position_actions",
        semantic_id="movement.move",
        display_name="Move",
        target_type="position_path",
    )
    second = _row(
        row_id="move|1,0",
        source_action_id="position_actions|source=move",
        bucket="position_actions",
        semantic_id="movement.move",
        display_name="Move",
        target_type="position_path",
    )
    third = _row(
        row_id="dash|self",
        source_action_id="self_actions|source=dash",
        bucket="self_actions",
        semantic_id="mobility.dash",
        display_name="Dash",
        target_type="self",
    )
    capabilities = tuple(
        ActionCapability(
            capability_id=f"capability-{index}",
            semantic_key=f"rules.capability.{index}",
            action_category="ability",
            target_type="self",
            cost=ActionCostProfile(action_cost=1, affordability="affordable"),
            requires_line_of_sight=False,
            valid_target_filter="self",
            semantic_id="setup.capability" if index == 0 else "action.unknown",
            semantics_ref=first.semantics_ref,
        )
        for index in range(2)
    )
    affordances = world.current_epoch.affordances.model_copy(update={
        "entity_actions": (),
        "position_actions": (first, second),
        "self_actions": (third,),
        "special_commands": (),
        "capabilities": capabilities,
    })
    epoch = world.current_epoch.model_copy(update={"affordances": affordances})
    projected_world = world.model_copy(update={"current_epoch": epoch})

    representation = CodexRepresentationProjector().project(
        _manifest(BALANCED_V2_PROFILE_ID),
        _inputs(projected_world),
    )
    actions = _block(representation, "actions.index", ActionFamilyBlock)

    assert len(actions.payload.families) == 2
    family = actions.payload.families[0]
    assert family.source_action_id == "position_actions|source=move"
    assert family.row_count == 2
    assert family.direct_row_id is None
    assert "row_ids" not in family.model_dump()

    manifest = _manifest(BALANCED_V2_PROFILE_ID)
    limited_manifest = manifest.model_copy(update={
        "components": tuple(
            component.model_copy(update={
                "parameters": {
                    **component.parameters,
                    "family_limit": 1,
                    "capability_limit": 1,
                },
            })
            if component.spec.component_id == "actions.index"
            else component
            for component in manifest.components
        ),
    })
    limited = CodexRepresentationProjector().project(
        limited_manifest,
        _inputs(projected_world),
    )
    limited_actions = _block(limited, "actions.index", ActionFamilyBlock)
    assert limited_actions.payload.total_family_count == 2
    assert limited_actions.payload.omitted_family_count == 1
    assert len(limited_actions.payload.families) == 1
    assert limited_actions.payload.total_capability_count == 2
    assert limited_actions.payload.omitted_capability_count == 1
    assert len(limited_actions.payload.capabilities) == 1
    assert limited_actions.payload.capabilities[0].capability_id == "capability-0"
    assert not hasattr(limited_actions.payload.capabilities[0], "outcome_profile")
    assert limited_actions.payload.semantic_coverage.source_action_count == 2
    assert limited_actions.payload.semantic_coverage.unknown_count == 2
    assert limited_actions.payload.semantic_coverage.capability_count == 2
    assert limited_actions.payload.semantic_coverage.unknown_capability_count == 1
    assert limited_actions.payload.semantic_coverage.unknown_capability_semantic_keys == (
        "rules.capability.1",
    )

def test_projection_payloads_are_deterministic_and_profile_specific() -> None:
    """Equal local inputs produce equal ordered payloads despite timing metadata."""
    inputs = _inputs(_world())
    projector = CodexRepresentationProjector()
    current_manifest = _manifest(CURRENT_V1_PROFILE_ID)
    balanced_manifest = _manifest(BALANCED_V2_PROFILE_ID)

    first = projector.project(current_manifest, inputs)
    second = projector.project(current_manifest, inputs)
    balanced = projector.project(balanced_manifest, inputs)

    assert tuple(block.payload for block in first.blocks) == tuple(
        block.payload for block in second.blocks
    )
    assert tuple(block.source_paths for block in first.blocks) == tuple(
        block.source_paths for block in second.blocks
    )
    assert first.manifest_digest == second.manifest_digest
    assert first.manifest_digest != balanced.manifest_digest
    assert tuple(block.component_id for block in first.blocks) != tuple(
        block.component_id for block in balanced.blocks
    )


def test_optional_component_failure_is_typed_but_required_failure_stops_projection() -> None:
    """Failure policy is explicit and never returns a silently partial required view."""
    inputs = _inputs(_world())
    balanced = _manifest(BALANCED_V2_PROFILE_ID)
    projector = CodexRepresentationProjector()

    def fail_component(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("sensitive implementation detail")

    projector._builders["contacts.partition"] = fail_component  # pyright: ignore[reportPrivateUsage, reportArgumentType]
    degraded = projector.project(balanced, inputs)
    failure = next(block for block in degraded.blocks if isinstance(block, ComponentErrorBlock))

    assert failure.payload.failed_component_id == "contacts.partition"
    assert failure.payload.error_type == "RuntimeError"
    assert failure.payload.recoverable is True
    assert "sensitive implementation detail" not in failure.model_dump_json()

    projector._builders["actions.index"] = fail_component  # pyright: ignore[reportPrivateUsage, reportArgumentType]
    with pytest.raises(RequiredRepresentationComponentError) as captured:
        projector.project(balanced, inputs)

    assert captured.value.component_id == "actions.index"
    assert captured.value.error_type == "RuntimeError"


def test_terminal_summary_counts_only_subjectively_observed_statistics() -> None:
    """Post-match evidence is useful while declaring every unavailable statistic."""
    world = _world()
    assert world.encounter is not None
    enemy = world.known_entities["enemy"].model_copy(update={"hp": 0, "is_dead": True})
    terminal = world.model_copy(update={
        "encounter": world.encounter.model_copy(update={"state": "ended", "round_number": 3}),
        "known_entities": {**world.known_entities, "enemy": enemy},
        "current_epoch": None,
        "combat_logs": [
            {
                "entry_type": "turn_start",
                "source_uuid": "actor",
                "data": {"round_number": 3},
            },
            {
                "entry_type": "damage_taken",
                "source_uuid": "actor",
                "target_uuid": "enemy",
                "data": {"damage": 7},
            },
            {
                "entry_type": "damage_taken",
                "source_uuid": "enemy",
                "target_uuid": "actor",
                "data": {"damage": 4},
            },
            {
                "entry_type": "heal",
                "source_uuid": "actor",
                "data": {"entity_uuid": "actor", "amount": 3},
            },
        ],
    })
    inputs = _inputs(terminal).model_copy(update={
        "runtime_telemetry": RuntimeTelemetryInput(
            command_count=6,
            inspection_count=2,
        ),
    })

    representation = CodexRepresentationProjector().project(
        _manifest(BALANCED_V2_PROFILE_ID),
        inputs,
    )
    summary = _block(representation, "encounter.summary", EncounterSummaryBlock).payload

    assert summary.available is True
    assert summary.subjective_only is True
    assert summary.outcome == "controlled_survived"
    assert summary.subjective_winning_faction == "heroes"
    assert summary.winner_basis == "controlled_survival"
    assert summary.rounds_observed == 3
    assert summary.turn_starts_observed == 1
    assert summary.surviving_controlled_entity_uuids == ("actor",)
    assert summary.known_hostile_death_uuids == ("enemy",)
    assert summary.observed_damage_dealt == 7
    assert summary.observed_damage_taken == 4
    assert summary.observed_healing_received == 3
    assert summary.command_count == 6
    assert summary.inspection_count == 2
    assert "unperceived_events" in summary.incomplete_statistics


def test_component_lifecycle_telemetry_is_ordered_and_observational() -> None:
    """Component evidence records work while sink failures cannot alter output."""
    inputs = _inputs(_world())
    manifest = _manifest(BALANCED_V2_PROFILE_ID)
    events: list[ComponentProjectionEvent] = []
    projector = CodexRepresentationProjector()

    representation = projector.project(
        manifest,
        inputs,
        component_observer=events.append,
    )

    expected_components = [
        component.spec.component_id
        for component in manifest.components
        if component.enabled and component.exposure is ExposureTiming.DECISION_EPOCH
    ]
    assert [event.component_id for event in events[::2]] == expected_components
    assert all(event.phase == "started" for event in events[::2])
    assert all(event.phase == "completed" for event in events[1::2])
    assert all(event.payload_bytes > 0 for event in events[1::2])

    def broken_sink(_event: ComponentProjectionEvent) -> None:
        raise RuntimeError("telemetry must not affect projection")

    without_sink = projector.project(manifest, inputs, component_observer=broken_sink)
    assert tuple(block.payload for block in without_sink.blocks) == tuple(
        block.payload for block in representation.blocks
    )


def _manifest(profile_id: str):
    """Resolve one built-in manifest at a stable audit timestamp."""
    return build_builtin_representation_registry().resolve_profile(
        profile_id,
        created_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )


def _inputs(
    world: SubjectiveWorldState,
    *,
    previous_world: SubjectiveWorldState | None = None,
) -> RepresentationProjectionInput:
    """Build aligned facts and a focused predicate ledger for a world."""
    facts = derive_agent_facts(world).facts
    ledger = PredicateLedger()
    initial = ledger.evaluate(world, facts)
    focus_ids = tuple(
        evaluation.predicate_id for evaluation in initial.predicates[:3]
    )
    focused = ledger.apply_focus(
        initial,
        PredicateFocusProfile(
            profile_id="codex.projector_test",
            always_include=focus_ids,
            max_automatic_items=3,
        ),
    )
    return RepresentationProjectionInput(
        world=world,
        agent_state=AgentState(facts=facts),
        predicate_snapshot=focused,
        previous_world=previous_world,
    )


def _world(
    *,
    cursor: int = 7,
    enemy_hp: int = 5,
) -> SubjectiveWorldState:
    """Build one dense subjective world with no objective hidden contact."""
    session = ObservationSessionState(
        session_id="session",
        player_type="codex",
        name="Codex",
        connection_status="connected",
        controlled_entity_uuids=["actor"],
        active_entity_uuid="actor",
        active_entity_name="Hero",
        is_my_turn=True,
    )
    encounter = ObservationEncounterState(
        uuid="encounter",
        name="Projection Test",
        state="active",
        round_number=2,
        current_turn_index=0,
        current_entity_uuid="actor",
        current_entity_name="Hero",
    )
    entities = {
        "actor": ObservationEntityFact(
            uuid="actor",
            name="Hero",
            knowledge_state=KnowledgeState.VISIBLE,
            observer_uuids=["actor"],
            controlled=True,
            position=(2, 2),
            hp=18,
            normal_hp=18,
            max_hp=24,
            ac=15,
            faction="heroes",
            is_dead=False,
        ),
        "enemy": ObservationEntityFact(
            uuid="enemy",
            name="Goblin",
            knowledge_state=KnowledgeState.VISIBLE,
            observer_uuids=["actor"],
            position=(5, 2),
            hp=enemy_hp,
            normal_hp=enemy_hp,
            max_hp=9,
            ac=13,
            faction="monsters",
            is_dead=False,
        ),
        "remembered-enemy": ObservationEntityFact(
            uuid="remembered-enemy",
            name="Skeleton",
            knowledge_state=KnowledgeState.REMEMBERED,
            observer_uuids=["actor"],
            position=(7, 7),
            faction="monsters",
            is_dead=False,
        ),
        "remembered-ally": ObservationEntityFact(
            uuid="remembered-ally",
            name="Scout",
            knowledge_state=KnowledgeState.SEEN,
            observer_uuids=["actor"],
            position=(1, 3),
            faction="heroes",
            is_dead=False,
        ),
    }
    strike = _row(
        row_id="strike-enemy",
        bucket="entity_actions",
        semantic_id="attack.weapon.melee",
        display_name="Longsword",
        target_type="entity",
        targets=(ActionTarget(index=0, target_uuid="enemy", target_name="Goblin"),),
    )
    missiles = _row(
        row_id="missiles-enemy",
        bucket="entity_actions",
        semantic_id="spell.magic_missile",
        display_name="Magic Missile",
        target_type="multi_entity",
        targets=(ActionTarget(index=0, target_uuid="enemy", target_name="Goblin"),),
        target_options=(
            ActionTarget(index=0, target_uuid="enemy", target_name="Goblin"),
            ActionTarget(
                index=1,
                target_uuid="remembered-enemy",
                target_name="Skeleton",
            ),
        ),
        num_projectiles=3,
        allow_same_target=True,
    )
    end_turn = _row(
        row_id="end-turn",
        bucket="special_commands",
        semantic_id="command.end_turn",
        display_name="End Turn",
        target_type="self",
    )
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=cursor,
        entity_actions=(strike, missiles),
        special_commands=(end_turn,),
    )
    epoch = DecisionEpoch(
        epoch_id="epoch-7",
        epoch_index=7,
        basis_observation_cursor=cursor,
        reason=DecisionEpochReason.ACTION_COMPLETED,
        actor_uuid="actor",
        round_number=2,
        turn_index=0,
        economy=ActionEconomyState(
            actor_uuid="actor",
            actions=1,
            bonus_actions=1,
            reactions=1,
            movement_remaining=25,
            meaningful_commands_remaining=True,
        ),
        affordances=affordances,
    )
    logs = [
        {
            "entry_type": "attack",
            "source_name": "Hero",
            "target_name": "Goblin",
            "compact": f"visible log {index}",
            "success": True,
            "sub_entries": [
                {
                    "entry_type": "damage_taken",
                    "target_name": "Goblin",
                    "compact": f"child {child}",
                    "success": True,
                }
                for child in range(9)
            ],
        }
        for index in range(4)
    ]
    return SubjectiveWorldState(
        observation_cursor=cursor,
        session=session,
        encounter=encounter,
        known_entities=entities,
        known_objects={
            "door": ObservationObjectFact(
                uuid="door",
                name="Ancient Door",
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                position=(3, 2),
                state=ItemObservationState(
                    blocks_movement=True,
                    blocks_vision=True,
                    is_pickable=False,
                    is_usable=True,
                    stack_count=1,
                    is_hazardous=False,
                    is_open=False,
                ),
            ),
        },
        known_tiles={
            "2,2": ObservationTileFact(
                key="2,2",
                position=(2, 2),
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                walkable=True,
                walking_cost=5,
                is_hazardous=False,
            ),
            "3,2": ObservationTileFact(
                key="3,2",
                position=(3, 2),
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                walkable=True,
                walking_cost=10,
                is_hazardous=True,
                directional_blocks_vision={"east": True},
            ),
            "4,2": ObservationTileFact(
                key="4,2",
                position=(4, 2),
                knowledge_state=KnowledgeState.SEEN,
                observer_uuids=["actor"],
                walkable=False,
                walking_cost=5,
                is_hazardous=False,
            ),
        },
        combat_logs=logs,
        current_epoch=epoch,
        epoch_cursor=7,
    )


def _row(
    *,
    row_id: str,
    source_action_id: str | None = None,
    bucket: ActionBucket,
    semantic_id: str,
    display_name: str,
    target_type: str,
    targets: tuple[ActionTarget, ...] = (),
    target_options: tuple[ActionTarget, ...] = (),
    num_projectiles: int | None = None,
    allow_same_target: bool | None = None,
) -> ActionAffordance:
    """Build one complete legal row for projection tests."""
    return ActionAffordance(
        row_id=row_id,
        source=ActionSourceDefinition(
            source_action_id=source_action_id or row_id,
            bucket=bucket,
            template_name=display_name,
            semantic_key=semantic_id,
            display_name=display_name,
            action_category="spell" if semantic_id.startswith("spell.") else "ability",
            target_type=target_type,
            can_afford=True,
            cost=ActionCostProfile(action_cost=1, affordability="affordable"),
            target_options=target_options,
            num_projectiles=num_projectiles,
            allow_same_target=allow_same_target,
            semantic_id=semantic_id,
        ),
        targets=targets,
    )


def _block(representation, component_id: str, expected_type):
    """Return and narrow one emitted discriminated block."""
    block = next(
        row for row in representation.blocks if row.component_id == component_id
    )
    assert isinstance(block, expected_type)
    return block
