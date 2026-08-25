"""Single-process owner for committed entities and world deployment."""

from typing import Optional
from uuid import UUID

from dnd.entities.entity import Entity
from dnd.core.positioning import PositionCommitError, PositionPublicationError


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
        try:
            entity._attach_to_world(position)
        except PositionPublicationError:
            if entity.is_deployed:
                self.entities[entity.uuid] = entity
            raise
        self.entities[entity.uuid] = entity

    def get_entity(self, entity_uuid: UUID) -> Optional[Entity]:
        """Return an entity owned by this game."""
        return self.entities.get(entity_uuid)

    def remove_entity(self, entity_uuid: UUID) -> Optional[Entity]:
        """Remove one entity from game ownership and spatial occupancy."""
        entity = self.entities.get(entity_uuid)
        if entity is None:
            return None
        try:
            entity._detach_from_world()
        except PositionCommitError:
            raise
        except PositionPublicationError:
            self.entities.pop(entity_uuid, None)
            raise
        self.entities.pop(entity_uuid, None)
        return entity

    def close(self) -> None:
        """Release every entity owned by this in-process game."""
        for entity_uuid in tuple(self.entities):
            self.remove_entity(entity_uuid)


__all__ = ["Game"]
