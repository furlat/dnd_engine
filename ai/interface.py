"""Agent interface adapters for reading and executing NeuroDragon turns."""

from typing import Dict, Iterable, List, Optional, Protocol, Tuple, cast
from uuid import UUID

from ai.models import (
    ActionEconomy,
    ActionOption,
    ActionResult,
    AttackData,
    DiceSpec,
    SpellData,
    TacticalEntity,
    TacticalState,
    TargetOption,
)
from dnd.actions_functional import execute_by_index
from dnd.core.base_actions import (
    ActionCategory,
    AvailableActionInfo,
    TargetType,
    spell_slot_cost_type,
)
from dnd.core.base_object import BaseObject
from dnd.core.events import AbilityName, WeaponSlot
from dnd.entity import Entity


class GameInterface(Protocol):
    """Protocol for tactical agents that read state and execute legal choices."""

    def get_tactical_state(self, entity_uuid: str) -> TacticalState:
        """Build the controlled actor's subjective tactical snapshot.

        Args:
            entity_uuid: UUID string of the actor controlled by the agent.

        Returns:
            Tactical state containing the actor, perceived entities, resources,
            available actions, target rows, and combat math.
        """
        raise NotImplementedError

    def execute(
        self,
        entity_uuid: str,
        template_name: str,
        target_index: int = 0,
        extra_target_uuids: Optional[List[str]] = None,
        prefer_safe: bool = True,
    ) -> ActionResult:
        """Execute one discovered action row through the game.

        Args:
            entity_uuid: UUID string of the acting entity.
            template_name: Registered action template name selected by the
                agent.
            target_index: Target row index from the tactical snapshot.
            extra_target_uuids: Optional extra targets for multi-target actions.
            prefer_safe: Whether movement selection should prefer safe paths.

        Returns:
            Agent-facing action result summarizing the outcome.
        """
        raise NotImplementedError


class LocalGameInterface:
    """Direct in-process adapter between live engine objects and AI models."""

    def get_tactical_state(self, entity_uuid: str) -> TacticalState:
        """Build the controlled actor's subjective tactical snapshot.

        Args:
            entity_uuid: UUID string of the actor controlled by the agent.

        Returns:
            Tactical state containing the actor, perceived entities, resources,
            available actions, target rows, and combat math.

        Raises:
            ValueError: If the actor UUID is not registered.
        """
        entity = Entity.get(UUID(entity_uuid))
        if entity is None:
            raise ValueError(f"Entity {entity_uuid} not found")

        available = entity.get_available_actions(target_filter="all")
        enemies = _visible_entities(entity, entity.get_visible_enemies().items())
        allies = _visible_entities(entity, entity.get_visible_allies().items())
        attacks, spells, movements, self_actions, object_actions = _group_action_options(
            available.entity_actions,
            available.position_actions,
            available.self_actions,
            available.object_actions,
            entity,
        )

        return TacticalState(
            me=_entity_snapshot(entity, entity.position),
            action_economy=_action_economy_snapshot(entity),
            enemies=enemies,
            allies=allies,
            attacks=attacks,
            spells=spells,
            movements=movements,
            self_actions=self_actions,
            object_actions=object_actions,
            is_threatened=_is_threatened(enemies),
            is_concentrating="Concentrating" in entity.active_conditions,
            spell_slots=_spell_slots(entity),
            resources=_resources(entity),
        )

    def execute(
        self,
        entity_uuid: str,
        template_name: str,
        target_index: int = 0,
        extra_target_uuids: Optional[List[str]] = None,
        prefer_safe: bool = True,
    ) -> ActionResult:
        """Execute one discovered action row through the live engine.

        Args:
            entity_uuid: UUID string of the acting entity.
            template_name: Registered action template name selected by the
                agent.
            target_index: Target row index from the tactical snapshot.
            extra_target_uuids: Optional extra targets for multi-target actions.
            prefer_safe: Whether movement selection should prefer safe paths.

        Returns:
            Agent-facing action result summarizing HP, deaths, and reactions.
        """
        entity = Entity.get(UUID(entity_uuid))
        if entity is None:
            return ActionResult(success=False, message=f"Entity {entity_uuid} not found")

        try:
            event = execute_by_index(
                entity,
                template_name,
                target_index,
                extra_target_uuids=extra_target_uuids,
                prefer_safe=prefer_safe,
            )
        except ValueError as exc:
            return ActionResult(success=False, message=str(exc))

        hp_after = entity.get_hp()
        deaths: List[str] = []
        target_hp: Optional[int] = None
        reactions: List[str] = []

        if event is not None:
            target_uuid = getattr(event, "target_entity_uuid", None)
            if target_uuid:
                target_entity = Entity.get(target_uuid)
                if target_entity is not None:
                    target_hp = target_entity.get_hp()
                    if not target_entity.has_hp:
                        deaths.append(target_entity.name)

            for child_uuid in getattr(event, "child_events", []):
                child = BaseObject.get(child_uuid)
                if child is not None:
                    child_name = getattr(child, "name", "")
                    if child_name:
                        reactions.append(child_name)

        return ActionResult(
            success=event is not None,
            entity_hp=hp_after,
            target_hp=target_hp,
            deaths=deaths,
            triggered_reactions=reactions,
        )


def _entity_snapshot(
    entity: Entity,
    position: Tuple[int, int],
    observer: Optional[Entity] = None,
) -> TacticalEntity:
    """Create the tactical model for one visible entity.

    Args:
        entity: Entity being serialized for the agent.
        position: Position visible to the observing actor.
        observer: Optional observing actor used to compute distance.

    Returns:
        Tactical entity snapshot.
    """
    return TacticalEntity(
        uuid=str(entity.uuid),
        name=entity.name,
        position=position,
        hp=entity.get_hp(),
        max_hp=_get_max_hp(entity),
        ac=entity.equipment.ac_bonus.normalized_score,
        conditions=[
            condition.name for condition in entity.active_conditions.values()
            if condition.name is not None
        ],
        distance_feet=(
            observer.senses.get_feet_distance(position)
            if observer is not None else None
        ),
        faction=entity.faction,
        is_dead=not entity.has_hp,
    )


def _visible_entities(
    observer: Entity,
    visible_positions: Iterable[Tuple[UUID, Tuple[int, int]]],
) -> List[TacticalEntity]:
    """Serialize visible actors for one observing entity.

    Args:
        observer: Entity whose subjective senses produced the visible set.
        visible_positions: UUID and position pairs from a senses query.

    Returns:
        Tactical entity snapshots ordered by distance.
    """
    snapshots: List[TacticalEntity] = []
    for entity_uuid, position in visible_positions:
        entity = Entity.get(entity_uuid)
        if entity is not None:
            snapshots.append(_entity_snapshot(entity, position, observer))
    snapshots.sort(
        key=lambda snapshot: (
            snapshot.distance_feet if snapshot.distance_feet is not None else 999
        )
    )
    return snapshots


def _action_economy_snapshot(entity: Entity) -> ActionEconomy:
    """Return remaining action economy for an entity."""
    return ActionEconomy(
        actions=entity.action_economy.actions.normalized_score,
        bonus_actions=entity.action_economy.bonus_actions.normalized_score,
        reactions=entity.action_economy.reactions.normalized_score,
        movement=entity.action_economy.movement.normalized_score,
    )


def _is_threatened(enemies: Iterable[TacticalEntity]) -> bool:
    """Return whether any visible enemy is within melee reach."""
    return any(
        enemy.distance_feet is not None and enemy.distance_feet <= 5
        for enemy in enemies
    )


def _spell_slots(entity: Entity) -> Dict[int, Tuple[int, int]]:
    """Return current and maximum spell slots keyed by level."""
    slots: Dict[int, Tuple[int, int]] = {}
    if not entity.is_spellcaster:
        return slots
    for level in range(1, 10):
        max_slots = entity.action_economy.get_base_value(spell_slot_cost_type(level))
        current = entity.action_economy._get_spell_slot_value(level).normalized_score
        if max_slots > 0:
            slots[level] = (current, max_slots)
    return slots


def _resources(entity: Entity) -> Dict[str, Tuple[int, int]]:
    """Return current and maximum named resources."""
    return {
        resource_name: (resource.current, resource.maximum)
        for resource_name, resource in entity.action_economy.resources.items()
    }


def _group_action_options(
    entity_actions: Iterable[AvailableActionInfo],
    position_actions: Iterable[AvailableActionInfo],
    self_actions_source: Iterable[AvailableActionInfo],
    object_actions_source: Iterable[AvailableActionInfo],
    entity: Entity,
) -> Tuple[
    List[ActionOption],
    List[ActionOption],
    List[ActionOption],
    List[ActionOption],
    List[ActionOption],
]:
    """Group engine action rows into tactical categories.

    Args:
        entity_actions: Entity-targeting available actions.
        position_actions: Position-targeting available actions.
        self_actions_source: Self-targeting available actions.
        object_actions_source: Object-targeting available actions.
        entity: Acting entity that owns the templates.

    Returns:
        Attack, spell, movement, self-action, and object-action options.
    """
    attacks: List[ActionOption] = []
    spells: List[ActionOption] = []
    movements: List[ActionOption] = []
    self_actions: List[ActionOption] = []
    object_actions: List[ActionOption] = []

    for info in entity_actions:
        option = _info_to_action_option(info, entity)
        if option.category == "attack":
            attacks.append(option)
        elif option.category == "spell":
            spells.append(option)

    for info in position_actions:
        option = _info_to_action_option(info, entity)
        if option.category == "movement":
            movements.append(option)
        elif option.category == "spell":
            spells.append(option)

    for info in self_actions_source:
        option = _info_to_action_option(info, entity)
        if option.category == "spell":
            spells.append(option)
        else:
            self_actions.append(option)

    for info in object_actions_source:
        object_actions.append(_info_to_action_option(info, entity))

    return attacks, spells, movements, self_actions, object_actions


def _get_max_hp(entity: Entity) -> int:
    """Return maximum hit points for an entity."""
    con_mod = entity.ability_scores.get_ability("constitution").get_combined_values().normalized_score
    base_max = entity.health.get_max_hit_dices_points(constitution_modifier=con_mod)
    bonus = entity.health.max_hit_points_bonus.normalized_score
    return base_max + bonus


def _info_to_action_option(info: AvailableActionInfo, entity: Entity) -> ActionOption:
    """Convert one engine action row into an agent-facing action option.

    Args:
        info: Available action row produced by engine action discovery.
        entity: Entity that owns the action template.

    Returns:
        Tactical action option with target rows and combat math.
    """
    attack_data: Optional[AttackData] = None
    spell_data: Optional[SpellData] = None

    if info.action_category == ActionCategory.ATTACK and info.weapon_slot:
        weapon_slot = WeaponSlot(info.weapon_slot)
        attack_bonus = entity.attack_bonus(weapon_slot)
        damages = entity.get_damages(weapon_slot)
        attack_data = AttackData(
            attack_bonus=attack_bonus.normalized_score,
            advantage=attack_bonus.advantage.name.lower(),
            crit_threshold=entity.get_crit_threshold(weapon_slot),
            crit_extra_dice=entity.get_crit_extra_dice(weapon_slot),
            damage_dice=[
                DiceSpec(
                    count=damage.dice_numbers,
                    sides=damage.damage_dice,
                    bonus=(
                        damage.damage_bonus.normalized_score
                        if damage.damage_bonus else 0
                    ),
                    damage_type=damage.damage_type.value,
                )
                for damage in damages
            ],
        )

    if info.action_category == ActionCategory.SPELL:
        template = entity.get_action_template(info.template_name)
        if template is not None:
            spell_level = getattr(template, "spell_level", 0)
            cast_at_level = getattr(template, "cast_at_level", spell_level)
            save_ability = getattr(template, "save_ability", "")
            half_on_save = getattr(template, "half_on_save", True)
            concentration = getattr(template, "concentration", False)
            school = getattr(template, "spell_school", "")
            is_attack_roll = info.target_type == TargetType.ENTITY

            damage_dice: List[DiceSpec] = []
            template_damages = getattr(template, "damages", None)
            if template_damages:
                for damage in template_damages:
                    damage_type = getattr(damage, "damage_type", "")
                    damage_dice.append(
                        DiceSpec(
                            count=getattr(damage, "dice_numbers", 0),
                            sides=getattr(damage, "damage_dice", 6),
                            bonus=0,
                            damage_type=getattr(damage_type, "value", damage_type),
                        )
                    )

            spell_data = SpellData(
                spell_level=spell_level,
                cast_at_level=cast_at_level,
                spell_dc=entity.spell_save_dc() if entity.is_spellcaster else 0,
                spell_attack_bonus=(
                    entity.spellcasting.spell_attack_bonus.normalized_score
                    if entity.is_spellcaster else 0
                ),
                save_ability=str(save_ability),
                half_on_save=half_on_save,
                is_attack_roll=is_attack_roll,
                damage_dice=damage_dice,
                concentration=concentration,
                school=str(school),
            )

    targets: List[TargetOption] = []
    for target in info.valid_targets:
        target_ac: Optional[int] = None
        target_save_bonus: Optional[int] = None
        if target.target_uuid:
            target_entity = Entity.get(target.target_uuid)
            if target_entity is not None:
                target_ac = target_entity.equipment.ac_bonus.normalized_score
                if spell_data and spell_data.save_ability:
                    save_ability = cast(AbilityName, spell_data.save_ability)
                    save_mv = target_entity.saving_throw_bonus(
                        entity.uuid,
                        save_ability,
                    )
                    target_save_bonus = save_mv.normalized_score

        targets.append(
            TargetOption(
                index=target.index,
                target_uuid=str(target.target_uuid) if target.target_uuid else None,
                target_name=target.target_name,
                position=target.position,
                distance=target.distance,
                path_cost=target.path_cost,
                is_path_hazardous=target.is_path_hazardous,
                safe_path_cost=target.safe_path_cost,
                aoe_affected_count=target.affected_count,
                aoe_affected_uuids=(
                    [str(uuid) for uuid in target.affected_entity_uuids]
                    if target.affected_entity_uuids else None
                ),
                aoe_affected_names=target.affected_entity_names,
                target_ac=target_ac,
                target_save_bonus=target_save_bonus,
            )
        )

    return ActionOption(
        template_name=info.template_name,
        display_name=info.display_name,
        category=info.action_category.value,
        target_type=info.target_type.value,
        cost_type=info.cost_type,
        cost_amount=info.cost_amount,
        can_afford=info.can_afford,
        weapon_name=info.weapon_name,
        weapon_slot=info.weapon_slot,
        num_projectiles=info.num_projectiles,
        allow_same_target=info.allow_same_target,
        is_item_use=info.is_item_use,
        source_item_uuid=str(info.source_item_uuid) if info.source_item_uuid else None,
        targets=targets,
        attack_data=attack_data,
        spell_data=spell_data,
    )
