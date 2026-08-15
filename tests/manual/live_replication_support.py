"""Live replication scene builders used only by server tests."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from dnd.controller import HumanController, PassController
from dnd.core.events.events_registry import (
    EventQueue,
)
from dnd.core.modifiers import AutoHitModifier
from dnd.types.rolls import AutoHitStatus
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
)
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import BoundedSubscription, event_stream


@dataclass(frozen=True)
class LiveStreamScene:
    """Active encounter scene that can publish replication frames."""

    hero: Entity
    monster: Entity
    encounter: Encounter


def reset_live_stream_state(width: int = 12, height: int = 8) -> None:
    """Clear global runtime state and attach the live event stream.

    Args:
        width: Arena width in tiles.
        height: Arena height in tiles.
    """
    event_stream.stop()
    reset_engine_runtime(grid_size=(width, height))
    event_stream.ensure_attached()


def create_stream_pair() -> tuple[Entity, Entity]:
    """Create adjacent opposing actors for live-stream examples.

    Returns:
        Hero and monster entities with current senses.
    """
    hero = create_goblin(
        name="Stream Hero",
        position=(1, 1),
        faction="heroes",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["goblin"].ref,
    )
    monster = create_skeleton(
        name="Stream Skeleton",
        position=(2, 1),
        faction="monsters",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref,
    )
    Entity.update_all_entities_senses(max_distance=20)
    return hero, monster


def start_stream_encounter(hero: Entity, monster: Entity) -> Encounter:
    """Start a deterministic encounter used by stream examples.

    Args:
        hero: Hero-side entity.
        monster: Monster-side entity.

    Returns:
        Active encounter with the hero turn already open.
    """
    encounter = Encounter(name="Stream Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))
    encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [hero.uuid, monster.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    return encounter


def create_stream_scene() -> LiveStreamScene:
    """Create one active scene ready to publish event-stream payloads.

    Returns:
        Scene containing the hero, monster, and active encounter.
    """
    reset_live_stream_state()
    hero, monster = create_stream_pair()
    encounter = start_stream_encounter(hero, monster)
    return LiveStreamScene(hero=hero, monster=monster, encounter=encounter)


def make_melee_attack_auto_hit(entity: Entity) -> UUID:
    """Add an explicit auto-hit modifier to the entity's melee attack bonus.

    Args:
        entity: Attacking entity.

    Returns:
        UUID of the temporary attack modifier.
    """
    modifier = AutoHitModifier(
        name="Stream Auto Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return entity.equipment.melee_attack_bonus.self_static.add_auto_hit_modifier(modifier)


def clear_melee_attack_modifier(entity: Entity, modifier_uuid: UUID) -> None:
    """Remove an explicit melee attack modifier from an entity.

    Args:
        entity: Entity whose attack bonus was modified.
        modifier_uuid: UUID returned by `make_melee_attack_auto_hit`.
    """
    entity.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)


def execute_stream_attack(
    hero: Entity,
    monster: Entity,
    encounter: Encounter,
) -> tuple[int, int]:
    """Execute one real attack and return the cursors from before it resolved.

    Args:
        hero: Attacking entity.
        monster: Target entity.
        encounter: Encounter that owns the action execution.

    Returns:
        Event cursor and combat-log cursor recorded before the attack.

    Raises:
        RuntimeError: If the attack fails to resolve or publish history.
    """
    event_cursor_before = EventQueue.event_cursor()
    combat_log_cursor_before = len(encounter.combat_log)
    modifier_uuid = make_melee_attack_auto_hit(hero)
    initial_monster_hp = monster.get_hp()
    try:
        event = encounter.execute_action(hero.uuid, "Attack_MELEE_MAIN", 0)
    finally:
        clear_melee_attack_modifier(hero, modifier_uuid)

    if event is None or event.canceled:
        raise RuntimeError("Expected the stream attack to resolve")
    if monster.get_hp() >= initial_monster_hp:
        raise RuntimeError("Expected the stream attack to damage the monster")
    if EventQueue.event_cursor() <= event_cursor_before:
        raise RuntimeError("Expected the attack to publish event history")
    if len(encounter.combat_log) <= combat_log_cursor_before:
        raise RuntimeError("Expected the attack to publish combat-log history")
    return event_cursor_before, combat_log_cursor_before


def parse_sse_data(frame: str) -> dict[str, Any]:
    """Return the JSON data object from one Server-Sent Events frame.

    Args:
        frame: Text frame formatted by `format_sse`.

    Returns:
        Parsed JSON `data` object.
    """
    data_lines = [
        line.removeprefix("data: ")
        for line in frame.splitlines()
        if line.startswith("data: ")
    ]
    return json.loads("\n".join(data_lines))


async def drain_subscription(
    subscription: BoundedSubscription,
    limit: int = 64,
    timeout: float = 0.01,
) -> list[dict[str, Any]]:
    """Collect currently queued stream envelopes.

    Args:
        subscription: Live stream subscription queue.
        limit: Maximum number of envelopes to collect.
        timeout: Seconds to wait for each envelope before stopping.

    Returns:
        Stream envelopes collected from the subscription.
    """
    envelopes: list[dict[str, Any]] = []
    for _ in range(limit):
        try:
            envelopes.append(await asyncio.wait_for(subscription.get(), timeout=timeout))
        except asyncio.TimeoutError:
            break
    return envelopes
