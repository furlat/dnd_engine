"""The existing Protection reaction installed as an authored creature's own behavior."""

from dnd.classes.fighter import create_protection_handler
from dnd.content_system.reaction_definitions import PROTECTION_REACTION_DECLARATION
from dnd.core.content.identities import ContentRef
from dnd.core.content.runtime import BehaviorBinding
from dnd.entity import Entity


def register_protection(entity: Entity, provider: ContentRef) -> None:
    """Install the shared Protection handler, owned by the creature recipe that grants it."""
    handler = create_protection_handler(entity.uuid)
    handler.behavior_binding = BehaviorBinding(behavior_id=PROTECTION_REACTION_DECLARATION.ref.content_id,
        provided_by_id=provider.content_id, origin_root_id=provider.content_id, runtime_owner_uuid=entity.uuid)
    entity.add_event_handler(handler)
