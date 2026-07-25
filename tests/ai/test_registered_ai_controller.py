"""Two-phase execution and lifecycle tests for registered AI controllers."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import replace
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from dnd.ai.contracts.decision import ExecuteIntent
from dnd.ai.instrumentation import AIInstrumentation
from dnd.controller import Controller, TurnContext
from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.runtime_reset import reset_engine_runtime
from server.registered_ai_controller import (
    RegisteredAIController,
    RegisteredAIPendingIntent,
)
from server.registered_ai_provider import RegisteredAIProviderCatalog
from services.ai_policy_server.app import create_ai_policy_service
from services.ai_policy_server.composition import (
    create_ai_policy_service_runtime,
)
from services.ai_policy_server.policies import EXTERNAL_BASIC_POLICY_ID


def _run[ResultT](operation: Coroutine[Any, Any, ResultT]) -> ResultT:
    return asyncio.run(operation)


def _scene() -> tuple[Entity, Entity]:
    reset_engine_runtime(grid_size=(10, 8))
    actor = create_goblin(
        name="Registered AI",
        position=(4, 4),
        faction="ai",
    )
    target = create_skeleton(
        name="Target",
        position=(5, 4),
        faction="enemy",
    )
    Entity.update_all_entities_senses(max_distance=20)
    return actor, target


def _context(actor: Entity, target: Entity) -> TurnContext:
    economy = actor.action_economy
    return TurnContext(
        source_entity_uuid=actor.uuid,
        entity_uuid=actor.uuid,
        round_number=1,
        turn_index=0,
        actions_remaining=economy.actions.normalized_score,
        bonus_actions_remaining=economy.bonus_actions.normalized_score,
        reactions_remaining=economy.reactions.normalized_score,
        movement_remaining=economy.movement.normalized_score,
        visible_enemies={target.uuid: target.position},
        initiative_order=[actor.uuid, target.uuid],
    )


async def _catalog_and_runtime(
    provider_id: str,
) -> tuple[
    RegisteredAIProviderCatalog,
    Any,
]:
    runtime = create_ai_policy_service_runtime(
        provider_id=provider_id,
        capacity=2,
    )
    app = create_ai_policy_service(runtime=runtime)
    catalog = RegisteredAIProviderCatalog()
    await catalog.register(
        provider_id=provider_id,
        base_url=f"http://{provider_id}",
        transport=httpx.ASGITransport(app=app),
    )
    return catalog, runtime


def test_post_open_construction_failure_closes_remote_lease() -> None:
    async def exercise() -> None:
        actor, _ = _scene()
        catalog, runtime = await _catalog_and_runtime(
            "provider.construction"
        )

        with patch(
            "server.registered_ai_controller.SubjectiveAIStateProjector",
            side_effect=RuntimeError("projector construction failed"),
        ):
            with pytest.raises(
                RuntimeError,
                match="projector construction failed",
            ):
                await RegisteredAIController.create(
                    source_entity_uuid=actor.uuid,
                    game_id="game",
                    assignment_id="game:side_a",
                    controlled_entity_uuids=(actor.uuid,),
                    policy_id=EXTERNAL_BASIC_POLICY_ID,
                    provider_catalog=catalog,
                    instrumentation=AIInstrumentation(),
                )

        assert runtime.provider.handshake().active_assignments == 0
        assert catalog.provider(
            "provider.construction"
        ).active_assignments == 0
        assert not any(
            isinstance(controller, RegisteredAIController)
            for controller in Controller.get_all()
        )
        await catalog.close()

    _run(exercise())


def test_provider_await_cannot_execute_before_synchronous_turn_fence() -> None:
    async def exercise() -> None:
        actor, target = _scene()
        catalog, _ = await _catalog_and_runtime("provider.await")
        controller = await RegisteredAIController.create(
            source_entity_uuid=actor.uuid,
            game_id="game",
            assignment_id="game:side_a",
            controlled_entity_uuids=(actor.uuid,),
            policy_id=EXTERNAL_BASIC_POLICY_ID,
            provider_catalog=catalog,
            instrumentation=AIInstrumentation(),
        )
        controller.start([actor])
        context = _context(actor, target)
        actions_before = actor.action_economy.actions.normalized_score
        target_damage_before = target.health.damage_taken
        events_before = EventQueue.event_cursor()

        pending = await controller.request_intent(actor, context)

        assert isinstance(pending, RegisteredAIPendingIntent)
        assert isinstance(pending.intent, ExecuteIntent)
        assert actor.action_economy.actions.normalized_score == actions_before
        assert target.health.damage_taken == target_damage_before
        assert EventQueue.event_cursor() == events_before
        assert await controller.request_intent(actor, context) is pending
        copied = replace(pending)
        with pytest.raises(
            RuntimeError,
            match="exact pending provider intent",
        ):
            controller.resolve_pending_intent(actor, context, copied)
        changed_turn = context.model_copy(update={"turn_index": 1})
        with pytest.raises(
            RuntimeError,
            match="authoritative turn fence",
        ):
            controller.resolve_pending_intent(
                actor,
                changed_turn,
                pending,
            )

        assert actor.action_economy.actions.normalized_score == actions_before
        assert target.health.damage_taken == target_damage_before
        assert EventQueue.event_cursor() == events_before
        step = controller.resolve_pending_intent(actor, context, pending)

        assert step.event is not None
        assert EventQueue.event_cursor() > events_before
        await controller.close()
        await catalog.close()

    _run(exercise())


def test_close_discards_uncommitted_intent_without_executing_it() -> None:
    async def exercise() -> None:
        actor, target = _scene()
        catalog, runtime = await _catalog_and_runtime("provider.close")
        controller = await RegisteredAIController.create(
            source_entity_uuid=actor.uuid,
            game_id="game",
            assignment_id="game:side_a",
            controlled_entity_uuids=(actor.uuid,),
            policy_id=EXTERNAL_BASIC_POLICY_ID,
            provider_catalog=catalog,
            instrumentation=AIInstrumentation(),
        )
        controller.start([actor])
        context = _context(actor, target)
        actions_before = actor.action_economy.actions.normalized_score
        events_before = EventQueue.event_cursor()
        pending = await controller.request_intent(actor, context)
        assert isinstance(pending, RegisteredAIPendingIntent)

        await controller.close()

        assert runtime.provider.handshake().active_assignments == 0
        assert actor.action_economy.actions.normalized_score == actions_before
        assert EventQueue.event_cursor() == events_before
        with pytest.raises(RuntimeError, match="closed"):
            controller.resolve_pending_intent(actor, context, pending)
        await catalog.close()

    _run(exercise())
