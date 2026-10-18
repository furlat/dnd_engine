"""Player control and recorded sensory evidence, independent of turn ownership.

This module never queries native owners. The display view is composed from
complete recorded observations; it grants no actor additional senses or actions.
"""

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from uuid import UUID

import numpy as np

from dnd.core.cells import Box, cell_layers, mask_box, mask_union, pack_layers, pack_mask, pack_values, union_box
from dnd.core.sensory_fold import apply_current_senses, prepare_sensory_delta
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

    def granted(self, observers: Collection[str]) -> bool:
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
    """Each member's own snapshot: what it perceives now (native perception, its retained effect rows included).

    The seat's composed view is a function of these snapshots alone (`composed_view`); no sighting order or
    remembered footprint enters it (plan §3.2).
    """

    members: dict[UUID, SensesSnapshot] = field(default_factory=dict)


def perceived_entities(audience: PlayerAudience, senses: SensesSnapshot | None) -> frozenset[UUID]:
    """The entities a seat perceives now: its controlled actors and its composed view's entity contacts (every
    member's)."""
    return frozenset(audience.controlled).union(senses.entities if senses is not None else ())


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


def _visible_part(row: PerceivedSpatialEffect, senses: SensesSnapshot) -> PerceivedSpatialEffect | None:
    """A member's effect row as the member perceives it now (plan §3.2): its cells the member sees and its seen
    volume cells; None when nothing of it is perceived."""
    volume = row.visible_volume_positions
    positions = tuple(position for position in row.positions
                      if cell_in(senses.visible, position) or position in volume)
    if not positions and not row.upper_volume_surfaces:
        return None
    return row if len(positions) == len(row.positions) else row.model_copy(update={"positions": positions})


def _composed_effect(perception: AudiencePerception, identity: UUID, holders: Iterable[UUID]
                     ) -> "ComposedEffect | None":
    """An effect as the seat perceives it, and the members perceiving it: the members' visible parts joined,
    led by the newest revision (ties: the smaller member uuid)."""
    parts = {}
    for member in holders:
        senses = perception.members[member]
        row = senses.spatial_effects.get(identity)
        if row is not None and (part := _visible_part(row, senses)) is not None:
            parts[member] = part
    if not parts:
        return None
    newest = max(parts, key=lambda member: (parts[member].owner_revision if parts[member].owner_revision is not None
                                            else -1, -member.int))
    joined = _join_effects(parts[newest], (parts[member] for member in sorted(parts, key=lambda value: value.int)))
    return ComposedEffect(joined, frozenset(parts))


def _composed_contact(perception: AudiencePerception, identity: UUID, holders: Iterable[UUID], *,
                      objects: bool) -> "ComposedContact | None":
    """A contact as the seat perceives it, and the members holding it: a visual holder's first, then the smaller
    member uuid's."""
    rows = {member: contact for member in holders if (contact := (perception.members[member].objects if objects
            else perception.members[member].entities).get(identity)) is not None}
    if not rows:
        return None
    holder = max(rows, key=lambda member: (rows[member].visual, -member.int))
    return ComposedContact(rows[holder], frozenset(rows))


def _merged_light(rows: list[PerceivedLightSource]) -> PerceivedLightSource:
    """The first member's row with the first anchors any member discloses."""
    first = rows[0]
    if len(rows) == 1:
        return first
    entity = next((row.anchor_entity_uuid for row in rows if row.anchor_entity_uuid), None)
    item = next((row.anchor_item_uuid for row in rows if row.anchor_item_uuid), None)
    if entity == first.anchor_entity_uuid and item == first.anchor_item_uuid:
        return first
    return first.model_copy(update={"anchor_entity_uuid": entity, "anchor_item_uuid": item})


def _holders(perception: AudiencePerception) -> tuple[dict[UUID, set[UUID]], dict[UUID, set[UUID]], dict[UUID, set[UUID]]]:
    """Which members hold each entity contact, object contact and effect row."""
    entities: dict[UUID, set[UUID]] = {}
    objects: dict[UUID, set[UUID]] = {}
    effects: dict[UUID, set[UUID]] = {}
    for member, senses in perception.members.items():
        for identity in senses.entities:
            entities.setdefault(identity, set()).add(member)
        for identity in senses.objects:
            objects.setdefault(identity, set()).add(member)
        for identity in senses.spatial_effects:
            effects.setdefault(identity, set()).add(member)
    return entities, objects, effects


def composed_view(perception: AudiencePerception, observer_uuid: UUID) -> SensesSnapshot | None:
    """The seat's composed view of its members' snapshots (plan §3.1, §3.2), a function of those snapshots alone.

    Each visible cell shows the observation of the member seeing it in the brightest light (ties: the smaller
    uuid); each contact, its visual holder's (ties: the smaller uuid); each effect, its members' visible parts
    (`_composed_effect`); each light source, its newest rows. The seen cells are every member's; the scalar
    capabilities stay the stream observer's (the first member's before it perceives). It grants no actor
    additional senses or actions. `apply_settlement` keeps it incrementally.
    """
    if not perception.members:
        return None
    members = perception.members
    anchor = members.get(observer_uuid) or next(iter(members.values()))
    visible, light, hazards = _composed_view_cells(perception)
    entity_holders, object_holders, effect_holders = _holders(perception)
    entities = {identity: composed.contact for identity, owners in entity_holders.items()
                if (composed := _composed_contact(perception, identity, owners, objects=False)) is not None}
    objects = {identity: composed.contact for identity, owners in object_holders.items()
               if (composed := _composed_contact(perception, identity, owners, objects=True)) is not None}
    effects = {identity: composed.effect for identity, owners in effect_holders.items()
               if (composed := _composed_effect(perception, identity, owners)) is not None}
    names = {identity for senses in members.values() for identity in (*senses.light_sources, *senses.light_source_removals)}
    lights, removals = update_light_sources(perception, names, {}, {})
    return replace(anchor, light_sources=lights, light_source_removals=removals, visible=visible,
        seen=mask_union(*(senses.seen for senses in members.values())), entities=entities, objects=objects,
        effective_light_levels=light, hazardous_cells=hazards, spatial_effects=effects,
        paths_dirty=any(senses.paths_dirty for senses in members.values()))


@dataclass(slots=True)
class AudienceComposition:
    """One seat's composition: its members' snapshots, the composed view and the indexes that keep it."""

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
    # The members holding each entity contact, object contact and effect row.
    entity_members: dict[UUID, set[UUID]] = field(default_factory=dict)
    object_members: dict[UUID, set[UUID]] = field(default_factory=dict)
    effect_members: dict[UUID, set[UUID]] = field(default_factory=dict)
    dirty_members: set[UUID] = field(default_factory=set)


def _membership(index: dict, key, identity: UUID, present: bool) -> None:
    if present:
        index.setdefault(key, set()).add(identity)
    elif (members := index.get(key)) is not None:
        members.discard(identity)
        if not members:
            del index[key]


@dataclass(frozen=True, slots=True)
class ComposedContact:
    """A contact as the seat perceives it, and the members holding it."""

    contact: PerceivedContact
    members: frozenset[UUID]


@dataclass(frozen=True, slots=True)
class ComposedEffect:
    """An effect as the seat perceives it (its visible part, with its native duration and revision), and the
    members perceiving it."""

    effect: PerceivedSpatialEffect
    members: frozenset[UUID]


Position = tuple[int, int]


@dataclass(frozen=True, slots=True)
class ComposedChange:
    """One settlement's change of a seat's composed view: the composed before and after of every record it
    changed (None: absent), the cells, and which anchor scalars changed. Built from `apply_settlement`'s locals.

    `retired` are the cells that left a member's own effect row in the settlement: that member saw the effect
    leave them (a row loses a cell only when its member observes the cell again).
    """

    initial: bool
    visible_added: CellMask
    visible_removed: CellMask
    light_changed: CellValues
    hazards_changed: CellValues
    entities: Mapping[UUID, tuple[ComposedContact | None, ComposedContact | None]]
    objects: Mapping[UUID, tuple[ComposedContact | None, ComposedContact | None]]
    effects: Mapping[UUID, tuple[ComposedEffect | None, ComposedEffect | None]]
    retired: Mapping[UUID, frozenset[Position]]
    lights: Mapping[UUID, tuple[PerceivedLightSource | None, PerceivedLightSource | None]]
    position_changed: bool
    passive_perception_changed: bool
    sense_modes_changed: bool
    visual_access_changed: bool
    paths_dirty: bool


def _cells_change(before: SensesSnapshot | None, after: SensesSnapshot
                  ) -> tuple[CellMask, CellMask, CellValues, CellValues]:
    """The composed cells added and removed, and the light and hazard after-values where a cell was added or its
    value changed."""
    if (before is not None and before.visible is after.visible and before.effective_light_levels
            is after.effective_light_levels and before.hazardous_cells is after.hazardous_cells):
        return EMPTY_CELLS, EMPTY_CELLS, EMPTY_VALUES, EMPTY_VALUES
    held = before.visible if before is not None else EMPTY_CELLS
    box = union_box(mask_box(held), mask_box(after.visible))
    if box is None:
        return EMPTY_CELLS, EMPTY_CELLS, EMPTY_VALUES, EMPTY_VALUES
    if before is not None:
        old, (old_light, old_hazard) = cell_layers(held, (before.effective_light_levels, before.hazardous_cells), box)
    else:
        old, (old_light, old_hazard) = cell_layers(EMPTY_CELLS, (EMPTY_VALUES, EMPTY_VALUES), box)
    new, (new_light, new_hazard) = cell_layers(after.visible, (after.effective_light_levels, after.hazardous_cells), box)
    return (pack_mask(box[0], box[1], new & ~old), pack_mask(box[0], box[1], old & ~new),
            pack_values(box[0], box[1], new & (~old | (old_light != new_light)), new_light),
            pack_values(box[0], box[1], new & (~old | (old_hazard != new_hazard)), new_hazard))


def apply_settlement(current: AudienceComposition, audience: PlayerAudience, observer_uuid: UUID,
                     events: Sequence[SensoryDelta]) -> ComposedChange:
    """Fold one settlement's member observations (`events`, in order) into an exclusively owned composition and
    return the change of the composed view (plan §3.1): one composition per settlement, never member by member.

    Each member's snapshot advances by the shared native reducer and its cell layer over the cells it changed;
    the records its observation names (and its effect rows on cells its sight changed) are composed again once,
    from the members' snapshots after the settlement, so the view always equals `composed_view`.
    """
    perception = current.perception
    before_view = current.view
    entity_names: dict[UUID, ComposedContact | None] = {}
    object_names: dict[UUID, ComposedContact | None] = {}
    effect_names: dict[UUID, ComposedEffect | None] = {}
    light_names: set[UUID] = set()
    retired: dict[UUID, set[Position]] = {}
    initial = any(event.initial for event in events)
    seen_added = []
    for event in events:
        if not audience.observes(event.observer_uuid):
            raise ValueError("Sensory observation does not belong to this audience")
        observer = event.observer_uuid
        before = perception.members.get(observer)
        prepared = prepare_sensory_delta(observer, before, event)
        added, removed = event.visible_cells_added, event.visible_cells_removed
        # The box of the cells this observation can change for its own member, and so in the view.
        cells = union_box(mask_box(added), mask_box(removed), mask_box(event.effective_light_levels_changed.cells),
            mask_box(event.hazardous_cells_changed.cells),
            mask_box(before.visible) if event.initial and before is not None else None)
        entities = {*event.entity_contacts_changed, *event.entity_contacts_removed}
        objects = {*event.object_contacts_changed, *event.object_contacts_removed}
        effects = {*event.spatial_effects_changed, *event.spatial_effects_removed}
        if before is not None:
            if event.initial:
                entities.update(before.entities)
                objects.update(before.objects)
                effects.update(before.spatial_effects)
            elif added.width or removed.width:
                # A member's changed sight changes its rows' visible parts on those cells.
                sight = mask_union(added, removed)
                effects.update(identity for identity, row in before.spatial_effects.items()
                               if any(cell_in(sight, position) for position in row.positions))
        # Each record's composed value before the settlement, taken when it is first named (only members naming
        # a record change its inputs).
        for identity in entities - entity_names.keys():
            entity_names[identity] = _composed_contact(perception, identity,
                current.entity_members.get(identity, ()), objects=False)
        for identity in objects - object_names.keys():
            object_names[identity] = _composed_contact(perception, identity,
                current.object_members.get(identity, ()), objects=True)
        for identity in effects - effect_names.keys():
            effect_names[identity] = _composed_effect(perception, identity, current.effect_members.get(identity, ()))
        prior = {identity: before.spatial_effects.get(identity) for identity in effects} if before is not None else {}

        member = apply_current_senses(before, event, prepared)
        perception.members[observer] = member
        for identity in entities:
            _membership(current.entity_members, identity, observer, identity in member.entities)
        for identity in objects:
            _membership(current.object_members, identity, observer, identity in member.objects)
        for identity in effects:
            _membership(current.effect_members, identity, observer, identity in member.spatial_effects)
            row = prior.get(identity)
            if row is not None:
                now = member.spatial_effects.get(identity)
                gone = set(row.positions).difference(now.positions if now is not None else ())
                if gone:
                    retired.setdefault(identity, set()).update(gone)
        light_names.update(event.light_sources_changed, event.light_sources_removed)
        seen_added.append(event.seen_cells_added)
        if member.paths_dirty:
            current.dirty_members.add(observer)
        else:
            current.dirty_members.discard(observer)
        if current.view is None:
            current.view = replace(member, visible=EMPTY_CELLS, seen=EMPTY_CELLS, entities={}, objects={},
                effective_light_levels=EMPTY_VALUES, hazardous_cells=EMPTY_VALUES, spatial_effects={},
                light_sources={}, light_source_removals={})
        _fold_view_cells(current, observer, before, member, cells, hazards_only=not (event.initial or added.width
            or removed.width or event.effective_light_levels_changed.cells.width))

    view = current.view
    assert view is not None
    entities_after, objects_after, effects_after = dict(view.entities), dict(view.objects), dict(view.spatial_effects)
    entity_changes: dict[UUID, tuple[ComposedContact | None, ComposedContact | None]] = {}
    object_changes: dict[UUID, tuple[ComposedContact | None, ComposedContact | None]] = {}
    effect_changes: dict[UUID, tuple[ComposedEffect | None, ComposedEffect | None]] = {}
    for names, index, destination, changes, objects_kind in (
            (entity_names, current.entity_members, entities_after, entity_changes, False),
            (object_names, current.object_members, objects_after, object_changes, True)):
        for identity in sorted(names, key=str):
            after = _composed_contact(perception, identity, index.get(identity, ()), objects=objects_kind)
            if after is None:
                destination.pop(identity, None)
            else:
                destination[identity] = after.contact
            if after != names[identity]:
                changes[identity] = names[identity], after
    for identity in sorted(effect_names, key=str):
        after_effect = _composed_effect(perception, identity, current.effect_members.get(identity, ()))
        if after_effect is None:
            effects_after.pop(identity, None)
        else:
            effects_after[identity] = after_effect.effect
        if after_effect != effect_names[identity]:
            effect_changes[identity] = effect_names[identity], after_effect
    if initial:
        light_names.update(identity for senses in perception.members.values()
                           for identity in (*senses.light_sources, *senses.light_source_removals))
        light_names.update(view.light_sources)
    lights, removals = (update_light_sources(perception, light_names, view.light_sources, view.light_source_removals)
                        if light_names else (view.light_sources, view.light_source_removals))
    light_changes = {identity: (held, lights.get(identity)) for identity in sorted(light_names, key=str)
                     if (held := view.light_sources.get(identity)) != lights.get(identity)}
    anchor = perception.members.get(observer_uuid) or next(iter(perception.members.values()))
    current.view = replace(view, entities=entities_after, objects=objects_after, spatial_effects=effects_after,
        light_sources=lights, light_source_removals=removals,
        seen=(mask_union(*(senses.seen for senses in perception.members.values())) if initial
              else mask_union(view.seen, *seen_added)),
        position=anchor.position, passive_perception=anchor.passive_perception,
        sense_modes_key=anchor.sense_modes_key, sense_modes=anchor.sense_modes,
        visual_access=anchor.visual_access, paths_dirty=bool(current.dirty_members))
    after_view = current.view
    added_cells, removed_cells, light_values, hazard_values = _cells_change(before_view, after_view)
    entered = before_view is None
    return ComposedChange(initial=entered, visible_added=added_cells, visible_removed=removed_cells,
        light_changed=light_values, hazards_changed=hazard_values,
        entities=entity_changes, objects=object_changes, effects=effect_changes,
        retired={identity: frozenset(cells) for identity, cells in retired.items()}, lights=light_changes,
        position_changed=entered or before_view.position != after_view.position,
        passive_perception_changed=entered or before_view.passive_perception != after_view.passive_perception,
        sense_modes_changed=entered or before_view.sense_modes_key != after_view.sense_modes_key,
        visual_access_changed=entered or before_view.visual_access != after_view.visual_access,
        paths_dirty=any(event.paths_dirty for event in events))


def depart_contact(current: AudienceComposition, identity: UUID) -> None:
    """A witnessed terminal departure ends the entity's contact for every member and in the view: the departed
    entity is no member's contact (as the capture fold's terminal release), so no composition shows it again."""
    for senses in current.perception.members.values():
        senses.entities.pop(identity, None)
    current.entity_members.pop(identity, None)
    if current.view is not None:
        current.view.entities.pop(identity, None)



@dataclass(frozen=True, slots=True)
class SeatAssignment:
    """Private assignment using existing authored roster/member addresses."""

    seat_id: str
    controlled: tuple[tuple[str, str], ...]
    observers: tuple[tuple[str, str], ...] | None = None
