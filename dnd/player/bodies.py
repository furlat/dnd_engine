"""The bodies family of the seat wire (EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §3.3-§3.5).

One conversion (`change_rows`) turns an event's actor change (E2's record) into its seat-independent rows, and
`change_views` those rows into what each of the two views (controller, observer) may see, once per event for every
seat; one table (`DISCLOSURE`) says who may see each row. `change_fact` is a seat's part: the view `actor_view`
gives it of each actor. A body or item entering a seat's view is sent whole by `entering_body` and
`entering_items`, its static parts (birth, item look and profile) only the first time.

Data and functions only: the records are frozen, the session fold is the caller's, the seat contributes its
audience, the bodies it holds (`born`), its composed view and what static content it was sent (`sent`, and
`pending`: its walk's own, not yet emitted).
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID

from pydantic import TypeAdapter

from dnd.actor_projection import actor_fact_owner
from dnd.core.condition_types import ConditionCategory
from dnd.core.events import Event
from dnd.core.item_types import ItemEffectPresentationState, ItemPresentationState
from dnd.player.audience import PlayerAudience
from dnd.player.facts import (ActorBirth, ActorChangeFact, ActorRows, BodyRecord, BodyState, ItemRecord,
    VisualLoadout)
from dnd.player.static_sent import StaticSent
from dnd.types.actor_facts import (ActorFactChange, ActorState, ChangeField, ChangeRow, ConditionFact,
    ConditionMember, ConditionRow, DispositionRow, DurationRow, GrantRow, InventoryRow, ItemEffectsRow, ItemStateRow,
    LayerRow, NumberRow, SizeRow, WeaponSetRow)
from dnd.types.item_parts import ItemLook, ItemProfile, ItemState, ItemStateChanges, VisualItem
from dnd.types.senses import SensesSnapshot


class Disclosure(StrEnum):
    """Who may see a change field of an actor."""

    CONTROLLER = "controller"  # the seat controls the actor
    OBSERVER = "observer"  # the seat perceives the actor at the event (its controller too)
    NOBODY = "nobody"  # the session and AI folds only: no row


DISCLOSURE: Mapping[ChangeField, Disclosure] = MappingProxyType({
    ChangeField.NORMAL_HP: Disclosure.OBSERVER,
    ChangeField.MAXIMUM_HP: Disclosure.OBSERVER,
    ChangeField.TEMPORARY_HP: Disclosure.OBSERVER,
    ChangeField.TEMPORARY_HP_GRANT: Disclosure.OBSERVER,
    ChangeField.ARMOR_CLASS: Disclosure.OBSERVER,
    ChangeField.RESOLVED_SIZE: Disclosure.OBSERVER,
    ChangeField.SPATIAL_DISPOSITION: Disclosure.OBSERVER,
    ChangeField.WEAPON_SET: Disclosure.OBSERVER,
    ChangeField.CONDITION: Disclosure.OBSERVER,
    ChangeField.LAYER: Disclosure.OBSERVER,
    # An item's rows are also gated by the item being shown to the view (`shown_items`).
    ChangeField.ITEM_EFFECTS: Disclosure.OBSERVER,
    ChangeField.CONDITION_DURATION: Disclosure.CONTROLLER,
    ChangeField.INVENTORY: Disclosure.CONTROLLER,
    ChangeField.ITEM_STATE: Disclosure.CONTROLLER,
    ChangeField.ITEM_EFFECT_DURATION: Disclosure.CONTROLLER,
    ChangeField.HEALING_BLOCKED: Disclosure.NOBODY,
    ChangeField.DAMAGE_AFFINITIES: Disclosure.NOBODY,
})


# The parts of an engine value a seat may hold.

def item_look(item: ItemPresentationState) -> ItemLook:
    return ItemLook(item_id=item.item_id, item_kind=item.item_kind, visual_item_name=item.visual_item_name,
        visual_variant_id=item.visual_variant_id, equipped_visual_policy=item.equipped_visual_policy,
        very_bright_radius_feet=item.very_bright_radius_feet, bright_radius_feet=item.bright_radius_feet,
        dim_radius_feet=item.dim_radius_feet)


def item_profile(item: ItemPresentationState) -> ItemProfile:
    return ItemProfile(name=item.name, description=item.description, rarity=item.rarity, weight=item.weight,
        value=item.value, tags=item.tags, is_pickable=item.is_pickable, is_equippable=item.is_equippable,
        is_usable=item.is_usable, is_targetable=item.is_targetable, door_mechanism=item.door_mechanism,
        door_swing=item.door_swing, stack_id=item.stack_id, damage_dice=item.damage_dice,
        damage_type=item.damage_type, weapon_properties=item.weapon_properties, armor_type=item.armor_type,
        armor_ac=item.armor_ac, shield_ac_bonus=item.shield_ac_bonus, max_charges=item.max_charges,
        max_stack=item.max_stack, is_consumable=item.is_consumable, map_char=item.map_char,
        include_in_senses_objects=item.include_in_senses_objects,
        include_in_adjacent_senses_objects=item.include_in_adjacent_senses_objects,
        include_in_available_object_actions=item.include_in_available_object_actions,
        maximum_hit_points=item.maximum_hit_points, concentration_capacity=item.concentration_capacity,
        boundary_structure=item.boundary_structure)


def item_state(item: ItemPresentationState) -> ItemState:
    return ItemState(stack_count=item.stack_count, charges=item.charges, integrity=item.integrity,
        destruction_outcome=item.destruction_outcome, remnant_state=item.remnant_state,
        current_hit_points=item.current_hit_points, concentration_slots=item.concentration_slots,
        construction_owner_uuid=item.construction_owner_uuid, construction_geometry=item.construction_geometry,
        construction_suppressions=item.construction_suppressions, known_to_creator=item.known_to_creator,
        supported_by_uuid=item.supported_by_uuid, contact_passage=item.contact_passage,
        surface_residues=item.surface_residues, linked_spatial_condition_uuid=item.linked_spatial_condition_uuid,
        is_open=item.is_open, is_engaged=item.is_engaged, blocks_movement=item.blocks_movement,
        blocks_optics=item.blocks_optics, blocks_propagation=item.blocks_propagation, is_lit=item.is_lit)


def _state_changes(before: ItemPresentationState, after: ItemPresentationState) -> ItemStateChanges:
    """The state fields an item's after-value changes against the copy its holder held before."""
    changes: ItemStateChanges = {}
    if before.stack_count != after.stack_count:
        changes["stack_count"] = after.stack_count
    if before.charges != after.charges:
        changes["charges"] = after.charges
    if before.integrity != after.integrity:
        changes["integrity"] = after.integrity
    if before.destruction_outcome != after.destruction_outcome:
        changes["destruction_outcome"] = after.destruction_outcome
    if before.remnant_state != after.remnant_state:
        changes["remnant_state"] = after.remnant_state
    if before.current_hit_points != after.current_hit_points:
        changes["current_hit_points"] = after.current_hit_points
    if before.concentration_slots != after.concentration_slots:
        changes["concentration_slots"] = after.concentration_slots
    if before.construction_owner_uuid != after.construction_owner_uuid:
        changes["construction_owner_uuid"] = after.construction_owner_uuid
    if before.construction_geometry != after.construction_geometry:
        changes["construction_geometry"] = after.construction_geometry
    if before.construction_suppressions != after.construction_suppressions:
        changes["construction_suppressions"] = after.construction_suppressions
    if before.known_to_creator != after.known_to_creator:
        changes["known_to_creator"] = after.known_to_creator
    if before.supported_by_uuid != after.supported_by_uuid:
        changes["supported_by_uuid"] = after.supported_by_uuid
    if before.contact_passage != after.contact_passage:
        changes["contact_passage"] = after.contact_passage
    if before.surface_residues != after.surface_residues:
        changes["surface_residues"] = after.surface_residues
    if before.linked_spatial_condition_uuid != after.linked_spatial_condition_uuid:
        changes["linked_spatial_condition_uuid"] = after.linked_spatial_condition_uuid
    if before.is_open != after.is_open:
        changes["is_open"] = after.is_open
    if before.is_engaged != after.is_engaged:
        changes["is_engaged"] = after.is_engaged
    if before.blocks_movement != after.blocks_movement:
        changes["blocks_movement"] = after.blocks_movement
    if before.blocks_optics != after.blocks_optics:
        changes["blocks_optics"] = after.blocks_optics
    if before.blocks_propagation != after.blocks_propagation:
        changes["blocks_propagation"] = after.blocks_propagation
    if before.is_lit != after.is_lit:
        changes["is_lit"] = after.is_lit
    return changes


def condition_member(fact: ConditionFact) -> ConditionMember:
    """A held condition's membership: its identity and committed state, without its event's change payload."""
    return ConditionMember(condition_uuid=fact.condition_uuid, name=fact.name, category=fact.category,
        behavior_id=fact.behavior_id, state=fact.state)


def _without_duration(member: ConditionMember) -> ConditionMember:
    """A membership as an observer holds it: its state without the duration."""
    if member.state is None or member.state.duration is None:
        return member
    return replace(member, state=member.state.model_copy(update={"duration": None}))


LOADOUT = TypeAdapter(VisualLoadout)


def loadout_id(loadout: VisualLoadout) -> str:
    """A visual loadout's content id: a digest of its canonical encoding."""
    return sha256(LOADOUT.dump_json(loadout)).hexdigest()[:16]


def visual_loadout(actor: ActorState) -> VisualLoadout:
    items = {item.item_uuid: item for item in actor.items}
    return VisualLoadout(active_weapon_set=actor.active_weapon_set, layers=tuple(
        VisualItem(slot=slot, item_uuid=identity, item_id=items[identity].item_id, is_lit=items[identity].is_lit)
        for slot, identity in actor.equipment))


def _layer(item: ItemPresentationState, slot: str) -> VisualItem:
    return VisualItem(slot=slot, item_uuid=item.item_uuid, item_id=item.item_id, is_lit=item.is_lit)


def _effect_rows(item_uuid: UUID, before: tuple[ItemEffectPresentationState, ...],
                 after: tuple[ItemEffectPresentationState, ...]) -> tuple[ChangeRow, ...]:
    """An item's effects against its holder's copy: their durations alone, else the effects whole."""
    if before == after:
        return ()
    if tuple(effect.model_copy(update={"duration": None}) for effect in before) == tuple(
            effect.model_copy(update={"duration": None}) for effect in after):
        return tuple(DurationRow(field=ChangeField.ITEM_EFFECT_DURATION, key=effect.effect_uuid, item_uuid=item_uuid,
            duration=effect.duration) for held, effect in zip(before, after, strict=True) if held != effect)
    return (ItemEffectsRow(item_uuid=item_uuid, effects=after),)


def _item_rows(held: ActorState, before: ItemPresentationState, after: ItemPresentationState, *,
               layers: bool) -> list[ChangeRow]:
    """A held item's after-value against the copy its holder held: its state fields, its effects and, with
    `layers`, the layers it is worn in when its light changed."""
    rows: list[ChangeRow] = []
    if changes := _state_changes(before, after):
        rows.append(ItemStateRow(item_uuid=after.item_uuid, changes=changes))
    rows.extend(_effect_rows(after.item_uuid, before.item_effects, after.item_effects))
    if layers and before.is_lit != after.is_lit:
        rows.extend(LayerRow(slot=slot, layer=_layer(after, slot))
                    for slot, worn in held.equipment if worn == after.item_uuid)
    return rows


def _released_rows(held: ActorState, item_uuid: UUID) -> list[ChangeRow]:
    """An item leaving a holder: its inventory entry and each layer it is worn in."""
    if not any(item.item_uuid == item_uuid for item in held.items):
        return []
    return [InventoryRow(item_uuid=item_uuid, held=False),
            *(LayerRow(slot=slot) for slot, worn in held.equipment if worn == item_uuid)]


def _member_rows(held: ActorState, change: ActorFactChange, consumed: bool) -> list[ChangeRow]:
    """The owner's memberships set and removed, keyed against those it held: a change of duration alone is
    its duration. INTERNAL memberships are never held (the presented fold), so they have no rows."""
    members = {member.condition_uuid: member for member in held.conditions}
    rows: list[ChangeRow] = []
    for identity in change.conditions_removed:
        if identity in members:
            rows.append(ConditionRow(condition_uuid=identity, consumed=consumed))
    for fact in change.conditions_set:
        if fact.category is ConditionCategory.INTERNAL:
            continue
        member = condition_member(fact)
        previous = members.get(fact.condition_uuid)
        if (previous is not None and previous.state is not None and member.state is not None
                and _without_duration(condition_member(previous)) == _without_duration(member)):
            if previous.state.duration != member.state.duration:
                rows.append(DurationRow(field=ChangeField.CONDITION_DURATION, key=fact.condition_uuid,
                    duration=member.state.duration))
            continue
        rows.append(ConditionRow(condition_uuid=fact.condition_uuid, member=member))
    return rows


def change_rows(change: ActorFactChange, actors: Mapping[UUID, ActorState], *, consumed: bool = False
                ) -> tuple[ActorRows, ...]:
    """An event's actor change as rows: each actor's, seat-independent and in the order E2's fold applies them.

    `actors` is the session fold before the event. Only the fields the record names are read, each against the
    session fold's value of that same field: a scalar becomes a row when its after-value differs from it; the
    memberships, holdings and item operations are keyed against it. The engine-only scalars (`DISCLOSURE` NOBODY) have no row, and the
    ones the event's own presentation fact carries (faction, life state, remains, occupancy) none either.
    `consumed` tells how an ended membership ended (its event's presentation; the record names only its key).
    """
    result: list[ActorRows] = []
    owner = actors.get(change.owner_uuid) if change.owner_uuid is not None else None
    if (released := change.released_by_others) is not None:
        for identity, held in actors.items():
            if identity != change.owner_uuid and (left := _released_rows(held, released)):
                result.append(ActorRows(actor_uuid=identity, rows=tuple(left)))
    if owner is not None:
        rows: list[ChangeRow] = []
        values = change.values
        if "normal_hp" in values and values["normal_hp"] != owner.normal_hp:
            rows.append(NumberRow(field=ChangeField.NORMAL_HP, value=values["normal_hp"]))
        if "maximum_hp" in values and values["maximum_hp"] != owner.maximum_hp:
            rows.append(NumberRow(field=ChangeField.MAXIMUM_HP, value=values["maximum_hp"]))
        if "temporary_hp" in values and values["temporary_hp"] != owner.temporary_hp:
            rows.append(NumberRow(field=ChangeField.TEMPORARY_HP, value=values["temporary_hp"]))
        if "temporary_hp_grant" in values and values["temporary_hp_grant"] != owner.temporary_hp_grant:
            rows.append(GrantRow(value=values["temporary_hp_grant"]))
        if "armor_class" in values and values["armor_class"] != owner.armor_class:
            rows.append(NumberRow(field=ChangeField.ARMOR_CLASS, value=values["armor_class"]))
        if "resolved_size" in values and values["resolved_size"] != owner.resolved_size:
            rows.append(SizeRow(value=values["resolved_size"]))
        if "spatial_disposition" in values and values["spatial_disposition"] != owner.spatial_disposition:
            rows.append(DispositionRow(value=values["spatial_disposition"]))
        if "active_weapon_set" in values and values["active_weapon_set"] != owner.active_weapon_set:
            rows.append(WeaponSetRow(value=values["active_weapon_set"]))
        rows.extend(_member_rows(owner, change, consumed))
        if (identity := change.released_by_owner) is not None:
            rows.extend(_released_rows(owner, identity))
        if (used := change.used_item) is not None:
            copy = next((item for item in owner.items if item.item_uuid == used.item_uuid), None)
            if used.destroyed:
                rows.extend(_released_rows(owner, used.item_uuid))
            elif copy is not None:
                rows.extend(_item_rows(owner, copy, copy.model_copy(update={
                    "charges": used.charges, "stack_count": used.stack_count}), layers=True))
        if (placed := change.held_item) is not None:
            item = placed.item
            copy = next((row for row in owner.items if row.item_uuid == item.item_uuid), None)
            if copy is None:
                rows.append(InventoryRow(item_uuid=item.item_uuid, held=True))
            else:
                rows.extend(_item_rows(owner, copy, item, layers=False))
            # The item leaves every slot it was worn in, then takes its own (a dict's assignment order).
            rows.extend(LayerRow(slot=slot) for slot, worn in owner.equipment if worn == item.item_uuid)
            if placed.slot is not None:
                rows.append(LayerRow(slot=placed.slot, layer=_layer(item, placed.slot)))
        if rows:
            result.append(ActorRows(actor_uuid=owner.uuid, rows=tuple(rows)))
    if (replaced := change.replaced_item) is not None:
        for identity, held in actors.items():
            copy = next((item for item in held.items if item.item_uuid == replaced.item_uuid), None)
            if copy is not None and (copied := _item_rows(held, copy, replaced, layers=True)):
                result.append(ActorRows(actor_uuid=identity, rows=tuple(copied)))
    return tuple(result)


# Both views, once per event.

@dataclass(frozen=True, slots=True)
class ViewedChange:
    """One actor's rows at an event as one view may see them, and the items the event brings into that view."""

    rows: ActorRows | None
    entering: tuple[ItemPresentationState, ...]


@dataclass(frozen=True, slots=True)
class ActorChangeViews:
    """An actor's change at an event in both views, built once per event; each seat picks one (`actor_view`)."""

    actor_uuid: UUID
    controller: ViewedChange
    observer: ViewedChange


class View(StrEnum):
    """A seat's view of one actor at an event."""

    CONTROLLER = "controller"
    OBSERVER = "observer"


def shown_items(actor: ActorState, view: View) -> tuple[UUID, ...]:
    """The items a body shows a seat: its controller's whole inventory, anyone else's equipped layers."""
    if view is View.CONTROLLER:
        return tuple(item.item_uuid for item in actor.items)
    return tuple(dict.fromkeys(identity for _, identity in actor.equipment))


def _row_item(row: ChangeRow) -> UUID | None:
    match row:
        case ItemEffectsRow() | ItemStateRow():
            return row.item_uuid
        case DurationRow(field=ChangeField.ITEM_EFFECT_DURATION):
            return row.item_uuid
    return None


def _shown_effects(effects: tuple[ItemEffectPresentationState, ...], view: View
                   ) -> tuple[ItemEffectPresentationState, ...]:
    if view is View.CONTROLLER:
        return effects
    return tuple(effect.model_copy(update={"duration": None}) if effect.duration is not None else effect
                 for effect in effects)


def _observed_row(row: ChangeRow) -> ChangeRow:
    """A row as an observer sees it: membership and effect values without their durations."""
    match row:
        case ConditionRow(member=ConditionMember() as member):
            return replace(row, member=_without_duration(member))
        case ItemEffectsRow():
            return replace(row, effects=_shown_effects(row.effects, View.OBSERVER))
    return row


def _viewed(change: ActorRows, before: ActorState, after: ActorState | None, view: View) -> ViewedChange:
    """The rows `DISCLOSURE` and the item gate give a view (an item row needs its item shown before or after the
    event), and the items shown after the event but not before."""
    shown_before = shown_items(before, view)
    shown = {*shown_before, *(shown_items(after, view) if after is not None else ())}
    rows = tuple(row if view is View.CONTROLLER else _observed_row(row) for row in change.rows
        if (DISCLOSURE[row.field] is Disclosure.OBSERVER
            or DISCLOSURE[row.field] is Disclosure.CONTROLLER and view is View.CONTROLLER)
        and ((item := _row_item(row)) is None or item in shown))
    entering: tuple[ItemPresentationState, ...] = ()
    if after is not None:
        items = {item.item_uuid: item for item in after.items}
        entering = tuple(items[identity] for identity in shown_items(after, view) if identity not in shown_before)
    return ViewedChange(ActorRows(actor_uuid=change.actor_uuid, rows=rows) if rows else None, entering)


def change_views(rows: tuple[ActorRows, ...], before: Mapping[UUID, ActorState],
                 after: Mapping[UUID, ActorState]) -> tuple[ActorChangeViews, ...]:
    """An event's rows in both views (`before`, `after`: the session values of the actors they name; an actor
    whose lifetime the event ended has no after-value)."""
    return tuple(ActorChangeViews(actor_uuid=change.actor_uuid,
        controller=_viewed(change, before[change.actor_uuid], after.get(change.actor_uuid), View.CONTROLLER),
        observer=_viewed(change, before[change.actor_uuid], after.get(change.actor_uuid), View.OBSERVER))
        for change in rows)


# A seat's part.

def actor_view(event: Event, actor_uuid: UUID, audience: PlayerAudience, born: Collection[UUID],
               senses: SensesSnapshot | None) -> View | None:
    """The seat's view of an actor an event changes: its controller's; an observer's if the seat holds its body and
    perceives it at the event (the owner by the event's identity grant, another holder by a visual contact)."""
    if audience.controls(actor_uuid):
        return View.CONTROLLER
    if actor_uuid not in born:
        return None
    if actor_uuid == actor_fact_owner(event):
        return View.OBSERVER if audience.granted(event.identified_entity_observer_uuids.get(str(actor_uuid), set())) else None
    contact = senses.entities.get(actor_uuid) if senses is not None else None
    return View.OBSERVER if contact is not None and contact.visual else None


def item_record(item: ItemPresentationState, view: View, *, sent: StaticSent, pending: StaticSent) -> ItemRecord:
    """An item entering a seat's view: its look and (its controller's) profile if not yet sent, its dynamic parts."""
    controlled = view is View.CONTROLLER
    identity = item.item_uuid
    return ItemRecord(item_uuid=identity,
        look=item_look(item) if identity not in sent.item_looks and identity not in pending.item_looks else None,
        profile=item_profile(item) if controlled and identity not in sent.item_profiles
            and identity not in pending.item_profiles else None,
        state=item_state(item) if controlled else None, effects=_shown_effects(item.item_effects, view))


def _carries(record: ItemRecord) -> bool:
    return (record.look is not None or record.profile is not None or record.state is not None
            or bool(record.effects))


def entering_items(actor: ActorState, view: View, *, sent: StaticSent, pending: StaticSent
                   ) -> tuple[ItemRecord, ...]:
    """The records of the items a body shows a seat, except those carrying nothing (their look sent, no state
    and no effects): the client derives those from the body (a shown item without a record has no effects)."""
    items = {item.item_uuid: item for item in actor.items}
    return tuple(record for identity in shown_items(actor, view)
                 if _carries(record := item_record(items[identity], view, sent=sent, pending=pending)))


def change_fact(event: Event, views: tuple[ActorChangeViews, ...], audience: PlayerAudience, born: Collection[UUID],
                senses: SensesSnapshot | None, *, sent: StaticSent, pending: StaticSent) -> ActorChangeFact | None:
    """A seat's part of an event's rows: each actor it views, in the view it has, and the records of the items the
    event brings into that view; None when nothing is disclosed."""
    actors: list[ActorRows] = []
    records: list[ItemRecord] = []
    for change in views:
        view = actor_view(event, change.actor_uuid, audience, born, senses)
        if view is None:
            continue
        viewed = change.controller if view is View.CONTROLLER else change.observer
        records.extend(item_record(item, view, sent=sent, pending=pending) for item in viewed.entering)
        if viewed.rows is not None:
            actors.append(viewed.rows)
    if not actors and not records:
        return None
    return ActorChangeFact(actors=tuple(actors), items=tuple(records))


def entering_body(occurrence: int, actor: ActorState, audience: PlayerAudience, *, visual: bool, birth: bool,
                  sent: StaticSent, pending: StaticSent, loadout_ids: dict[VisualLoadout, str]) -> BodyRecord:
    """A body entering a seat's view, whole: every changeable field, its birth if the seat has none, its visual
    loadout by content id (its value if the seat has none of that id), the records of the items it shows.
    Occupancy is disclosed to its controller or a visual contact; INTERNAL memberships are never held.
    `loadout_ids` is the session's memo of content ids by value: each value is digested once."""
    view = View.CONTROLLER if audience.controls(actor.uuid) else View.OBSERVER
    controlled = view is View.CONTROLLER
    conditions = tuple(condition_member(fact) if controlled else _without_duration(condition_member(fact))
                       for fact in actor.conditions if fact.category is not ConditionCategory.INTERNAL)
    loadout = visual_loadout(actor)
    identity = loadout_ids.get(loadout)
    if identity is None:
        identity = loadout_ids[loadout] = loadout_id(loadout)
    body = BodyState(visual_loadout_id=identity, normal_hp=actor.normal_hp, maximum_hp=actor.maximum_hp,
        temporary_hp=actor.temporary_hp, life_state=actor.life_state, armor_class=actor.armor_class,
        temporary_hp_grant=actor.temporary_hp_grant, conditions=conditions,
        controlled_items=tuple(item.item_uuid for item in actor.items) if controlled else None,
        occupancy_layer=actor.occupancy_layer if controlled or visual else None,
        resolved_size=actor.resolved_size, faction=actor.faction, remains_disposition=actor.remains_disposition,
        spatial_disposition=actor.spatial_disposition)
    return BodyRecord(occurrence=occurrence, actor_uuid=actor.uuid,
        birth=ActorBirth(name=actor.name, character_body_id=actor.character_body_id,
            creature_content_ref=actor.creature_content_ref, appearance=actor.appearance,
            structural_base_size=actor.structural_base_size,
            manifestation=actor.summon_origin.manifestation if actor.summon_origin is not None else None)
            if birth else None,
        body=body, loadout=loadout if identity not in sent.visual_loadouts and identity not in pending.visual_loadouts
            else None,
        items=entering_items(actor, view, sent=sent, pending=pending))
