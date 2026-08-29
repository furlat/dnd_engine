"""Prove the headless event-batch acknowledgement boundary."""

import asyncio
from typing import TypeAlias
from uuid import UUID, uuid4

import pytest

from dnd.actions.operations import get_available_actions
from dnd.actions.reactions import add_opportunity_attack_handler
from dnd.actions.standard import AttackEvent, MovementEvent, SpellEvent
from dnd.content.monsters.monster_builders import create_monster
from dnd.content.scenarios.battlefield_builders import build_battlefield
from dnd.core.events.events_registry import Event, EventQueue
from dnd.core.events.knowledge import (
    EventBatch,
    Known,
    SourceDisposition,
)
from dnd.core.dice import fixed_dice_faces
import dnd.core.gridmap as gridmap_module
from dnd.encounters.controllers import HumanController, PassController
from dnd.encounters.encounter import AdvanceResult, Encounter
from dnd.entities.entity import Entity
from dnd.game import Game
from dnd.event_reduction import (
    _CONCRETE_EVENT_MANIFEST,
    EventReducer,
    format_subjective_delivery,
    format_subjective_delivery_tree,
)
from dnd.runtime_reset import reset_engine_runtime
from dnd.core.events.world_events import SensoryUpdateEvent


ReceiptCoverage: TypeAlias = tuple[
    int,
    SourceDisposition,
    int,
    tuple[str, ...] | str,
]
PresentationReceipt: TypeAlias = tuple[
    UUID,
    int,
    int,
    tuple[ReceiptCoverage, ...],
]


def _select_target(
    entity: Entity,
    template_name: str,
    *,
    position: tuple[int, int] | None = None,
    target_uuid: UUID | None = None,
):
    """Select one target from the current public discovery result."""
    available = get_available_actions(entity)
    action_info = next(
        info
        for info in available.all_actions
        if info.template_name == template_name
    )
    target = next(
        target
        for target in action_info.valid_targets
        if (
            position is not None
            and target.position == position
        )
        or (
            target_uuid is not None
            and target.target_uuid == target_uuid
        )
        or (
            position is None
            and target_uuid is None
        )
    )
    return action_info, target


def _format_detached_delivery(delivery) -> str:
    """Format one delivery while proving no live lookup is available."""
    with pytest.MonkeyPatch.context() as fatal_accessors:
        fatal_accessors.setattr(
            Entity,
            "get",
            classmethod(
                lambda _cls, _uuid: (_ for _ in ()).throw(
                    AssertionError("consumer accessed live Entity")
                )
            ),
        )
        fatal_accessors.setattr(
            EventQueue,
            "get_event_by_uuid",
            classmethod(
                lambda _cls, _uuid: (_ for _ in ()).throw(
                    AssertionError("consumer accessed live EventQueue")
                )
            ),
        )
        fatal_accessors.setattr(
            gridmap_module,
            "get_map",
            lambda: (_ for _ in ()).throw(
                AssertionError("consumer accessed live GridMap")
            ),
        )
        return format_subjective_delivery(delivery)


async def _run_async_boundary_proof() -> dict[str, object]:
    """Run real encounter boundaries behind a deterministic fake consumer."""
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    game = Game()
    roles: dict[str, Entity] = {}
    authored_roles = (
        ("hero_frontline", "monster.goblin", (3, 3), "heroes"),
        ("hero_caster", "monster.generic_caster", (2, 6), "heroes"),
        ("enemy_guard", "monster.skeleton", (4, 3), "monsters"),
        ("enemy_raider", "monster.skeleton", (2, 5), "monsters"),
    )
    for role_name, monster_id, position, faction in authored_roles:
        role = create_monster(
            monster_id,
            uuid4(),
            name=role_name,
            faction=faction,
        )
        game.deploy_entity(role, position)
        roles[role_name] = role

    add_opportunity_attack_handler(roles["enemy_guard"])
    controllers = {
        "hero_frontline": HumanController(
            source_entity_uuid=roles["hero_frontline"].uuid,
        ),
        "hero_caster": HumanController(
            source_entity_uuid=roles["hero_caster"].uuid,
        ),
        "enemy_guard": PassController(
            source_entity_uuid=roles["enemy_guard"].uuid,
        ),
        "enemy_raider": PassController(
            source_entity_uuid=roles["enemy_raider"].uuid,
        ),
    }
    encounter = Encounter(
        name="Async event knowledge boundary",
        source_entity_uuid=uuid4(),
    )
    for role_name in (
        "hero_frontline",
        "enemy_guard",
        "enemy_raider",
        "hero_caster",
    ):
        encounter.add_combatant(roles[role_name], controllers[role_name])

    with fixed_dice_faces(20, 16, 12, 8):
        encounter.roll_initiative()
    expected_order = [
        roles[role_name].uuid
        for role_name in (
            "hero_frontline",
            "enemy_guard",
            "enemy_raider",
            "hero_caster",
        )
    ]
    assert encounter.initiative_order == expected_order

    source_base = EventQueue.event_cursor()
    reducer = EventReducer(
        roles["hero_frontline"].uuid,
        roles["hero_caster"].uuid,
        source_cursor=source_base,
    )
    game_to_presentation: asyncio.Queue[EventBatch] = asyncio.Queue()
    presentation_to_game: asyncio.Queue[
        PresentationReceipt | BaseException
    ] = asyncio.Queue()
    presentation_gate = asyncio.Event()
    cursor_changed = asyncio.Event()
    errors: list[BaseException] = []
    presentation_cursor = source_base
    accepted_receipts: list[PresentationReceipt] = []
    accepted_batch_ids: set[tuple[UUID, int, int]] = set()
    seen_delivery_ids: set[object] = set()
    maximum_queue_high_water = 0
    maximum_engine_lead = 0
    tree_batch_count = 0

    def accept_receipt(receipt: PresentationReceipt) -> None:
        """Advance only across one complete contiguous disposed source range."""
        nonlocal presentation_cursor
        generation, start, stop, coverage = receipt
        if generation != reducer.generation_id:
            raise ValueError("presentation receipt has the wrong generation")
        batch_id = (generation, start, stop)
        if batch_id in accepted_batch_ids:
            raise ValueError("duplicate presentation receipt")
        if stop <= start:
            raise ValueError("backwards or empty presentation receipt")
        if start != presentation_cursor:
            raise ValueError("presentation receipt is missing or overlapping")
        indexes = tuple(row[0] for row in coverage)
        if indexes != tuple(range(start, stop)):
            raise ValueError("presentation receipt has a coverage gap")
        if any(not row[3] and row[1] is SourceDisposition.DELIVERED for row in coverage):
            raise ValueError("delivered source lacks a terminal disposition")
        accepted_batch_ids.add(batch_id)
        accepted_receipts.append(receipt)
        presentation_cursor = stop
        cursor_changed.set()

    async def fake_consumer() -> None:
        """Consume only detached batches and return test-local receipts."""
        nonlocal maximum_queue_high_water, tree_batch_count
        while True:
            batch = await game_to_presentation.get()
            await presentation_gate.wait()
            deliveries = tuple(batch.deliveries)
            tree_deliveries = tuple(
                delivery
                for delivery in deliveries
                if all(
                    isinstance(delivery.knowledge.read((path,)), Known)
                    for path in ("uuid", "parent_event", "parent_lineage")
                )
            )
            if tree_deliveries:
                tree_batch_count += 1
                format_subjective_delivery_tree(tree_deliveries)
            delivery_dispositions: dict[object, str] = {}
            for delivery in deliveries:
                event_class = delivery.knowledge.event_class
                if not any(
                    event_class is manifest_row[0]
                    for manifest_row in _CONCRETE_EVENT_MANIFEST
                ):
                    raise AssertionError("delivery class lacks exact manifest policy")
                if event_class is SensoryUpdateEvent:
                    disposition = "scene-state-applied"
                elif event_class in {MovementEvent, AttackEvent, SpellEvent}:
                    disposition = "animated"
                else:
                    disposition = "text fallback"
                _format_detached_delivery(delivery)
                if delivery.delivery_id is None:
                    raise AssertionError("delivered event lacks a DeliveryId")
                if delivery.delivery_id in seen_delivery_ids:
                    raise AssertionError("delivery was disposed more than once")
                seen_delivery_ids.add(delivery.delivery_id)
                delivery_dispositions[delivery.delivery_id] = disposition

            coverage_rows: list[ReceiptCoverage] = []
            for coverage in batch.coverage:
                if coverage.generation_id != batch.generation_id:
                    raise AssertionError("coverage generation differs from batch")
                owned = tuple(coverage.delivery_ids)
                if coverage.disposition is SourceDisposition.DELIVERED:
                    if not owned or any(delivery_id not in delivery_dispositions for delivery_id in owned):
                        raise AssertionError("delivered coverage does not own its delivery")
                    dispositions = tuple(delivery_dispositions[delivery_id] for delivery_id in owned)
                else:
                    if owned:
                        raise AssertionError("hidden/lifecycle coverage owns a delivery")
                    dispositions = (
                        "errored"
                        if coverage.disposition is SourceDisposition.ERROR
                        else "intentionally silent"
                    )
                coverage_rows.append((
                    coverage.source_index,
                    coverage.disposition,
                    len(owned),
                    dispositions,
                ))
            if len(coverage_rows) != batch.stop - batch.start:
                raise AssertionError("consumer skipped a SourceCoverage slot")
            receipt: PresentationReceipt = (
                batch.generation_id,
                batch.start,
                batch.stop,
                tuple(coverage_rows),
            )
            maximum_queue_high_water = max(
                maximum_queue_high_water,
                game_to_presentation.qsize(),
            )
            await presentation_to_game.put(receipt)
    async def receipt_loop() -> None:
        try:
            while True:
                receipt_or_error = await presentation_to_game.get()
                if isinstance(receipt_or_error, BaseException):
                    cursor_changed.set()
                    raise receipt_or_error
                accept_receipt(receipt_or_error)
        except BaseException as exc:
            errors.append(exc)
            raise

    async def await_presentation_cursor(target: int) -> None:
        while presentation_cursor < target:
            if errors:
                raise errors[0]
            for task in (consumer_task, receipt_task, pump_task):
                if task.done() and not task.cancelled():
                    failure = task.exception()
                    if failure is not None:
                        raise failure
            await asyncio.sleep(0.001)
            if errors:
                raise errors[0]

    consumer_task = asyncio.create_task(fake_consumer())
    receipt_task = asyncio.create_task(receipt_loop())

    async def explicit_reducer_pump() -> None:
        """Test-local pull pump; production remains callback-free."""
        while True:
            for batch in reducer.drain_committed_trees():
                game_to_presentation.put_nowait(batch)
            await asyncio.sleep(0.001)

    pump_task = asyncio.create_task(explicit_reducer_pump())

    try:
        presentation_gate.clear()
        encounter.start_encounter()

        first_waiting = asyncio.Event()

        async def first_player_command() -> object:
            target = EventQueue.event_cursor()
            first_waiting.set()
            await await_presentation_cursor(target)
            result = encounter.advance_one_controller_action_boundary()
            assert result.status.value == "waiting_for_human"
            presentation_gate.clear()
            move_info, move_target = _select_target(
                roles["hero_frontline"],
                "Move",
                position=(2, 3),
            )
            assert move_info.can_afford
            with fixed_dice_faces(19, 1):
                return encounter.execute_action(
                    roles["hero_frontline"].uuid,
                    move_info.template_name,
                    move_target.index,
                )

        first_task = asyncio.create_task(first_player_command())
        await first_waiting.wait()
        assert not first_task.done()
        presentation_gate.set()
        first_event = await first_task
        assert first_event is not None

        second_waiting = asyncio.Event()

        async def second_player_command() -> object:
            target = EventQueue.event_cursor()
            second_waiting.set()
            await await_presentation_cursor(target)
            attack_info, attack_target = _select_target(
                roles["hero_frontline"],
                "Attack_RANGED_MAIN",
                target_uuid=roles["enemy_guard"].uuid,
            )
            assert attack_info.can_afford
            with fixed_dice_faces(1, 1):
                return encounter.execute_action(
                    roles["hero_frontline"].uuid,
                    attack_info.template_name,
                    attack_target.index,
                )

        second_task = asyncio.create_task(second_player_command())
        await second_waiting.wait()
        assert not second_task.done()
        presentation_gate.set()
        second_event = await second_task
        assert second_event is not None

        presentation_gate.clear()
        encounter.complete_current_turn()
        guard_boundary = encounter.advance_one_controller_action_boundary()
        raider_boundary = encounter.advance_one_controller_action_boundary()
        assert guard_boundary.status.value == "advanced_autonomous"
        assert raider_boundary.status.value == "advanced_autonomous"
        await asyncio.sleep(0.01)
        maximum_queue_high_water = max(
            maximum_queue_high_water,
            game_to_presentation.qsize(),
        )
        maximum_engine_lead = max(
            maximum_engine_lead,
            EventQueue.event_cursor() - presentation_cursor,
        )
        assert maximum_queue_high_water > 1
        assert maximum_engine_lead > 1

        next_waiting = asyncio.Event()

        async def next_player_decision() -> AdvanceResult:
            target = EventQueue.event_cursor()
            next_waiting.set()
            await await_presentation_cursor(target)
            return encounter.advance_one_controller_action_boundary()

        next_task = asyncio.create_task(next_player_decision())
        await next_waiting.wait()
        assert not next_task.done()
        presentation_gate.set()
        next_result = await next_task
        assert next_result.status.value == "waiting_for_human"

        dodge_info, dodge_target = _select_target(
            roles["hero_caster"],
            "Dodge",
        )
        assert dodge_info.can_afford
        encounter.execute_action(
            roles["hero_caster"].uuid,
            dodge_info.template_name,
            dodge_target.index,
        )
        presentation_gate.clear()

        terminal_waiting = asyncio.Event()

        async def finish_encounter_after_receipts() -> object:
            target = EventQueue.event_cursor()
            terminal_waiting.set()
            await await_presentation_cursor(target)
            end_event = encounter.end_encounter("async boundary complete")
            terminal_target = EventQueue.event_cursor()
            await await_presentation_cursor(terminal_target)
            return end_event

        terminal_task = asyncio.create_task(finish_encounter_after_receipts())
        await terminal_waiting.wait()
        assert not terminal_task.done()
        presentation_gate.set()
        end_event = await terminal_task
        assert end_event.__class__.__name__ == "EncounterEndEvent"
        await await_presentation_cursor(EventQueue.event_cursor())
        assert presentation_cursor == EventQueue.event_cursor()
        assert game_to_presentation.qsize() == 0
        assert presentation_to_game.qsize() == 0
        assert not errors
        assert accepted_receipts
        assert len(seen_delivery_ids) == sum(
            coverage[2]
            for receipt in accepted_receipts
            for coverage in receipt[3]
        )

        first_receipt = accepted_receipts[0]
        with pytest.raises(ValueError, match="duplicate"):
            accept_receipt(first_receipt)
        with pytest.raises(ValueError, match="gap"):
            accept_receipt((
                reducer.generation_id,
                presentation_cursor,
                presentation_cursor + 2,
                ((presentation_cursor, SourceDisposition.HIDDEN, 0, ("intentionally silent",)),),
            ))
        with pytest.raises(ValueError, match="missing or overlapping"):
            accept_receipt((
                reducer.generation_id,
                presentation_cursor - 1,
                presentation_cursor + 1,
                ((presentation_cursor - 1, SourceDisposition.HIDDEN, 0, ("intentionally silent",)),),
            ))
        with pytest.raises(ValueError, match="backwards"):
            accept_receipt((
                reducer.generation_id,
                presentation_cursor,
                presentation_cursor - 1,
                ((presentation_cursor, SourceDisposition.HIDDEN, 0, ("intentionally silent",)),),
            ))
        with pytest.raises(ValueError, match="wrong generation"):
            accept_receipt((
                uuid4(),
                presentation_cursor,
                presentation_cursor + 1,
                ((presentation_cursor, SourceDisposition.HIDDEN, 0, ("intentionally silent",)),),
            ))
        return {
            "source_base": source_base,
            "source_stop": EventQueue.event_cursor(),
            "accepted_ranges": len(accepted_receipts),
            "delivery_count": len(seen_delivery_ids),
            "maximum_queue_high_water": maximum_queue_high_water,
            "maximum_engine_lead": maximum_engine_lead,
            "tree_batch_count": tree_batch_count,
            "generation": reducer.generation_id,
        }
    finally:
        pump_task.cancel()
        consumer_task.cancel()
        receipt_task.cancel()
        await asyncio.gather(
            pump_task,
            consumer_task,
            receipt_task,
            return_exceptions=True,
        )


def test_real_encounter_batches_cross_two_queue_presentation_boundary() -> None:
    """Public encounter facts wait for deterministic terminal presentation receipts."""
    try:
        evidence = asyncio.run(_run_async_boundary_proof())
    finally:
        reset_engine_runtime()
    accepted_ranges = evidence["accepted_ranges"]
    delivery_count = evidence["delivery_count"]
    maximum_queue_high_water = evidence["maximum_queue_high_water"]
    maximum_engine_lead = evidence["maximum_engine_lead"]
    tree_batch_count = evidence["tree_batch_count"]
    assert isinstance(accepted_ranges, int)
    assert isinstance(delivery_count, int)
    assert isinstance(maximum_queue_high_water, int)
    assert isinstance(maximum_engine_lead, int)
    assert isinstance(tree_batch_count, int)
    assert accepted_ranges > 1
    assert delivery_count > 0
    assert maximum_queue_high_water > 1
    assert maximum_engine_lead > 1
    assert tree_batch_count > 0
