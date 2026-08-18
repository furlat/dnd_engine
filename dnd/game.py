"""Single-process owner for committed entities and world deployment."""

from typing import Optional
from uuid import UUID

from dnd.entities.entity import Entity


class Game:
    """Own one in-process game without server, database, or content imports."""

    def __init__(self) -> None:
        self.entities: dict[UUID, Entity] = {}

    def deploy_entity(
        self,
        entity: Entity,
        position: tuple[int, int],
    ) -> None:
        """Place one committed entity into this game's world."""
        existing = self.entities.get(entity.uuid)
        if existing is not None and existing is not entity:
            raise ValueError(f"entity identity {entity.uuid} is already owned")
        entity._attach_to_world(position)
        self.entities[entity.uuid] = entity

    def get_entity(self, entity_uuid: UUID) -> Optional[Entity]:
        """Return an entity owned by this game."""
        return self.entities.get(entity_uuid)

    def remove_entity(self, entity_uuid: UUID) -> Optional[Entity]:
        """Remove one entity from game ownership and spatial occupancy."""
        entity = self.entities.pop(entity_uuid, None)
        if entity is not None:
            entity._detach_from_world()
        return entity

    def close(self) -> None:
        """Release every entity owned by this in-process game."""
        for entity_uuid in tuple(self.entities):
            self.remove_entity(entity_uuid)


__all__ = ["Game"]
