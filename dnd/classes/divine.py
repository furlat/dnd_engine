"""Shared divine turning: separate control identity and native retreat actions."""

from uuid import UUID

from pydantic import Field

from dnd.actions import Dash, Dodge, Move
from dnd.core.base_actions import ActionEvent
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.condition_types import ConditionTag, ConditionCategory, DurationType
from dnd.core.events import Event, EventHandler, EventPhase, EventType, Trigger
from dnd.core.modifiers import NumericalModifier
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.core.geometry import grid_distance_feet
from dnd.core.gridmap import get_map
from dnd.core.navigation import route_items
from dnd.core.creature_types import CreatureType
from dnd.entity import Entity
from dnd.spells.spell_utils import target_turn_expiry_handler
from dnd.types.world import MovementMode
from dnd.core.values import Channel, Kind, add_modifier


class ClassFeatureLifetime(BaseCondition):
    """One native root for exact cross-target feature cleanup on level removal."""

    name: str = "Class Feature Owner"
    description: str = "Owns exact active class feature descendants through native linked-condition cleanup."
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    duration: Duration = Field(
        default_factory=lambda: Duration(duration_type=DurationType.PERMANENT)
    )


class Turned(BaseCondition):
    creates = (Dash, Dodge, Move)
    name: str = "Turned"
    description: str = "Turned for three recipient turns: retreat, Dash or blocked-path Dodge; no reactions; ends on damage."
    immunity_names: tuple[str, ...] = ("Turned",)
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None, duration_type=DurationType.PERMANENT
        )
    )
    damage_break_armed: bool = True

    def model_post_init(self, context):
        super().model_post_init(context)
        self.name = f"Turned {self.uuid}"

    def get_display_name(self):
        return "Turned"

    def _apply(self, event):
        target = Entity.get(self.target_entity_uuid)
        if target is None:
            return (
                [],
                [],
                [],
                [],
                event.cancel(status_message="Turned target is absent"),
            )
        handlers = [
            EventHandler(
                name="Turned actions",
                source_entity_uuid=target.uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=kind,
                        event_phase=EventPhase.DECLARATION,
                        event_source_entity_uuid=target.uuid,
                    )
                    for kind in (
                        EventType.BASE_ACTION,
                        EventType.ATTACK,
                        EventType.CAST_SPELL,
                    )
                ],
                event_processor=self._deny_actions,
            ),
            EventHandler(
                name="Turned flee",
                source_entity_uuid=target.uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.TURN_START,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=target.uuid,
                    )
                ],
                event_processor=self._flee,
            ),
            EventHandler(
                name="Turned damage break",
                source_entity_uuid=target.uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.DAMAGE_APPLIED,
                        event_phase=EventPhase.EFFECT,
                        event_target_entity_uuid=target.uuid,
                    )
                ],
                event_processor=self._damage_break,
            ),
            EventHandler(
                name="Turned retreat direction",
                source_entity_uuid=target.uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.STEP_MOVEMENT,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=target.uuid,
                    )
                ],
                event_processor=self._retreat,
            ),
            target_turn_expiry_handler(self, turn_ends=3),
        ]
        for handler in handlers:
            target.add_event_handler(handler)
        # Reactions are denied through the native capacity owner, independently of fear.
        from_reactions = target.action_economy.reactions
        modifier = add_modifier(from_reactions, Channel.SELF_STATIC, Kind.MAX, NumericalModifier(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid,
                name="Turned",
                value=0,
            ))
        return (
            [(from_reactions.uuid, modifier)],
            [handler.uuid for handler in handlers],
            [],
            [],
            event.phase_to(EventPhase.EFFECT),
        )

    def _deny_actions(self, event, context):
        if isinstance(event, ActionEvent) and event.behavior_id in (
            "action.dash",
            "action.dodge",
        ):
            return event
        return event.cancel(
            status_message="Turned permits retreat, Dash or a blocked-path Dodge"
        )

    def _damage_break(self, event, context):
        if self.damage_break_armed:
            target = Entity.get(self.target_entity_uuid)
            if target is not None:
                target.remove_condition_by_uuid(self.uuid, parent_event=event)

    def _retreat(self, event, context):
        source = Entity.get(self.source_entity_uuid)
        if source is not None and grid_distance_feet(
            event.to_position, source.position
        ) < grid_distance_feet(event.from_position, source.position):
            return event.cancel(status_message="Turned cannot approach its source")
        return event

    def _flee(self, event, context):
        target, source = (
            Entity.get(self.target_entity_uuid),
            Entity.get(self.source_entity_uuid),
        )
        if target is None or source is None:
            return None
        target.materialize_navigation(max_distance=80)
        budget = (
            target.action_economy.movement_remaining()
            + target.action_economy.current_speed()
        )
        grid = get_map()
        candidates = []
        for destination, path in route_items(target.senses.paths):
            if len(path) < 2 or grid_distance_feet(
                destination, source.position
            ) <= grid_distance_feet(target.position, source.position):
                continue
            cost = int(
                sum(
                    grid.movement_edge_cost_units(
                        a,
                        b,
                        MovementMode.WALKING,
                        ignore_difficult_terrain=target.ignore_difficult_terrain,
                    )
                    for a, b in zip(path, path[1:])
                )
                * 5
            )
            if cost > budget or any(
                grid_distance_feet(b, source.position)
                < grid_distance_feet(a, source.position)
                for a, b in zip(path, path[1:])
            ):
                continue
            safe = not any(
                grid.is_position_hazardous_for(*position, target.uuid)
                for position in path[1:]
            )
            candidates.append(
                (
                    safe,
                    grid_distance_feet(destination, source.position),
                    -cost,
                    destination,
                    path,
                )
            )
        if not candidates:
            dodge = Dodge(
                source_entity_uuid=target.uuid,
                behavior_binding=BehaviorBinding(
                    behavior_id="action.dodge",
                    provided_by_id="action.dodge",
                    origin_root_id="action.dodge",
                    runtime_owner_uuid=target.uuid,
                ),
            )
            target.perform(dodge, dodge.current_selection(), parent_event=event)
            return None
        dash = Dash(
            source_entity_uuid=target.uuid,
            behavior_binding=BehaviorBinding(
                behavior_id="action.dash",
                provided_by_id="action.dash",
                origin_root_id="action.dash",
                runtime_owner_uuid=target.uuid,
            ),
        )
        result = target.perform(dash, dash.current_selection(), parent_event=event)
        if result is not None and not result.canceled:
            *_, destination, path = max(candidates)
            flight = Move(source_entity_uuid=target.uuid, end_position=destination, path=path)
            target.perform(flight, flight.current_selection(), parent_event=event)


def turn_creature(
    actor: Entity,
    target: Entity,
    event: Event,
    *,
    casting_source_id: UUID,
    feature_owner_uuid: UUID | None = None,
) -> None:
    root = BaseCondition.get(feature_owner_uuid) if feature_owner_uuid else None
    if feature_owner_uuid is not None and (root is None or not root.applied):
        return
    request = actor.create_saving_throw_request(
        target_entity_uuid=target.uuid,
        ability_name="wisdom",
        dc=actor.spell_save_dc(spellcasting_source_id=casting_source_id),
        parent_event=event.uuid,
        saving_throw_context=SavingThrowContext(
            cause_id="class_feature.divine.turning",
            effect_id="class_feature.divine.turning.save",
            is_magical=True,
        ),
    )
    if target.saving_throw(request)[2]:
        return
    condition = Turned(
        source_entity_uuid=actor.uuid,
        target_entity_uuid=target.uuid,
        effect_origin=event.get_effect_origin(),
    )
    result = target.add_condition(condition, parent_event=event)
    root = BaseCondition.get(feature_owner_uuid) if feature_owner_uuid else None
    if root is not None and result is not None and not result.canceled:
        root.add_linked_condition(target.uuid, condition.uuid)


def turning_targets(
    actor: Entity, creature_types: tuple[CreatureType, ...]
) -> list[UUID]:
    return [
        target.uuid
        for target in map(Entity.get, get_map().get_entities_within(actor.position, 30))
        if target.creature_type in creature_types
        and (
            target.uuid == actor.uuid
            or (contact := target.senses.entities.get(actor.uuid)) is not None
            and contact.visual
        )
    ]
