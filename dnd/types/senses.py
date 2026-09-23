"""Dependency-neutral values shared by perception components and events."""

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.types.world import LightLevel
from dnd.core.content.identities import ContentRef
from dnd.core.presentation_geometry import AoEPresentationGeometry
from dnd.types.traps import TrapState
from dnd.types.material_deposits import MaterialDepositSource


class SensesType(str, Enum):
    """Special sense categories supported by the perception pipeline."""

    BLINDSIGHT = "Blindsight"
    DARKVISION = "Darkvision"
    TREMORSENSE = "Tremorsense"
    TRUESIGHT = "Truesight"
    DEVILS_SIGHT = "Devils Sight"
    SEE_INVISIBLE = "See Invisible"


class SenseMode(BaseModel):
    """A special sense and its effective range in feet; zero is unlimited."""

    sense_type: SensesType = Field(description="Special sense category.")
    range_feet: int = Field(default=0, description="Range in feet; zero means unlimited.")


class OpticalObscurement(str, Enum):
    """Observer-relative optical obstruction contributed by world mechanics."""

    HEAVY = "heavy"
    MAGICAL_DARKNESS = "magical_darkness"


class PerceivedContact(BaseModel):
    """One identified entity or object perceived by an observer."""

    model_config = ConfigDict(frozen=True)

    position: tuple[int, int] = Field(description="Observed grid position.")
    visual: bool = Field(description="Whether a visual route establishes this contact.")
    special_senses: tuple[SensesType, ...] = Field(
        default=(),
        description="Special senses which independently establish this contact.",
    )


class PerceivedSpatialEffect(BaseModel):
    """Last observed spatial effect and only its discovered footprint cells."""

    model_config = ConfigDict(frozen=True)

    content_ref: ContentRef
    name: str
    description: str
    positions: tuple[tuple[int, int], ...]
    trap_state: TrapState | None = None
    pressed: bool | None = None
    direction: tuple[int, int] | None = None
    anchor_item_uuid: UUID | None = None
    sustainer_item_uuid: UUID | None = None
    concentration_slot_uuid: UUID | None = None
    anchor_position: tuple[int, int] | None = None
    anchor_elevation_steps: int | None = None
    area_geometry: AoEPresentationGeometry | None = None
    deposit_source: MaterialDepositSource | None = None
    visible_volume_positions: tuple[tuple[int, int], ...] = ()


class SensesView(Protocol):
    """Minimal perception surface exposed upward by an observing block."""

    position: tuple[int, int]
    visible: Mapping[tuple[int, int], object]
    entities: Mapping[UUID, PerceivedContact]
    objects: Mapping[UUID, PerceivedContact]
    spatial_effects: Mapping[UUID, PerceivedSpatialEffect]

    def get_feet_distance(self, position: tuple[int, int]) -> int:
        """Return grid distance to one position in rules feet."""
        ...


class SensoryDelta(Protocol):
    """Recorded observer after-values consumed by the shared sensory reducer.

    Native events and public player facts expose the same values. Reduction
    needs neither native event construction nor its source/handler metadata.
    """

    @property
    def observer_uuid(self) -> UUID: ...
    @property
    def initial(self) -> bool: ...
    @property
    def observer_position(self) -> tuple[int, int]: ...
    @property
    def observer_position_changed(self) -> bool: ...
    @property
    def visible_cells_added(self) -> Sequence[tuple[int, int]]: ...
    @property
    def visible_cells_removed(self) -> Sequence[tuple[int, int]]: ...
    @property
    def seen_cells_added(self) -> Sequence[tuple[int, int]]: ...
    @property
    def entity_contacts_changed(self) -> Mapping[UUID, PerceivedContact]: ...
    @property
    def entity_contacts_removed(self) -> Set[UUID]: ...
    @property
    def object_contacts_changed(self) -> Mapping[UUID, PerceivedContact]: ...
    @property
    def object_contacts_removed(self) -> Set[UUID]: ...
    @property
    def effective_light_levels_changed(self) -> Mapping[str, int]: ...
    @property
    def hazardous_cells_changed(self) -> Mapping[str, bool]: ...
    @property
    def spatial_effects_changed(self) -> Mapping[UUID, PerceivedSpatialEffect]: ...
    @property
    def spatial_effects_removed(self) -> Set[UUID]: ...
    @property
    def sense_modes_changed(self) -> bool: ...
    @property
    def sense_modes(self) -> Sequence[SenseMode] | None: ...
    @property
    def passive_perception_changed(self) -> bool: ...
    @property
    def passive_perception(self) -> int | None: ...
    @property
    def visual_access_changed(self) -> bool: ...
    @property
    def visual_access(self) -> int | None: ...
    @property
    def paths_dirty(self) -> bool: ...


@dataclass(frozen=True)
class SensesSnapshot:
    """Observer snapshot with detached containers for sensory reduction."""

    position: tuple[int, int]
    visible: set[tuple[int, int]]
    seen: set[tuple[int, int]]
    entities: dict[UUID, PerceivedContact]
    objects: dict[UUID, PerceivedContact]
    effective_light_levels: dict[tuple[int, int], LightLevel]
    paths_dirty: bool
    passive_perception: int
    sense_modes_hash: int
    sense_modes: tuple[SenseMode, ...]
    visual_access: int
    hazardous_cells: dict[tuple[int, int], bool] = field(default_factory=dict)
    spatial_effects: dict[UUID, PerceivedSpatialEffect] = field(default_factory=dict)


def reduce_senses_snapshot(
    expected_observer_uuid: UUID,
    previous: SensesSnapshot | None,
    event: SensoryDelta,
) -> SensesSnapshot:
    """Reduce recorded observer after-values into a fresh sensory snapshot."""
    if event.observer_uuid != expected_observer_uuid:
        raise ValueError("sensory update belongs to a different observer")
    if event.initial:
        if event.passive_perception is None or event.visual_access is None:
            raise ValueError("initial sensory update requires capability after-values")
        # Initial additions are the complete view, not a merge with stale caches.
        previous = SensesSnapshot(
            position=event.observer_position, visible=set(), seen=set(),
            entities={}, objects={}, effective_light_levels={}, paths_dirty=False,
            passive_perception=event.passive_perception,
            sense_modes_hash=hash(()), sense_modes=(), visual_access=event.visual_access,
        )
    if previous is None:
        raise ValueError("sensory delta requires a previously recorded initial state")

    visible = set(previous.visible)
    visible.difference_update(event.visible_cells_removed)
    visible.update(event.visible_cells_added)

    entities = dict(previous.entities)
    for entity_uuid in event.entity_contacts_removed:
        entities.pop(entity_uuid, None)
    entities.update(event.entity_contacts_changed)

    objects = dict(previous.objects)
    for object_uuid in event.object_contacts_removed:
        objects.pop(object_uuid, None)
    objects.update(event.object_contacts_changed)

    spatial_effects = dict(previous.spatial_effects)
    for identity in event.spatial_effects_removed:
        spatial_effects.pop(identity, None)
    spatial_effects.update(event.spatial_effects_changed)

    light_levels = dict(previous.effective_light_levels)
    for position in event.visible_cells_removed:
        light_levels.pop(position, None)
    for key, level in event.effective_light_levels_changed.items():
        x_text, y_text = key.split(",", maxsplit=1)
        light_levels[(int(x_text), int(y_text))] = LightLevel(level)

    hazardous_cells = dict(previous.hazardous_cells)
    for position in event.visible_cells_removed:
        hazardous_cells.pop(position, None)
    for key, hazardous in event.hazardous_cells_changed.items():
        x_text, y_text = key.split(",", maxsplit=1)
        hazardous_cells[(int(x_text), int(y_text))] = hazardous

    sense_modes = tuple(
        mode.model_copy(deep=True) for mode in previous.sense_modes
    )
    sense_modes_hash = previous.sense_modes_hash
    if event.sense_modes_changed and event.sense_modes is not None:
        sense_modes = tuple(
            mode.model_copy(deep=True) for mode in event.sense_modes
        )
        sense_modes_hash = hash(
            tuple(
                sorted(
                    (mode.sense_type.value, mode.range_feet)
                    for mode in sense_modes
                )
            )
        )

    return SensesSnapshot(
        position=(
            event.observer_position
            if event.observer_position_changed
            else previous.position
        ),
        visible=visible,
        seen=set(previous.seen) | set(event.seen_cells_added),
        entities=entities,
        objects=objects,
        effective_light_levels=light_levels,
        hazardous_cells=hazardous_cells,
        spatial_effects=spatial_effects,
        paths_dirty=previous.paths_dirty or event.paths_dirty,
        passive_perception=(
            event.passive_perception
            if event.passive_perception_changed
            and event.passive_perception is not None
            else previous.passive_perception
        ),
        sense_modes_hash=sense_modes_hash,
        sense_modes=sense_modes,
        visual_access=(
            event.visual_access
            if event.visual_access_changed and event.visual_access is not None
            else previous.visual_access
        ),
    )


__all__ = [
    "OpticalObscurement",
    "PerceivedContact",
    "PerceivedSpatialEffect",
    "SenseMode",
    "SensesType",
    "SensesView",
    "SensoryDelta",
    "SensesSnapshot",
    "reduce_senses_snapshot",
]
