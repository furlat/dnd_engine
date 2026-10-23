"""Shoving furniture one cell at a time, as R63's barricade of couches needs."""

from typing import List, Optional, Tuple

from pydantic import Field

from dnd.actions import entity_action_economy_cost_evaluator
from dnd.blocks.base_item import BaseItem
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.dice import RollType
from dnd.core.events import EventPhase
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.types.discovery import ActorScan
from dnd.types.physical_access import PhysicalAccess
from dnd.types.materials import Material
from dnd.types.world_placement import WorldPlacementKind

HEAVY_SHOVE_DC = 15
_HEAVY_MATERIALS = frozenset({Material.STONE.value, Material.METAL.value})
SHOVEABLE_TAG = "shoveable"


def _shove_step(entity: Entity, item: BaseItem) -> Tuple[int, int] | None:
    """The cardinal step pushing a floor body straight away from the actor, when it touches one."""
    placement = get_map().get_object_placement(item.uuid)
    if placement is None or placement.kind is not WorldPlacementKind.CENTER:
        return None
    x, y = entity.position
    for cell in placement.positions:
        step = (cell[0] - x, cell[1] - y)
        if step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            return step
    return None


def is_heavy(item: BaseItem) -> bool:
    """Bodies over one cell, or of stone or metal, need a Strength (Athletics) check to move."""
    placement = get_map().get_object_placement(item.uuid)
    return (placement is not None and len(placement.positions) > 1) or bool(_HEAVY_MATERIALS.intersection(item.tags))


class ShoveObject(BaseAction):
    """Shove a piece of furniture one cell straight away: every cell of its body must cross freely.

    Only bodies authored as shoveable move (not a fireplace or a fountain). A heavy body needs a
    Strength (Athletics) check. A step that terrain, a wall, a closed door, a height step, another
    body or a creature stops leaves it where it was.
    """

    name: str = Field(default="Shove Object", description="Action name.")
    description: str = Field(default="Push a piece of furniture one square away from you",
                             description="Player-facing summary.")
    target_type: TargetType = Field(default=TargetType.OBJECT, description="Targets the furniture.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Shove Object Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        return PhysicalAccess.HAND

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(selection.target_uuids[0]) if selection.target_uuids else None
        if (not isinstance(entity, Entity) or not isinstance(item, BaseItem) or item.is_pickable
                or SHOVEABLE_TAG not in item.tags or not item.blocks_walking()):
            return "Nothing to shove"
        return None if _shove_step(entity, item) is not None else "Stand square against it to shove"

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        step = _shove_step(entity, item) if isinstance(entity, Entity) and isinstance(item, BaseItem) else None
        if not isinstance(entity, Entity) or not isinstance(item, BaseItem) or step is None:
            return execution_event.cancel(status_message="Nothing to shove")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if is_heavy(item) and entity.roll_d20(entity.skill_bonus(target_entity_uuid=None, skill_name="athletics"),
                RollType.CHECK, skill_name="athletics", parent_event=effect.uuid).total < HEAVY_SHOVE_DC:
            return effect.with_updates(status_message=f"{item.name} will not budge")
        grid = get_map()
        placement = grid.get_object_placement(item.uuid)
        assert placement is not None
        cells = set(placement.positions)
        # A step into the body's own cell crosses nothing; every other one goes as a walker's would,
        # into a free cell with no creature in it.
        if not all(grid.can_transition(start, end) and grid.is_walkable_for(*end) and not grid.get_entities_at(end)
                   for start, end in (((x, y), (x + step[0], y + step[1])) for x, y in cells)
                   if end not in cells):
            return effect.with_updates(status_message=f"{item.name} is stopped")
        anchor = placement.position
        try:
            grid.move_object(item.uuid, (anchor[0] + step[0], anchor[1] + step[1]), parent_event=effect.uuid,
                             orientation=placement.orientation)
        except ValueError:
            return effect.with_updates(status_message=f"{item.name} is stopped")
        return effect.with_updates(status_message=f"{entity.name} shoves {item.name}")
