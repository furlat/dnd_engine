"""Direct behavior identity without the deleted content runtime gateway."""

from uuid import uuid4

from dnd.actions.standard import Dodge
from dnd.core.events.action_events import ActionEvent
from dnd.core.events.events_registry import EventPhase, EventQueue, EventType
from dnd.entities.entity_creation import compose_entity, create_entity


def test_registered_action_and_child_condition_keep_direct_identity() -> None:
    EventQueue.reset()
    entity = create_entity(uuid4(), entity_kind_id="test.direct_behavior")
    try:
        compose_entity(entity)
        template = Dodge(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            template=True,
        )
        entity.register_action(template)

        assert template.behavior_id == "action.dodge"
        assert template.provided_by_id == "action.dodge"
        assert template.origin_root_id == "test.direct_behavior"

        result = template.instantiate(
            target_entity_uuid=entity.uuid,
        ).apply()
        assert isinstance(result, ActionEvent)
        assert result.phase is EventPhase.COMPLETION
        assert result.behavior_id == "action.dodge"
        assert result.provided_by_id == "action.dodge"
        assert result.origin_root_id == "test.direct_behavior"
        assert result.model_dump(mode="json")["behavior_id"] == "action.dodge"

        condition = entity.active_conditions["Dodging"]
        assert condition.behavior_id == "condition.dodging"
        assert condition.provided_by_id == "action.dodge"
        assert condition.origin_root_id == "test.direct_behavior"
        condition_facts = [
            event
            for event in EventQueue.get_events_by_type(
                EventType.CONDITION_APPLICATION,
            )
            if event.phase is EventPhase.COMPLETION
        ]
        assert condition_facts[-1].condition_behavior_id == "condition.dodging"
    finally:
        entity.discard_unpublished_runtime()
        EventQueue.reset()
