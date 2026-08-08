"""Focused integration tests for canonical live subjective replication."""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import uuid4

import pytest

from dnd.actions import Move, SpellEvent
from dnd.actions_functional import execute_use_action
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.conditions import GreaterInvisibilityEffect
from dnd.controller import Controller
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventPhase, EventQueue, EventType
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
from dnd.environmental_effect_runtime import materialize_spike_trap_effect
from dnd.items.consumables import GREATER_INVISIBILITY_POTION_RECIPE
from dnd.items.torches import TORCH_RECIPE, Torch
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import DndEventStream
from server.player_replication.journal import (
    SubjectiveJournalIdentityError,
    SubjectiveJournalStore,
    SubjectiveProjectionError,
    SubjectiveSubscriptionClosedError,
)
from server.player_replication.runtime import (
    CanonicalSubjectiveReplicationContext,
    CanonicalSubjectiveReplicationRuntime,
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
    MovementPresentationCue,
    ObserverVisibilityReplacePatch,
    SpellPresentationCue,
    SubjectiveCombatLogDelivery,
    SubjectiveFrameDelivery,
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
        movement_sequence_ids: set[str] = set()
        for path_index, frame in enumerate(movement_frames, start=1):
            movement = next(
                cue
                for cue in frame.presentation
                if isinstance(cue, MovementPresentationCue)
            )
            assert movement.trajectory == (
                (path_index - 1, 0),
                (path_index, 0),
            )
            assert movement.path_start_index == path_index - 1
            assert movement.endpoint_outcome.value == "committed"
            movement_sequence_ids.add(movement.movement_sequence_id)
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
        assert len(movement_sequence_ids) == 1
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
    assert movement.trajectory == ((0, 0), (1, 0))
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
