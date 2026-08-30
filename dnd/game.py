"""Single-process owner for entities deployed into the world."""

from typing import Optional
from uuid import UUID

from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.entity import Entity


class Game:
    """Own committed entities without server or transport infrastructure."""

    def __init__(self) -> None:
        self.entities: dict[UUID, Entity] = {}

    def deploy_entity(self, entity: Entity, position: tuple[int, int]) -> None:
        """Deploy one unowned Entity at an admitted Tile."""
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
        """Return an Entity owned by this game."""
        return self.entities.get(entity_uuid)

    def remove_entity(self, entity_uuid: UUID) -> Optional[Entity]:
        """Remove world presence before releasing game ownership."""
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
        """Release every Entity owned by this game."""
        for entity_uuid in tuple(self.entities):
            self.remove_entity(entity_uuid)


__all__ = ["Game"]
