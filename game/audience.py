"""Player control and recorded sensory evidence, independent of turn ownership.

This module never queries native owners. The display view is composed from
complete recorded observations; it grants no actor additional senses or actions.
"""

from dataclasses import dataclass, field, replace
from uuid import UUID

from dnd.types.senses import PerceivedContact, PerceivedSpatialEffect, SensoryDelta, SensesSnapshot, reduce_senses_snapshot
from dnd.types.world import LightLevel


@dataclass(frozen=True, slots=True)
class PlayerAudience:
    controlled: tuple[UUID, ...]
    observers: tuple[UUID, ...]
    revision: int = 0

    def __post_init__(self) -> None:
        if (not self.observers or len(set(self.observers)) != len(self.observers)
                or len(set(self.controlled)) != len(self.controlled) or self.revision < 0):
            raise ValueError("Audience requires unique observers/controlled actors and a nonnegative revision")

    def controls(self, identity: UUID | None) -> bool:
        return identity in self.controlled

    def observes(self, identity: UUID | None) -> bool:
        return identity in self.observers

    def granted(self, observers: set[str]) -> bool:
        return any(str(identity) in observers for identity in self.observers)


def resolve_audience(observer_uuid: UUID, audience: PlayerAudience | None) -> PlayerAudience:
    """Normalize existing single-observer callers at the capture/packet boundary."""
    if audience is None:
        return PlayerAudience((observer_uuid,), (observer_uuid,))
    if observer_uuid not in audience.observers:
        raise ValueError("The stream observer must belong to its audience")
    return audience


@dataclass(frozen=True, slots=True)
class AudiencePerception:
    """Independent member snapshots with event-order provenance for arbitration."""
    members: dict[UUID, SensesSnapshot] = field(default_factory=dict)
    contact_cursors: dict[tuple[UUID, UUID], int] = field(default_factory=dict)
    effect_cursors: dict[tuple[UUID, UUID], int] = field(default_factory=dict)
    effect_absences: dict[tuple[UUID, tuple[int, int]], int] = field(default_factory=dict)


def observe_audience(previous: AudiencePerception, audience: PlayerAudience,
                     event: SensoryDelta, cursor: int) -> AudiencePerception:
    if not audience.observes(event.observer_uuid):
        raise ValueError("Sensory observation does not belong to this audience")
    members = dict(previous.members)
    members[event.observer_uuid] = reduce_senses_snapshot(
        event.observer_uuid, members.get(event.observer_uuid), event)
    contacts = dict(previous.contact_cursors)
    effects = dict(previous.effect_cursors)
    absent = dict(previous.effect_absences)
    current = members[event.observer_uuid]
    before = previous.members.get(event.observer_uuid)
    for identity in (*event.entity_contacts_changed, *event.object_contacts_changed):
        contacts[event.observer_uuid, identity] = cursor
    for identity, observed in event.spatial_effects_changed.items():
        if (current.visible.intersection(observed.positions) or observed.visible_volume_positions
                or observed.upper_volume_surfaces):
            effects[event.observer_uuid, identity] = cursor
    # Seeing an empty cell is evidence too, including a member's first visit.
    # It retires only that cell of another member's remembered footprint.
    known: dict[UUID, set[tuple[int, int]]] = {}
    for senses in (*previous.members.values(), current):
        for identity, observed in senses.spatial_effects.items():
            known.setdefault(identity, set()).update(observed.positions)
    for identity, positions in known.items():
        observed = current.spatial_effects.get(identity)
        present = set(observed.positions) if observed is not None else set()
        for position in positions & current.visible:
            key = identity, position
            if position in present:
                if absent.get(key, -1) <= cursor:
                    absent.pop(key, None)
            elif absent.get(key, -1) <= cursor:
                prior = before.spatial_effects.get(identity) if before is not None else None
                apparent = any(row.apparent_presence for senses in previous.members.values()
                               if (row := senses.spatial_effects.get(identity)) is not None)
                # A known concealed effect has native removal evidence too;
                # another observer merely failing to discover it does not.
                if apparent or prior is not None and position in prior.positions:
                    absent[key] = cursor
    return AudiencePerception(members, contacts, effects, absent)


def _contacts(perception: AudiencePerception, *, objects: bool) -> dict[UUID, PerceivedContact]:
    selected: dict[UUID, tuple[tuple[bool, int, int], PerceivedContact]] = {}
    for observer, senses in perception.members.items():
        for identity, contact in (senses.objects if objects else senses.entities).items():
            rank = (contact.visual, perception.contact_cursors.get((observer, identity), -1), -observer.int)
            if identity not in selected or rank > selected[identity][0]:
                selected[identity] = rank, contact
    return {identity: row[1] for identity, row in selected.items()}


_OBSERVED_EFFECT_FIELDS = {
    'anchor_position', 'anchor_elevation_steps', 'anchor_entity_uuid', 'anchor_item_uuid',
    'sustainer_item_uuid', 'concentration_slot_uuid', 'area_geometry',
}
_EFFECT_COLLECTIONS = {
    'positions', 'visible_volume_positions', 'upper_volume_surfaces', 'suppressions', 'construction_sections',
}


def _join_effect(first: PerceivedSpatialEffect, second: PerceivedSpatialEffect) -> PerceivedSpatialEffect | None:
    """Union one owner's compatible observations, checking the accumulated value."""
    if (first.owner_revision is None or first.owner_revision != second.owner_revision
            or first.model_dump(exclude=_EFFECT_COLLECTIONS | _OBSERVED_EFFECT_FIELDS)
            != second.model_dump(exclude=_EFFECT_COLLECTIONS | _OBSERVED_EFFECT_FIELDS)):
        return None
    first_optional = first.model_dump(include=_OBSERVED_EFFECT_FIELDS, mode='python')
    second_optional = second.model_dump(include=_OBSERVED_EFFECT_FIELDS, mode='python')
    if any(first_optional[key] is not None and value is not None and first_optional[key] != value
           for key, value in second_optional.items()):
        return None
    # Use the typed field values; model_validate restores the geometry union.
    optional = {key: first_optional[key] if first_optional[key] is not None else value
                for key, value in second_optional.items()}
    protections = {row.provider_uuid: row for row in first.suppressions}
    for row in second.suppressions:
        prior = protections.get(row.provider_uuid)
        if prior is not None and prior.model_dump(exclude={'positions'}) != row.model_dump(exclude={'positions'}):
            return None
        protections[row.provider_uuid] = row.model_copy(update={
            'positions': tuple(sorted(set(row.positions) | (set(prior.positions) if prior else set())))})
    upper = {(row.position, row.lower_height_planes): row
             for row in (*first.upper_volume_surfaces, *second.upper_volume_surfaces)}
    sections = tuple(dict.fromkeys((*first.construction_sections, *second.construction_sections)))
    values = {**first.model_dump(), **optional,
        'positions': tuple(sorted(set(first.positions) | set(second.positions))),
        'visible_volume_positions': tuple(sorted(set(first.visible_volume_positions) | set(second.visible_volume_positions))),
        'upper_volume_surfaces': tuple(upper[key] for key in sorted(upper)),
        'suppressions': tuple(protections[key] for key in sorted(protections, key=str)),
        'construction_sections': sections}
    return PerceivedSpatialEffect.model_validate(values)


def _effects(perception: AudiencePerception) -> dict[UUID, PerceivedSpatialEffect]:
    selected: dict[UUID, tuple[tuple[int, int, int], PerceivedSpatialEffect]] = {}
    for observer, senses in perception.members.items():
        for identity, observed in senses.spatial_effects.items():
            rank = (observed.owner_revision if observed.owner_revision is not None else -1,
                    perception.effect_cursors.get((observer, identity), -1), -observer.int)
            if identity not in selected or rank > selected[identity][0]:
                selected[identity] = rank, observed
    result = {}
    for identity, (_, newest) in selected.items():
        merged = newest
        for observer in sorted(perception.members, key=lambda value: value.int):
            row = perception.members[observer].spatial_effects.get(identity)
            if row is not None:
                merged = _join_effect(merged, row) or merged
        positions = {position for position in merged.positions
                     if (identity, position) not in perception.effect_absences}
        if positions or merged.visible_volume_positions or merged.upper_volume_surfaces:
            result[identity] = merged.model_copy(update={'positions': tuple(sorted(positions))})
    return result


def tile_observers(perception: AudiencePerception) -> dict[tuple[int, int], UUID]:
    """Choose one complete light observation per visible cell, with stable ties."""
    selected: dict[tuple[int, int], UUID] = {}
    for observer in sorted(perception.members, key=lambda identity: identity.int):
        senses = perception.members[observer]
        for position in senses.visible:
            previous = selected.get(position)
            if previous is None or senses.effective_light_levels.get(position, LightLevel.DARKNESS).value > (
                    perception.members[previous].effective_light_levels.get(position, LightLevel.DARKNESS).value):
                selected[position] = observer
    return selected


def audience_view(perception: AudiencePerception, observer_uuid: UUID) -> SensesSnapshot | None:
    """Compose display evidence, never a native observer or targeting capability.

    Scalar sense capabilities remain those of the stable stream observer. Only
    already-authorized spatial observations are united for presentation.
    """
    if not perception.members:
        return None
    anchor = perception.members.get(observer_uuid) or next(iter(perception.members.values()))
    owners = tile_observers(perception)
    return replace(anchor, visible=set(owners),
        seen=set().union(*(senses.seen for senses in perception.members.values())),
        entities=_contacts(perception, objects=False), objects=_contacts(perception, objects=True),
        effective_light_levels={position: perception.members[owner].effective_light_levels[position]
                                for position, owner in owners.items()
                                if position in perception.members[owner].effective_light_levels},
        hazardous_cells={position: perception.members[owner].hazardous_cells[position]
                         for position, owner in owners.items()
                         if position in perception.members[owner].hazardous_cells},
        spatial_effects=_effects(perception),
        paths_dirty=any(senses.paths_dirty for senses in perception.members.values()))
