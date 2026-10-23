"""R65's purple fungus: lingering in its spores leaves a creature hearing sounds that are not there."""

from typing import Dict, List, Literal, Optional, Set, Tuple
from uuid import UUID, uuid4

from pydantic import Field, PrivateAttr

from dnd.actions import Move, commit_forced_movement
from dnd.conditions import NoReactions, Prone
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EmptyLogData
from dnd.core.condition_types import ConditionTag, DurationType, HazardFilter
from dnd.core.content.identities import ContentRef
from dnd.core.dice import roll_die_face
from dnd.core.events import (
    Event, EventHandler, EventPhase, EventQueue, EventType, ForcedMovementEvent, SpatialChangeEvent, Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.core.values import Channel, Kind, add_modifier
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.environmental_conditions import SPIKE_TRAP_CONTENT_REF, install_authored_area_condition
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy, SpatialEffectTriggerKind
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import CARDINAL_DELTAS

SPORE_FUNGUS_CONTENT_REF = SPIKE_TRAP_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.spore_fungus",
})

HauntingEffect = Literal["startled", "drawn", "distracted"]

# The book's d12 table; each sound acts through one existing owner (authored choice, plan §4.G).
HAUNTING_SOUNDS: Tuple[Tuple[str, HauntingEffect], ...] = (
    ("a baby crying", "drawn"), ("a frog croaking", "distracted"), ("whistling", "drawn"),
    ("a very loud heartbeat", "startled"), ("cackling laughter", "startled"), ("chanting", "distracted"),
    ("sounds from behind the wall", "drawn"), ("water dripping", "distracted"),
    ("a young girl crying for help", "drawn"), ("a harsh voice saying your name", "startled"),
    ("a door slamming shut", "startled"), ("footsteps", "distracted"),
)
_DIRECTIONS = (CardinalDirection.NORTH, CardinalDirection.EAST, CardinalDirection.SOUTH, CardinalDirection.WEST)


class Distracted(BaseCondition):
    """Straining after a sound: −5 to Perception, passive Perception included, until it fades."""

    name: str = Field(default="Distracted", description="Condition name.")
    description: str = Field(default="Distracted by a sound: −5 to Wisdom (Perception), passive included.",
                             description="Condition description.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Distracted needs a creature")
        perception = target.skill_set.get_skill("perception").skill_bonus
        modifier_uuid = add_modifier(perception, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
            name="Distracted", value=-5, source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
        return [(perception.uuid, modifier_uuid)], [], [], [], declaration_event.phase_to(
            EventPhase.EFFECT, update={"condition": self}, status_message=f"{target.name} is distracted")


class Haunted(BaseCondition):
    """Sounds that are not there: every few rounds, at the owner's turn start, one of them.

    A poison-family affliction: immunity to Poisoned prevents it and Lesser Restoration cures it.
    The sounds reach only the owner's log; each one acts through an existing owner.
    """
    creates = (Distracted, NoReactions, Move, Prone)  # the forced step may build movement and a fall
    immunity_names: tuple[str, ...] = ("Poisoned",)

    name: str = Field(default="Haunted", description="Condition name.")
    description: str = Field(default="Hears sounds that are not there.", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.POISON})
    cue_interval_rounds: int = Field(default=3, ge=1, description="Rounds between sounds.")
    _rounds_since_cue: int = PrivateAttr(default=0)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Haunted needs a creature")
        handler = EventHandler(name="Haunted sounds", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EXECUTION,
                                        event_source_entity_uuid=target.uuid)],
            event_processor=self._on_turn_start)
        target.add_event_handler(handler)
        return [], [handler.uuid], [], [], declaration_event.phase_to(
            EventPhase.EFFECT, status_message=f"{target.name} is haunted")

    def _on_turn_start(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        entity = Entity.get(source_entity_uuid)
        self._rounds_since_cue += 1
        if not isinstance(entity, Entity) or self._rounds_since_cue < self.cue_interval_rounds:
            return None
        self._rounds_since_cue = 0
        sound, effect = HAUNTING_SOUNDS[roll_die_face(12) - 1]
        direction = _DIRECTIONS[roll_die_face(4) - 1]
        if effect == "drawn":
            self._step_toward(entity, direction, parent_event=event)
        else:
            # Added before this turn start's countdown and refresh, so two rounds last until the next
            # turn start; a startled creature gets no reaction this round.
            condition_type = NoReactions if effect == "startled" else Distracted
            entity.add_condition(condition_type(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid,
                duration=Duration(duration=2, duration_type=DurationType.ROUNDS,
                                  source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)),
                parent_event=event)
        heard = f"{entity.name} hears {sound} from the {direction.value.lower()}"
        EventQueue.push_combat_log(CombatLogEntry(entry_type=CombatLogEntryType.ACTION, source_name=entity.name,
            source_uuid=str(entity.uuid), compact=heard, verbose=heard, detailed=heard, data=EmptyLogData(),
            perceiver_uuids={str(entity.uuid)}), entity.uuid)
        return None

    def _step_toward(self, entity: Entity, direction: CardinalDirection, *, parent_event: Event) -> None:
        if not entity.can_take_actions() or entity.action_economy.current_speed() <= 0:
            return  # a paralyzed, grappled or stopped creature only hears it
        dx, dy = CARDINAL_DELTAS[direction]
        destination = entity.position[0] + dx, entity.position[1] + dy
        if not get_map().can_transition(entity.position, destination, entity.uuid):
            return
        moved = EventQueue.publish_declaration(ForcedMovementEvent(
            source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid, source_entity_name=entity.name,
            target_entity_name=entity.name, start_position=entity.position, end_position=destination,
            direction=(dx, dy), intended_distance=5, actual_distance=5, cause="haunting",
            parent_event=parent_event.uuid, use_register=False))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            if moved.canceled:
                return
            moved = moved.phase_to(phase)
        commit_forced_movement(entity, moved, parent_event=parent_event)


class SporeFungus(AreaCondition):
    """Purple fungus in the tile cracks: a third turn end in its spores asks one Constitution save.

    Failing leaves the creature Haunted for haunt_rounds, a sound every cue_interval_rounds; both
    are authored. One save per continuous stay; leaving resets it.
    """
    creates = (Haunted,)

    name: str = Field(default="Purple fungus")
    description: str = Field(default="Strange spores: lingering here may leave one hearing things.")
    has_visible_presence: bool = True
    content_ref: ContentRef = Field(default=SPORE_FUNGUS_CONTENT_REF)
    layer: SpatialEffectLayer = SpatialEffectLayer.GROUND_SURFACE
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({
        SpatialEffectTriggerKind.TURN_END, SpatialEffectTriggerKind.LEAVE})
    hazard_filter: HazardFilter = HazardFilter.ALL
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))
    save_dc: int = Field(default=13, ge=0)
    haunt_rounds: int = Field(default=100, ge=1)
    cue_interval_rounds: int = Field(default=3, ge=1)
    _turn_ends_inside: Dict[UUID, int] = PrivateAttr(default_factory=dict)
    _settled: Set[UUID] = PrivateAttr(default_factory=set)  # saved or haunted during this stay

    def _linger(self, entity: Entity, *, parent_event: Event) -> None:
        if entity.uuid in self._settled:
            return
        self._turn_ends_inside[entity.uuid] = self._turn_ends_inside.get(entity.uuid, 0) + 1
        if self._turn_ends_inside[entity.uuid] < 3:
            return
        self._settled.add(entity.uuid)
        if "Haunted" in entity.active_conditions:
            return
        request = entity.create_saving_throw_request(target_entity_uuid=entity.uuid, ability_name="constitution",
            dc=self.save_dc, parent_event=parent_event.uuid, condition_context="Poisoned",
            saving_throw_context=SavingThrowContext(cause_id=self.content_ref.content_id,
                effect_id=f"{self.content_ref.content_id}.spores", is_magical=False,
                effect_tags=(SavingThrowEffectTag.POISON,)))
        _, _, saved = entity.saving_throw(request)
        if not saved:
            entity.add_condition(Haunted(source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid,
                cue_interval_rounds=self.cue_interval_rounds,
                duration=Duration(duration=self.haunt_rounds, duration_type=DurationType.ROUNDS,
                                  source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid)),
                parent_event=parent_event)

    def _create_zone_turn_end_handler(self) -> EventHandler:
        def linger(event: Event, _source_entity_uuid: UUID) -> None:
            entity = Entity.get(event.source_entity_uuid)
            if isinstance(entity, Entity) and entity.position in self.affected_positions:
                self._linger(entity, parent_event=event)

        return EventHandler(name="Purple fungus spores", source_entity_uuid=self.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EXECUTION)],
            event_processor=linger)

    def _create_zone_exit_handler(self) -> EventHandler:
        def leave(event: Event, _source_entity_uuid: UUID) -> None:
            entity = Entity.get(event.entity_uuid) if isinstance(event, SpatialChangeEvent) and event.entity_uuid else None
            if isinstance(entity, Entity) and entity.position not in self.affected_positions:
                self._turn_ends_inside.pop(entity.uuid, None)
                self._settled.discard(entity.uuid)

        return EventHandler(name="Purple fungus exit", source_entity_uuid=self.uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_LEFT, event_phase=EventPhase.EFFECT)],
            event_processor=leave)


def materialize_spore_fungus(positions: Set[Tuple[int, int]], *, haunt_rounds: int = 100,
                             cue_interval_rounds: int = 3, parent_event: Optional[Event] = None) -> SporeFungus:
    """One authored fungus-cracked floor, with its tunable haunting length and sound interval."""
    fungus = SporeFungus(source_entity_uuid=uuid4(), position=min(positions), affected_positions=set(positions),
                         haunt_rounds=haunt_rounds, cue_interval_rounds=cue_interval_rounds)
    install_authored_area_condition(fungus, parent_event=parent_event)
    return fungus
