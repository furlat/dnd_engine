"""Player control and recorded sensory evidence, independent of turn ownership.

This module never queries native owners. The display view is composed from
complete recorded observations; it grants no actor additional senses or actions.
"""

from collections.abc import Collection
from dataclasses import dataclass, field, replace
from uuid import UUID

from dnd.types.senses import (PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect, PreparedSensoryDelta, SensoryDelta,
    SensesSnapshot, apply_current_senses, copy_senses_snapshot, prepare_sensory_delta, reduce_senses_snapshot)
from dnd.types.world import LightLevel


@dataclass(frozen=True, slots=True)
class PlayerAudience:
    controlled: tuple[UUID, ...]
    observers: tuple[UUID, ...]
    revision: int = 0
    # Membership views of the two tuples: one hash per check instead of a tuple scan.
    _controlled_set: frozenset[UUID] = field(init=False, repr=False, compare=False)
    _observer_set: frozenset[UUID] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (not self.observers or len(set(self.observers)) != len(self.observers)
                or len(set(self.controlled)) != len(self.controlled) or self.revision < 0):
            raise ValueError("Audience requires unique observers/controlled actors and a nonnegative revision")
        object.__setattr__(self, "_controlled_set", frozenset(self.controlled))
        object.__setattr__(self, "_observer_set", frozenset(self.observers))

    def controls(self, identity: UUID | None) -> bool:
        return identity in self._controlled_set

    def observes(self, identity: UUID | None) -> bool:
        return identity in self._observer_set

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


def _effect_signature(value: PerceivedSpatialEffect) -> tuple:
    return (value.duration, value.content_ref, value.name, value.description, value.owner_revision,
        value.apparent_presence, value.trap_state, value.pressed, value.direction, value.energy_type,
        value.presence_mode, value.area_propagation, value.deposit_source)


def _join_effect(first: PerceivedSpatialEffect, second: PerceivedSpatialEffect) -> PerceivedSpatialEffect | None:
    """Union compatible, already validated typed observations of one owner."""
    if (first.owner_revision is None or first.owner_revision != second.owner_revision
            or _effect_signature(first) != _effect_signature(second)):
        return None
    optional = {}
    for key, old, new in (
        ('anchor_position', first.anchor_position, second.anchor_position),
        ('anchor_elevation_steps', first.anchor_elevation_steps, second.anchor_elevation_steps),
        ('anchor_entity_uuid', first.anchor_entity_uuid, second.anchor_entity_uuid),
        ('anchor_item_uuid', first.anchor_item_uuid, second.anchor_item_uuid),
        ('sustainer_item_uuid', first.sustainer_item_uuid, second.sustainer_item_uuid),
        ('concentration_slot_uuid', first.concentration_slot_uuid, second.concentration_slot_uuid),
        ('area_geometry', first.area_geometry, second.area_geometry),
    ):
        if old is not None and new is not None and old != new:
            return None
        optional[key] = old if old is not None else new
    protections = {row.provider_uuid: row for row in first.suppressions}
    for row in second.suppressions:
        prior = protections.get(row.provider_uuid)
        if prior is not None and (
                prior.provider_content_ref, prior.area_geometry, prior.anchor_elevation_steps
                ) != (row.provider_content_ref, row.area_geometry, row.anchor_elevation_steps):
            return None
        protections[row.provider_uuid] = row.model_copy(update={
            'positions': tuple(sorted(set(row.positions) | (set(prior.positions) if prior else set())))})
    upper = {(row.position, row.lower_height_planes): row
             for row in (*first.upper_volume_surfaces, *second.upper_volume_surfaces)}
    sections = tuple(dict.fromkeys((*first.construction_sections, *second.construction_sections)))
    return first.model_copy(update={**optional,
        'positions': tuple(sorted(set(first.positions) | set(second.positions))),
        'visible_volume_positions': tuple(sorted(set(first.visible_volume_positions) | set(second.visible_volume_positions))),
        'upper_volume_surfaces': tuple(upper[key] for key in sorted(upper)),
        'suppressions': tuple(protections[key] for key in sorted(protections, key=str)),
        'construction_sections': sections})


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


def light_sources(perception: AudiencePerception) -> tuple[dict[UUID, PerceivedLightSource], dict[UUID, int]]:
    """Union only current-revision optical footprints across permitted observers.

    Equal revision removal means this observer lost sight; a newer removal
    retires stale source versions still retained by other observer snapshots.
    """
    revisions: dict[UUID, int] = {}
    for senses in perception.members.values():
        for identity, revision in senses.light_source_removals.items():
            revisions[identity] = max(revisions.get(identity, -1), revision)
        for identity, source in senses.light_sources.items():
            revisions[identity] = max(revisions.get(identity, -1), source.revision)
    result: dict[UUID, PerceivedLightSource] = {}
    for observer in sorted(perception.members, key=lambda value: value.int):
        for identity, source in perception.members[observer].light_sources.items():
            if source.revision != revisions[identity]:
                continue
            previous = result.get(identity)
            if previous is None:
                result[identity] = source
            else:
                result[identity] = previous.model_copy(update={
                    "affected_tiles": {**previous.affected_tiles, **source.affected_tiles},
                    "anchor_entity_uuid": previous.anchor_entity_uuid or source.anchor_entity_uuid,
                    "anchor_item_uuid": previous.anchor_item_uuid or source.anchor_item_uuid})
    return result, {identity: revision for identity, revision in revisions.items() if identity not in result}


def update_light_sources(
    perception: AudiencePerception,
    identities: Collection[UUID],
    lights: dict[UUID, PerceivedLightSource],
    removals: dict[UUID, int],
) -> tuple[dict[UUID, PerceivedLightSource], dict[UUID, int]]:
    """Recompose only the named sources; every other source keeps its composed row.

    A source's composed row depends only on the members' rows for that source,
    so this equals `light_sources(perception)` restricted to `identities`.
    """
    lights, removals = dict(lights), dict(removals)
    observers = sorted(perception.members, key=lambda value: value.int)
    for identity in identities:
        revision = -1
        for observer in observers:
            senses = perception.members[observer]
            if identity in senses.light_source_removals:
                revision = max(revision, senses.light_source_removals[identity])
            source = senses.light_sources.get(identity)
            if source is not None:
                revision = max(revision, source.revision)
        merged: PerceivedLightSource | None = None
        for observer in observers:
            source = perception.members[observer].light_sources.get(identity)
            if source is None or source.revision != revision:
                continue
            merged = source if merged is None else merged.model_copy(update={
                "affected_tiles": {**merged.affected_tiles, **source.affected_tiles},
                "anchor_entity_uuid": merged.anchor_entity_uuid or source.anchor_entity_uuid,
                "anchor_item_uuid": merged.anchor_item_uuid or source.anchor_item_uuid})
        if merged is not None:
            lights[identity] = merged
            removals.pop(identity, None)
        else:
            lights.pop(identity, None)
            if revision >= 0:
                removals[identity] = revision
            else:
                removals.pop(identity, None)
    return lights, removals


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
    lights, removals = light_sources(perception)
    return replace(anchor, light_sources=lights, light_source_removals=removals, visible=set(owners),
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


@dataclass(slots=True)
class AudienceComposition:
    """Indexes and current view owned by one private recorded audience fold."""

    perception: AudiencePerception = field(default_factory=AudiencePerception)
    view: SensesSnapshot | None = None
    cell_members: dict[tuple[int, int], set[UUID]] = field(default_factory=dict)
    # The member whose observation the view shows for each cell (tile_observers' choice).
    cell_owners: dict[tuple[int, int], UUID] = field(default_factory=dict)
    entity_members: dict[UUID, set[UUID]] = field(default_factory=dict)
    object_members: dict[UUID, set[UUID]] = field(default_factory=dict)
    effect_members: dict[UUID, set[UUID]] = field(default_factory=dict)
    effect_positions: dict[UUID, set[tuple[int, int]]] = field(default_factory=dict)
    member_effect_positions: dict[tuple[UUID, UUID], set[tuple[int, int]]] = field(default_factory=dict)
    effects_at: dict[tuple[int, int], set[UUID]] = field(default_factory=dict)
    visible_effects: dict[UUID, set[UUID]] = field(default_factory=dict)
    dirty_members: set[UUID] = field(default_factory=set)
    contact_overrides: set[UUID] = field(default_factory=set)
    # The member whose contact the view shows, per (is object, identity), once composed.
    contact_holders: dict[tuple[bool, UUID], UUID] = field(default_factory=dict)


def _membership(index: dict, key, identity: UUID, present: bool) -> None:
    if present:
        index.setdefault(key, set()).add(identity)
    elif (members := index.get(key)) is not None:
        members.discard(identity)
        if not members:
            del index[key]


def copy_audience_perception(perception: AudiencePerception) -> AudiencePerception:
    """Detach a retained public before-state from an owned current fold."""
    return AudiencePerception(
        {identity: copy_senses_snapshot(value) for identity, value in perception.members.items()},
        dict(perception.contact_cursors), dict(perception.effect_cursors), dict(perception.effect_absences))


def begin_audience_composition(perception: AudiencePerception, observer_uuid: UUID) -> AudienceComposition:
    """Acquire a detached fold once; ordinary observations never recopy history."""
    perception = copy_audience_perception(perception)
    current = AudienceComposition(perception=perception, view=audience_view(perception, observer_uuid),
        cell_owners=tile_observers(perception))
    for observer, senses in perception.members.items():
        for position in senses.visible:
            _membership(current.cell_members, position, observer, True)
        for identity in senses.entities:
            _membership(current.entity_members, identity, observer, True)
        for identity in senses.objects:
            _membership(current.object_members, identity, observer, True)
        for identity, effect in senses.spatial_effects.items():
            _membership(current.effect_members, identity, observer, True)
            positions = set(effect.positions)
            current.member_effect_positions[observer, identity] = positions
            current.effect_positions.setdefault(identity, set()).update(positions)
        if senses.paths_dirty:
            current.dirty_members.add(observer)
    for identity, positions in current.effect_positions.items():
        for position in positions:
            _membership(current.effects_at, position, identity, True)
            for observer in current.cell_members.get(position, ()):
                current.visible_effects.setdefault(observer, set()).add(identity)
    return current


def _contact_rank(current: AudienceComposition, observer: UUID, identity: UUID,
                  contact: PerceivedContact) -> tuple[bool, int, int]:
    return contact.visual, current.perception.contact_cursors.get((observer, identity), -1), -observer.int


def _current_contact(current: AudienceComposition, identity: UUID, *,
                     objects: bool) -> tuple[PerceivedContact | None, UUID | None]:
    owners = (current.object_members if objects else current.entity_members).get(identity, ())
    selected = holder = None
    rank = None
    for observer in owners:
        member = current.perception.members[observer]
        contact = (member.objects if objects else member.entities)[identity]
        candidate = _contact_rank(current, observer, identity, contact)
        if rank is None or candidate > rank:
            rank, selected, holder = candidate, contact, observer
    return selected, holder


def _current_effect(current: AudienceComposition, identity: UUID) -> PerceivedSpatialEffect | None:
    owners = current.effect_members.get(identity, ())
    if not owners:
        return None
    perception = current.perception
    owner = max(owners, key=lambda observer: (
        perception.members[observer].spatial_effects[identity].owner_revision
            if perception.members[observer].spatial_effects[identity].owner_revision is not None else -1,
        perception.effect_cursors.get((observer, identity), -1), -observer.int))
    merged = perception.members[owner].spatial_effects[identity]
    for observer in sorted(owners, key=lambda value: value.int):
        merged = _join_effect(merged, perception.members[observer].spatial_effects[identity]) or merged
    positions = {position for position in merged.positions if (identity, position) not in perception.effect_absences}
    if positions or merged.visible_volume_positions or merged.upper_volume_surfaces:
        return merged.model_copy(update={'positions': tuple(sorted(positions))})
    return None


def apply_current_audience(current: AudienceComposition, audience: PlayerAudience, observer_uuid: UUID,
                           event: SensoryDelta, cursor: int, *,
                           prepared: PreparedSensoryDelta | None = None) -> None:
    """Apply local sensory changes to an exclusively owned audience composition."""
    if not audience.observes(event.observer_uuid):
        raise ValueError("Sensory observation does not belong to this audience")
    observer = event.observer_uuid
    perception = current.perception
    before = perception.members.get(observer)
    prepared = prepared or prepare_sensory_delta(observer, before, event)
    added, removed = set(event.visible_cells_added), set(event.visible_cells_removed)
    cells = added | removed | prepared.light_levels.keys() | prepared.hazardous_cells.keys()
    contacts = (set(event.entity_contacts_changed) | event.entity_contacts_removed
                | event.object_contacts_changed.keys() | event.object_contacts_removed)
    overrides = set(current.contact_overrides)
    contacts.update(overrides)
    current.contact_overrides.clear()
    effects = set(event.spatial_effects_changed) | event.spatial_effects_removed
    if event.initial and before is not None:
        cells.update(before.visible)
        contacts.update(before.entities)
        contacts.update(before.objects)
        effects.update(before.spatial_effects)
    def visible(position: tuple[int, int]) -> bool:
        return position in added or (not event.initial and position not in removed
            and before is not None and position in before.visible)
    changed_effect_positions = {identity: set(effect.positions)
        for identity, effect in event.spatial_effects_changed.items()}
    def observed_positions(identity: UUID) -> set[tuple[int, int]]:
        if identity in changed_effect_positions:
            return changed_effect_positions[identity]
        if event.initial or identity in event.spatial_effects_removed:
            return set()
        return current.member_effect_positions.get((observer, identity), set())
    def visible_positions(positions: set[tuple[int, int]]) -> set[tuple[int, int]]:
        result = positions.intersection(before.visible) if before is not None and not event.initial else set()
        result.difference_update(removed)
        result.update(positions.intersection(added))
        return result

    # Preserve empty-cell evidence even for an otherwise empty sensory delta.
    # Previous member rows must still be available here, before owned mutation.
    candidates = set(current.visible_effects.get(observer, ())) | effects
    for position in added:
        candidates.update(current.effects_at.get(position, ()))
    absence_updates: dict[tuple[UUID, tuple[int, int]], int | None] = {}
    recompute_effects = set(effects)
    for identity in candidates:
        positions = visible_positions(current.effect_positions.get(identity, set()))
        present = observed_positions(identity)
        positions.update(visible_positions(present))
        prior = current.member_effect_positions.get((observer, identity), set())
        apparent = any(perception.members[member].spatial_effects[identity].apparent_presence
                       for member in current.effect_members.get(identity, ()))
        for position in positions:
            key = identity, position
            old = perception.effect_absences.get(key)
            if (old if old is not None else -1) > cursor:
                continue
            if position in present:
                if old is not None:
                    absence_updates[key] = None
                    recompute_effects.add(identity)
            elif apparent or position in prior:
                absence_updates[key] = cursor
                if old is None:
                    recompute_effects.add(identity)
    effect_cursors = {identity: cursor for identity, effect in event.spatial_effects_changed.items()
        if any(visible(position) for position in effect.positions)
        or effect.visible_volume_positions or effect.upper_volume_surfaces}
    # This delta changes only its own observer: a cell whose visibility, light
    # and hazard are unchanged for it keeps its membership and composed value.
    # Record them before the fold mutates the member in place.
    previous_cells = ({position: (position in before.visible, before.effective_light_levels.get(position),
                                  before.hazardous_cells.get(position)) for position in cells}
                      if before is not None and current.view is not None else {})

    member = apply_current_senses(before, event, prepared)
    perception.members[observer] = member
    for identity in (*event.entity_contacts_changed, *event.object_contacts_changed):
        perception.contact_cursors[observer, identity] = cursor
    perception.effect_cursors.update(((observer, identity), value) for identity, value in effect_cursors.items())
    for key, value in absence_updates.items():
        if value is None:
            perception.effect_absences.pop(key, None)
        else:
            perception.effect_absences[key] = value
    for position in cells:
        _membership(current.cell_members, position, observer, position in member.visible)
    for identity in contacts:
        _membership(current.entity_members, identity, observer, identity in member.entities)
        _membership(current.object_members, identity, observer, identity in member.objects)
    for identity in effects:
        _membership(current.effect_members, identity, observer, identity in member.spatial_effects)
        if identity in member.spatial_effects:
            current.member_effect_positions[observer, identity] = changed_effect_positions[identity]
        else:
            current.member_effect_positions.pop((observer, identity), None)
        previous_positions = current.effect_positions.pop(identity, set())
        positions = set().union(*(current.member_effect_positions[owner, identity]
            for owner in current.effect_members.get(identity, ())))
        if positions:
            current.effect_positions[identity] = positions
        affected_members = {observer}
        for position in previous_positions | positions:
            _membership(current.effects_at, position, identity, position in positions)
            affected_members.update(current.cell_members.get(position, ()))
        for owner in affected_members:
            values = current.visible_effects.setdefault(owner, set())
            if positions.intersection(perception.members[owner].visible):
                values.add(identity)
            else:
                values.discard(identity)
    active_effects = current.visible_effects.setdefault(observer, set())
    for identity in candidates:
        if current.effect_positions.get(identity, set()).intersection(member.visible):
            active_effects.add(identity)
        else:
            active_effects.discard(identity)
    if member.paths_dirty:
        current.dirty_members.add(observer)
    else:
        current.dirty_members.discard(observer)

    if current.view is None:
        current.view = replace(member, visible=set(), seen=set(), entities={}, objects={},
            effective_light_levels={}, hazardous_cells={}, spatial_effects={})
    view = current.view
    for position in cells:
        if previous_cells.get(position) == (position in member.visible, member.effective_light_levels.get(position),
                                            member.hazardous_cells.get(position)):
            continue
        owners = current.cell_members.get(position)
        if not owners:
            current.cell_owners.pop(position, None)
            view.visible.discard(position)
            view.effective_light_levels.pop(position, None)
            view.hazardous_cells.pop(position, None)
            continue

        def rank(identity: UUID) -> tuple[int, int]:
            return (perception.members[identity].effective_light_levels.get(position, LightLevel.DARKNESS).value,
                    -identity.int)

        held = current.cell_owners.get(position)
        if held is not None and held != observer and held in owners:
            # Only this observer changed: it takes the cell only by outranking the holder.
            if observer not in owners or rank(observer) <= rank(held):
                continue
            owner = observer
        else:
            owner = max(owners, key=rank)
        current.cell_owners[position] = owner
        source = perception.members[owner]
        view.visible.add(position)
        if position in source.effective_light_levels:
            view.effective_light_levels[position] = source.effective_light_levels[position]
        else:
            view.effective_light_levels.pop(position, None)
        if position in source.hazardous_cells:
            view.hazardous_cells[position] = source.hazardous_cells[position]
        else:
            view.hazardous_cells.pop(position, None)
    for identity in contacts:
        for objects, destination in ((False, view.entities), (True, view.objects)):
            key = objects, identity
            held = current.contact_holders.get(key)
            owners = (current.object_members if objects else current.entity_members).get(identity, ())
            if identity not in overrides and held is not None and held != observer and held in owners:
                # Only this observer changed: it takes the contact only by outranking the holder.
                if observer not in owners:
                    continue
                mine = (member.objects if objects else member.entities)[identity]
                theirs = (perception.members[held].objects if objects else perception.members[held].entities)[identity]
                if _contact_rank(current, observer, identity, mine) <= _contact_rank(current, held, identity, theirs):
                    continue
                contact, holder = mine, observer
            else:
                contact, holder = _current_contact(current, identity, objects=objects)
            if contact is None or holder is None:
                destination.pop(identity, None)
                current.contact_holders.pop(key, None)
            else:
                destination[identity] = contact
                current.contact_holders[key] = holder
    for identity in recompute_effects:
        effect = _current_effect(current, identity)
        if effect is None:
            view.spatial_effects.pop(identity, None)
        else:
            view.spatial_effects[identity] = effect
    if event.initial:
        view.seen.clear()
        for source in perception.members.values():
            view.seen.update(source.seen)
    else:
        view.seen.update(event.seen_cells_added)
    anchor = perception.members.get(observer_uuid) or next(iter(perception.members.values()))
    # Only the sources this delta names can change their composed row.
    if event.initial:
        lights, removals = light_sources(perception)
    elif event.light_sources_changed or event.light_sources_removed:
        lights, removals = update_light_sources(perception,
            set(event.light_sources_changed) | set(event.light_sources_removed),
            view.light_sources, view.light_source_removals)
    else:
        lights, removals = view.light_sources, view.light_source_removals
    current.view = replace(view, light_sources=lights, light_source_removals=removals,
        position=anchor.position, passive_perception=anchor.passive_perception,
        sense_modes_hash=anchor.sense_modes_hash, sense_modes=anchor.sense_modes,
        visual_access=anchor.visual_access, paths_dirty=bool(current.dirty_members))


@dataclass(frozen=True, slots=True)
class SeatAssignment:
    """Private assignment using existing authored roster/member addresses."""

    seat_id: str
    controlled: tuple[tuple[str, str], ...]
    observers: tuple[tuple[str, str], ...] | None = None
