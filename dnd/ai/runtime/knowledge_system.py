"""The AI knowledge system: the one owner of every native AI assignment's knowledge.

Bound at composition (`bind_ai_knowledge`), the system advances each open
assignment's `AIKnowledge` to the EventQueue cursor at every batch dispatch. A
decision or movement-guard read inside a batch first advances its own
assignment the same way, over that batch's versions only.

Lifetime: an assignment's knowledge opens where the assignment is created, by
folding the recorded history once (the cold fold), and is dropped when the
assignment closes. A new event generation (`EventQueue.reset`) removes the batch
callback; reads of the earlier generation's system are refused.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from dnd.ai.runtime.knowledge_reduction import AIKnowledge
from dnd.core.events import Event, EventQueue


@dataclass(slots=True, eq=False)
class AIKnowledgeSystem:
    """Every open assignment's recorded knowledge, keyed by its controller's identity."""

    generation: UUID
    knowledge: dict[UUID, AIKnowledge] = field(default_factory=dict)

    def __call__(self, events: Sequence[Event]) -> None:
        """Batch dispatch: advance every open assignment to the cursor."""
        del events
        for knowledge in self.knowledge.values():
            advance_knowledge(knowledge)


def advance_knowledge(knowledge: AIKnowledge) -> None:
    """Fold the recorded versions after this knowledge's cursor (the one advance)."""
    knowledge.consume((index, event, None) for index, event in EventQueue.iter_events_since(knowledge.source_cursor))


def bind_ai_knowledge() -> AIKnowledgeSystem:
    """Attach one system to the current event generation's batch dispatch."""
    system = AIKnowledgeSystem(EventQueue.generation_id())
    EventQueue.add_on_event_batch_callback(system)
    return system


def unbind_ai_knowledge(system: AIKnowledgeSystem) -> None:
    """Detach the system and drop what it still holds."""
    EventQueue.remove_on_event_batch_callback(system)
    system.knowledge.clear()


def open_assignment_knowledge(system: AIKnowledgeSystem, key: UUID, controlled_entity_uuids: tuple[UUID, ...]) -> None:
    """Create one assignment's knowledge by the cold fold of the recorded history."""
    _require_generation(system)
    if key in system.knowledge:
        raise ValueError("AI assignment knowledge is already open")
    knowledge = AIKnowledge(controlled_entity_uuids)
    advance_knowledge(knowledge)
    system.knowledge[key] = knowledge


def close_assignment_knowledge(system: AIKnowledgeSystem, key: UUID) -> None:
    """Drop one assignment's knowledge; closing twice is a no-op."""
    system.knowledge.pop(key, None)


def assignment_knowledge(system: AIKnowledgeSystem, key: UUID) -> AIKnowledge:
    """One assignment's knowledge at the current cursor, for a decision or guard read."""
    _require_generation(system)
    knowledge = system.knowledge[key]
    advance_knowledge(knowledge)
    return knowledge


def _require_generation(system: AIKnowledgeSystem) -> None:
    if EventQueue.generation_id() != system.generation:
        raise RuntimeError("AI knowledge belongs to an earlier event generation")


__all__ = [
    "AIKnowledgeSystem",
    "advance_knowledge",
    "assignment_knowledge",
    "bind_ai_knowledge",
    "close_assignment_knowledge",
    "open_assignment_knowledge",
    "unbind_ai_knowledge",
]
