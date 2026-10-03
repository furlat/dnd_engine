"""Single-process owner for entities deployed into the world."""

from dataclasses import dataclass
from typing import Callable, Optional
from uuid import UUID

from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.entity import Entity, PreparedEntityRetirement
from dnd.types.summoning import TerminalOwnerRelease
from dnd.core.events import Event
from dnd.core.gridmap import get_map


@dataclass(slots=True)
class PreparedDeployment:
    game: 'Game'
    entity: Entity
    position: tuple[int, int]
    parent_event: Event | None
    committed: bool = False
    published: bool = False


@dataclass
class PreparedRetirement:
    game: 'Game'
    entity: PreparedEntityRetirement




class Game:
    """Own committed entities without server or transport infrastructure."""

    def __init__(self) -> None:
        self.entities: dict[UUID, Entity] = {}
        self._close_callbacks: list[Callable[[Event | None], None]] = []

    def add_close_callback(self, callback: Callable[[Event | None], None]) -> None:
        if callback in self._close_callbacks:
            raise ValueError("close callback already installed")
        self._close_callbacks.append(callback)

    def remove_close_callback(self, callback: Callable[[Event | None], None]) -> None:
        if callback in self._close_callbacks:
            self._close_callbacks.remove(callback)

    def prepare_deployment(self, entity: Entity, position: tuple[int, int], *,
                           parent_event: Event | None = None) -> PreparedDeployment:
        """Admit new presence without committing birth or occupancy."""
        token = PreparedDeployment(self, entity, position, parent_event)
        self.validate_prepared_deployment(token)
        return token

    def validate_prepared_deployment(self, prepared: PreparedDeployment) -> None:
        if prepared.game is not self:
            raise ValueError("deployment token belongs to another game")
        if prepared.committed:
            return
        entity = prepared.entity
        if (entity.uuid in self.entities or entity.is_deployed or entity.is_spatially_suspended
                or Entity.get(entity.uuid) is not entity):
            raise ValueError("deployment requires an unowned, absent live identity")
        grid = get_map()
        grid._validate_entity_position(prepared.position, allow_none=False)
        if not grid.is_walkable_for(*prepared.position, requesting_entity_uuid=entity.uuid):
            raise ValueError("deployment destination is unavailable")

    def commit_deployment(self, prepared: PreparedDeployment) -> None:
        """Commit already-admitted presence before its observation facts."""
        if prepared.game is not self:
            raise ValueError("deployment token belongs to another game")
        if prepared.committed:
            return
        self.validate_prepared_deployment(prepared)
        prepared.entity._commit_world_attachment(prepared.position)
        self.entities[prepared.entity.uuid] = prepared.entity
        prepared.committed = True

    def publish_deployment(self, prepared: PreparedDeployment) -> None:
        if prepared.game is not self or not prepared.committed:
            raise ValueError("deployment must commit before publication")
        if prepared.published:
            return
        prepared.published = True
        prepared.entity._publish_world_attachment(prepared.position, parent_event=prepared.parent_event)

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

    def prepare_entity_retirement(self, entity_uuid: UUID, *, cause: TerminalOwnerRelease,
                                  parent_event: Event | None = None) -> PreparedRetirement | None:
        entity = self.entities.get(entity_uuid)
        if entity is None:
            return None
        prepared = entity.prepare_retirement(terminal_release=cause, parent_event=parent_event)
        return PreparedRetirement(self, prepared) if prepared is not None else None

    def commit_entity_retirement(self, prepared: PreparedRetirement) -> None:
        if prepared.game is not self:
            raise ValueError("Retirement token belongs to another game")
        entity = prepared.entity.entity
        try:
            entity.commit_retirement(prepared.entity)
        finally:
            if prepared.entity.committed:
                self.entities.pop(entity.uuid, None)

    def close(self, parent_event: Event | None = None) -> None:
        """Release every Entity owned by this game."""
        for callback in tuple(self._close_callbacks):
            callback(parent_event)
        for entity_uuid in tuple(self.entities):
            self.remove_entity(entity_uuid)


__all__ = ["Game"]
