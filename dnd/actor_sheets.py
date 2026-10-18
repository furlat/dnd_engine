"""The engine's one player sheet publisher.

A sheet's groups (`ActorSheetState`) are computed when read and change with no write to the actor
(a frightener in sight, an aura's provider, an item's equip state), so they are evaluated at the
operation boundary and compared, group by group, with what the actor's last sheet event established.
Each actor whose groups changed gets one `ActorSheetEvent` carrying only the changed groups; an
actor's first publication carries all of them.

The publisher's one kept value is `PublishedSheets`: per actor, the sheet its last sheet event
established, named by that event. It is replaced at the actor's next publication, lives as long as
the session holding it, and is refused in another event generation or when its event is not stored.
"""

from dataclasses import dataclass, field
from uuid import UUID

from dnd.blocks.equipment import EquippableItem
from dnd.core.base_actions import CostType, spell_slot_cost_type
from dnd.core.events import ActorSheetEvent, EventPhase, EventQueue
from dnd.entity import Entity
from dnd.game import Game
from dnd.types.actor_sheet import ActorSheetChange, ActorSheetState, PlayerResource, PlayerResourceValue

CHANNELS: tuple[tuple[CostType, str], ...] = (("actions", "Actions"), ("bonus_actions", "Bonus"), ("reactions", "Reaction"))
UNCHANGED = ActorSheetChange()


@dataclass(frozen=True, slots=True)
class PublishedSheet:
    """The sheet an actor's last sheet event established, named by that event."""

    event_uuid: UUID
    sheet: ActorSheetState


@dataclass(slots=True)
class PublishedSheets:
    """The publisher's one record: each published actor's last publication, in one event generation."""

    generation: UUID = field(default_factory=EventQueue.generation_id)
    by_actor: dict[UUID, PublishedSheet] = field(default_factory=dict)


def evaluate_actor_sheet(actor: Entity) -> ActorSheetState:
    """The actor's sheet groups as they read now."""
    economy = actor.action_economy
    resources = [PlayerResource(key=key, label=label, current=value.normalized_score,
                                maximum=economy.channel_capacity(key))
                 for (key, label), value in zip(CHANNELS, (economy.actions, economy.bonus_actions, economy.reactions))]
    resources.append(PlayerResource(key="movement", label="Movement (ft)",
                     current=economy.movement_remaining(), maximum=economy.channel_capacity("movement")))
    resources.extend(PlayerResource(key=f"spell_slot_{rank}", label=f"Spell rank {rank}",
        current=economy.spell_slot_value(rank).normalized_score, maximum=economy.channel_capacity(spell_slot_cost_type(rank)))
        for rank, capacity in economy.get_normal_spell_slot_capacities().items() if capacity)
    resources.extend(PlayerResource(key=f"resource:{name}", label=name.replace('_', ' ').title(),
        current=resource.current, maximum=resource.maximum) for name, resource in economy.resources.items())
    return ActorSheetState(
        abilities=tuple((ability.name, ability.ability_score.score) for ability in actor.ability_scores.abilities_list),
        skills=tuple(skill.name for skill in actor.skill_set.proficiencies),
        expertise=tuple(skill.name for skill in actor.skill_set.expertise),
        saves=tuple(save.name for save in actor.saving_throws.proficiencies),
        proficiency_bonus=actor.proficiency_bonus.normalized_score, resources=tuple(resources),
        compatible_item_slots=tuple((item.uuid, tuple(slot.value for slot in actor.equipment.compatible_slots_for_actor(item)))
            for item in actor.inventory.items.values() if isinstance(item, EquippableItem)),
        handler_details=tuple(actor.get_player_toggleable_handler_infos()))


def _whole(sheet: ActorSheetState) -> ActorSheetChange:
    return ActorSheetChange(abilities=sheet.abilities, skills=sheet.skills, expertise=sheet.expertise,
        saves=sheet.saves, proficiency_bonus=sheet.proficiency_bonus, resources=sheet.resources,
        compatible_item_slots=sheet.compatible_item_slots, handler_details=sheet.handler_details)


def _changed(before: ActorSheetState, after: ActorSheetState) -> ActorSheetChange:
    """The groups of `after` that differ from `before`; resource rows by key while the keys stay the same."""
    same_keys = tuple(row.key for row in before.resources) == tuple(row.key for row in after.resources)
    return ActorSheetChange(
        abilities=after.abilities if after.abilities != before.abilities else None,
        skills=after.skills if after.skills != before.skills else None,
        expertise=after.expertise if after.expertise != before.expertise else None,
        saves=after.saves if after.saves != before.saves else None,
        proficiency_bonus=after.proficiency_bonus if after.proficiency_bonus != before.proficiency_bonus else None,
        resources=None if same_keys else after.resources,
        resource_values=tuple(PlayerResourceValue(key=row.key, current=row.current, maximum=row.maximum)
            for old, row in zip(before.resources, after.resources) if old != row) if same_keys else (),
        compatible_item_slots=(after.compatible_item_slots
            if after.compatible_item_slots != before.compatible_item_slots else None),
        handler_details=after.handler_details if after.handler_details != before.handler_details else None)


def publish_actor_sheets(published: PublishedSheets, game: Game, actor_uuids: tuple[UUID, ...]) -> None:
    """Publish each actor's sheet change since its last publication (player actors stay in the game)."""
    if published.generation != EventQueue.generation_id():
        raise RuntimeError("Published sheets belong to an earlier event generation")
    for identity in actor_uuids:
        previous = published.by_actor.get(identity)
        if previous is not None and EventQueue.get_event_by_uuid(previous.event_uuid) is None:
            raise RuntimeError("A published sheet names an event this queue does not hold")
        sheet = evaluate_actor_sheet(game.entities[identity])
        change = _whole(sheet) if previous is None else _changed(previous.sheet, sheet)
        if change == UNCHANGED:
            continue
        event = ActorSheetEvent(source_entity_uuid=identity, change=change, phase=EventPhase.COMPLETION)
        published.by_actor[identity] = PublishedSheet(event.uuid, sheet)
