"""Player control and recorded sensory evidence, independent of turn ownership.

This module never queries native owners. The display view is composed from
complete recorded observations; it grants no actor additional senses or actions.
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass, field, replace
from uuid import UUID

import numpy as np

from dnd.core.cells import Box, cell_layers, mask_box, mask_positions, mask_union, pack_layers, union_box
from dnd.core.sensory_fold import apply_current_senses, copy_senses_snapshot, prepare_sensory_delta, reduce_senses_snapshot
from dnd.types.cells import EMPTY_CELLS, EMPTY_VALUES, CellMask, CellValues, cell_in
from dnd.types.senses import PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect, SensoryDelta, SensesSnapshot


@dataclass(frozen=True, slots=True)
class PlayerAudience:
    controlled: tuple[UUID, ...]
    observers: tuple[UUID, ...]
    revision: int = 0
    # Membership views of the two tuples: one hash per check instead of a tuple scan.
    _controlled_set: frozenset[UUID] = field(init=False, repr=False, compare=False)
    _observer_set: frozenset[UUID] = field(init=False, repr=False, compare=False)
    # The same members as the string identities combat logs carry.
    _controlled_ids: frozenset[str] = field(init=False, repr=False, compare=False)
    _observer_ids: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (not self.observers or len(set(self.observers)) != len(self.observers)
                or len(set(self.controlled)) != len(self.controlled) or self.revision < 0):
            raise ValueError("Audience requires unique observers/controlled actors and a nonnegative revision")
        object.__setattr__(self, "_controlled_set", frozenset(self.controlled))
        object.__setattr__(self, "_observer_set", frozenset(self.observers))
        object.__setattr__(self, "_controlled_ids", frozenset(map(str, self.controlled)))
        object.__setattr__(self, "_observer_ids", frozenset(map(str, self.observers)))

    @property
    def controlled_ids(self) -> frozenset[str]:
        return self._controlled_ids

    @property
    def observer_ids(self) -> frozenset[str]:
        return self._observer_ids

    def controls(self, identity: UUID | None) -> bool:
        return identity in self._controlled_set

    def observes(self, identity: UUID | None) -> bool:
        return identity in self._observer_set

    def granted(self, observers: set[str]) -> bool:
        return not self.observer_ids.isdisjoint(observers)


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


def perceived_entities(audience: PlayerAudience, perception: AudiencePerception) -> frozenset[UUID]:
    """The entities a seat perceives now: its controlled actors and every member's entity contacts."""
    return frozenset(audience.controlled).union(*(snapshot.entities for snapshot in perception.members.values()))


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
        if (any(cell_in(current.visible, position) for position in observed.positions)
                or observed.visible_volume_positions or observed.upper_volume_surfaces):
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
        for position in (position for position in positions if cell_in(current.visible, position)):
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


def _joined_optional(value: PerceivedSpatialEffect) -> dict:
    """The fields one observation may leave unset and another may supply."""
    return {'anchor_position': value.anchor_position, 'anchor_elevation_steps': value.anchor_elevation_steps,
        'anchor_entity_uuid': value.anchor_entity_uuid, 'anchor_item_uuid': value.anchor_item_uuid,
        'sustainer_item_uuid': value.sustainer_item_uuid, 'concentration_slot_uuid': value.concentration_slot_uuid,
        'area_geometry': value.area_geometry}


def _join_effects(first: PerceivedSpatialEffect, rows: Iterable[PerceivedSpatialEffect]) -> PerceivedSpatialEffect:
    """Union compatible, already validated typed observations of one owner, left to right.

    A row whose revision, signature, anchors or protections conflict with the
    union so far is skipped whole; the union is built once at the end.
    """
    if first.owner_revision is None:
        return first
    signature = _effect_signature(first)
    optional = _joined_optional(first)
    positions = set(first.positions)
    volume = set(first.visible_volume_positions)
    upper = {(row.position, row.lower_height_planes): row for row in first.upper_volume_surfaces}
    sections = dict.fromkeys(first.construction_sections)
    # provider -> (the row whose attributes the protection carries, its united positions or None if untouched)
    protections: dict = {row.provider_uuid: (row, None) for row in first.suppressions}
    joined = False
    for second in rows:
        if second.owner_revision != first.owner_revision or _effect_signature(second) != signature:
            continue
        values = {}
        for key, new in _joined_optional(second).items():
            old = optional[key]
            if old is not None and new is not None and old != new:
                break
            values[key] = old if old is not None else new
        else:
            staged = {}
            for row in second.suppressions:
                prior, united = staged.get(row.provider_uuid) or protections.get(row.provider_uuid, (None, None))
                if prior is not None and (
                        prior.provider_content_ref, prior.area_geometry, prior.anchor_elevation_steps
                        ) != (row.provider_content_ref, row.area_geometry, row.anchor_elevation_steps):
                    break
                previous = united if united is not None else set(prior.positions) if prior is not None else set()
                staged[row.provider_uuid] = (row, previous | set(row.positions))
            else:
                joined = True
                optional = values
                protections.update(staged)
                positions.update(second.positions)
                volume.update(second.visible_volume_positions)
                upper.update(((row.position, row.lower_height_planes), row) for row in second.upper_volume_surfaces)
                sections.update(dict.fromkeys(second.construction_sections))
    if not joined:
        return first
    suppressions = tuple(row if united is None else row.model_copy(update={'positions': tuple(sorted(united))})
        for row, united in (protections[key] for key in sorted(protections, key=str)))
    return first.model_copy(update={**optional,
        'positions': tuple(sorted(positions)),
        'visible_volume_positions': tuple(sorted(volume)),
        'upper_volume_surfaces': tuple(upper[key] for key in sorted(upper)),
        'suppressions': suppressions,
        'construction_sections': tuple(sections)})


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
        merged = _join_effects(newest, (row for observer in sorted(perception.members, key=lambda value: value.int)
            if (row := perception.members[observer].spatial_effects.get(identity)) is not None))
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
    rows: dict[UUID, list[PerceivedLightSource]] = {}
    for observer in sorted(perception.members, key=lambda value: value.int):
        for identity, source in perception.members[observer].light_sources.items():
            if source.revision == revisions[identity]:
                rows.setdefault(identity, []).append(source)
    result = {identity: _merged_light(members) for identity, members in rows.items()}
    return result, {identity: revision for identity, revision in revisions.items() if identity not in result}


def _merged_light(rows: list[PerceivedLightSource]) -> PerceivedLightSource:
    """The first member's row with every member's footprint (later rows win) and first anchors."""
    first = rows[0]
    if len(rows) == 1:
        return first
    tiles: dict = {}
    for row in rows:
        tiles.update(row.affected_tiles)
    entity = next((row.anchor_entity_uuid for row in rows if row.anchor_entity_uuid), None)
    item = next((row.anchor_item_uuid for row in rows if row.anchor_item_uuid), None)
    if tiles == first.affected_tiles and entity == first.anchor_entity_uuid and item == first.anchor_item_uuid:
        return first
    return first.model_copy(update={"affected_tiles": tiles, "anchor_entity_uuid": entity, "anchor_item_uuid": item})


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
        rows = [source for observer in observers
                if (source := perception.members[observer].light_sources.get(identity)) is not None
                and source.revision == revision]
        if rows:
            lights[identity] = _merged_light(rows)
            removals.pop(identity, None)
        else:
            lights.pop(identity, None)
            if revision >= 0:
                removals[identity] = revision
            else:
                removals.pop(identity, None)
    return lights, removals


def _member_order(perception: AudiencePerception) -> tuple[UUID, ...]:
    """Members by uuid: equal light goes to the earlier member."""
    return tuple(sorted(perception.members, key=lambda value: value.int))


def _stack(members: Iterable[SensesSnapshot], box: Box) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Each member's visible cells, light and hazard over a box, one layer per member."""
    rows = [(seen, *layers) for seen, layers in (cell_layers(senses.visible, (senses.effective_light_levels,
        senses.hazardous_cells), box) for senses in members)]
    seen, lights, hazards = (np.stack(layer) for layer in zip(*rows))
    return seen, lights, hazards


def _ranked(seen: np.ndarray, lights: np.ndarray, hazards: np.ndarray
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The composed visible cells, light, hazard and owner (member index) of member layers in uuid order.

    Each visible cell shows one member's complete observation: the member
    seeing it in the brightest light, ties to the smaller observer uuid.
    """
    count = seen.shape[0]
    order = np.arange(count - 1, -1, -1, dtype=np.int32)[:, None, None]
    rank = np.where(seen, lights.astype(np.int32) * count + order, -1)
    owner = rank.argmax(axis=0)[None]
    visible = np.take_along_axis(rank, owner, axis=0)[0] >= 0
    return (visible, np.take_along_axis(lights, owner, axis=0)[0] * visible,
            np.take_along_axis(hazards, owner, axis=0)[0] * visible, owner[0].astype(np.uint16))


def _composed_view_cells(perception: AudiencePerception) -> tuple[CellMask, CellValues, CellValues]:
    box = union_box(*(mask_box(senses.visible) for senses in perception.members.values()))
    if box is None:
        return EMPTY_CELLS, EMPTY_VALUES, EMPTY_VALUES
    visible, light, hazard, _ = _ranked(*_stack((perception.members[identity] for identity in _member_order(perception)), box))
    cells, (light_values, hazard_values) = pack_layers(box[0], box[1], visible, light, hazard)
    return cells, light_values, hazard_values


def _cover(current: "AudienceComposition", box: Box) -> None:
    """Grow the member layers' window to cover a box; cells outside every member's view are unseen."""
    window = current.window
    grown = union_box(window, box)
    assert grown is not None
    if grown == window:
        return
    count = len(current.order)
    shape = (count, grown[2] - grown[0] + 1, grown[3] - grown[1] + 1)
    seen, lights, hazards = np.zeros(shape, dtype=bool), np.zeros(shape, dtype=np.uint8), np.zeros(shape, dtype=np.uint8)
    shown, shown_light, shown_hazard, shown_owner = (np.zeros(shape[1:], dtype=bool), np.zeros(shape[1:], dtype=np.uint8),
                                                     np.zeros(shape[1:], dtype=np.uint8), np.zeros(shape[1:], dtype=np.uint16))
    if window is not None:
        part = (slice(window[0] - grown[0], window[2] - grown[0] + 1), slice(window[1] - grown[1], window[3] - grown[1] + 1))
        seen[:, part[0], part[1]], lights[:, part[0], part[1]], hazards[:, part[0], part[1]] = (
            current.seen, current.lights, current.hazards)
        shown[part], shown_light[part], shown_hazard[part], shown_owner[part] = (
            current.shown, current.shown_light, current.shown_hazard, current.shown_owner)
    current.window, current.seen, current.lights, current.hazards = grown, seen, lights, hazards
    current.shown, current.shown_light, current.shown_hazard, current.shown_owner = shown, shown_light, shown_hazard, shown_owner


def _restack(current: "AudienceComposition") -> None:
    """Every member's layer and the composed cells over the members' window, in uuid order."""
    perception = current.perception
    current.order = _member_order(perception)
    members = [perception.members[identity] for identity in current.order]
    current.window = union_box(*(mask_box(senses.visible) for senses in members))
    if current.window is None:
        return
    current.seen, current.lights, current.hazards = _stack(members, current.window)
    current.shown, current.shown_light, current.shown_hazard, current.shown_owner = _ranked(
        current.seen, current.lights, current.hazards)


def _fold_view_cells(current: "AudienceComposition", observer: UUID, before: SensesSnapshot | None,
                     member: SensesSnapshot, box: Box | None, *, hazards_only: bool) -> None:
    """Fold one member's changed cells into its layer and the composed view.

    Only cells in `box` (around those where this member's observation
    changed) can change in the view; they are recomposed from every member's
    layer. A hazard never changes a cell's owner, so when only hazards moved
    the member's new hazards show where it owns the cell. A new member
    renumbers the layers, so its first observation restacks every member.
    """
    view = current.view
    assert view is not None
    if before is None or observer not in current.order:
        _restack(current)
    else:
        if box is None:
            return
        _cover(current, box)
        window = current.window
        assert window is not None
        index = current.order.index(observer)
        part = (slice(box[0] - window[0], box[2] - window[0] + 1), slice(box[1] - window[1], box[3] - window[1] + 1))
        current.seen[index][part], (current.lights[index][part], current.hazards[index][part]) = cell_layers(
            member.visible, (member.effective_light_levels, member.hazardous_cells), box)
        if hazards_only:
            shown = current.shown_hazard[part]
            composed_hazard = np.where(current.shown[part] & (current.shown_owner[part] == index),
                                       current.hazards[index][part], shown)
            if np.array_equal(shown, composed_hazard):
                return
            current.shown_hazard[part] = composed_hazard
        else:
            composed = _ranked(current.seen[:, part[0], part[1]], current.lights[:, part[0], part[1]],
                               current.hazards[:, part[0], part[1]])
            held = (current.shown[part], current.shown_light[part], current.shown_hazard[part], current.shown_owner[part])
            if all(np.array_equal(old, new) for old, new in zip(held[:3], composed[:3])):
                current.shown_owner[part] = composed[3]
                return  # The view shows these cells as it did.
            current.shown[part], current.shown_light[part], current.shown_hazard[part], current.shown_owner[part] = composed
    window = current.window
    if window is None:
        current.view = replace(view, visible=EMPTY_CELLS, effective_light_levels=EMPTY_VALUES, hazardous_cells=EMPTY_VALUES)
        return
    cells, (light, hazard) = pack_layers(window[0], window[1], current.shown, current.shown_light, current.shown_hazard)
    current.view = replace(view, visible=cells, effective_light_levels=light, hazardous_cells=hazard)


def audience_view(perception: AudiencePerception, observer_uuid: UUID) -> SensesSnapshot | None:
    """Compose display evidence, never a native observer or targeting capability.

    Scalar sense capabilities remain those of the stable stream observer. Only
    already-authorized spatial observations are united for presentation.
    """
    if not perception.members:
        return None
    anchor = perception.members.get(observer_uuid) or next(iter(perception.members.values()))
    visible, light, hazards = _composed_view_cells(perception)
    lights, removals = light_sources(perception)
    return replace(anchor, light_sources=lights, light_source_removals=removals, visible=visible,
        seen=mask_union(*(senses.seen for senses in perception.members.values())),
        entities=_contacts(perception, objects=False), objects=_contacts(perception, objects=True),
        effective_light_levels=light, hazardous_cells=hazards,
        spatial_effects=_effects(perception),
        paths_dirty=any(senses.paths_dirty for senses in perception.members.values()))


@dataclass(slots=True)
class AudienceComposition:
    """Indexes and current view owned by one private recorded audience fold."""

    perception: AudiencePerception = field(default_factory=AudiencePerception)
    view: SensesSnapshot | None = None
    # Every member's cells as layers over one window that only grows: members in
    # uuid order; seen, light and hazard per cell (the composition's working arrays).
    order: tuple[UUID, ...] = ()
    window: Box | None = None
    seen: np.ndarray = field(default_factory=lambda: np.zeros((0, 0, 0), dtype=bool))
    lights: np.ndarray = field(default_factory=lambda: np.zeros((0, 0, 0), dtype=np.uint8))
    hazards: np.ndarray = field(default_factory=lambda: np.zeros((0, 0, 0), dtype=np.uint8))
    # The view's cells over the same window: their composition, kept as each fold changes it.
    shown: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=bool))
    shown_light: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.uint8))
    shown_hazard: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.uint8))
    shown_owner: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.uint16))
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
    current = AudienceComposition(perception=perception, view=audience_view(perception, observer_uuid))
    _restack(current)
    for observer, senses in perception.members.items():
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
        for observer, senses in perception.members.items():
            if any(cell_in(senses.visible, position) for position in positions):
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


def _rank_of(row: PerceivedSpatialEffect, cursor: int, observer: UUID) -> tuple[int, int, int]:
    """A member's claim to show an effect: its row's newest revision, then its latest sighting, then the smaller uuid."""
    return (row.owner_revision if row.owner_revision is not None else -1, cursor, -observer.int)


def _effect_rank(perception: AudiencePerception, observer: UUID, identity: UUID) -> tuple[int, int, int]:
    return _rank_of(perception.members[observer].spatial_effects[identity],
                    perception.effect_cursors.get((observer, identity), -1), observer)


def _current_effect(current: AudienceComposition, identity: UUID) -> PerceivedSpatialEffect | None:
    owners = current.effect_members.get(identity, ())
    if not owners:
        return None
    perception = current.perception
    owner = max(owners, key=lambda observer: _effect_rank(perception, observer, identity))
    merged = _join_effects(perception.members[owner].spatial_effects[identity],
        (perception.members[observer].spatial_effects[identity] for observer in sorted(owners, key=lambda value: value.int)))
    positions = {position for position in merged.positions if (identity, position) not in perception.effect_absences}
    if positions or merged.visible_volume_positions or merged.upper_volume_surfaces:
        return merged.model_copy(update={'positions': tuple(sorted(positions))})
    return None


def _keeps_composed_effect(current: AudienceComposition, observer: UUID, identity: UUID,
                           sighting: PerceivedSpatialEffect, prior: PerceivedSpatialEffect | None,
                           prior_cursor: int) -> bool:
    """Whether `observer` now seeing `sighting` (instead of `prior`, sighted at `prior_cursor`) leaves the composed effect as it is.

    It does when the newest row among the other members equals it: the newest
    row is then this value before and after, a row equal to the join's first
    is a no-op in the join wherever it sorts, and the observer's prior row
    either equals it, was absent, or neither led nor joined (another revision,
    ranked below). The caller has checked that no absence of the effect
    appeared or retired.
    """
    perception = current.perception
    others = [owner for owner in current.effect_members.get(identity, ()) if owner != observer]
    if not others:
        return False
    newest = max(others, key=lambda owner: _effect_rank(perception, owner, identity))
    row = perception.members[newest].spatial_effects[identity]
    if not (row is sighting or row == sighting):
        return False
    if prior is None or prior is sighting or prior == sighting:
        return True
    return (prior.owner_revision != sighting.owner_revision
            and _rank_of(prior, prior_cursor, observer) < _effect_rank(perception, newest, identity))


def _keeps_composed_light(view: SensesSnapshot, identity: UUID, source: PerceivedLightSource,
                          prior: PerceivedLightSource | None) -> bool:
    """Whether a member now holding `source` (instead of `prior`) leaves the composed light as it is.

    It does when the view already shows `source`: the newest revision is then
    its own, and `_merged_light` of rows merging to `source` gains one more
    equal row (or swaps an equal one), unless the member's prior row of that
    revision differs.
    """
    held = view.light_sources.get(identity)
    return (held is not None and (held is source or held == source)
            and (prior is None or prior.revision != source.revision or prior is source or prior == source))


def apply_current_audience(current: AudienceComposition, audience: PlayerAudience, observer_uuid: UUID,
                           event: SensoryDelta, cursor: int) -> None:
    """Apply local sensory changes to an exclusively owned audience composition."""
    if not audience.observes(event.observer_uuid):
        raise ValueError("Sensory observation does not belong to this audience")
    observer = event.observer_uuid
    perception = current.perception
    before = perception.members.get(observer)
    prepared = prepare_sensory_delta(observer, before, event)
    added, removed = event.visible_cells_added, event.visible_cells_removed
    # The box of the cells this delta can change for its own observer, and so in the view.
    cells = union_box(mask_box(added), mask_box(removed), mask_box(event.effective_light_levels_changed.cells),
        mask_box(event.hazardous_cells_changed.cells),
        mask_box(before.visible) if event.initial and before is not None else None)
    contacts = (set(event.entity_contacts_changed) | event.entity_contacts_removed
                | event.object_contacts_changed.keys() | event.object_contacts_removed)
    overrides = set(current.contact_overrides)
    contacts.update(overrides)
    current.contact_overrides.clear()
    effects = set(event.spatial_effects_changed) | event.spatial_effects_removed
    if event.initial and before is not None:
        contacts.update(before.entities)
        contacts.update(before.objects)
        effects.update(before.spatial_effects)
    def visible(position: tuple[int, int]) -> bool:
        return cell_in(added, position) or (not event.initial and not cell_in(removed, position)
            and before is not None and cell_in(before.visible, position))
    changed_effect_positions = {identity: set(effect.positions)
        for identity, effect in event.spatial_effects_changed.items()}
    def observed_positions(identity: UUID) -> set[tuple[int, int]]:
        if identity in changed_effect_positions:
            return changed_effect_positions[identity]
        if event.initial or identity in event.spatial_effects_removed:
            return set()
        return current.member_effect_positions.get((observer, identity), set())
    def visible_positions(positions: set[tuple[int, int]]) -> set[tuple[int, int]]:
        return {position for position in positions if visible(position)}

    # Preserve empty-cell evidence even for an otherwise empty sensory delta.
    # Previous member rows must still be available here, before owned mutation.
    candidates = set(current.visible_effects.get(observer, ())) | effects
    for position in mask_positions(added):
        candidates.update(current.effects_at.get(position, ()))
    absence_updates: dict[tuple[UUID, tuple[int, int]], int | None] = {}
    # Effects whose absent cells appear or retire.
    absence_changed: set[UUID] = set()
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
                    absence_changed.add(identity)
            elif apparent or position in prior:
                absence_updates[key] = cursor
                if old is None:
                    absence_changed.add(identity)
    recompute_effects = effects | absence_changed
    effect_cursors = {identity: cursor for identity, effect in event.spatial_effects_changed.items()
        if any(visible(position) for position in effect.positions)
        or effect.visible_volume_positions or effect.upper_volume_surfaces}
    # The member's rows before this delta (its snapshot's containers are advanced in place below).
    prior_effects = ({identity: (before.spatial_effects.get(identity), perception.effect_cursors.get((observer, identity), -1))
                      for identity in event.spatial_effects_changed} if before is not None and not event.initial else {})
    prior_lights = ({identity: before.light_sources.get(identity) for identity in event.light_sources_changed}
                    if before is not None and not event.initial else {})

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
        touched = previous_positions | positions
        for position in touched:
            _membership(current.effects_at, position, identity, position in positions)
        for owner, senses in perception.members.items():
            if owner != observer and not any(cell_in(senses.visible, position) for position in touched):
                continue
            values = current.visible_effects.setdefault(owner, set())
            if any(cell_in(senses.visible, position) for position in positions):
                values.add(identity)
            else:
                values.discard(identity)
    active_effects = current.visible_effects.setdefault(observer, set())
    for identity in candidates:
        if any(cell_in(member.visible, position) for position in current.effect_positions.get(identity, ())):
            active_effects.add(identity)
        else:
            active_effects.discard(identity)
    if member.paths_dirty:
        current.dirty_members.add(observer)
    else:
        current.dirty_members.discard(observer)

    if current.view is None:
        current.view = replace(member, visible=EMPTY_CELLS, seen=EMPTY_CELLS, entities={}, objects={},
            effective_light_levels=EMPTY_VALUES, hazardous_cells=EMPTY_VALUES, spatial_effects={})
    _fold_view_cells(current, observer, before, member, cells, hazards_only=not (event.initial or added.width
        or removed.width or event.effective_light_levels_changed.cells.width))
    view = current.view
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
        if (identity in prior_effects and identity not in absence_changed
                and identity not in event.spatial_effects_removed
                and _keeps_composed_effect(current, observer, identity, event.spatial_effects_changed[identity],
                                           *prior_effects[identity])):
            continue
        effect = _current_effect(current, identity)
        if effect is None:
            view.spatial_effects.pop(identity, None)
        else:
            view.spatial_effects[identity] = effect
    view = replace(view, seen=mask_union(*(source.seen for source in perception.members.values()))
        if event.initial else mask_union(view.seen, event.seen_cells_added))
    anchor = perception.members.get(observer_uuid) or next(iter(perception.members.values()))
    # Only the sources this delta names can change their composed row.
    if event.initial:
        lights, removals = light_sources(perception)
    else:
        # A source the view already shows as this member's new row keeps its composed row.
        names = set(event.light_sources_removed) | {identity for identity, source in event.light_sources_changed.items()
            if not _keeps_composed_light(view, identity, source, prior_lights.get(identity))}
        lights, removals = (update_light_sources(perception, names, view.light_sources, view.light_source_removals)
                            if names else (view.light_sources, view.light_source_removals))
    current.view = replace(view, light_sources=lights, light_source_removals=removals,
        position=anchor.position, passive_perception=anchor.passive_perception,
        sense_modes_key=anchor.sense_modes_key, sense_modes=anchor.sense_modes,
        visual_access=anchor.visual_access, paths_dirty=bool(current.dirty_members))


def depart_contact(current: AudienceComposition, identity: UUID) -> None:
    """A witnessed terminal departure ends the view's contact; the next fold recomposes that identity."""
    if current.view is None:
        return
    current.view.entities.pop(identity, None)
    current.contact_overrides.add(identity)


@dataclass(frozen=True, slots=True)
class SeatAssignment:
    """Private assignment using existing authored roster/member addresses."""

    seat_id: str
    controlled: tuple[tuple[str, str], ...]
    observers: tuple[tuple[str, str], ...] | None = None
