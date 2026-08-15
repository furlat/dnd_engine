"""Focused integration tests for canonical live subjective replication."""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import uuid4

import pytest
import server.player_replication.mapper as presentation_mapper_module
import server.player_replication.runtime as replication_runtime_module

from dnd.actions.standard import (
    MovementEvent,
    Move,
    SpellEvent,
)
from dnd.actions.operations import execute_use_action
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.conditions import GreaterInvisibilityEffect
from dnd.controller import Controller
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.world_events import (
    MovementTrajectory,
    StepMovementEvent,
)
from dnd.core.gridmap import GridMap, LightLevel
from dnd.core.traversal_connectors import (
    ConnectorProvocationPolicy,
    TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.content.spike_trap_materialization import materialize_spike_trap_effect
from dnd.items.consumables import GREATER_INVISIBILITY_POTION_RECIPE
from dnd.items.torches import TORCH_RECIPE, Torch
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import DndEventStream
from server.player_replay_capture import subjective_replay_capture_store
from server.player_replication.journal import (
    SubjectiveFrameProjectionContext,
    SubjectiveJournalIdentityError,
    SubjectiveJournalStore,
    SubjectiveJournalUnhealthyError,
    SubjectiveProjectionError,
    SubjectiveSubscriptionClosedError,
)
from server.player_replication.mapper import (
    CausalEventBatch,
    MovementRootDeliveryScope,
    MovementRootProjectionContext,
    MovementRootProjectionView,
)
from server.player_replication.runtime import (
    CanonicalSubjectiveReplicationContext,
    CanonicalSubjectiveReplicationRuntime,
    MovementRootCaptureHealth,
    SubjectiveBootstrapDeferredError,
    SubjectiveRuntimeIdentityError,
)
from server.player_replication_contract import (
    ActionPresentationCue,
    ConditionOperation,
    ConditionPresentationCue,
    ConnectorSetReplacePatch,
    DamagePresentationCue,
    EncounterReplacePatch,
    EntityRemovePatch,
    EntityUpsertPatch,
    ItemActionPresentationCue,
    LightPresentationCue,
    LocomotionFamily,
    LocomotionTrajectory,
    MovementPresentationCue,
    PlayerReplicationWatermarks,
    PresentationDeliveryMode,
    ObserverVisibilityReplacePatch,
    SpellPresentationCue,
    SubjectiveCombatLogDelivery,
    SubjectiveFrameDelivery,
    SubjectiveReplicationFrame,
    SubjectiveSyncDelivery,
    VisualLoadoutReplacePatch,
)
from server.replication_perspective import PerspectiveScope
from server.subjective_authority import ResolvedSubjectiveAuthority
from server.timeline_contracts import CombatLogProjection


@dataclass(frozen=True)
class RuntimeScene:
    grid: GridMap
    observer: Entity
    encounter: Encounter
    authority: ResolvedSubjectiveAuthority
    source_stream: DndEventStream
    runtime: CanonicalSubjectiveReplicationRuntime
    context: CanonicalSubjectiveReplicationContext


def _materialize_test_actor(
    *,
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    """Build one exact authored actor without unrelated default possessions."""
    runtime_entity_uuid = uuid4()
    return materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID["goblin"],
        runtime_entity_uuid=runtime_entity_uuid,
        display_name=name,
        faction=faction,
        position=position,
        deployment_role=CreatureDeploymentRole(
            role_id=(
                "tests.canonical_replication_runtime.actor_"
                f"{runtime_entity_uuid.hex}"
            ),
        ),
        possession_mode=CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY,
    )


def _authority(
    observer: Entity,
    *,
    epoch: str = "perspective-1",
    session_id: str = "session-1",
) -> ResolvedSubjectiveAuthority:
    observer_uuid = str(observer.uuid)
    return ResolvedSubjectiveAuthority(
        scope=PerspectiveScope(
            session_id=session_id,
            membership_id="membership-1",
            authority_epoch=1,
            projection=CombatLogProjection.SUBJECTIVE,
            controlled_entity_uuids=(observer_uuid,),
            observer_entity_uuids=(observer_uuid,),
            active_observer_uuid=observer_uuid,
        ),
        perspective_epoch_id=epoch,
    )


@pytest.fixture
def runtime_scene() -> Iterator[RuntimeScene]:
    grid = reset_engine_runtime(grid_size=(3, 1))
    observer = _materialize_test_actor(
        name="Observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    observer.senses.entities = {}
    observer.senses.objects = {}

    encounter = Encounter(name="Runtime encounter", source_entity_uuid=observer.uuid)
    EventQueue.set_combat_log_callback(encounter._on_event_combat_log)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    authority = _authority(observer)
    context = runtime.bind(authority, encounter=encounter)
    try:
        yield RuntimeScene(
            grid=grid,
            observer=observer,
            encounter=encounter,
            authority=authority,
            source_stream=source_stream,
            runtime=runtime,
            context=context,
        )
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def _log(observer: Entity, text: str) -> CombatLogEntry:
    return CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=observer.name,
        source_uuid=str(observer.uuid),
        compact=text,
        verbose=text,
        detailed=text,
    )


def test_normal_log_is_delivered_after_its_causal_observation_frame(
    runtime_scene: RuntimeScene,
) -> None:
    """Objective finalization cannot overtake the reducer's event barrier."""
    context = runtime_scene.context
    snapshot = context.subscribe_with_backfill(
        from_observation_cursor=0,
        from_combat_log_cursor=0,
    )
    subscription = snapshot.subscription
    sync = asyncio.run(subscription.get())
    assert isinstance(sync, SubjectiveSyncDelivery)
    assert sync == snapshot.sync
    assert snapshot.observation_backfill.frames == ()
    assert snapshot.combat_log_backfill.frames == ()

    with EventQueue.batch_on_event_callbacks():
        declaration = Event(
            event_type=EventType.BASE_ACTION,
            source_entity_uuid=runtime_scene.observer.uuid,
            combat_log=_log(runtime_scene.observer, "Observed action"),
        )
        declaration.phase_to(EventPhase.COMPLETION)

    frame_delivery = asyncio.run(subscription.get())
    log_delivery = asyncio.run(subscription.get())
    assert isinstance(frame_delivery, SubjectiveFrameDelivery)
    assert isinstance(log_delivery, SubjectiveCombatLogDelivery)
    assert frame_delivery.frame.presentation == ()
    assert frame_delivery.frame.watermarks.source_event_cursor == EventQueue.event_cursor()
    assert frame_delivery.frame.watermarks.observation_cursor == 1
    assert frame_delivery.frame.watermarks.combat_log_cursor == 0
    assert log_delivery.frame.event_cursor == frame_delivery.frame.watermarks.source_event_cursor
    assert log_delivery.frame.combat_log_cursor == 1
    assert log_delivery.watermarks.observation_cursor == 1
    assert log_delivery.watermarks.combat_log_cursor == 1
    assert context.journal.watermarks == log_delivery.watermarks


def test_standalone_log_releases_immediately_behind_consumed_barrier(
    runtime_scene: RuntimeScene,
) -> None:
    """A standalone exact slot needs no later dummy event to reach subscribers."""
    context = runtime_scene.context
    subscription = context.subscribe()
    asyncio.run(subscription.get())
    opening_watermarks = context.journal.watermarks

    EventQueue.push_combat_log(
        _log(runtime_scene.observer, "Standalone observation"),
        runtime_scene.observer.uuid,
    )

    delivery = asyncio.run(subscription.get())
    assert isinstance(delivery, SubjectiveCombatLogDelivery)
    assert delivery.frame.event_cursor == opening_watermarks.source_event_cursor
    assert delivery.watermarks.observation_cursor == opening_watermarks.observation_cursor
    assert delivery.watermarks.combat_log_cursor == 1


def test_bind_catches_up_exact_existing_logs_at_the_opening_event_cursor() -> None:
    """A mid-game perspective seed includes all exact reducer log inputs."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Late observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True}
    observer.senses.seen = {(0, 0)}
    observer.senses.entities = {}
    observer.senses.objects = {}
    encounter = Encounter(name="Existing history", source_entity_uuid=observer.uuid)
    EventQueue.set_combat_log_callback(encounter._on_event_combat_log)
    source_stream = DndEventStream()
    source_stream.ensure_attached()
    with EventQueue.batch_on_event_callbacks():
        declaration = Event(
            event_type=EventType.BASE_ACTION,
            source_entity_uuid=observer.uuid,
            combat_log=_log(observer, "Before join"),
        )
        declaration.phase_to(EventPhase.COMPLETION)

    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    try:
        context = runtime.bind(_authority(observer), encounter=encounter)
        bootstrap = context.bootstrap()
        assert bootstrap.watermarks.source_event_cursor == EventQueue.event_cursor()
        assert bootstrap.watermarks.observation_cursor == 0
        assert bootstrap.watermarks.combat_log_cursor == 1
        assert bootstrap.combat_log_frames.total == 1
        assert bootstrap.combat_log_frames.frames[0].entry is not None
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_batch_world_diff_is_injected_as_typed_patches(
    runtime_scene: RuntimeScene,
) -> None:
    """Every consumed causal batch carries the same-boundary world reduction."""
    subscription = runtime_scene.context.subscribe()
    asyncio.run(subscription.get())
    runtime_scene.observer.name = "Renamed observer"

    Event(
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=runtime_scene.observer.uuid,
    )

    delivery = asyncio.run(subscription.get())
    assert isinstance(delivery, SubjectiveFrameDelivery)
    upserts = [
        patch
        for patch in delivery.frame.patches
        if isinstance(patch, EntityUpsertPatch)
    ]
    assert len(upserts) == 1
    assert upserts[0].entity.name == "Renamed observer"


def test_real_torch_ignite_is_one_authoritative_subjective_light_frame() -> None:
    """Igniting a carried torch must deliver its complete sensory replacement."""
    grid = reset_engine_runtime(grid_size=(5, 1))
    for tile in grid.get_all_tiles().values():
        tile.default_light = LightLevel.DARKNESS
    observer = materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID["goblin"],
        runtime_entity_uuid=uuid4(),
        display_name="Torchbearer",
        faction="heroes",
        position=(2, 0),
        deployment_role=CreatureDeploymentRole(
            role_id="tests.replication.torchbearer",
        ),
        possession_mode=CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY,
    )
    torch = materialize_item(
        TORCH_RECIPE,
        observer.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    assert observer.loot_item(torch)
    stored_torch = next(
        item
        for item in observer.inventory.items.values()
        if item.stack_id == torch.stack_id
    )
    Entity.update_all_entities_senses(max_distance=10)

    encounter = Encounter(name="Torch encounter", source_entity_uuid=observer.uuid)
    encounter.add_combatant(
        observer,
        Controller(source_entity_uuid=observer.uuid, name="Torch controller"),
    )
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    context = runtime.bind(_authority(observer), encounter=encounter)
    subscription = context.subscribe()
    try:
        sync = asyncio.run(subscription.get())
        assert isinstance(sync, SubjectiveSyncDelivery)

        result = execute_use_action(
            observer,
            stored_torch.uuid,
            "Ignite Torch",
        )
        assert result is not None and not result.canceled

        delivery = asyncio.run(subscription.get())
        assert isinstance(delivery, SubjectiveFrameDelivery)
        frame = delivery.frame
        assert tuple(type(cue) for cue in frame.presentation) == (
            ActionPresentationCue,
            LightPresentationCue,
        )
        action = frame.presentation[0]
        assert isinstance(action, ActionPresentationCue)
        assert action.content_attributions[0].definition_ref.content_id == (
            "action.item.torch.ignite"
        )
        light = frame.presentation[1]
        assert isinstance(light, LightPresentationCue)
        assert light.observer_uuid == str(observer.uuid)
        assert any(
            cell.position == observer.position
            and cell.light_level == LightLevel.VERY_BRIGHT.value
            for cell in light.cells
        )
        visibility = next(
            patch
            for patch in frame.patches
            if isinstance(patch, ObserverVisibilityReplacePatch)
        )
        assert visibility.observer_uuid == str(observer.uuid)
        assert visibility.visibility.effective_light_levels == {
            f"{cell.position[0]},{cell.position[1]}": cell.light_level
            for cell in light.cells
        }
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_each_committed_movement_step_has_authoritative_perception_frame() -> None:
    """Moving light commits exact world/light replacements at every arrival."""
    grid = reset_engine_runtime(grid_size=(5, 1))
    for tile in grid.get_all_tiles().values():
        tile.default_light = LightLevel.DARKNESS
    observer = materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID["goblin"],
        runtime_entity_uuid=uuid4(),
        display_name="Moving torchbearer",
        faction="heroes",
        position=(0, 0),
        deployment_role=CreatureDeploymentRole(
            role_id="tests.replication.moving_torchbearer",
        ),
        possession_mode=CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY,
    )
    torch = materialize_item(
        TORCH_RECIPE,
        observer.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    assert observer.loot_item(torch)
    stored_torch = next(
        item
        for item in observer.inventory.items.values()
        if item.stack_id == torch.stack_id
    )
    assert isinstance(stored_torch, Torch)
    stored_torch.ignite(observer.uuid)
    Entity.update_all_entities_senses(max_distance=10)

    encounter = Encounter(name="Moving light encounter", source_entity_uuid=observer.uuid)
    encounter.add_combatant(
        observer,
        Controller(source_entity_uuid=observer.uuid, name="Torch controller"),
    )
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    context = runtime.bind(_authority(observer), encounter=encounter)
    try:
        result = Move(
            source_entity_uuid=observer.uuid,
            end_position=(3, 0),
            path=((0, 0), (1, 0), (2, 0), (3, 0)),
            use_movement_cost=False,
        ).apply()
        assert result is not None and not result.canceled

        frames = context.frames(from_observation_cursor=0).frames
        movement_frames = tuple(
            frame
            for frame in frames
            if any(
                isinstance(cue, MovementPresentationCue)
                for cue in frame.presentation
            )
        )
        assert len(movement_frames) == 3
        presentation_ids: set[str] = set()
        for path_index, frame in enumerate(movement_frames, start=1):
            movement = next(
                cue
                for cue in frame.presentation
                if isinstance(cue, MovementPresentationCue)
            )
            assert tuple(anchor.position for anchor in movement.anchors) == (
                (path_index - 1, 0),
                (path_index, 0),
            )
            assert movement.locomotion_family is LocomotionFamily.WALK
            assert movement.trajectory_family is LocomotionTrajectory.PATH
            assert movement.endpoint_outcome.value == "committed"
            presentation_ids.add(movement.presentation_id)
            upsert = next(
                patch
                for patch in frame.patches
                if isinstance(patch, EntityUpsertPatch)
                and patch.entity.uuid == str(observer.uuid)
            )
            assert upsert.entity.position == (path_index, 0)
            visibility = next(
                patch
                for patch in frame.patches
                if isinstance(patch, ObserverVisibilityReplacePatch)
                and patch.observer_uuid == str(observer.uuid)
            )
            observer_light_cues = tuple(
                cue
                for cue in frame.presentation
                if isinstance(cue, LightPresentationCue)
                and cue.observer_uuid == str(observer.uuid)
            )
            assert len(observer_light_cues) == 1
            light = observer_light_cues[0]
            assert visibility.visibility.effective_light_levels == {
                f"{cell.position[0]},{cell.position[1]}": cell.light_level
                for cell in light.cells
            }
            assert visibility.visibility.position == (path_index, 0)
        assert len(presentation_ids) == 3
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_spike_damage_is_scheduled_after_its_destination_arrival(
    runtime_scene: RuntimeScene,
) -> None:
    """Real entry damage follows its exact committed destination segment."""
    scene = runtime_scene
    starting_cursor = scene.context.journal.watermarks.observation_cursor
    materialize_spike_trap_effect({(1, 0)})
    Entity.update_all_entities_senses(max_distance=10)

    with fixed_dice_faces(1, 1):
        result = Move(
            source_entity_uuid=scene.observer.uuid,
            end_position=(1, 0),
            path=((0, 0), (1, 0)),
            use_movement_cost=False,
        ).apply()
    assert result is not None and not result.canceled, (
        (
            result.status_message,
            result.canceled_from_phase,
            result.termination_reason,
        )
        if result is not None
        else None
    )

    frames = scene.context.frames(
        from_observation_cursor=starting_cursor,
    ).frames
    frame = next(
        candidate
        for candidate in frames
        if any(
            isinstance(cue, MovementPresentationCue)
            for cue in candidate.presentation
        )
        and any(
            isinstance(cue, DamagePresentationCue)
            for cue in candidate.presentation
        )
    )
    movement = next(
        cue for cue in frame.presentation
        if isinstance(cue, MovementPresentationCue)
    )
    damage = next(
        cue for cue in frame.presentation
        if isinstance(cue, DamagePresentationCue)
    )
    assert tuple(anchor.position for anchor in movement.anchors) == (
        (0, 0),
        (1, 0),
    )
    assert movement.locomotion_family is LocomotionFamily.WALK
    assert movement.trajectory_family is LocomotionTrajectory.PATH
    assert movement.parent_presentation_id is None
    assert damage.parent_presentation_id is None
    assert frame.presentation.index(movement) < frame.presentation.index(damage)
    assert damage.target_uuid == str(scene.observer.uuid)
    assert damage.damage_types == ("Piercing",)


def test_live_connector_lifecycle_and_privacy_replace_replica_state(
    runtime_scene: RuntimeScene,
) -> None:
    """Register/disable/hide/reveal/remove all reach the canonical journal."""
    scene = runtime_scene

    def connector_patches_since(
        cursor: int,
    ) -> tuple[ConnectorSetReplacePatch, ...]:
        return tuple(
            patch
            for frame in scene.context.frames(
                from_observation_cursor=cursor,
            ).frames
            for patch in frame.patches
            if isinstance(patch, ConnectorSetReplacePatch)
        )

    definition = TraversalConnectorDefinition(
        authored_id="connector.runtime.delta",
        kind=TraversalConnectorKind.PASSAGE,
        presentation_key="traversal.passage",
        endpoint_positions=((0, 0), (1, 0)),
        movement_cost_feet=5,
        action_cost_type=None,
        action_cost_amount=0,
        bidirectional=True,
        enabled=True,
        provocation_policy=ConnectorProvocationPolicy.DOES_NOT_PROVOKE,
    )

    cursor = scene.context.journal.watermarks.observation_cursor
    connector = scene.grid.register_connector(definition)
    assert connector is not None
    registered = connector_patches_since(cursor)
    assert registered
    assert [row.uuid for row in registered[-1].connectors] == [str(connector.uuid)]

    cursor = scene.context.journal.watermarks.observation_cursor
    disabled = scene.grid.set_connector_enabled(connector.uuid, False)
    assert disabled is not None
    disabled_patches = connector_patches_since(cursor)
    assert disabled_patches and disabled_patches[-1].connectors[0].enabled is False

    scene.observer.senses.visible[(1, 0)] = False
    cursor = scene.context.journal.watermarks.observation_cursor
    Event(
        source_entity_uuid=scene.observer.uuid,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.COMPLETION)
    hidden = connector_patches_since(cursor)
    assert hidden and hidden[-1].connectors == ()

    scene.observer.senses.visible[(1, 0)] = True
    cursor = scene.context.journal.watermarks.observation_cursor
    Event(
        source_entity_uuid=scene.observer.uuid,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.COMPLETION)
    revealed = connector_patches_since(cursor)
    assert revealed and len(revealed[-1].connectors) == 1

    cursor = scene.context.journal.watermarks.observation_cursor
    assert scene.grid.remove_connector(connector.uuid) is True
    removed = connector_patches_since(cursor)
    assert removed and removed[-1].connectors == ()


def test_greater_invisibility_reveal_is_one_closed_subjective_frame() -> None:
    """A revealing cast restores state and cues at the same censored boundary."""
    grid = reset_engine_runtime(grid_size=(5, 1))
    observer = _materialize_test_actor(
        name="Observer",
        position=(0, 0),
        faction="heroes",
    )
    caster = _materialize_test_actor(
        name="Invisible caster",
        position=(2, 0),
        faction="monsters",
    )
    potion = materialize_item(
        GREATER_INVISIBILITY_POTION_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert caster.loot_item(potion)
    stored_potion = next(
        item
        for item in caster.inventory.items.values()
        if item.stack_id == potion.stack_id
    )
    Entity.update_all_entities_senses(max_distance=10)
    assert caster.uuid in observer.senses.entities

    encounter = Encounter(name="Reveal encounter", source_entity_uuid=observer.uuid)
    encounter.add_combatant(
        observer,
        Controller(source_entity_uuid=observer.uuid, name="Observer controller"),
    )
    encounter.add_combatant(
        caster,
        Controller(source_entity_uuid=caster.uuid, name="Caster controller"),
    )
    with fixed_dice_faces(10, 10):
        encounter.start_encounter()

    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    context = runtime.bind(_authority(observer), encounter=encounter)
    subscription = context.subscribe()

    def next_frame() -> SubjectiveFrameDelivery:
        while True:
            delivery = asyncio.run(subscription.get())
            if isinstance(delivery, SubjectiveFrameDelivery):
                return delivery

    try:
        sync = asyncio.run(subscription.get())
        assert isinstance(sync, SubjectiveSyncDelivery)
        assert any(
            entity.uuid == str(caster.uuid)
            for entity in context.bootstrap().world.state.entities
        )

        potion_result = execute_use_action(
            caster,
            stored_potion.uuid,
            "Drink Greater Invisibility Potion",
        )
        assert potion_result is not None and not potion_result.canceled
        assert caster.is_invisible is True
        assert caster.uuid not in observer.senses.entities

        hidden = next_frame().frame
        assert tuple(type(patch) for patch in hidden.patches) == (
            EntityRemovePatch,
            EncounterReplacePatch,
            ObserverVisibilityReplacePatch,
        )
        removal = hidden.patches[0]
        assert isinstance(removal, EntityRemovePatch)
        assert removal.entity_uuid == str(caster.uuid)
        assert tuple(type(cue) for cue in hidden.presentation) == (
            ItemActionPresentationCue,
            ConditionPresentationCue,
            LightPresentationCue,
        )
        applied = hidden.presentation[1]
        assert isinstance(applied, ConditionPresentationCue)
        assert applied.target_uuid == str(caster.uuid)
        assert applied.condition_name == "Invisible"
        assert applied.operation is ConditionOperation.APPLIED
        assert all(
            entity.uuid != str(caster.uuid)
            for entity in context.bootstrap().world.state.entities
        )

        invisible = caster.active_conditions["Invisible"]
        assert isinstance(invisible, GreaterInvisibilityEffect)
        invisible.base_dc = 100
        with fixed_dice_faces(1):
            with EventQueue.batch_on_event_callbacks():
                spell = SpellEvent(
                    name="Fireball",
                    spell_id="fireball",
                    source_entity_uuid=caster.uuid,
                    source_entity_name=caster.name,
                    source_position=caster.position,
                    spell_level=3,
                    cast_at_level=3,
                    spell_school="evocation",
                    range_type="ranged",
                )
                spell = spell.phase_to(EventPhase.EXECUTION)
                spell = spell.phase_to(EventPhase.EFFECT)
                spell = spell.phase_to(EventPhase.COMPLETION)

        observer_key = str(observer.uuid)
        caster_key = str(caster.uuid)
        assert observer_key in spell.identified_entity_observer_uuids[caster_key]
        assert caster.is_invisible is False
        assert "Invisible" not in caster.active_conditions
        assert caster.uuid in observer.senses.entities

        revealed = next_frame().frame
        assert revealed.watermarks.observation_cursor == (
            hidden.watermarks.observation_cursor + 1
        )
        assert tuple(type(patch) for patch in revealed.patches) == (
            EntityUpsertPatch,
            EncounterReplacePatch,
            ObserverVisibilityReplacePatch,
            VisualLoadoutReplacePatch,
        )
        upsert = revealed.patches[0]
        assert isinstance(upsert, EntityUpsertPatch)
        assert upsert.entity.uuid == caster_key
        assert "Invisible" not in upsert.entity.conditions
        visibility = revealed.patches[2]
        assert isinstance(visibility, ObserverVisibilityReplacePatch)
        assert visibility.observer_uuid == observer_key
        assert caster_key in visibility.visibility.visible_entities
        loadout = revealed.patches[3]
        assert isinstance(loadout, VisualLoadoutReplacePatch)
        assert loadout.loadout.entity_uuid == caster_key

        assert tuple(type(cue) for cue in revealed.presentation) == (
            SpellPresentationCue,
            ConditionPresentationCue,
            LightPresentationCue,
        )
        cast = revealed.presentation[0]
        assert isinstance(cast, SpellPresentationCue)
        assert cast.actor_uuid == caster_key
        assert cast.spell_id == "fireball"
        removed = revealed.presentation[1]
        assert isinstance(removed, ConditionPresentationCue)
        assert removed.target_uuid == caster_key
        assert removed.condition_name == "Invisible"
        assert removed.operation is ConditionOperation.REMOVED
        light = revealed.presentation[2]
        assert isinstance(light, LightPresentationCue)
        assert light.observer_uuid == observer_key
        assert revealed.presentation_from_cursor == hidden.watermarks.presentation_cursor
        assert revealed.watermarks.presentation_cursor == (
            revealed.presentation_from_cursor + len(revealed.presentation)
        )

        current_caster = next(
            entity
            for entity in context.bootstrap().world.state.entities
            if entity.uuid == caster_key
        )
        assert current_caster == upsert.entity
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_repeated_bootstrap_reuses_memory_without_leaking_hidden_mutation(
    runtime_scene: RuntimeScene,
) -> None:
    """A request cannot rebuild unseen cells from mutable objective state."""
    first = runtime_scene.context.bootstrap()
    first_tile = next(tile for tile in first.world.state.grid.tiles if (tile.x, tile.y) == (1, 0))
    assert first_tile.visible is True
    original_name = first_tile.name

    runtime_scene.observer.senses.visible[(1, 0)] = False
    hidden_tile = runtime_scene.grid.get_tile(1, 0)
    assert hidden_tile is not None
    hidden_tile.name = "Secret changed terrain"

    repeated = runtime_scene.context.bootstrap()
    remembered = next(
        tile
        for tile in repeated.world.state.grid.tiles
        if (tile.x, tile.y) == (1, 0)
    )
    assert remembered.visible is False
    assert remembered.name == original_name
    assert "Secret changed terrain" not in repeated.model_dump_json()


def test_authority_rotation_closes_stream_and_drops_old_spatial_memory(
    runtime_scene: RuntimeScene,
) -> None:
    """A new perspective epoch cannot resume a prior epoch's journal or memory."""
    old_context = runtime_scene.context
    old_key = old_context.partition_key
    subscription = old_context.subscribe()
    asyncio.run(subscription.get())

    runtime_scene.observer.senses.visible[(1, 0)] = False
    hidden_tile = runtime_scene.grid.get_tile(1, 0)
    assert hidden_tile is not None
    hidden_tile.name = "Changed after authority rotation"
    rotated = _authority(runtime_scene.observer, epoch="perspective-2")
    new_context = runtime_scene.runtime.bind(rotated, encounter=runtime_scene.encounter)

    assert new_context is not old_context
    assert new_context.partition_key != old_key
    assert old_context.healthy is False
    with pytest.raises(SubjectiveSubscriptionClosedError):
        asyncio.run(subscription.get())
    with pytest.raises(SubjectiveJournalIdentityError):
        runtime_scene.runtime.get(old_key)
    assert all(
        (tile.x, tile.y) != (1, 0)
        for tile in new_context.bootstrap().world.state.grid.tiles
    )


def test_generation_reset_retires_context_and_reattaches_in_source_first_order(
    runtime_scene: RuntimeScene,
) -> None:
    """Reset closes stale subscribers and opens only a new generation partition."""
    old_context = runtime_scene.context
    old_key = old_context.partition_key
    subscription = old_context.subscribe()
    asyncio.run(subscription.get())

    EventQueue.reset()
    EventQueue.set_combat_log_callback(runtime_scene.encounter._on_event_combat_log)
    runtime_scene.runtime.ensure_attached()

    assert old_context.healthy is False
    with pytest.raises(SubjectiveSubscriptionClosedError):
        asyncio.run(subscription.get())
    with pytest.raises(SubjectiveJournalIdentityError):
        runtime_scene.runtime.get(old_key)
    with pytest.raises(SubjectiveRuntimeIdentityError):
        old_context.bootstrap()

    new_context = runtime_scene.runtime.bind(
        runtime_scene.authority,
        encounter=runtime_scene.encounter,
    )
    assert new_context.protocol.generation_id == str(EventQueue.generation_id())
    assert new_context.partition_key != old_key


def test_expected_identity_validation_never_falls_back(
    runtime_scene: RuntimeScene,
) -> None:
    with pytest.raises(SubjectiveRuntimeIdentityError):
        runtime_scene.context.validate_identity(expected_generation_id="stale")


def test_explicit_foreign_encounter_is_rejected_before_touching_subscribed_source() -> None:
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Source identity observer",
        position=(0, 0),
        faction="heroes",
    )
    subscribed = Encounter(
        name="Subscribed encounter",
        source_entity_uuid=observer.uuid,
    )
    foreign = Encounter(
        name="Foreign encounter",
        source_entity_uuid=observer.uuid,
    )
    EventQueue.set_combat_log_callback(subscribed._on_event_combat_log)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: subscribed,
    )
    authority = _authority(observer)
    try:
        context = runtime.bind(authority, encounter=subscribed)
        with pytest.raises(
            SubjectiveRuntimeIdentityError,
            match="runtime subscribed source",
        ):
            runtime.bind(
                _authority(
                    observer,
                    epoch="foreign-source-epoch",
                    session_id="foreign-source-session",
                ),
                encounter=foreign,
            )
        assert runtime.bind(authority, encounter=subscribed) is context

        subscribed.end_encounter("subscribed source remains exact")
        bundle = subjective_replay_capture_store.build_bundle(
            game_id="subscribed-source-game",
            encounter_uuid=str(subscribed.uuid),
            membership_id="membership-1",
            terminal_source_event_cursor=EventQueue.event_cursor(),
            terminal_combat_log_cursor=len(subscribed.combat_log),
        )
        assert len(bundle.segments) == 1
        assert bundle.segments[0].bootstrap.protocol.source_stream_id == str(
            subscribed.uuid
        )
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_transient_initial_projection_failure_can_rebind_without_reusing_bad_state() -> None:
    """A failed provisional open is discarded without tombstoning its identity."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Retry observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True}
    observer.senses.seen = {(0, 0)}
    observer.senses.entities = {}
    observer.senses.objects = {}
    encounter = Encounter(name="Retry encounter", source_entity_uuid=observer.uuid)
    EventQueue.set_combat_log_callback(encounter._on_event_combat_log)
    source_stream = DndEventStream()
    attempts = 0

    def flaky_grid_provider() -> GridMap:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient grid capture failure")
        return grid

    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=flaky_grid_provider,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    authority = _authority(observer)
    try:
        with pytest.raises(SubjectiveProjectionError, match="transient grid"):
            runtime.bind(authority, encounter=encounter)

        context = runtime.bind(authority, encounter=encounter)
        assert context.healthy is True
        assert context.bootstrap().protocol == context.protocol
        assert attempts >= 2
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def _movement_root_effect(source: Entity) -> MovementEvent:
    """Publish one exact accepted PATH root without an action helper."""
    return MovementEvent(
        source_entity_uuid=source.uuid,
        source_entity_name=source.name,
        start_position=(0, 0),
        end_position=(1, 0),
        requested_end_position=(1, 0),
        objective_end_position=None,
        path=((0, 0), (1, 0)),
        phase=EventPhase.EFFECT,
    )


def _movement_step_completion(
    source: Entity,
    *,
    parent_event,
    committed: bool = True,
    to_position: tuple[int, int] = (1, 0),
    canceled_from_phase: EventPhase | None = None,
) -> StepMovementEvent:
    """Publish one exact committed PATH Step completion."""
    parent = EventQueue.get_event_by_uuid(parent_event)
    return StepMovementEvent(
        source_entity_uuid=source.uuid,
        source_entity_name=source.name,
        from_position=(0, 0),
        to_position=to_position,
        path_index=1,
        total_path_length=2,
        movement_cost=5,
        trajectory=MovementTrajectory.PATH,
        disclosed_path=((0, 0), to_position),
        committed=committed,
        canceled_from_phase=canceled_from_phase,
        parent_event=parent_event,
        parent_lineage=parent.lineage_uuid if parent is not None else None,
        phase=EventPhase.COMPLETION,
    )


def test_root_context_capture_precedes_step_with_zero_partitions() -> None:
    """Passive root capture is source-owned and survives healthy singletons."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Unbound observer",
        position=(0, 0),
        faction="heroes",
    )
    encounter = Encounter(name="Unbound runtime", source_entity_uuid=observer.uuid)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    try:
        runtime.ensure_attached()
        effect = _movement_root_effect(observer)
        assert runtime.movement_root_context_count == 1
        assert runtime.movement_root_alias_count == 1

        _movement_step_completion(observer, parent_event=effect.uuid)
        assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
        assert runtime.movement_root_context_count == 1

        effect.phase_to(EventPhase.COMPLETION)
        assert runtime.movement_root_context_count == 0
    finally:
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_explicit_missing_terminal_audit_evicts_without_poisoning_bootstrap() -> None:
    """Only a real explicit action closure may classify a root incomplete."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Missing terminal observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    encounter = Encounter(name="Missing terminal", source_entity_uuid=observer.uuid)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    try:
        runtime.ensure_attached()
        with EventQueue.batch_on_event_callbacks():
            _movement_root_effect(observer)
            assert runtime.movement_root_context_count == 1
        assert runtime.movement_root_context_count == 0
        assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY

        context = runtime.bind(_authority(observer), encounter=encounter)
        assert context.healthy is True
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_zero_partition_poison_defers_absent_bind_until_exact_batch_closure() -> None:
    """A missing Step root blocks only the in-flight absent-partition bootstrap."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Deferred observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    encounter = Encounter(name="Deferred bootstrap", source_entity_uuid=observer.uuid)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    try:
        runtime.ensure_attached()
        with EventQueue.batch_on_event_callbacks():
            _movement_step_completion(observer, parent_event=uuid4())
            assert (
                runtime.movement_root_capture_health
                is MovementRootCaptureHealth.POISONED_AWAITING_CONTAINING_DELIVERY
            )
            with pytest.raises(SubjectiveBootstrapDeferredError) as deferred:
                runtime.bind(_authority(observer), encounter=encounter)
            assert deferred.value.deferral.code == "source_batch_in_flight"
            assert deferred.value.deferral.retryable is True
            runtime.stop()
            assert runtime.attached is True

        assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
        assert runtime.attached is False
        runtime.ensure_attached()
        context = runtime.bind(_authority(observer), encounter=encounter)
        assert context.healthy is True
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_status_only_effect_alias_resolves_without_recapturing_root() -> None:
    """A later allowed EFFECT UUID is one alias of the same frozen context."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Alias observer",
        position=(0, 0),
        faction="heroes",
    )
    encounter = Encounter(name="Alias runtime", source_entity_uuid=observer.uuid)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    try:
        runtime.ensure_attached()
        effect = _movement_root_effect(observer)
        alias = effect.model_copy(update={
            "uuid": uuid4(),
            "modified": True,
            "status_message": "Allowed status-only effect",
        })
        EventQueue.register(alias)
        assert runtime.movement_root_context_count == 1
        assert runtime.movement_root_alias_count == 2
        _movement_step_completion(observer, parent_event=alias.uuid)
        assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
        alias.phase_to(EventPhase.COMPLETION)
        assert runtime.movement_root_context_count == 0
    finally:
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_alias_seventeen_poison_is_bounded_and_closes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The seeded alias counts toward the exact sixteen-alias cap."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Alias cap observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    encounter = Encounter(name="Alias cap", source_entity_uuid=observer.uuid)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    path_validation_calls = 0
    grant_freeze_calls = 0
    real_require_path = presentation_mapper_module._require_position_path
    real_freeze_grants = presentation_mapper_module._root_source_identity_grants

    def checked_require_path(
        value: object,
        *,
        field_name: str,
        minimum_length: int,
    ) -> tuple[tuple[int, int], ...]:
        nonlocal path_validation_calls
        path_validation_calls += 1
        result = real_require_path(
            value,
            field_name=field_name,
            minimum_length=minimum_length,
        )
        assert result is value
        return result

    def counted_freeze_grants(event: Event) -> frozenset[str]:
        nonlocal grant_freeze_calls
        grant_freeze_calls += 1
        return real_freeze_grants(event)

    monkeypatch.setattr(
        presentation_mapper_module,
        "_require_position_path",
        checked_require_path,
    )
    monkeypatch.setattr(
        presentation_mapper_module,
        "_root_source_identity_grants",
        counted_freeze_grants,
    )
    try:
        runtime.ensure_attached()
        with EventQueue.batch_on_event_callbacks():
            effect = _movement_root_effect(observer)
            for index in range(15):
                EventQueue.register(effect.model_copy(update={
                    "uuid": uuid4(),
                    "modified": True,
                    "status_message": f"Allowed alias {index + 2}",
                }))
            assert runtime.movement_root_alias_count == 16
            EventQueue.register(effect.model_copy(update={
                "uuid": uuid4(),
                "modified": True,
                "status_message": "Rejected alias 17",
            }))
            assert (
                runtime.movement_root_capture_health
                is MovementRootCaptureHealth.POISONED_AWAITING_CONTAINING_DELIVERY
            )
            with pytest.raises(SubjectiveBootstrapDeferredError):
                runtime.bind(_authority(observer), encounter=encounter)
        assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
        assert runtime.movement_root_context_count == 0
        assert path_validation_calls == 18
        assert grant_freeze_calls == 1
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


@pytest.mark.parametrize(
    "updates",
    (
        {"phase": "completion"},
        {
            "phase": EventPhase.COMPLETION,
            "canceled": True,
            "canceled_from_phase": EventPhase.EFFECT,
        },
        {
            "phase": EventPhase.CANCEL,
            "canceled": False,
            "canceled_from_phase": EventPhase.EFFECT,
        },
        {
            "phase": EventPhase.EFFECT,
            "canceled": True,
            "canceled_from_phase": EventPhase.DECLARATION,
        },
        {
            "phase": EventPhase.COMPLETION,
            "event_type": "movement",
        },
    ),
)
@pytest.mark.filterwarnings("ignore:Pydantic serializer warnings:UserWarning")
def test_malformed_root_lifecycle_never_satisfies_terminal_audit(
    updates: dict[str, object],
) -> None:
    """Equal-valued or incoherent root lifecycle evidence poisons exactly once."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Malformed terminal observer",
        position=(0, 0),
        faction="heroes",
    )
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: None,
    )
    try:
        runtime.ensure_attached()
        with EventQueue.batch_on_event_callbacks():
            effect = _movement_root_effect(observer)
            EventQueue.register(
                effect.model_copy(
                    update={"uuid": uuid4(), "modified": True, **updates}
                )
            )
            assert (
                runtime.movement_root_capture_health
                is MovementRootCaptureHealth.POISONED_AWAITING_CONTAINING_DELIVERY
            )
        assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
        assert runtime.movement_root_context_count == 0
    finally:
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_existing_partition_receives_ordered_reset_at_poison_closure(
    runtime_scene: RuntimeScene,
) -> None:
    """Poison keeps the journal healthy and emits no fabricated movement cue."""
    context = runtime_scene.context
    opening = context.journal.watermarks
    with EventQueue.batch_on_event_callbacks():
        _movement_step_completion(
            runtime_scene.observer,
            parent_event=uuid4(),
        )
    frames = context.frames(
        from_observation_cursor=opening.observation_cursor,
    ).frames
    assert len(frames) == 2
    assert all(
        frame.presentation_delivery is PresentationDeliveryMode.RESET_REQUIRED
        and frame.presentation == ()
        and frame.watermarks.presentation_cursor == opening.presentation_cursor
        for frame in frames
    )
    assert frames[0].watermarks.source_event_cursor > opening.source_event_cursor
    assert (
        frames[1].watermarks.source_event_cursor
        == frames[0].watermarks.source_event_cursor
    )
    assert context.healthy is True
    assert (
        runtime_scene.runtime.movement_root_capture_health
        is MovementRootCaptureHealth.HEALTHY
    )


def test_healthy_singleton_sequence_survives_until_terminal_root() -> None:
    """Singleton root/Step deliveries are boundaries, not incomplete audits."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Singleton observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    encounter = Encounter(name="Singleton runtime", source_entity_uuid=observer.uuid)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    try:
        context = runtime.bind(_authority(observer), encounter=encounter)
        effect = _movement_root_effect(observer)
        assert runtime.movement_root_context_count == 1
        _movement_step_completion(observer, parent_event=effect.uuid)
        assert runtime.movement_root_context_count == 1
        effect.phase_to(EventPhase.COMPLETION)
        assert runtime.movement_root_context_count == 0
        frames = context.frames(from_observation_cursor=0).frames
        assert sum(
            isinstance(cue, MovementPresentationCue)
            for frame in frames
            for cue in frame.presentation
        ) == 1
        assert all(
            frame.presentation_delivery is PresentationDeliveryMode.NORMAL
            for frame in frames
        )
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_poison_closure_is_sole_terminal_reset_authority(
    runtime_scene: RuntimeScene,
) -> None:
    """An intermediate reset cannot carry ended state or terminal authority."""
    context = runtime_scene.context
    opening = context.journal.watermarks.observation_cursor
    with EventQueue.batch_on_event_callbacks():
        _movement_step_completion(
            runtime_scene.observer,
            parent_event=uuid4(),
        )
        terminal = runtime_scene.encounter.end_encounter("Poison terminal")
    frames = context.frames(from_observation_cursor=opening).frames
    assert len(frames) == 2
    intermediate, final = frames
    assert intermediate.encounter_terminal is None
    assert not any(
        isinstance(patch, EncounterReplacePatch)
        and patch.encounter is not None
        and patch.encounter.state == "ended"
        for patch in intermediate.patches
    )
    assert final.encounter_terminal is not None
    assert final.encounter_terminal.source_event_uuid == terminal.uuid
    assert final.encounter_terminal.source_event_cursor == final.watermarks.source_event_cursor
    assert final.encounter_terminal.terminal_authority_id == (
        f"{final.perspective_epoch_id}:{final.watermarks.observation_cursor}:"
        f"reset-terminal:{terminal.uuid}"
    )
    assert any(
        isinstance(patch, EncounterReplacePatch)
        and patch.encounter is not None
        and patch.encounter.state == "ended"
        for patch in final.patches
    )


def test_uncommitted_step_completion_is_an_immediate_runtime_boundary() -> None:
    """Reaction-bearing NOT_COMMITTED Steps are not deferred to root completion."""
    captured: list[CausalEventBatch] = []

    class RecordingProjector:
        def project_frame(
            self,
            source: CausalEventBatch,
            context: SubjectiveFrameProjectionContext,
        ) -> SubjectiveReplicationFrame:
            captured.append(source)
            return SubjectiveReplicationFrame(
                source_stream_id=context.protocol.source_stream_id,
                generation_id=context.protocol.generation_id,
                perspective_epoch_id=context.perspective.perspective_epoch_id,
                watermarks=PlayerReplicationWatermarks(
                    source_event_cursor=source.through_source_event_cursor,
                    observation_cursor=context.next_observation_cursor,
                    presentation_cursor=(
                        context.previous_watermarks.presentation_cursor
                    ),
                    combat_log_cursor=context.previous_watermarks.combat_log_cursor,
                ),
                presentation_from_cursor=(
                    context.previous_watermarks.presentation_cursor
                ),
                patches=source.patches,
                presentation=(),
            )

    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Stopped Step observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    encounter = Encounter(name="Stopped Step", source_entity_uuid=observer.uuid)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
        frame_projector=RecordingProjector(),
    )
    try:
        runtime.bind(_authority(observer), encounter=encounter)
        effect = _movement_root_effect(observer)
        captured.clear()
        step = _movement_step_completion(
            observer,
            parent_event=effect.uuid,
            committed=False,
        )
        assert len(captured) == 1
        assert captured[0].slots[-1].event is step
        assert captured[0].movement_root_contexts[0].context.lineage_uuid == (
            effect.lineage_uuid
        )
        effect.phase_to(EventPhase.COMPLETION)
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_shared_root_context_copies_once_and_validates_each_step_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path capture is O(n) once; partition work is one indexed check per Step."""
    grid = reset_engine_runtime(grid_size=(4, 1))
    observer = _materialize_test_actor(
        name="Shared context observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {
        (0, 0): True,
        (1, 0): True,
        (2, 0): True,
        (3, 0): True,
    }
    observer.senses.seen = set(observer.senses.visible)
    Entity.update_all_entities_senses(max_distance=10)
    encounter = Encounter(name="Shared contexts", source_entity_uuid=observer.uuid)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    capture_calls = 0
    runtime_validation_calls = 0
    partition_validation_calls = 0
    real_capture = replication_runtime_module.capture_movement_root_context
    real_validate = presentation_mapper_module.validate_step_against_movement_root

    def counted_capture(
        event: Event,
        *,
        source_event_cursor: int,
        generation_id: str,
        delivery_scope: MovementRootDeliveryScope,
    ) -> MovementRootProjectionView:
        nonlocal capture_calls
        capture_calls += 1
        return real_capture(
            event,
            source_event_cursor=source_event_cursor,
            generation_id=generation_id,
            delivery_scope=delivery_scope,
        )

    def counted_runtime_validate(
        step: StepMovementEvent,
        context: MovementRootProjectionContext,
    ) -> None:
        nonlocal runtime_validation_calls
        runtime_validation_calls += 1
        real_validate(step, context)

    def counted_partition_validate(
        step: StepMovementEvent,
        context: MovementRootProjectionContext,
    ) -> None:
        nonlocal partition_validation_calls
        partition_validation_calls += 1
        real_validate(step, context)

    monkeypatch.setattr(
        replication_runtime_module,
        "capture_movement_root_context",
        counted_capture,
    )
    monkeypatch.setattr(
        replication_runtime_module,
        "validate_step_against_movement_root",
        counted_runtime_validate,
    )
    monkeypatch.setattr(
        presentation_mapper_module,
        "validate_step_against_movement_root",
        counted_partition_validate,
    )
    try:
        first = runtime.bind(_authority(observer), encounter=encounter)
        second = runtime.bind(
            _authority(observer, epoch="perspective-2", session_id="session-2"),
            encounter=encounter,
        )
        result = Move(
            source_entity_uuid=observer.uuid,
            end_position=(3, 0),
            path=((0, 0), (1, 0), (2, 0), (3, 0)),
            use_movement_cost=False,
        ).apply()
        assert result is not None and not result.canceled
        assert capture_calls == 1
        assert runtime_validation_calls == 3
        assert partition_validation_calls == 6
        assert runtime.movement_root_context_count == 0
        for context in (first, second):
            frames = context.frames(from_observation_cursor=0).frames
            assert sum(
                isinstance(cue, MovementPresentationCue)
                for frame in frames
                for cue in frame.presentation
            ) == 3
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_immediate_singleton_poison_emits_one_reset_and_closes(
    runtime_scene: RuntimeScene,
) -> None:
    """Outside-batch poison waits for its synchronous singleton callback."""
    opening = runtime_scene.context.journal.watermarks.observation_cursor
    _movement_step_completion(runtime_scene.observer, parent_event=uuid4())
    frames = runtime_scene.context.frames(
        from_observation_cursor=opening,
    ).frames
    assert len(frames) == 1
    assert frames[0].presentation_delivery is PresentationDeliveryMode.RESET_REQUIRED
    assert runtime_scene.runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY


def test_unrelated_batch_cannot_clear_an_open_poison(
    runtime_scene: RuntimeScene,
) -> None:
    """Only the exact cursor-containing delivery owns poison closure."""
    runtime = runtime_scene.runtime
    with EventQueue.batch_on_event_callbacks():
        _movement_step_completion(runtime_scene.observer, parent_event=uuid4())
        unrelated = Event(
            source_entity_uuid=runtime_scene.observer.uuid,
            event_type=EventType.BASE_ACTION,
        )
        runtime._on_event_batch((unrelated,))
        assert (
            runtime.movement_root_capture_health
            is MovementRootCaptureHealth.POISONED_AWAITING_CONTAINING_DELIVERY
        )
    assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY


def test_generation_change_retires_open_poison_and_reattaches() -> None:
    """A real source generation boundary cannot preserve a stale 409 latch."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Generation poison observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    encounter = Encounter(name="Generation poison", source_entity_uuid=observer.uuid)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    runtime.ensure_attached()
    batch = EventQueue.batch_on_event_callbacks()
    batch.__enter__()
    try:
        _movement_step_completion(observer, parent_event=uuid4())
        assert (
            runtime.movement_root_capture_health
            is MovementRootCaptureHealth.POISONED_AWAITING_CONTAINING_DELIVERY
        )
        EventQueue.reset()
        runtime.ensure_attached()
        assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
        assert runtime.attached is True
        context = runtime.bind(_authority(observer), encounter=encounter)
        assert context.protocol.generation_id == str(EventQueue.generation_id())
    finally:
        batch.__exit__(None, None, None)
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_malformed_step_is_rejected_before_two_partition_projection(
    runtime_scene: RuntimeScene,
) -> None:
    """One malformed but alias-resolving Step resets all partitions once."""
    runtime = runtime_scene.runtime
    second = runtime.bind(
        _authority(
            runtime_scene.observer,
            epoch="malformed-step-perspective-2",
            session_id="malformed-step-session-2",
        ),
        encounter=runtime_scene.encounter,
    )
    contexts = (runtime_scene.context, second)
    openings = tuple(
        context.journal.watermarks.observation_cursor for context in contexts
    )
    with EventQueue.batch_on_event_callbacks():
        effect = _movement_root_effect(runtime_scene.observer)
        _movement_step_completion(
            runtime_scene.observer,
            parent_event=effect.uuid,
            to_position=(2, 0),
        )
        assert (
            runtime.movement_root_capture_health
            is MovementRootCaptureHealth.POISONED_AWAITING_CONTAINING_DELIVERY
        )
    assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
    assert runtime.movement_root_context_count == 0
    for context, opening in zip(contexts, openings, strict=True):
        frames = context.frames(from_observation_cursor=opening).frames
        assert frames
        assert all(
            frame.presentation_delivery is PresentationDeliveryMode.RESET_REQUIRED
            and frame.presentation == ()
            for frame in frames
        )
        assert context.healthy is True


@pytest.mark.parametrize(
    "updates",
    (
        {"canceled_from_phase": EventPhase.EFFECT},
        {"event_type": "step_movement"},
        {"uuid": "malformed-step-uuid"},
        {"lineage_uuid": "malformed-step-lineage"},
    ),
)
@pytest.mark.filterwarnings("ignore:Pydantic serializer warnings:UserWarning")
def test_malformed_step_lifecycle_or_identity_poison_before_projection(
    runtime_scene: RuntimeScene,
    updates: dict[str, object],
) -> None:
    """Equal-valued wrong shapes and closed-lifecycle drift never reach mapping."""
    context = runtime_scene.context
    opening = context.journal.watermarks.observation_cursor
    with EventQueue.batch_on_event_callbacks():
        effect = _movement_root_effect(runtime_scene.observer)
        parent = EventQueue.get_event_by_uuid(effect.uuid)
        assert parent is not None
        candidate = StepMovementEvent(
            source_entity_uuid=runtime_scene.observer.uuid,
            source_entity_name=runtime_scene.observer.name,
            from_position=(0, 0),
            to_position=(1, 0),
            path_index=1,
            total_path_length=2,
            movement_cost=5,
            trajectory=MovementTrajectory.PATH,
            disclosed_path=((0, 0), (1, 0)),
            committed=True,
            parent_event=effect.uuid,
            parent_lineage=parent.lineage_uuid,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ).model_copy(update=updates)
        EventQueue.register(candidate)
        assert (
            runtime_scene.runtime.movement_root_capture_health
            is MovementRootCaptureHealth.POISONED_AWAITING_CONTAINING_DELIVERY
        )
    frames = context.frames(from_observation_cursor=opening).frames
    assert frames
    assert all(
        frame.presentation_delivery is PresentationDeliveryMode.RESET_REQUIRED
        and frame.presentation == ()
        for frame in frames
    )


def test_poison_closure_also_evicts_independent_terminal_root(
    runtime_scene: RuntimeScene,
) -> None:
    """A reset interval cannot strand an unrelated root completed in that batch."""
    runtime = runtime_scene.runtime
    with EventQueue.batch_on_event_callbacks():
        completed = _movement_root_effect(runtime_scene.observer)
        completed.phase_to(EventPhase.COMPLETION)
        poisoned = _movement_root_effect(runtime_scene.observer)
        _movement_step_completion(
            runtime_scene.observer,
            parent_event=poisoned.uuid,
            to_position=(2, 0),
        )
        assert runtime.movement_root_context_count == 2
    assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
    assert runtime.movement_root_context_count == 0


def test_poison_closure_also_evicts_independent_incomplete_explicit_root(
    runtime_scene: RuntimeScene,
) -> None:
    """A reset interval clears every explicit root whose own batch closed incomplete."""
    runtime = runtime_scene.runtime
    with EventQueue.batch_on_event_callbacks():
        _movement_root_effect(runtime_scene.observer)
        poisoned = _movement_root_effect(runtime_scene.observer)
        _movement_step_completion(
            runtime_scene.observer,
            parent_event=poisoned.uuid,
            to_position=(2, 0),
        )
        assert runtime.movement_root_context_count == 2
    assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
    assert runtime.movement_root_context_count == 0


def test_malformed_step_poison_closes_with_zero_partitions() -> None:
    """Partition-independent Step validation cannot depend on a bound player."""
    grid = reset_engine_runtime(grid_size=(3, 1))
    observer = _materialize_test_actor(
        name="Unbound malformed Step observer",
        position=(0, 0),
        faction="heroes",
    )
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: None,
    )
    try:
        runtime.ensure_attached()
        with EventQueue.batch_on_event_callbacks():
            _movement_root_effect(observer)
            effect = _movement_root_effect(observer)
            _movement_step_completion(
                observer,
                parent_event=effect.uuid,
                to_position=(2, 0),
            )
            assert (
                runtime.movement_root_capture_health
                is MovementRootCaptureHealth.POISONED_AWAITING_CONTAINING_DELIVERY
            )
            assert runtime.movement_root_context_count == 2
        assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
        assert runtime.movement_root_context_count == 0
    finally:
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_context_capacity_poison_clears_store_and_allows_later_root() -> None:
    """The ambiguous sixty-fifth root cannot strand sixty-four contexts."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = _materialize_test_actor(
        name="Root capacity observer",
        position=(0, 0),
        faction="heroes",
    )
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: None,
    )
    try:
        runtime.ensure_attached()
        for _ in range(64):
            _movement_root_effect(observer)
        assert runtime.movement_root_context_count == 64
        _movement_root_effect(observer)
        assert runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
        assert runtime.movement_root_context_count == 0

        later = _movement_root_effect(observer)
        assert runtime.movement_root_context_count == 1
        later.phase_to(EventPhase.COMPLETION)
        assert runtime.movement_root_context_count == 0
    finally:
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_reset_terminal_rejects_any_later_real_source_slot(
    runtime_scene: RuntimeScene,
) -> None:
    """A terminal fact cannot authorize a suffix that continues objectively."""
    context = runtime_scene.context
    opening = context.journal.watermarks.observation_cursor
    with EventQueue.batch_on_event_callbacks():
        _movement_step_completion(runtime_scene.observer, parent_event=uuid4())
        runtime_scene.encounter.end_encounter("Terminal before later fact")
        Event(
            event_type=EventType.BASE_ACTION,
            source_entity_uuid=runtime_scene.observer.uuid,
            phase=EventPhase.COMPLETION,
        )
    assert context.healthy is False
    with pytest.raises(SubjectiveJournalUnhealthyError):
        context.frames(from_observation_cursor=opening)
    assert runtime_scene.runtime.movement_root_capture_health is MovementRootCaptureHealth.HEALTHY
