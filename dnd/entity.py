from typing import AbstractSet, DefaultDict, Dict, Mapping, Optional, Any, Iterator, List, ClassVar, Sequence, Union, Tuple, Set, cast
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, PrivateAttr
from collections import defaultdict
from contextlib import contextmanager
import time

from dnd.action_timing import action_timing_enabled, record_action_elapsed, record_action_timing
from dnd.core.values import ModifiableValue, AdvantageStatus
from dnd.core.modifiers import NumericalModifier, CreatureType, DamageType, Size
from dnd.core.values import CriticalStatus, AutoHitStatus
from dnd.core.base_conditions import BaseCondition, ConditionTag
from dnd.core.dice import Dice, RollType, DiceRoll, AttackOutcome

from dnd.core.events import (
    Event, EventPhase, EventQueue, RangeType, SavingThrowEvent, SkillCheckEvent, TurnStartEvent, TurnEndEvent,
    D20RollResultEvent, AttackD20RollResultEvent, SavingThrowD20RollResultEvent, SkillCheckD20RollResultEvent,
    TakeDamageEvent, DamageAppliedEvent, DeathSaveEvent, InstantDeathEvent, DeathEvent, HealEvent, EquipmentSlot
)
from dnd.core.base_block import BaseBlock, MovementMode
from dnd.blocks.abilities import AbilityScoresConfig, AbilityScores
from dnd.blocks.saving_throws import SavingThrowSetConfig, SavingThrowSet
from dnd.blocks.health import DamageApplicationPreview, HealthConfig, Health, HitDiceHealingResult
from dnd.blocks.equipment import EquipmentConfig, Equipment, WeaponSlot, WeaponProperty, Range, Shield, Damage, Armor, Weapon
from dnd.blocks.action_economy import ActionEconomyConfig, ActionEconomy
from dnd.blocks.skills import SkillSetConfig, SkillSet
from dnd.blocks.sensory import Senses, VisibilityComputationCache, spatial_senses_system
from dnd.core.base_block import SensesType, SenseMode, LightLevel
from dnd.blocks.inventory import Inventory
from dnd.blocks.spellcasting import SpellcastingBlock, SpellcastingConfig
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.blocks.appearance import Appearance, AppearanceConfig
from dnd.core.events import AbilityName, SkillName
from dnd.core.gridmap import get_map
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EntitySpottedLogData
from dnd.core.base_actions import (
    AttackRollBaseline, BaseAction, BaseCost, DamageRollProfile, TargetType,
    AvailableTarget, AvailableActionInfo, AvailableActionsResult, AvailableHandlerInfo,
    OpportunityAttackExposure,
    PositionDiscoveryContract, target_resolution_sort_key,
)


def get_natural_roll(roll: DiceRoll) -> int:
    """Return the d20 face selected by the roll's advantage state.

    Args:
        roll: D20 roll whose raw results may be an int or a list.

    Returns:
        The single roll, the higher advantage die, the lower disadvantage die,
        or the first listed die for a normal multi-result roll.
    """
    results = roll.results
    if isinstance(results, int):
        return results
    if roll.advantage_status == AdvantageStatus.ADVANTAGE:
        return max(results)
    elif roll.advantage_status == AdvantageStatus.DISADVANTAGE:
        return min(results)
    else:
        return results[0] if results else 0


def determine_attack_outcome(
    roll: DiceRoll,
    ac: Union[int, ModifiableValue],
    crit_threshold: int = 20
) -> AttackOutcome:
        """Determine current engine d20 outcome from a roll and target number.

        Args:
            roll: D20 roll result.
            ac: Target number or modifiable target number.
            crit_threshold: Minimum natural attack roll that upgrades a hit to
                a critical hit.

        Returns:
            Engine outcome for the roll. Attack rolls use natural 1/critical
            semantics; saving throws and checks compare total against DC.
        """
        target_ac = ac.normalized_score if isinstance(ac, ModifiableValue) else ac

        if roll.roll_type != RollType.ATTACK:
            return AttackOutcome.HIT if roll.total >= target_ac else AttackOutcome.MISS

        natural_roll = get_natural_roll(roll)

        if roll.auto_hit_status == AutoHitStatus.AUTOMISS:
            return AttackOutcome.MISS
        elif roll.auto_hit_status == AutoHitStatus.AUTOHIT:
            if roll.critical_status == CriticalStatus.NOCRIT:
                return AttackOutcome.HIT
            if roll.critical_status == CriticalStatus.AUTOCRIT or natural_roll >= crit_threshold:
                return AttackOutcome.CRIT
            else:
                return AttackOutcome.HIT
        elif natural_roll == 1:
            return AttackOutcome.CRIT_MISS
        elif natural_roll == 20:
            return AttackOutcome.HIT if roll.critical_status == CriticalStatus.NOCRIT else AttackOutcome.CRIT
        elif roll.total >= target_ac:
            if roll.critical_status == CriticalStatus.NOCRIT:
                return AttackOutcome.HIT
            if roll.critical_status == CriticalStatus.AUTOCRIT or natural_roll >= crit_threshold:
                return AttackOutcome.CRIT
            else:
                return AttackOutcome.HIT
        else:
            return AttackOutcome.MISS

class EntityConfig(BaseModel):
    """Configuration used by the reliable `Entity.create(..., config=...)` path."""

    ability_scores: AbilityScoresConfig = Field(
        default_factory=AbilityScoresConfig,
        description="Ability score configuration for the entity."
    )
    skill_set: SkillSetConfig = Field(
        default_factory=SkillSetConfig,
        description="Skill configuration for the entity."
    )
    saving_throws: SavingThrowSetConfig = Field(
        default_factory=SavingThrowSetConfig,
        description="Saving throw configuration for the entity."
    )
    health: HealthConfig = Field(
        default_factory=HealthConfig,
        description="Health and hit dice configuration for the entity."
    )
    equipment: EquipmentConfig = Field(
        default_factory=EquipmentConfig,
        description="Equipment configuration for the entity."
    )
    action_economy: ActionEconomyConfig = Field(
        default_factory=ActionEconomyConfig,
        description="Action economy and spell-slot configuration for the entity."
    )
    proficiency_bonus: int = Field(default=0, description="Base proficiency bonus.")
    proficiency_bonus_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="Static named modifiers applied to proficiency bonus."
    )
    initiative_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="Static named modifiers applied to initiative."
    )
    position: Tuple[int, int] = Field(
        default_factory=lambda: (0, 0),
        description="Starting grid position for the entity."
    )
    sprite_name: Optional[str] = Field(default=None, description="Renderer sprite identifier.")
    faction: Optional[str] = Field(default=None, description="Faction identifier. None = enemy to everyone")
    spellcasting: Optional[SpellcastingConfig] = Field(
        default=None,
        description="Optional spellcasting modifier configuration. None creates harmless defaults.",
    )
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig, description="Passive renderer identity metadata")
    weight: int = Field(default=150, description="Weight in pounds (default 150 for Medium humanoid)")
    creature_type: CreatureType = Field(default=CreatureType.HUMANOID, description="Creature type (default humanoid)")
    size: Size = Field(default=Size.MEDIUM, description="Creature size (Tiny through Gargantuan)")
    has_ordinary_sight: bool = Field(
        default=True,
        description="Whether the entity can see visual phenomena without special senses."
    )
    requires_breathing: bool = Field(
        default=True,
        description="Whether the entity must breathe and is affected by inhaled hazards."
    )
    swimming_speed: int = Field(
        default=0,
        ge=0,
        description="Swimming speed in feet. Zero means no natural or granted swimming speed."
    )
    uses_death_saves: bool = Field(
        default=False,
        description="Whether this entity follows the player-style death saving throw rules at 0 HP."
    )
    death_save_successes: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Initial player-style death saving throw successes."
    )
    death_save_failures: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Initial player-style death saving throw failures."
    )
    is_stable: bool = Field(
        default=False,
        description="Whether a 0-HP player-style entity is stable and skips death saves."
    )

class Entity(BaseBlock):
    """Game actor composed from specialized engine blocks.

    Entity owns the high-level registries for creature lookup and position
    lookup. It also coordinates child blocks whose data must be combined across
    abilities, skills, equipment, health, actions, senses, inventory, and
    spellcasting.
    """

    name: str = Field(default="Entity", description="Display name for this entity.")
    ability_scores: AbilityScores = Field(
        default_factory=lambda: AbilityScores.create(source_entity_uuid=uuid4()),
        description="Ability score block owned by this entity."
    )
    skill_set: SkillSet = Field(
        default_factory=lambda: SkillSet.create(source_entity_uuid=uuid4()),
        description="Skill block owned by this entity."
    )
    saving_throws: SavingThrowSet = Field(
        default_factory=lambda: SavingThrowSet.create(source_entity_uuid=uuid4()),
        description="Saving throw block owned by this entity."
    )
    health: Health = Field(
        default_factory=lambda: Health.create(source_entity_uuid=uuid4()),
        description="Health block owned by this entity."
    )
    equipment: Equipment = Field(
        default_factory=lambda: Equipment.create(source_entity_uuid=uuid4()),
        description="Equipment block owned by this entity."
    )
    action_economy: ActionEconomy = Field(
        default_factory=lambda: ActionEconomy.create(source_entity_uuid=uuid4()),
        description="Action economy block owned by this entity."
    )
    proficiency_bonus: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), value_name="proficiency_bonus", base_value=2),
        description="Entity proficiency bonus value."
    )
    initiative: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), value_name="initiative", base_value=0),
        description="Initiative modifier value."
    )
    senses: Senses = Field(
        default_factory=lambda: Senses.create(source_entity_uuid=uuid4()),
        description="Spatial senses block owned by this entity."
    )
    inventory: Inventory = Field(
        default_factory=lambda: Inventory(source_entity_uuid=uuid4()),
        description="Inventory block owned by this entity."
    )
    appearance: Appearance = Field(
        default_factory=lambda: Appearance.create(source_entity_uuid=uuid4()),
        description="Renderer-facing appearance metadata."
    )
    spellcasting: SpellcastingBlock = Field(
        default_factory=lambda: SpellcastingBlock.create(source_entity_uuid=uuid4()),
        description="Spellcasting block (always present, defaults are harmless for non-casters)"
    )
    allow_events_conditions: bool = Field(default=True, description="If True, events and conditions will be allowed to be added to the block")
    sprite_name: Optional[str] = Field(default=None, description="The name of the sprite to use for the entity")
    weight: int = Field(default=150, description="Weight in pounds (default 150 for Medium humanoid)")
    creature_type: CreatureType = Field(default=CreatureType.HUMANOID, description="Creature type (default humanoid)")
    size: Size = Field(default=Size.MEDIUM, description="Creature size (Tiny through Gargantuan)")
    has_ordinary_sight: bool = Field(
        default=True,
        description="Whether the entity can see visual phenomena without special senses."
    )
    requires_breathing: bool = Field(
        default=True,
        description="Whether the entity must breathe and is affected by inhaled hazards."
    )
    swimming_speed: int = Field(
        default=0,
        ge=0,
        description="Swimming speed in feet. Zero means no natural or granted swimming speed."
    )
    uses_death_saves: bool = Field(
        default=False,
        description="Whether this entity follows the player-style death saving throw rules at 0 HP."
    )
    death_save_successes: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Current player-style death saving throw successes."
    )
    death_save_failures: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Current player-style death saving throw failures."
    )
    is_stable: bool = Field(
        default=False,
        description="Whether a 0-HP player-style entity is stable and skips death saves."
    )

    jump_distance_additive: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), value_name="Jump Distance (Additive)", base_value=0),
        description="Additive jump-distance value used by spell and condition effects."
    )
    jump_distance_multiplier: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), value_name="Jump Distance (Multiplier)", base_value=1),
        description="Multiplicative jump-distance value used by spell and condition effects."
    )
    is_my_turn: bool = Field(default=False, description="True when it's this entity's turn")
    non_blocking: bool = Field(default=False, description="When True, entity does not block movement through its cell")
    ignore_difficult_terrain: bool = Field(default=False, description="When True, ignores difficult terrain movement costs")
    ignore_magical_speed_reduction: bool = Field(
        default=False,
        description="When True, magical effects cannot reduce this entity's movement speed."
    )
    ignore_underwater_penalties: bool = Field(
        default=False,
        description="When True, underwater movement and attack penalties are ignored."
    )
    max_concentration_slots: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), value_name="max_concentration_slots", base_value=1),
        description="Maximum simultaneous concentration slots available to this entity."
    )
    registered_actions: List[BaseAction] = Field(default_factory=list, description="Registered action templates for this entity")

    _aoe_footprint_cache_context: Optional[Tuple[Any, ...]] = PrivateAttr(default=None)
    _aoe_footprint_cache: Dict[
        Tuple[Any, ...],
        frozenset[Tuple[int, int]],
    ] = PrivateAttr(default_factory=dict)
    _aoe_preview_cache_context: Optional[Tuple[Any, ...]] = PrivateAttr(default=None)
    _aoe_preview_cache: Dict[
        Tuple[Any, ...],
        Tuple[AvailableTarget, ...],
    ] = PrivateAttr(default_factory=dict)
    _aoe_contact_alive: Dict[UUID, bool] = PrivateAttr(default_factory=dict)
    _aoe_origin_fov_cache_revision: Optional[int] = PrivateAttr(default=None)
    _aoe_origin_fov_cache: Dict[
        Tuple[Tuple[int, int], int],
        Set[Tuple[int, int]],
    ] = PrivateAttr(default_factory=dict)
    _fast_move_target_cache_revision: Optional[Tuple[int, int]] = PrivateAttr(default=None)
    _fast_move_target_cache: Dict[
        Tuple[Any, ...],
        Tuple[AvailableTarget, ...],
    ] = PrivateAttr(default_factory=dict)
    _position_preview_cache_context: Optional[Tuple[Any, ...]] = PrivateAttr(default=None)
    _position_preview_cache: Dict[
        Tuple[Any, ...],
        Tuple[AvailableTarget, ...],
    ] = PrivateAttr(default_factory=dict)
    _visible_position_cache: Dict[int, Tuple[Tuple[int, int], ...]] = PrivateAttr(
        default_factory=dict
    )
    _aoe_nearby_candidates_cache: Dict[
        Tuple[Tuple[Tuple[int, int], ...], int],
        frozenset[Tuple[int, int]],
    ] = PrivateAttr(default_factory=dict)

    _entity_registry: ClassVar[Dict[UUID, 'Entity']] = {}
    _entity_by_position: ClassVar[DefaultDict[Tuple[int, int], List['Entity']]] = defaultdict(list)

    def model_post_init(self, __context: Any) -> None:
        """Register entity identity, position, grid, and senses callbacks."""
        super().model_post_init(__context)
        self.__class__._entity_registry[self.uuid] = self
        self.__class__._entity_by_position[self.position].append(self)
        get_map().register_entity(self.uuid, self.position)

        if self.senses is not None:
            update_senses_func = lambda: self.update_entity_senses(max_distance=20)
            update_visibility_func = lambda: self.update_entity_visibility(max_distance=20)
            spatial_callback = self.senses.create_spatial_callback(
                self.uuid,
                update_senses_func=update_senses_func,
                update_visibility_func=update_visibility_func
            )
            spatial_senses_system.register_observer(spatial_callback)
            spatial_senses_system.attach()

    @classmethod
    def update_entity_position(
        cls,
        entity: 'Entity',
        new_position: Tuple[int, int],
        parent_event: Optional[UUID] = None
    ) -> None:
        """Update entity position in both class registry and GridMap.

        Args:
            entity: Entity to move.
            new_position: New grid position.
            parent_event: Optional parent event UUID for movement lineage.
        """
        cls._entity_by_position[entity.position].remove(entity)
        cls._entity_by_position[new_position].append(entity)
        entity._set_position(new_position)
        get_map().move_entity(entity.uuid, new_position, parent_event=parent_event)

    @classmethod
    def register_entity(cls, entity: 'Entity') -> None:
        """Register an entity in the entity registry.

        Args:
            entity: Entity instance to register.
        """
        cls._entity_registry[entity.uuid] = entity

    @classmethod
    def get_all_entities(cls) -> List['Entity']:
        """Return all entities currently in the entity registry."""
        return list(cls._entity_registry.values())

    @classmethod
    def get_all_entities_at_position(cls, position: Tuple[int,int]) -> List['Entity']:
        """Return the live entity list indexed at a grid position.

        Args:
            position: Grid position to inspect.

        Returns:
            The registry list for that position.
        """
        return cls._entity_by_position[position]

    @classmethod
    def get(cls, uuid: UUID) -> Optional['Entity']:
        """Retrieve an entity by UUID from the entity registry.

        Args:
            uuid: UUID of the entity to retrieve.

        Returns:
            The entity when registered, otherwise `None`.
        """
        return cls._entity_registry.get(uuid)

    @classmethod
    def create(
        cls,
        source_entity_uuid: UUID,
        name: str = "Entity",
        description: Optional[str] = None,
        config: Optional[EntityConfig] = None
    ) -> 'Entity':
        """Create an entity whose UUID and source UUID match.

        Args:
            source_entity_uuid: UUID used as both entity UUID and source UUID.
            name: Display name for the entity.
            description: Optional entity description.
            config: Optional component configuration. Defaults create a minimal
                entity with default child blocks.

        Returns:
            Newly created entity.
        """
        if config is None:
            appearance = Appearance.create(source_entity_uuid=source_entity_uuid)
            return cls(
                uuid=source_entity_uuid,
                source_entity_uuid=source_entity_uuid,
                name=name,
                appearance=appearance)
        else:
            ability_scores = AbilityScores.create(source_entity_uuid=source_entity_uuid, config=config.ability_scores)
            skill_set = SkillSet.create(source_entity_uuid=source_entity_uuid, config=config.skill_set)
            saving_throws = SavingThrowSet.create(source_entity_uuid=source_entity_uuid, config=config.saving_throws)
            health = Health.create(source_entity_uuid=source_entity_uuid, config=config.health)
            equipment = Equipment.create(source_entity_uuid=source_entity_uuid, config=config.equipment)
            senses = Senses.create(source_entity_uuid=source_entity_uuid, position=config.position)
            appearance = Appearance.create(source_entity_uuid=source_entity_uuid, config=config.appearance)
            action_economy = ActionEconomy.create(source_entity_uuid=source_entity_uuid, config=config.action_economy)
            proficiency_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.proficiency_bonus)
            for modifier in config.proficiency_bonus_modifiers:
                proficiency_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            dex_mod = ability_scores.get_ability("dexterity").modifier
            initiative = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=dex_mod, value_name="initiative")
            for modifier in config.initiative_modifiers:
                initiative.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            spellcasting = SpellcastingBlock.create(
                source_entity_uuid=source_entity_uuid,
                config=config.spellcasting
            )

            inventory = Inventory(source_entity_uuid=source_entity_uuid)

            return cls(
                uuid=source_entity_uuid,
                source_entity_uuid=source_entity_uuid,
                name=name,
                description=description,
                ability_scores=ability_scores,
                skill_set=skill_set,
                saving_throws=saving_throws,
                health=health,
                equipment=equipment,
                senses=senses,
                inventory=inventory,
                appearance=appearance,
                action_economy=action_economy,
                proficiency_bonus=proficiency_bonus,
                initiative=initiative,
                spellcasting=spellcasting,
                position=config.position,
                sprite_name=config.sprite_name,
                faction=config.faction,
                weight=config.weight,
                creature_type=config.creature_type,
                size=config.size,
                has_ordinary_sight=config.has_ordinary_sight,
                requires_breathing=config.requires_breathing,
                swimming_speed=config.swimming_speed,
                uses_death_saves=config.uses_death_saves,
                death_save_successes=config.death_save_successes,
                death_save_failures=config.death_save_failures,
                is_stable=config.is_stable
            )

    def _set_position(self, new_position: Tuple[int, int]) -> None:
        """Set entity and senses position without updating registry indexes.

        Args:
            new_position: Position to store on the entity and senses block.
        """
        self.position = new_position
        self.senses.position = new_position

    def move(self, new_position: Tuple[int, int], update_senses: bool = True) -> None:
        """Move the entity through the registry-aware position path.

        Args:
            new_position: Destination grid position.
            update_senses: Whether to refresh all entity senses after moving.
        """
        Entity.update_entity_position(self, new_position)
        if update_senses:
            Entity.update_all_entities_senses()

    def get_target_entity(self, copy: bool = False) -> Optional['Entity']:
        """Return the currently targeted entity.

        Args:
            copy: Whether to return a deep copy instead of the live entity.

        Returns:
            The targeted entity, a copy of it, or `None` when no target is set.
        """
        if self.target_entity_uuid is None:
            return None
        target_entity = Entity.get(self.target_entity_uuid)
        assert isinstance(target_entity, Entity)
        return target_entity if not copy else target_entity.model_copy(deep=True)

    @contextmanager
    def _temporary_target(self, target_entity_uuid: UUID) -> Iterator[None]:
        """Bind one cross-entity evaluation target and restore prior context.

        Args:
            target_entity_uuid: Entity UUID used while contextual values are evaluated.

        Yields:
            Control while this entity and its child values target the supplied entity.
        """
        previous_uuid = self.target_entity_uuid
        previous_name = self.target_entity_name
        changed = previous_uuid != target_entity_uuid
        if changed:
            self.set_target_entity(target_entity_uuid)
        try:
            yield
        finally:
            if changed:
                self.clear_target_entity()
                if previous_uuid is not None:
                    self.set_target_entity(previous_uuid, previous_name)

    def check_condition_immunity(self, condition_name: str, condition: Optional[BaseCondition] = None) -> bool:
        """Evaluate static and contextual immunity for a condition.

        Args:
            condition_name: Condition name to check.
            condition: Optional incoming condition used by contextual immunity
                checks.

        Returns:
            True when the entity is immune in its current target/context state.
        """
        for static_immunity in self.condition_immunities:
            if static_immunity[0] == condition_name:
                return True
        condition_contextual_immunities = self.contextual_condition_immunities.get(condition_name, [])
        immunity_context = dict(self.context or {})
        if condition is not None:
            immunity_context.setdefault("condition", condition)
            immunity_context.setdefault("condition_tags", condition.tags)
        for _, immunity_check in condition_contextual_immunities:
            if immunity_check(self, self.get_target_entity(), immunity_context):
                return True
        return False

    def add_condition(self, condition: BaseCondition, context: Optional[Dict[str, Any]] = None, check_save_throw: bool = True, parent_event: Optional[Event] = None)  -> Optional[Event]:
        """Apply an entity condition with immunities, saves, and combat-log names.

        Args:
            condition: Condition to apply.
            context: Optional runtime context for the condition.
            check_save_throw: Whether to honor the condition's application save.
            parent_event: Optional parent event for condition event lineage.

        Returns:
            Completion or cancellation event from the condition application, or
            `None` when no declaration event exists.
        """
        if condition.name is None:
            raise ValueError("BaseCondition name is not set")
        if condition.target_entity_uuid is None:
            condition.target_entity_uuid = self.uuid
        if context is not None:
            condition.set_context(context)

        condition.target_entity_name = self.name
        source = Entity.get(condition.source_entity_uuid)
        if source and isinstance(source, Entity):
            condition.source_entity_name = source.name

        declaration_event = condition.declare_event(parent_event)

        if self.check_condition_immunity(condition.name, condition=condition):
            target_name = self.name
            condition_name = condition.name
            entry = CombatLogEntry(
                entry_type=CombatLogEntryType.CONDITION_APPLIED,
                source_name=target_name,
                source_uuid=str(self.uuid),
                target_name=target_name,
                target_uuid=str(self.uuid),
                compact=f"{{yellow:{target_name}}} is **immune** to {condition_name}",
                verbose=f"{{yellow:{target_name}}} is **immune** to {condition_name}",
                detailed=f"{{yellow:{target_name}}} is **immune** to {condition_name}",
                success=False,
            )
            EventQueue.push_combat_log(entry, self.uuid)

            if declaration_event is not None:
                return declaration_event.cancel(status_message=f"Condition {condition.name} is immune")
            else:
                return None
        if check_save_throw and condition.application_saving_throw is not None:
            (_, _, success) = self.saving_throw(condition.application_saving_throw)
            if success:
                if declaration_event is not None:
                    return declaration_event.cancel(status_message=f"Target passed the {condition.application_saving_throw.ability_name} saving throw with")
                else:
                    return None
        condition_applied = condition.apply(declaration_event=declaration_event)
        if condition_applied and not condition_applied.canceled:
            if condition.name in self.active_conditions:
                self.remove_condition(condition.name)
            self.active_conditions[condition.name] = condition
            self.active_conditions_by_uuid[condition.uuid] = condition
            self.active_conditions_by_source[condition.source_entity_uuid].append(condition.name)
        return condition_applied

    def advance_duration_condition(self, condition_name: str, skip_save_throw: bool = False) -> bool:
        """Progress a condition's duration and remove if expired.

        Handles saving throw checks for conditional removal. Uses Entity's
        remove_condition() for full tree traversal on expiration.

        Args:
            condition_name: Name of the condition to progress
            skip_save_throw: If True, skip removal saving throw check

        Returns:
            True if condition was removed by save or expiration.
        """
        condition = self.active_conditions.get(condition_name)
        if condition is None:
            return False

        if not skip_save_throw and condition.removal_saving_throw is not None:
            (_, _, success) = self.saving_throw(condition.removal_saving_throw)
            if success:
                self.remove_condition(condition_name)
                return True

        expired = condition.progress()
        if expired:
            self.remove_condition(condition_name, expire=True)
        return expired

    def reduce_condition_level(
        self,
        condition_name: str,
        amount: int = 1,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Reduce a levelled condition while preserving cleanup semantics.

        Args:
            condition_name: Name of the active condition to reduce.
            amount: Number of levels to remove.
            parent_event: Optional parent event for removal/application lineage.

        Returns:
            True if a supported levelled condition was reduced or removed.

        Raises:
            ValueError: If `amount` is less than 1.
        """
        if amount < 1:
            raise ValueError("amount must be at least 1")
        condition = self.active_conditions.get(condition_name)
        if condition is None or not condition.supports_level_reduction():
            return False

        replacement = condition.get_reduced_level_condition(amount)
        self.remove_condition(condition_name, parent_event=parent_event)
        if replacement is not None:
            self.add_condition(replacement, check_save_throw=False, parent_event=parent_event)
        return True

    def reduce_condition_by_tag(
        self,
        condition_tag: ConditionTag,
        amount: int = 1,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Reduce the first active levelled condition carrying a tag.

        Args:
            condition_tag: Tag identifying the condition family to reduce.
            amount: Number of levels to remove.
            parent_event: Optional parent event for removal/application lineage.

        Returns:
            True if a matching supported condition was reduced or removed.
        """
        for condition_name, condition in list(self.active_conditions.items()):
            if condition_tag in condition.tags and condition.supports_level_reduction():
                return self.reduce_condition_level(condition_name, amount, parent_event)
        return False

    def _expire_long_rest_conditions_on_block(self, block: BaseBlock) -> None:
        """Mark long-rest durations on a block and remove expired conditions."""
        for condition_name, condition in list(block.active_conditions.items()):
            condition.long_rest()
            if condition.duration.is_expired:
                block.remove_condition(condition_name, expire=True)

    def on_short_rest(self) -> None:
        """Apply entity-level short-rest recovery."""
        self.action_economy.on_short_rest()

    def spend_hit_dice(
        self,
        count: int = 1,
        hit_dice_index: int = 0,
    ) -> List[HitDiceHealingResult]:
        """Spend hit dice for short-rest healing.

        Args:
            count: Number of hit dice to spend.
            hit_dice_index: Index of the hit-dice block to spend from.

        Returns:
            Hit-dice healing results with actual HP restored.

        Raises:
            ValueError: If count is invalid, the entity cannot benefit, or not
                enough hit dice remain.
        """
        if count < 1:
            raise ValueError("count must be at least 1")
        if not self.has_hp or "Dead" in self.active_conditions:
            raise ValueError("Entity must have at least 1 HP to spend hit dice")
        hit_die = self.health.get_hit_dice(hit_dice_index)
        if count > hit_die.available_hit_dice:
            raise ValueError(f"Not enough hit dice available to spend {count}")

        constitution_modifier = self.ability_scores.get_ability("constitution").get_combined_values().normalized_score
        results: List[HitDiceHealingResult] = []
        for _ in range(count):
            roll_result = self.health.spend_hit_die(
                constitution_modifier=constitution_modifier,
                hit_dice_index=hit_dice_index,
            )
            actual_healing = self.receive_healing(
                roll_result.total_healing,
                source_entity_uuid=self.uuid,
                source_description=(
                    f"Short Rest Hit Die d{roll_result.die_value}: "
                    f"{roll_result.roll} + {roll_result.constitution_modifier}"
                ),
            )
            results.append(roll_result.model_copy(update={"actual_healing": actual_healing}))
        return results

    def on_long_rest(self) -> bool:
        """Apply entity-level long-rest recovery.

        The current engine lifecycle restores spell slots, recharges rest-based
        resources, expires long-rest condition durations, restores lost normal
        HP, clears temporary HP, and reduces Exhaustion by one level.

        Returns:
            True when the entity had at least 1 HP and gained long-rest
            benefits, otherwise False.
        """
        if not self.has_hp or "Dead" in self.active_conditions:
            return False

        self.action_economy.reset_all_costs()
        self.action_economy.reset_spell_slot_costs()
        self.action_economy.on_long_rest()
        self._expire_long_rest_conditions_on_block(self)
        for item in self.equipment.get_all_equipped_items():
            self._expire_long_rest_conditions_on_block(item)
        for item in self.inventory.items.values():
            self._expire_long_rest_conditions_on_block(item)
        self.reduce_condition_by_tag(ConditionTag.EXHAUSTION)
        self.health.on_long_rest()
        return True

    def get_max_hp(self) -> int:
        """Return maximum normal HP before temporary hit points and damage."""
        con_modifier = self.ability_scores.get_ability("constitution").get_combined_values()
        return self.health.get_max_hit_dices_points(
            constitution_modifier=con_modifier.normalized_score
        ) + self.health.max_hit_points_bonus.normalized_score

    def get_normal_hp(self) -> int:
        """Return current normal HP before temporary hit points."""
        return self.get_max_hp() - self.health.damage_taken

    @property
    def is_dying(self) -> bool:
        """Whether this entity is alive but at 0 HP under death-save rules."""
        return (
            self.uses_death_saves
            and "Dead" not in self.active_conditions
            and self.get_normal_hp() <= 0
            and "Unconscious" in self.active_conditions
        )

    @property
    def is_encounter_alive(self) -> bool:
        """Whether encounter turn order should still treat this entity as alive."""
        return "Dead" not in self.active_conditions and (self.has_hp or self.is_dying)

    def reset_death_save_state(self) -> None:
        """Clear player-style death-save counters and stable state."""
        self.death_save_successes = 0
        self.death_save_failures = 0
        self.is_stable = False

    def _set_normal_hp(self, hit_points: int) -> None:
        """Set normal HP while preserving the current maximum HP."""
        self.health.damage_taken = max(0, self.get_max_hp() - hit_points)

    def stabilize(self, parent_event: Optional[Event] = None) -> bool:
        """Stabilize a player-style dying entity at 0 HP.

        Args:
            parent_event: Optional event that caused stabilization.

        Returns:
            True when the entity is now stable.
        """
        if not self.uses_death_saves or "Dead" in self.active_conditions or self.get_normal_hp() > 0:
            return False
        self._set_normal_hp(0)
        self.death_save_successes = 0
        self.death_save_failures = 0
        self.is_stable = True
        if "Unconscious" not in self.active_conditions:
            from dnd.conditions import Unconscious
            self.add_condition(
                Unconscious(source_entity_uuid=self.uuid, target_entity_uuid=self.uuid),
                check_save_throw=False,
                parent_event=parent_event,
            )
        return True

    def enter_dying_state(self, parent_event: Optional[Event] = None) -> None:
        """Put a player-style entity at 0 HP and apply Unconscious."""
        self._set_normal_hp(0)
        self.reset_death_save_state()
        if "Unconscious" not in self.active_conditions:
            from dnd.conditions import Unconscious
            self.add_condition(
                Unconscious(source_entity_uuid=self.uuid, target_entity_uuid=self.uuid),
                check_save_throw=False,
                parent_event=parent_event,
            )

    def _clear_dying_state_after_healing(self, parent_event: Optional[Event] = None) -> None:
        """Clear death-save state when true healing restores positive HP."""
        if not self.uses_death_saves or self.get_normal_hp() <= 0:
            return
        self.reset_death_save_state()
        if "Unconscious" in self.active_conditions:
            self.remove_condition("Unconscious", parent_event=parent_event)

    def _fire_death_event(
        self,
        source_entity_uuid: UUID,
        parent_event: Optional[UUID] = None,
        encounter_uuid: Optional[UUID] = None,
    ) -> DeathEvent:
        """Fire the standard death event through completion."""
        killer = Entity.get(source_entity_uuid)
        killer_name = killer.name if killer and isinstance(killer, Entity) else ""
        if self.uses_death_saves:
            self.is_stable = False
            self.death_save_successes = 0
            self.death_save_failures = min(3, max(3, self.death_save_failures))
            if "Unconscious" in self.active_conditions:
                self.remove_condition("Unconscious")
        death_event = DeathEvent(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=self.uuid,
            entity_uuid=self.uuid,
            entity_name=self.name,
            killer_uuid=source_entity_uuid,
            killer_name=killer_name,
            final_hp=self.get_normal_hp(),
            encounter_uuid=encounter_uuid,
            phase=EventPhase.DECLARATION,
            parent_event=parent_event
        )
        death_event = death_event.phase_to(EventPhase.EXECUTION)
        death_event = death_event.phase_to(EventPhase.EFFECT)
        return death_event.phase_to(EventPhase.COMPLETION)

    def add_death_save_failure(
        self,
        count: int = 1,
        source_entity_uuid: Optional[UUID] = None,
        parent_event: Optional[UUID] = None,
    ) -> Optional[DeathEvent]:
        """Apply death-save failures and kill at three failures.

        Args:
            count: Number of failures to add.
            source_entity_uuid: Entity or effect causing the failure.
            parent_event: Optional parent event UUID for death lineage.

        Returns:
            Completed `DeathEvent` if this failure kills the entity.
        """
        if count < 1:
            raise ValueError("count must be at least 1")
        if not self.uses_death_saves or "Dead" in self.active_conditions:
            return None
        self.is_stable = False
        self.death_save_failures = min(3, self.death_save_failures + count)
        if self.death_save_failures >= 3:
            return self._fire_death_event(
                source_entity_uuid=source_entity_uuid or self.uuid,
                parent_event=parent_event,
            )
        return None

    def make_death_save(
        self,
        parent_event: Optional[UUID] = None,
        encounter_uuid: Optional[UUID] = None,
        round_number: int = 0,
        turn_index: int = 0,
    ) -> Optional[DeathSaveEvent]:
        """Roll and resolve one player-style death saving throw.

        Args:
            parent_event: Optional parent event UUID.
            encounter_uuid: Encounter UUID for context.
            round_number: Current encounter round.
            turn_index: Current initiative index.

        Returns:
            Completed death-save event, or `None` when no death save is due.
        """
        if not self.is_dying or self.is_stable:
            return None

        event = DeathSaveEvent(
            source_entity_uuid=self.uuid,
            source_entity_name=self.name,
            target_entity_uuid=self.uuid,
            target_entity_name=self.name,
            entity_uuid=self.uuid,
            entity_name=self.name,
            phase=EventPhase.DECLARATION,
            parent_event=parent_event,
            context={
                "encounter_uuid": str(encounter_uuid) if encounter_uuid else None,
                "round_number": round_number,
                "turn_index": turn_index,
            },
        )
        event = event.phase_to(EventPhase.EXECUTION)

        bonus = ModifiableValue.create(
            source_entity_uuid=self.uuid,
            target_entity_uuid=self.uuid,
            base_value=0,
            value_name="Death Saving Throw",
        )
        roll, roll_event = self.roll_d20_event(
            bonus,
            RollType.SAVE,
            context={"death_save": True},
            parent_event=event.uuid,
        )
        natural_roll = get_natural_roll(roll)
        succeeded = natural_roll >= 10
        became_stable = False
        regained_hit_point = False
        died = False

        if natural_roll == 20:
            self.receive_healing(
                1,
                source_entity_uuid=self.uuid,
                source_description="Death Saving Throw",
                parent_event=event.uuid,
            )
            regained_hit_point = True
            succeeded = True
        elif natural_roll == 1:
            died = self.add_death_save_failure(2, self.uuid, event.uuid) is not None
        elif succeeded:
            self.death_save_successes = min(3, self.death_save_successes + 1)
            if self.death_save_successes >= 3:
                became_stable = self.stabilize(parent_event=event)
        else:
            died = self.add_death_save_failure(1, self.uuid, event.uuid) is not None

        roll_event = roll_event.model_copy(update={"dc": 10, "result": succeeded})
        roll_event.phase_to(EventPhase.COMPLETION)

        event = event.phase_to(
            EventPhase.EFFECT,
            roll=roll,
            natural_roll=natural_roll,
            succeeded=succeeded,
            successes=self.death_save_successes,
            failures=self.death_save_failures,
            became_stable=became_stable,
            regained_hit_point=regained_hit_point,
            died=died,
        )
        return event.phase_to(EventPhase.COMPLETION)

    def revive(
        self,
        hit_points: int = 1,
        reduce_exhaustion: bool = True,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Restore a dead entity to life as a rules primitive.

        Args:
            hit_points: Minimum HP total after revival.
            reduce_exhaustion: Whether revival reduces Exhaustion by one level.
            parent_event: Optional parent event for condition cleanup lineage.

        Returns:
            True if the entity was dead or at 0 HP and is now revived.

        Raises:
            ValueError: If `hit_points` is less than 1.
        """
        if hit_points < 1:
            raise ValueError("hit_points must be at least 1")
        was_dead = "Dead" in self.active_conditions or not self.has_hp
        if not was_dead:
            return False

        if "Dead" in self.active_conditions:
            self.remove_condition("Dead", parent_event=parent_event)

        hp_ceiling = self.get_hp() + self.health.damage_taken
        self.health.damage_taken = max(0, hp_ceiling - hit_points)
        self._clear_dying_state_after_healing(parent_event=parent_event)
        self.non_blocking = False
        get_map().invalidate_occupancy_paths()
        if reduce_exhaustion:
            self.reduce_condition_by_tag(ConditionTag.EXHAUSTION, parent_event=parent_event)
        return True

    def on_turn_start(self, encounter_uuid: Optional[UUID] = None, round_number: int = 0, turn_index: int = 0) -> TurnStartEvent:
        """
        Handle turn start for this entity.

        Called by Encounter.start_turn(). Consolidates turn-start logic:
        1. Fire TurnStartEvent through phases (handlers can respond at EXECUTION)
        2. Advance condition durations
        3. Reset and recharge action economy

        Args:
            encounter_uuid: UUID of the encounter (optional for standalone use)
            round_number: Current round number
            turn_index: Position in initiative order

        Returns:
            TurnStartEvent after all phases complete
        """

        event = TurnStartEvent(
            source_entity_uuid=self.uuid,
            source_entity_name=self.name,
            target_entity_uuid=self.uuid,
            entity_uuid=self.uuid,
            encounter_uuid=encounter_uuid or self.uuid,
            round_number=round_number,
            turn_index=turn_index,
            phase=EventPhase.DECLARATION
        )

        event = event.phase_to(EventPhase.EXECUTION)

        self.make_death_save(
            parent_event=event.uuid,
            encounter_uuid=encounter_uuid,
            round_number=round_number,
            turn_index=turn_index,
        )

        condition_names = list(self.active_conditions.keys())
        for condition_name in condition_names:
            self.advance_duration_condition(condition_name)

        for item in self.equipment.get_all_equipped_items():
            for cond_name in list(item.active_conditions.keys()):
                item.advance_duration(cond_name)
        for item in self.inventory.items.values():
            for cond_name in list(item.active_conditions.keys()):
                item.advance_duration(cond_name)

        self.action_economy.reset_all_costs()
        self.action_economy.on_turn_start()

        self.is_my_turn = True

        actions = self.action_economy.actions.normalized_score
        bonus_actions = self.action_economy.bonus_actions.normalized_score
        movement = self.action_economy.movement.normalized_score
        reactions = self.action_economy.reactions.normalized_score

        event = event.phase_to(
            EventPhase.EFFECT,
            actions_available=actions,
            bonus_actions_available=bonus_actions,
            movement_available=movement,
            reaction_available=reactions
        )
        event = event.phase_to(EventPhase.COMPLETION)

        return event

    def on_turn_end(self, encounter_uuid: Optional[UUID] = None, round_number: int = 0, turn_index: int = 0) -> TurnEndEvent:
        """
        Handle turn end for this entity.

        Called by Encounter.end_turn(). Provides phase progression for handlers.

        Phase sequence:
        1. DECLARATION - Event created
        2. EXECUTION - Handlers run (e.g., rage maintenance check)
        3. EFFECT - Post-handler effects
        4. COMPLETION - Turn officially ends

        Note: Condition durations advance at TURN_START, not TURN_END.

        Args:
            encounter_uuid: UUID of the encounter (optional for standalone use)
            round_number: Current round number
            turn_index: Position in initiative order

        Returns:
            TurnEndEvent after all phases complete
        """

        actions_used = max(0, 1 - self.action_economy.actions.normalized_score)
        bonus_used = max(0, 1 - self.action_economy.bonus_actions.normalized_score)
        base_mod = self.action_economy.movement.get_base_modifier()
        base_movement = base_mod.value if base_mod else 30
        movement_used = max(0, base_movement - self.action_economy.movement.normalized_score)

        event = TurnEndEvent(
            source_entity_uuid=self.uuid,
            source_entity_name=self.name,
            target_entity_uuid=self.uuid,
            entity_uuid=self.uuid,
            encounter_uuid=encounter_uuid or self.uuid,
            round_number=round_number,
            turn_index=turn_index,
            actions_used=actions_used,
            bonus_actions_used=bonus_used,
            movement_used=movement_used,
            phase=EventPhase.DECLARATION
        )

        event = event.phase_to(EventPhase.EXECUTION)

        event = event.phase_to(EventPhase.EFFECT)

        event = event.phase_to(EventPhase.COMPLETION)

        self.is_my_turn = False

        return event

    def _get_bonuses_for_skill(self, skill_name: SkillName) -> Tuple[ModifiableValue, ModifiableValue, ModifiableValue]:
        """Return component values that make up an entity skill bonus.

        Args:
            skill_name: Skill to assemble.

        Returns:
            Normalized proficiency, skill bonus, and ability modifier values.
        """
        proficiency_bonus = self.proficiency_bonus
        skill = self.skill_set.get_skill(skill_name)
        skill_bonus = skill.skill_bonus
        proficiency_bonus_multiplier_callable = skill._get_proficiency_converter()
        ability_name = skill.ability
        ability_bonus = self.ability_scores.get_ability(ability_name).get_combined_values()
        normalized_proficiency_bonus = proficiency_bonus.model_copy(deep=True)
        normalized_proficiency_bonus.update_normalizers(proficiency_bonus_multiplier_callable)
        return normalized_proficiency_bonus, skill_bonus, ability_bonus

    def _get_bonuses_for_saving_throw(self, ability_name: AbilityName) -> Tuple[ModifiableValue, ModifiableValue, ModifiableValue]:
        """Return component values that make up an entity saving throw bonus.

        Args:
            ability_name: Ability save to assemble.

        Returns:
            Normalized proficiency, save bonus, and ability modifier values.
        """
        saving_throw = self.saving_throws.get_saving_throw(ability_name)
        saving_throw_bonus = saving_throw.bonus
        proficiency_bonus_multiplier_callable = saving_throw._get_proficiency_converter()
        proficiency_bonus = self.proficiency_bonus
        ability_bonus = self.ability_scores.get_ability(ability_name).get_combined_values()

        normalized_proficiency_bonus = proficiency_bonus.model_copy(deep=True)
        normalized_proficiency_bonus.update_normalizers(proficiency_bonus_multiplier_callable)
        return normalized_proficiency_bonus, saving_throw_bonus, ability_bonus

    def _get_attack_bonuses(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN, override_ability: Optional[AbilityName] = None) -> Tuple[ModifiableValue, ModifiableValue, List[ModifiableValue], List[ModifiableValue], Range]:
        """Return component values that make up a weapon attack bonus.

        Args:
            weapon_slot: Equipment slot used for the attack.
            override_ability: Optional ability to use instead of weapon rules.

        Returns:
            Proficiency value, weapon bonus, attack bonus list, ability bonus
            list, and weapon range.
        """
        weapon = self.equipment._get_weapon_by_slot(weapon_slot)

        ability_bonuses: List[ModifiableValue] = []
        attack_bonuses: List[ModifiableValue] = [self.equipment.attack_bonus]

        if override_ability is not None:
            ability = self.ability_scores.get_ability(override_ability)
            ability_bonuses.append(ability.get_combined_values())
            if weapon is None or isinstance(weapon, Shield):
                weapon_bonus = self.equipment.unarmed_attack_bonus
                attack_bonuses.append(self.equipment.melee_attack_bonus)
                range = Range(type=RangeType.REACH, normal=5)
            else:
                weapon_bonus = weapon.attack_bonus
                range = weapon.range
                if range.type == RangeType.RANGE:
                    attack_bonuses.append(self.equipment.ranged_attack_bonus)
                else:
                    attack_bonuses.append(self.equipment.melee_attack_bonus)
        else:
            dexterity_bonus = self.ability_scores.get_ability("dexterity").get_combined_values()
            strength_bonus = self.ability_scores.get_ability("strength").get_combined_values()
            if weapon is None or isinstance(weapon, Shield):
                weapon_bonus = self.equipment.unarmed_attack_bonus
                attack_bonuses.append(self.equipment.melee_attack_bonus)
                ability_bonuses.append(strength_bonus)
                range = Range(type=RangeType.REACH, normal=5)
            else:
                weapon_bonus = weapon.attack_bonus
                range = weapon.range
                if range.type == RangeType.RANGE:

                    attack_bonuses.append(self.equipment.ranged_attack_bonus)
                    ability_bonuses.append(dexterity_bonus)
                elif range.type == RangeType.REACH and WeaponProperty.FINESSE in weapon.properties:
                    attack_bonuses.append(self.equipment.melee_attack_bonus)
                    if strength_bonus.normalized_score >= dexterity_bonus.normalized_score:
                        ability_bonuses.append(strength_bonus)
                    else:
                        ability_bonuses.append(dexterity_bonus)
                else:
                    attack_bonuses.append(self.equipment.melee_attack_bonus)
                    ability_bonuses.append(strength_bonus)
        proficiency_bonus = self.proficiency_bonus

        return proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, range

    def saving_throw_bonus(self, target_entity_uuid: Optional[UUID], ability_name: AbilityName) -> ModifiableValue:
        """Build the complete saving throw bonus for an ability.

        Args:
            target_entity_uuid: Optional opposing entity whose outgoing
                modifiers should be propagated.
            ability_name: Saving throw ability.

        Returns:
            Combined saving throw bonus.
        """
        if target_entity_uuid is None or target_entity_uuid == self.uuid:
            bonuses = self._get_bonuses_for_saving_throw(ability_name)
            return bonuses[0].combine_values(list(bonuses)[1:]).model_copy(deep=True)

        target_entity = Entity.get(target_entity_uuid)
        if not isinstance(target_entity, Entity):
            raise ValueError(f"Target entity {target_entity_uuid} not found")

        with self._temporary_target(target_entity_uuid), target_entity._temporary_target(self.uuid):
            source_bonuses = self._get_bonuses_for_saving_throw(ability_name)
            target_bonuses = target_entity._get_bonuses_for_saving_throw(ability_name)
            for source_bonus, target_bonus in zip(source_bonuses, target_bonuses):
                source_bonus.set_from_target(target_bonus)
            try:
                return source_bonuses[0].combine_values(list(source_bonuses)[1:]).model_copy(deep=True)
            finally:
                for source_bonus in source_bonuses:
                    source_bonus.reset_from_target()

    def skill_bonus(self, target_entity_uuid: Optional[UUID], skill_name: SkillName) -> ModifiableValue:
        """Build the complete skill bonus for a skill.

        Args:
            target_entity_uuid: Optional opposing entity whose outgoing
                modifiers should be propagated.
            skill_name: Skill to assemble.

        Returns:
            Combined skill bonus.
        """
        if target_entity_uuid is None or target_entity_uuid == self.uuid:
            bonuses = self._get_bonuses_for_skill(skill_name)
            return bonuses[0].combine_values(list(bonuses)[1:]).model_copy(deep=True)

        target_entity = Entity.get(target_entity_uuid)
        if not isinstance(target_entity, Entity):
            raise ValueError(f"Target entity {target_entity_uuid} not found")

        with self._temporary_target(target_entity_uuid), target_entity._temporary_target(self.uuid):
            source_bonuses = self._get_bonuses_for_skill(skill_name)
            target_bonuses = target_entity._get_bonuses_for_skill(skill_name)
            for source_bonus, target_bonus in zip(source_bonuses, target_bonuses):
                source_bonus.set_from_target(target_bonus)
            try:
                return source_bonuses[0].combine_values(list(source_bonuses)[1:]).model_copy(deep=True)
            finally:
                for source_bonus in source_bonuses:
                    source_bonus.reset_from_target()

    def passive_skill(self, skill_name: SkillName) -> int:
        """Calculate passive skill score for a skill.

        Advantage adds 5 and disadvantage subtracts 5 from the passive score.

        Args:
            skill_name: Skill to calculate.

        Returns:
            Passive score for the skill.
        """
        timing = action_timing_enabled()
        started = time.perf_counter() if timing else 0.0
        skill_bonuses = self._get_bonuses_for_skill(skill_name)
        skill_bonus = skill_bonuses[0].combine_values(list(skill_bonuses[1:]))
        if timing:
            record_action_timing(f"passive_skill.{skill_name}.skill_bonus_ms", started)

        started = time.perf_counter() if timing else 0.0
        base = 10 + skill_bonus.normalized_score
        if timing:
            record_action_timing(f"passive_skill.{skill_name}.normalized_score_ms", started)

        started = time.perf_counter() if timing else 0.0
        if skill_bonus.advantage == AdvantageStatus.ADVANTAGE:
            base += 5
        elif skill_bonus.advantage == AdvantageStatus.DISADVANTAGE:
            base -= 5
        if timing:
            record_action_timing(f"passive_skill.{skill_name}.advantage_ms", started)

        return base

    def get_passive_perception(self) -> int:
        """Entity's passive perception from skill system."""
        return self.passive_skill("perception")

    def can_bypass_invisibility(self) -> bool:
        """Entity can bypass invisibility with special senses."""
        return (self.senses.has_sense(SensesType.TRUESIGHT) or
                self.senses.has_sense(SensesType.BLINDSIGHT) or
                self.senses.has_sense(SensesType.TREMORSENSE) or
                self.senses.has_sense(SensesType.SEE_INVISIBLE))

    def can_pierce_magical_darkness(self) -> bool:
        """Entity can see through magical darkness with TRUESIGHT or DEVILS_SIGHT."""
        return (self.senses.has_sense(SensesType.TRUESIGHT) or
                self.senses.has_sense(SensesType.DEVILS_SIGHT))

    def can_see_visual_effects(self) -> bool:
        """Whether this entity can currently see visual effects at all."""
        if "Blinded" in self.active_conditions:
            return False
        if "Unconscious" in self.active_conditions:
            return False
        return self.has_ordinary_sight or self.senses.has_sense(SensesType.TRUESIGHT)

    def get_sense_modes(self) -> List[SenseMode]:
        """Entity relays to its Senses block for sense modes."""
        return self.senses.get_sense_modes()

    def skill_bonus_cross(self, target_entity_uuid: UUID, skill_name: SkillName) -> Tuple[ModifiableValue, ModifiableValue]:
        target_entity = Entity.get(target_entity_uuid)
        if not isinstance(target_entity, Entity):
            raise ValueError(f"Target entity {target_entity_uuid} not found")

        with self._temporary_target(target_entity_uuid), target_entity._temporary_target(self.uuid):
            source_bonuses = self._get_bonuses_for_skill(skill_name)
            target_bonuses = target_entity._get_bonuses_for_skill(skill_name)
            for source_bonus, target_bonus in zip(source_bonuses, target_bonuses):
                target_bonus.set_from_target(source_bonus)
                source_bonus.set_from_target(target_bonus)
            try:
                source_total = source_bonuses[0].combine_values(list(source_bonuses)[1:]).model_copy(deep=True)
                target_total = target_bonuses[0].combine_values(list(target_bonuses)[1:]).model_copy(deep=True)
                return source_total, target_total
            finally:
                for source_bonus, target_bonus in zip(source_bonuses, target_bonuses):
                    source_bonus.reset_from_target()
                    target_bonus.reset_from_target()

    def ac_bonus(self, target_entity_uuid: Optional[UUID]=None) -> ModifiableValue:
        """Build the entity's armor class value.

        Args:
            target_entity_uuid: Optional entity targeting this armor class.

        Returns:
            Combined armor class value.
        """
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True

        if self.equipment.is_unarmored():
            unarmored_values = self.equipment.get_unarmored_ac_values()
            abilities = self.equipment.get_unarmored_abilities()
            ability_bonuses = [self.ability_scores.get_ability(ability).get_combined_values() for ability in abilities]
            ac_bonus = unarmored_values[0].combine_values(unarmored_values[1:]+ability_bonuses)
        else:
            armored_values = self.equipment.get_armored_ac_values()
            max_dexterity_bonus = self.equipment.get_armored_max_dex_bonus()
            combined_dexterity_bonus = self.ability_scores.get_ability("dexterity").get_combined_values()

            if max_dexterity_bonus is not None and combined_dexterity_bonus.normalized_score > max_dexterity_bonus.normalized_score:
                combined_dexterity_bonus = max_dexterity_bonus

            ac_bonus = armored_values[0].combine_values(armored_values[1:]+[combined_dexterity_bonus])

        if should_clear_target:
            self.clear_target_entity()
        return ac_bonus

    def attack_bonus(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN, target_entity_uuid: Optional[UUID] = None, override_ability: Optional[AbilityName] = None) -> ModifiableValue:
        """Build the entity's weapon attack bonus.

        Args:
            weapon_slot: Equipment slot used for the attack.
            target_entity_uuid: Optional target entity.
            override_ability: Optional ability to use instead of weapon rules.

        Returns:
            Combined weapon attack bonus.
        """
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True

        proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, _ = self._get_attack_bonuses(weapon_slot, override_ability=override_ability)
        bonuses = [weapon_bonus] + attack_bonuses + ability_bonuses
        source_attack_bonus = proficiency_bonus.combine_values(bonuses)

        if should_clear_target:
            self.clear_target_entity()
        return source_attack_bonus

    def weapon_attack_outcome_baseline(
        self,
        weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN,
        override_ability: Optional[AbilityName] = None,
    ) -> AttackRollBaseline:
        """Read actor-side weapon attack values without allocating engine objects.

        The baseline excludes target-owned AC and cross-entity modifiers. It is
        therefore safe to disclose in a subjective decision epoch and combine
        later only with target facts known to that observing session.

        Args:
            weapon_slot: Equipment slot used by the attack template.
            override_ability: Optional ability selected by the action rule.

        Returns:
            Actor-baseline attack bonus, advantage, and critical rules.
        """
        weapon = self.equipment._get_weapon_by_slot(weapon_slot)
        ability = self._weapon_attack_ability(
            weapon if isinstance(weapon, Weapon) else None,
            override_ability,
        )
        if isinstance(weapon, Weapon):
            weapon_bonus = weapon.attack_bonus
            typed_bonus = (
                self.equipment.ranged_attack_bonus
                if weapon.range.type == RangeType.RANGE
                else self.equipment.melee_attack_bonus
            )
        else:
            weapon_bonus = self.equipment.unarmed_attack_bonus
            typed_bonus = self.equipment.melee_attack_bonus
        components = (
            self.proficiency_bonus,
            weapon_bonus,
            self.equipment.attack_bonus,
            typed_bonus,
        )
        advantage_sum = ability.modifier_bonus.advantage_sum + sum(
            component.advantage_sum for component in components
        )
        if advantage_sum > 0:
            advantage = AdvantageStatus.ADVANTAGE
        elif advantage_sum < 0:
            advantage = AdvantageStatus.DISADVANTAGE
        else:
            advantage = AdvantageStatus.NONE
        return AttackRollBaseline(
            attack_bonus=ability.modifier + sum(
                component.normalized_score for component in components
            ),
            advantage=advantage,
            critical_threshold=self.get_crit_threshold(weapon_slot),
            critical_extra_dice=self.get_crit_extra_dice(weapon_slot),
        )

    def weapon_damage_outcome_baseline(
        self,
        weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN,
        override_ability: Optional[AbilityName] = None,
    ) -> tuple[DamageRollProfile, ...]:
        """Read actor-side weapon damage formulas without transient damage objects.

        Args:
            weapon_slot: Equipment slot used by the attack template.
            override_ability: Optional ability selected by the action rule.

        Returns:
            Immutable damage formulas representing one ordinary hit.
        """
        weapon = self.equipment._get_weapon_by_slot(weapon_slot)
        profiles: list[DamageRollProfile] = []
        if isinstance(weapon, Weapon):
            base_bonuses = [
                value
                for value in (weapon.damage_bonus, self.equipment.damage_bonus)
                if value is not None
            ]
            ability_bonus = 0
            if weapon_slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF):
                base_bonuses.append(
                    self.equipment.off_hand_ranged_ability_bonus
                    if weapon_slot == WeaponSlot.RANGED_OFF
                    else self.equipment.off_hand_melee_ability_bonus
                )
            else:
                ability_bonus = self._weapon_damage_ability(
                    weapon,
                    override_ability,
                ).modifier
            base_bonuses.append(
                self.equipment.ranged_damage_bonus
                if WeaponProperty.RANGED in weapon.properties
                else self.equipment.melee_damage_bonus
            )
            profiles.append(DamageRollProfile(
                dice_count=weapon.dice_numbers,
                die_size=weapon.damage_dice,
                flat_bonus=(
                    sum(value.normalized_score for value in base_bonuses)
                    + ability_bonus
                ),
                damage_type=weapon.damage_type.value,
            ))
            profiles.extend(
                DamageRollProfile(
                    dice_count=dice_count,
                    die_size=die_size,
                    flat_bonus=bonus.normalized_score,
                    damage_type=damage_type.value,
                )
                for die_size, dice_count, bonus, damage_type in zip(
                    weapon.extra_damage_dices,
                    weapon.extra_damage_dices_numbers,
                    weapon.extra_damage_bonus,
                    weapon.extra_damage_type,
                )
            )
        else:
            ability = self._weapon_damage_ability(None, override_ability)
            base_bonuses = (
                self.equipment.unarmed_damage_bonus,
                self.equipment.damage_bonus,
                self.equipment.melee_damage_bonus,
            )
            profiles.append(DamageRollProfile(
                dice_count=self.equipment.unarmed_dice_numbers,
                die_size=self.equipment.unarmed_damage_dice,
                flat_bonus=(
                    sum(value.normalized_score for value in base_bonuses)
                    + ability.modifier
                ),
                damage_type=self.equipment.unarmed_damage_type.value,
            ))
        profiles.extend(
            DamageRollProfile(
                dice_count=dice_count,
                die_size=die_size,
                flat_bonus=bonus.normalized_score,
                damage_type=damage_type.value,
            )
            for die_size, dice_count, bonus, damage_type in zip(
                self.equipment.extra_attack_damage_dices,
                self.equipment.extra_attack_damage_dices_numbers,
                self.equipment.extra_attack_damage_bonus,
                self.equipment.extra_attack_damage_type,
            )
        )
        size_dice = self.get_size_damage_dice()
        if size_dice > 0 and profiles:
            profiles.append(DamageRollProfile(
                dice_count=size_dice,
                die_size=4,
                damage_type=profiles[0].damage_type,
            ))
        return tuple(profiles)

    def _weapon_attack_ability(
        self,
        weapon: Optional[Weapon],
        override_ability: Optional[AbilityName],
    ) -> Any:
        """Return the ability block used by a weapon attack roll."""
        if override_ability is not None:
            return self.ability_scores.get_ability(override_ability)
        if weapon is None:
            return self.ability_scores.strength
        if weapon.range.type == RangeType.RANGE:
            return self.ability_scores.dexterity
        if WeaponProperty.FINESSE in weapon.properties:
            strength = self.ability_scores.strength
            dexterity = self.ability_scores.dexterity
            return strength if strength.modifier >= dexterity.modifier else dexterity
        return self.ability_scores.strength

    def _weapon_damage_ability(
        self,
        weapon: Optional[Weapon],
        override_ability: Optional[AbilityName],
    ) -> Any:
        """Return the ability block used by a weapon damage roll."""
        if override_ability is not None:
            return self.ability_scores.get_ability(override_ability)
        if weapon is None:
            strength = self.ability_scores.strength
            if WeaponProperty.FINESSE in self.equipment.unarmed_properties:
                dexterity = self.ability_scores.dexterity
                return strength if strength.modifier >= dexterity.modifier else dexterity
            return strength
        if WeaponProperty.RANGED in weapon.properties:
            return self.ability_scores.dexterity
        if WeaponProperty.FINESSE in weapon.properties:
            strength = self.ability_scores.strength
            dexterity = self.ability_scores.dexterity
            return strength if strength.modifier >= dexterity.modifier else dexterity
        return self.ability_scores.strength

    def get_crit_threshold(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> int:
        """Get the minimum natural roll needed for a critical hit.

        Args:
            weapon_slot: Weapon slot used to choose melee or ranged bonuses.

        Returns:
            Minimum natural d20 roll for a critical hit.
        """
        general = self.equipment.crit_threshold.normalized_score

        if weapon_slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF]:
            specific = self.equipment.crit_threshold_melee.normalized_score
        else:
            specific = self.equipment.crit_threshold_ranged.normalized_score

        return 20 - (general + specific)

    def get_crit_extra_dice(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> int:
        """Get the number of extra dice to roll on critical hits.

        Combines general extra dice with weapon-type specific extra dice.
        Used by Brutal Critical and similar features.

        Args:
            weapon_slot: The weapon slot being used for the attack.

        Returns:
            Extra dice count.
        """
        general = self.equipment.crit_extra_dice.normalized_score

        if weapon_slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF]:
            specific = self.equipment.crit_extra_dice_melee.normalized_score
        else:
            specific = self.equipment.crit_extra_dice_ranged.normalized_score

        return general + specific

    def get_size_damage_dice(self) -> int:
        """Return extra d4 weapon damage dice from creature size."""
        size_order = [Size.TINY, Size.SMALL, Size.MEDIUM, Size.LARGE, Size.HUGE, Size.GARGANTUAN]
        idx = size_order.index(self.size)
        return max(0, idx - 2)

    def get_damages(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN, target_entity_uuid: Optional[UUID] = None, override_ability: Optional[AbilityName] = None) -> List[Damage]:
        """Build weapon damage packets for this entity.

        Args:
            weapon_slot: Equipment slot used for the attack.
            target_entity_uuid: Optional target entity.
            override_ability: Optional ability to use instead of weapon rules.

        Returns:
            Damage packets for the weapon attack.
        """
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True
        damages = self.equipment.get_damages(weapon_slot, self.ability_scores, override_ability=override_ability)
        size_dice = self.get_size_damage_dice()
        if size_dice > 0 and damages:
            primary_type = damages[0].damage_type
            size_damage_bonus = ModifiableValue.create(
                source_entity_uuid=self.uuid,
                base_value=0,
                value_name="Size Damage Bonus",
            )
            damages.append(Damage(
                source_entity_uuid=self.uuid,
                target_entity_uuid=target_entity_uuid or self.target_entity_uuid,
                damage_dice=4,
                dice_numbers=size_dice,
                damage_bonus=size_damage_bonus,
                damage_type=primary_type,
            ))
        if should_clear_target:
            self.clear_target_entity()
        return damages

    def take_damage(self, damages: List[Damage], attack_outcome: AttackOutcome) -> List[DiceRoll]:
        """Roll and apply direct damage packets without TakeDamageEvent wrapping.

        Args:
            damages: Damage packet specifications.
            attack_outcome: Attack outcome used to choose normal or critical dice.

        Returns:
            Rolls produced by each damage packet.
        """

        rolls = []
        for damage in damages:
            dice = damage.get_dice(attack_outcome=attack_outcome)
            roll = dice.roll
            rolls.append(roll)
            self.health.take_damage(roll.total, damage.damage_type, source_entity_uuid=damage.source_entity_uuid)

        return rolls

    def _complete_damage_applied_event(
        self,
        *,
        source_entity_uuid: UUID,
        damage_type: DamageType,
        damages: List[Damage],
        effect_id: Optional[str],
        parent_event: TakeDamageEvent,
        normal_hit_point_damage: int,
        temporary_hit_point_damage: int,
    ) -> DamageAppliedEvent:
        """Emit the factual positive-damage boundary through completion.

        Args:
            source_entity_uuid: Entity or effect source that dealt the damage.
            damage_type: Primary damage type of the incoming packet.
            damages: Typed damage components carried by the incoming packet.
            effect_id: Stable identity of the source effect, when available.
            parent_event: Interruptible incoming damage event that caused this result.
            normal_hit_point_damage: Damage applied beyond temporary hit points.
            temporary_hit_point_damage: Temporary hit points consumed.

        Returns:
            Completed positive post-mitigation damage event.
        """
        applied_damage = normal_hit_point_damage + temporary_hit_point_damage
        event = DamageAppliedEvent(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=self.uuid,
            source_entity_name=(
                source.name
                if (source := Entity.get(source_entity_uuid)) is not None
                else None
            ),
            target_entity_name=self.name,
            applied_damage=applied_damage,
            normal_hit_point_damage=normal_hit_point_damage,
            temporary_hit_point_damage=temporary_hit_point_damage,
            resulting_normal_hp=self.get_normal_hp(),
            resulting_temporary_hp=max(0, self.health.temporary_hit_points.normalized_score),
            damage_type=damage_type,
            damages=damages,
            effect_id=effect_id,
            parent_event=parent_event.uuid,
            phase=EventPhase.DECLARATION,
        )
        event = event.phase_to(EventPhase.EXECUTION)
        event = event.phase_to(EventPhase.EFFECT)
        return event.phase_to(EventPhase.COMPLETION)

    def preview_take_damage(self, event: TakeDamageEvent) -> DamageApplicationPreview:
        """Preview an incoming damage event against current defenses.

        Args:
            event: Interruptible incoming damage packet after earlier handlers.

        Returns:
            Typed post-mitigation preview without mutating health state.

        Raises:
            ValueError: If the event carries no typed damage component.
        """
        use_damage_components = (
            event.final_damage is None
            and len(event.damage_rolls) == len(event.damages)
            and len(event.damages) > 1
        )
        if use_damage_components:
            return self.health.preview_damage_components(
                [
                    (roll.total, damage.damage_type)
                    for roll, damage in zip(event.damage_rolls, event.damages)
                ],
                event.normal_hit_point_damage_cap,
            )
        if not event.damages:
            raise ValueError("TakeDamageEvent requires at least one typed damage component")
        return self.health.preview_damage(
            event.get_effective_damage(),
            event.damages[0].damage_type,
            event.normal_hit_point_damage_cap,
        )

    def receive_damage(
        self,
        amount: int,
        damage_type: DamageType,
        source_entity_uuid: UUID,
        damage_rolls: Optional[List[DiceRoll]] = None,
        damages: Optional[List[Damage]] = None,
        parent_event: Optional[UUID] = None,
        critical_hit: bool = False,
        effect_id: Optional[str] = None,
    ) -> int:
        """Apply damage through the engine event lifecycle.

        `TakeDamageEvent` reaches EFFECT before HP is changed, giving handlers
        a chance to track, modify, cancel, or react to incoming damage. If the
        target dies, a child `DeathEvent` is completed before the damage event
        completes so combat-log nesting remains causal.

        Args:
            amount: Damage amount before resistance or handler changes.
            damage_type: Damage type to apply.
            source_entity_uuid: Entity or effect source that dealt the damage.
            damage_rolls: Optional dice roll details for combat logs.
            damages: Optional damage packet specifications.
            parent_event: Optional parent event UUID for event-tree nesting.
            critical_hit: Whether this damage came from a critical hit, for
                damage-at-0 death-save failures.
            effect_id: Stable identity used by typed effect protections.

        Returns:
            Actual HP lost after handlers, cancellation, and resistances.
        """
        normal_hp_before = self.get_normal_hp()
        temporary_hp_before = max(0, self.health.temporary_hit_points.normalized_score)
        max_hp = self.get_max_hp()
        event_damages = damages if damages else [
            Damage(
                damage_type=damage_type,
                dice_numbers=1,
                damage_dice=4,
                source_entity_uuid=source_entity_uuid
            )
        ]

        take_damage_event = TakeDamageEvent(
            name="Take Damage",
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=self.uuid,
            target_entity_name=self.name,
            total_damage=amount,
            damage_rolls=damage_rolls or [],
            damages=event_damages,
            effect_id=effect_id,
            parent_event=parent_event,
            phase=EventPhase.DECLARATION
        )

        take_damage_event = take_damage_event.phase_to(EventPhase.EXECUTION)
        if not take_damage_event.canceled:
            take_damage_event = take_damage_event.phase_to(EventPhase.EFFECT)

        actual_damage = 0
        if not take_damage_event.canceled:
            use_damage_components = (
                take_damage_event.final_damage is None
                and len(take_damage_event.damage_rolls) == len(take_damage_event.damages)
                and len(take_damage_event.damages) > 1
            )
            effective_damage = take_damage_event.get_effective_damage()
            if use_damage_components:
                components = [
                    (roll.total, damage.damage_type)
                    for roll, damage in zip(take_damage_event.damage_rolls, take_damage_event.damages)
                ]
                actual_damage = self.health.take_damage_components(
                    components,
                    source_entity_uuid=source_entity_uuid,
                    normal_hit_point_damage_cap=take_damage_event.normal_hit_point_damage_cap,
                )
            else:
                actual_damage = self.health.take_damage(
                    effective_damage,
                    damage_type,
                    source_entity_uuid=source_entity_uuid,
                    normal_hit_point_damage_cap=take_damage_event.normal_hit_point_damage_cap,
                )
        else:
            actual_damage = 0

        temporary_hp_after = max(0, self.health.temporary_hit_points.normalized_score)
        temporary_hit_point_damage = max(0, temporary_hp_before - temporary_hp_after)
        applied_damage = actual_damage + temporary_hit_point_damage
        if applied_damage > 0:
            self._complete_damage_applied_event(
                source_entity_uuid=source_entity_uuid,
                damage_type=damage_type,
                damages=take_damage_event.damages,
                effect_id=take_damage_event.effect_id,
                parent_event=take_damage_event,
                normal_hit_point_damage=actual_damage,
                temporary_hit_point_damage=temporary_hit_point_damage,
            )

        if not take_damage_event.canceled and actual_damage > 0 and "Dead" not in self.active_conditions:
            normal_hp_after = self.get_normal_hp()
            if normal_hp_before <= 0 and self.uses_death_saves:
                self._set_normal_hp(0)
                self.is_stable = False
                if actual_damage >= max_hp:
                    self._fire_death_event(source_entity_uuid, parent_event=take_damage_event.uuid)
                else:
                    self.add_death_save_failure(
                        2 if critical_hit else 1,
                        source_entity_uuid=source_entity_uuid,
                        parent_event=take_damage_event.uuid,
                    )
            elif normal_hp_after <= 0:
                remaining_damage = max(0, actual_damage - max(0, normal_hp_before))
                if self.uses_death_saves and remaining_damage < max_hp:
                    self.enter_dying_state(parent_event=take_damage_event)
                else:
                    self._fire_death_event(source_entity_uuid, parent_event=take_damage_event.uuid)

        take_damage_event = take_damage_event.model_copy(
            update={
                "final_damage": applied_damage,
                "resulting_hp": max(0, self.get_normal_hp()) if self.uses_death_saves else self.get_hp(),
            }
        )

        take_damage_event = take_damage_event.phase_to(EventPhase.COMPLETION)

        return actual_damage

    def receive_instant_death(
        self,
        source_entity_uuid: UUID,
        source_description: str = "",
        parent_event: Optional[UUID] = None
    ) -> InstantDeathEvent:
        """Apply an interruptible no-damage death effect.

        Args:
            source_entity_uuid: Entity or effect source causing instant death.
            source_description: Rules-facing source description.
            parent_event: Optional parent event UUID for event-tree nesting.

        Returns:
            Final instant-death event version. A canceled event means the death
            was negated before HP or the `Dead` condition changed.
        """
        source = Entity.get(source_entity_uuid)
        source_name = source.name if source and isinstance(source, Entity) else ""
        instant_death_event = InstantDeathEvent(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=self.uuid,
            source_entity_name=source_name,
            target_entity_name=self.name,
            entity_uuid=self.uuid,
            entity_name=self.name,
            killer_uuid=source_entity_uuid,
            killer_name=source_name,
            source_description=source_description,
            parent_event=parent_event,
            phase=EventPhase.DECLARATION
        )

        instant_death_event = instant_death_event.phase_to(EventPhase.EXECUTION)
        instant_death_event = instant_death_event.phase_to(EventPhase.EFFECT)
        if instant_death_event.canceled:
            return instant_death_event

        hp_before = self.get_hp()
        if hp_before > 0:
            self.health.damage_taken += hp_before

        if "Dead" not in self.active_conditions:
            self._fire_death_event(source_entity_uuid, parent_event=instant_death_event.uuid)

        return instant_death_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{self.name} dies instantly"
        )

    def receive_healing(
        self,
        amount: int,
        source_entity_uuid: UUID,
        source_description: str = "",
        parent_event: Optional[UUID] = None,
        spell_level: int = 0
    ) -> int:
        """Apply healing through the engine event lifecycle.

        `HealEvent` reaches EFFECT before HP is restored, letting blockers or
        future handlers alter the result before completion creates the combat
        log entry.

        Args:
            amount: Requested healing amount.
            source_entity_uuid: Entity or effect source providing healing.
            source_description: Human-readable source text for combat logs.
            parent_event: Optional parent event UUID for combat-log nesting.
            spell_level: Spell level used, or 0 for non-spell healing.

        Returns:
            Actual HP restored after caps and blockers.
        """
        heal_event = HealEvent(
            name="Heal",
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=self.uuid,
            target_entity_name=self.name,
            total_healing=amount,
            source_description=source_description,
            parent_event=parent_event,
            spell_level=spell_level,
            phase=EventPhase.DECLARATION
        )

        heal_event = heal_event.phase_to(EventPhase.EXECUTION)
        heal_event = heal_event.phase_to(EventPhase.EFFECT)

        actual_healing = 0
        if not heal_event.canceled:
            if self.health.is_healing_blocked():
                heal_event = heal_event.model_copy(update={"was_blocked": True})
            else:
                hp_before = self.get_normal_hp()
                healing_amount = max(0, heal_event.total_healing)
                self.health.heal(healing_amount)
                actual_healing = max(0, self.get_normal_hp() - hp_before)
                if actual_healing > 0:
                    self._clear_dying_state_after_healing(parent_event=heal_event)

        heal_event = heal_event.model_copy(update={
            "actual_healing": actual_healing,
            "resulting_hp": self.get_hp(),
            "resulting_normal_hp": self.get_normal_hp(),
            "resulting_temporary_hp": max(0, self.health.temporary_hit_points.normalized_score),
        })
        heal_event.phase_to(EventPhase.COMPLETION)

        return actual_healing

    def get_senses(self) -> Senses:
        """Override BaseBlock virtual — returns Senses block for subjective perception."""
        return self.senses

    @property
    def has_hp(self) -> bool:
        """Whether this entity has positive normal HP."""
        return self.get_normal_hp() > 0

    @property
    def is_active(self) -> bool:
        """Entity is active if it has HP."""
        return self.has_hp

    def get_hp(self) -> int:
        """Return current total HP after Constitution, bonuses, temp HP, and damage."""
        con_modifier = self.ability_scores.get_ability("constitution").get_combined_values()
        return self.health.get_total_hit_points(constitution_modifier=con_modifier.normalized_score)

    def get_weapon_range(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> Range:
        """
        Get the range of a weapon without calculating attack bonuses.

        Args:
            weapon_slot: Weapon slot to inspect.

        Returns:
            Weapon range, or default unarmed reach when no weapon is equipped.
        """
        weapon = self.equipment._get_weapon_by_slot(weapon_slot)

        if weapon is None or isinstance(weapon, Shield):
            return Range(type=RangeType.REACH, normal=5)
        else:
            return weapon.range

    def is_threatened(self) -> bool:
        """
        Check if any enemy threatens this entity's position.

        An entity is threatened if it's within the threatened positions
        (adjacent cells) of any visible enemy. Used for ranged attack
        disadvantage - making a ranged attack while threatened imposes disadvantage.

        Returns:
            True if any visible enemy threatens this entity's position.
        """
        my_position = self.senses.position
        for entity_uuid in self.senses.entities.keys():
            other_entity = Entity.get(entity_uuid)
            if other_entity and self.is_enemy(other_entity):
                if my_position in other_entity.senses.get_threathened_positions():
                    return True
        return False

    def _visible_hostile_threat_domains(
        self,
    ) -> List[Tuple['Entity', Set[Tuple[int, int]]]]:
        """Return threat cells for hostiles visible to this moving entity."""
        if "Disengaging" in self.active_conditions:
            return []
        domains: List[Tuple['Entity', Set[Tuple[int, int]]]] = []
        for entity_uuid in sorted(self.senses.entities, key=str):
            reactor = Entity.get(entity_uuid)
            if (
                reactor is None
                or not isinstance(reactor, Entity)
                or not reactor.is_encounter_alive
                or not self.is_enemy(reactor)
            ):
                continue
            domains.append((
                reactor,
                set(reactor.senses.get_threathened_positions()),
            ))
        return domains

    @staticmethod
    def _opportunity_attack_exposures_for_path(
        path: List[Tuple[int, int]],
        threat_domains: List[Tuple['Entity', Set[Tuple[int, int]]]],
    ) -> List[OpportunityAttackExposure]:
        """Return the first disclosed threat exit for each visible hostile."""
        exposures: List[OpportunityAttackExposure] = []
        for reactor, threatened_positions in threat_domains:
            provoking_step = next(
                (
                    (from_position, to_position)
                    for from_position, to_position in zip(path, path[1:])
                    if from_position in threatened_positions
                    and to_position not in threatened_positions
                ),
                None,
            )
            if provoking_step is None:
                continue
            exposures.append(OpportunityAttackExposure(
                reactor_uuid=reactor.uuid,
                reactor_name=reactor.name,
                from_position=provoking_step[0],
                to_position=provoking_step[1],
            ))
        return exposures

    def spell_attack_bonus(self, target_entity_uuid: Optional[UUID] = None) -> ModifiableValue:
        """Build combined spell attack bonus.

        Args:
            target_entity_uuid: Optional target for cross-propagation.

        Returns:
            Combined spell attack bonus.
        """
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True

        ability = self.ability_scores.get_ability(self.spellcasting.spellcasting_ability)
        ability_bonus = ability.get_combined_values()

        combined = self.proficiency_bonus.combine_values([
            ability_bonus,
            self.equipment.attack_bonus,
            self.spellcasting.spell_attack_bonus,
        ])

        if should_clear_target:
            self.clear_target_entity()

        return combined

    def spell_attack_outcome_baseline(self) -> AttackRollBaseline:
        """Read the actor-side spell attack model without allocating values.

        The baseline deliberately excludes target-owned AC and cross-entity
        modifiers. Those facts are combined by the subjective policy only when
        the observing session knows them.

        Returns:
            Typed attack-roll contribution for a spell action outcome profile.
        """
        ability = self.ability_scores.get_ability(self.spellcasting.spellcasting_ability)
        value_components = (
            self.proficiency_bonus,
            self.equipment.attack_bonus,
            self.spellcasting.spell_attack_bonus,
        )
        advantage_sum = ability.modifier_bonus.advantage_sum + sum(
            component.advantage_sum for component in value_components
        )
        if advantage_sum > 0:
            advantage = AdvantageStatus.ADVANTAGE
        elif advantage_sum < 0:
            advantage = AdvantageStatus.DISADVANTAGE
        else:
            advantage = AdvantageStatus.NONE
        return AttackRollBaseline(
            attack_bonus=ability.modifier + sum(
                component.normalized_score for component in value_components
            ),
            advantage=advantage,
            critical_threshold=self.get_spell_crit_threshold(),
            critical_extra_dice=self.get_spell_crit_extra_dice(),
        )

    def spell_save_dc(self) -> int:
        """Calculate spell save DC.

        DC = 8 + proficiency + ability_modifier + spell_dc_bonus

        Returns:
            Spell save DC.
        """
        ability_mod = self.ability_scores.get_ability(
            self.spellcasting.spellcasting_ability
        ).modifier
        return (8 +
                self.proficiency_bonus.normalized_score +
                ability_mod +
                self.spellcasting.spell_dc_bonus.normalized_score)

    def get_spell_crit_threshold(self) -> int:
        """Get critical hit threshold for spell attacks.

        Combines (stacks):
        - Equipment.crit_threshold (Improved Critical adds here → affects spells!)
        - SpellcastingBlock.spell_crit_threshold (spell-only features)

        Returns:
            Minimum natural d20 roll for a spell critical hit.
        """
        general = self.equipment.crit_threshold.normalized_score
        spell_specific = self.spellcasting.spell_crit_threshold.normalized_score
        return 20 - (general + spell_specific)

    def get_spell_crit_extra_dice(self) -> int:
        """Get extra dice to add on spell critical hits.

        Combines (stacks):
        - Equipment.crit_extra_dice (general features)
        - SpellcastingBlock.spell_crit_extra_dice (spell-only features)

        Returns:
            Extra dice count for spell critical hits.
        """
        general = self.equipment.crit_extra_dice.normalized_score
        spell_specific = self.spellcasting.spell_crit_extra_dice.normalized_score
        return general + spell_specific

    def get_spell_damage_bonus(self) -> ModifiableValue:
        """Get combined spell damage bonus.

        Combines:
        - Equipment.damage_bonus (general damage modifiers)
        - SpellcastingBlock.spell_damage_bonus (Elemental Affinity, etc.)

        Returns:
            Combined spell damage bonus.
        """
        return self.equipment.damage_bonus.combine_values([
            self.spellcasting.spell_damage_bonus,
        ])

    def spell_damage_outcome_bonus(self) -> int:
        """Read the actor-side spell damage bonus without allocating values.

        Returns:
            Current normalized equipment and spell-specific damage bonus sum.
        """
        return (
            self.equipment.damage_bonus.normalized_score
            + self.spellcasting.spell_damage_bonus.normalized_score
        )

    def has_spell_slot(self, level: int) -> bool:
        """Check if entity has an available spell slot of given level.

        Args:
            level: Spell slot level, from 1 through 9.

        Returns:
            True if at least one slot of that level is available.
        """
        if level < 1 or level > 9:
            return False
        slot_attr = getattr(self.action_economy, f"spell_slot_{level}", None)
        if slot_attr is None:
            return False
        return slot_attr.normalized_score >= 1

    def get_lowest_spell_slot(self, min_level: int) -> Optional[int]:
        """Find lowest available slot at or above min_level.

        Args:
            min_level: Minimum slot level to consider.

        Returns:
            Lowest available slot level, or `None`.
        """
        for level in range(min_level, 10):
            if self.has_spell_slot(level):
                return level
        return None

    @property
    def is_spellcaster(self) -> bool:
        """Whether this entity has spell slots or registered spell actions.

        Returns:
            True if at least one spell-slot value has a positive base modifier
            or at least one registered action template is categorized as a
            spell.
        """
        for level in range(1, 10):
            slot_attr = getattr(self.action_economy, f"spell_slot_{level}", None)
            if slot_attr is not None:
                base_mod = slot_attr.get_base_modifier()
                if base_mod and base_mod.value > 0:
                    return True
        if any(action.is_spell for action in self.registered_actions):
            return True
        return False

    def is_ally(self, other: 'Entity') -> bool:
        """Check if another entity is an ally (same faction).

        Same faction = ally. None faction = no allies (except self).
        An entity is always its own ally.

        Args:
            other: The entity to check

        Returns:
            True if same entity, or same faction and neither has None faction
        """
        if other.uuid == self.uuid:
            return True
        if self.faction is None or other.faction is None:
            return False
        return self.faction == other.faction

    def is_enemy(self, other: 'Entity') -> bool:
        """Check if another entity is an enemy (different faction).

        Different faction = enemy. None faction = enemy to all (backward compatible).
        An entity is not its own enemy.

        Args:
            other: The entity to check

        Returns:
            True if different faction or either has None faction
        """
        if other.uuid == self.uuid:
            return False
        if self.faction is None or other.faction is None:
            return True
        return self.faction != other.faction

    def is_enemy_of(self, other_uuid: UUID) -> bool:
        """Faction-based enemy check (BaseBlock override)."""
        other = Entity.get(other_uuid)
        if not other or not isinstance(other, Entity):
            return True
        return self.is_enemy(other)

    def get_visible_enemies(self, include_dead: bool = False) -> Dict[UUID, Tuple[int, int]]:
        """Get visible entities that are enemies.

        Args:
            include_dead: Whether to include visible enemies at 0 HP or below.

        Returns:
            Enemy positions keyed by UUID.
        """
        enemies: Dict[UUID, Tuple[int, int]] = {}
        for entity_uuid, pos in self.senses.entities.items():
            other = Entity.get(entity_uuid)
            if other and self.is_enemy(other):
                if not include_dead and not self._has_positive_normal_hp_for_discovery(other):
                    continue
                enemies[entity_uuid] = pos
        return enemies

    def get_visible_allies(self, include_dead: bool = False) -> Dict[UUID, Tuple[int, int]]:
        """Get visible entities that are allies (same faction, not self).

        Args:
            include_dead: Whether to include visible allies at 0 HP or below.

        Returns:
            Ally positions keyed by UUID.
        """
        allies: Dict[UUID, Tuple[int, int]] = {}
        for entity_uuid, pos in self.senses.entities.items():
            other = Entity.get(entity_uuid)
            if other and self.is_ally(other):
                if not include_dead and not self._has_positive_normal_hp_for_discovery(other):
                    continue
                allies[entity_uuid] = pos
        return allies

    @classmethod
    def get_entities_by_faction(cls, faction: str) -> List['Entity']:
        """Get all entities with the given faction.

        Args:
            faction: Faction identifier.

        Returns:
            Registered entities with that faction.
        """
        return [e for e in cls._entity_registry.values() if e.faction == faction]

    @classmethod
    def get_alive_by_faction(cls, faction: str) -> List['Entity']:
        """Get all alive entities with the given faction.

        Args:
            faction: Faction identifier.

        Returns:
            Registered entities with that faction and positive HP.
        """
        return [e for e in cls._entity_registry.values()
                if e.faction == faction and e.has_hp]

    def roll_d20(
        self,
        bonus: ModifiableValue,
        roll_type: RollType = RollType.ATTACK,
        context: Optional[Dict[str, Any]] = None,
        ability_name: Optional[AbilityName] = None,
        skill_name: Optional[SkillName] = None,
        weapon_slot: Optional[WeaponSlot] = None,
        parent_event: Optional[UUID] = None
    ) -> DiceRoll:
        """Roll a d20 and complete the matching result event.

        The event subclass is chosen from `roll_type`. Attack, save, and check
        rolls include their specific context when supplied; missing required
        context falls back to the base `D20RollResultEvent`.

        Args:
            bonus: Modifiable value used as the d20 bonus.
            roll_type: Attack, save, check, or generic d20 category.
            context: Optional handler context.
            ability_name: Ability context for saving throws.
            skill_name: Skill context for skill checks.
            weapon_slot: Weapon context for attack rolls.
            parent_event: Optional parent event UUID for event-tree nesting.

        Returns:
            Effective d20 roll after result handlers have run.
        """
        dice = Dice(count=1, value=20, bonus=bonus, roll_type=roll_type)
        initial_roll = dice.roll

        common_fields = {
            "source_entity_uuid": self.uuid,
            "target_entity_uuid": bonus.target_entity_uuid,
            "roll": initial_roll,
            "original_roll": initial_roll,
            "bonus": bonus,
            "context": context or {},
            "phase": EventPhase.DECLARATION,
            "roll_type": roll_type,
            "parent_event": parent_event
        }

        if roll_type == RollType.ATTACK:
            event: D20RollResultEvent = AttackD20RollResultEvent(
                **common_fields,
                weapon_slot=weapon_slot
        )
        elif roll_type == RollType.SAVE:
            if ability_name is None:
                event = D20RollResultEvent(**common_fields)
            else:
                event = SavingThrowD20RollResultEvent(
                    **common_fields,
                    ability_name=ability_name
        )
        elif roll_type == RollType.CHECK:
            if skill_name is None:
                event = D20RollResultEvent(**common_fields)
            else:
                event = SkillCheckD20RollResultEvent(
                    **common_fields,
                    skill_name=skill_name
                )
        else:
            event = D20RollResultEvent(**common_fields)

        event = event.phase_to(EventPhase.EFFECT, status_message="D20 rolled, handlers may modify")
        event = event.phase_to(EventPhase.COMPLETION)
        return event.get_effective_roll()

    def roll_d20_event(
        self,
        bonus: ModifiableValue,
        roll_type: RollType = RollType.CHECK,
        context: Optional[Dict[str, Any]] = None,
        ability_name: Optional[AbilityName] = None,
        skill_name: Optional[SkillName] = None,
        weapon_slot: Optional[WeaponSlot] = None,
        parent_event: Optional[UUID] = None
    ) -> Tuple[DiceRoll, D20RollResultEvent]:
        """Roll a d20 and return the EFFECT-phase result event.

        Callers must complete the returned event themselves. This is used when
        the caller needs to add child events after roll handlers have run but
        before completion collects combat-log subentries.

        Args:
            bonus: Modifiable value used as the d20 bonus.
            roll_type: Attack, save, check, or generic d20 category.
            context: Optional handler context.
            ability_name: Ability context for saving throws.
            skill_name: Skill context for skill checks.
            weapon_slot: Weapon context for attack rolls.
            parent_event: Optional parent event UUID for event-tree nesting.

        Returns:
            Effective d20 roll and the uncompleted EFFECT-phase result event.
        """
        dice = Dice(count=1, value=20, bonus=bonus, roll_type=roll_type)
        initial_roll = dice.roll

        common_fields = {
            "source_entity_uuid": self.uuid,
            "target_entity_uuid": bonus.target_entity_uuid,
            "roll": initial_roll,
            "original_roll": initial_roll,
            "bonus": bonus,
            "context": context or {},
            "phase": EventPhase.DECLARATION,
            "roll_type": roll_type,
            "parent_event": parent_event
        }

        if roll_type == RollType.ATTACK:
            event: D20RollResultEvent = AttackD20RollResultEvent(
                **common_fields,
                weapon_slot=weapon_slot
            )
        elif roll_type == RollType.SAVE:
            if ability_name is None:
                event = D20RollResultEvent(**common_fields)
            else:
                event = SavingThrowD20RollResultEvent(
                    **common_fields,
                    ability_name=ability_name
                )
        elif roll_type == RollType.CHECK:
            if skill_name is None:
                event = D20RollResultEvent(**common_fields)
            else:
                event = SkillCheckD20RollResultEvent(
                    **common_fields,
                    skill_name=skill_name
                )
        else:
            event = D20RollResultEvent(**common_fields)

        event = event.phase_to(EventPhase.EFFECT, status_message="D20 rolled, handlers may modify")
        return event.get_effective_roll(), event

    def create_saving_throw_request(
        self,
        target_entity_uuid: UUID,
        ability_name: AbilityName,
        dc: Union[int, UUID],
        parent_event: Optional[UUID] = None,
        condition_context: Optional[str] = None,
    ) -> SavingThrowEvent:
        """Create a saving throw request event for another entity.

        Args:
            target_entity_uuid: Entity that will roll the save.
            ability_name: Saving throw ability.
            dc: Fixed DC or UUID of this entity's modifiable DC value.
            parent_event: Optional parent event UUID for event-tree nesting.
            condition_context: Optional condition name this save is made against.

        Returns:
            Declaration-phase saving throw event.
        """
        if isinstance(dc, UUID):
            self.set_target_entity(dc)
            new_dc = ModifiableValue.get(dc)
            if new_dc is None or new_dc.source_entity_uuid != self.uuid:
                raise ValueError("DC is not coming from self oir not present")
            new_dc = new_dc.model_copy(deep=True)
            new_dc.set_target_entity(target_entity_uuid)
            int_dc = new_dc.normalized_score
        else:
            int_dc = dc
        self.clear_target_entity()

        target_entity = Entity.get(target_entity_uuid)
        target_entity_name = target_entity.name if target_entity else None

        return SavingThrowEvent(
            source_entity_uuid=self.uuid,
            target_entity_uuid=target_entity_uuid,
            ability_name=ability_name,
            dc=int_dc,
            source_entity_name=self.name,
            target_entity_name=target_entity_name,
            parent_event=parent_event,
            condition_context=condition_context,
        )

    def create_skill_check_request(
        self,
        target_entity_uuid: UUID,
        skill_name: SkillName,
        dc: Union[int, UUID],
        parent_event: Optional[UUID] = None
    ) -> SkillCheckEvent:
        """Create a skill check request event for another entity.

        Args:
            target_entity_uuid: Entity that will roll the check.
            skill_name: Skill used for the check.
            dc: Fixed DC or UUID of this entity's modifiable DC value.
            parent_event: Optional parent event UUID for event-tree nesting.

        Returns:
            Declaration-phase skill check event.
        """
        if isinstance(dc, UUID):
            self.set_target_entity(dc)
            dc_modifier = ModifiableValue.get(dc)
            if dc_modifier is None or dc_modifier.source_entity_uuid != self.uuid:
                raise ValueError(f"not present {dc_modifier is None} or not coming from self")
            if target_entity_uuid != dc_modifier.target_entity_uuid:
                new_dc = dc_modifier.model_copy(deep=True)
                new_dc.set_target_entity(target_entity_uuid)
            else:
                new_dc = dc_modifier
            int_dc = new_dc.normalized_score
        else:
            int_dc = dc
        self.clear_target_entity()

        target_entity = Entity.get(target_entity_uuid)
        target_entity_name = target_entity.name if target_entity else None

        return SkillCheckEvent(
            source_entity_uuid=self.uuid,
            target_entity_uuid=target_entity_uuid,
            skill_name=skill_name,
            dc=int_dc,
            source_entity_name=self.name,
            target_entity_name=target_entity_name,
            parent_event=parent_event
        )

    def saving_throw(self, request: SavingThrowEvent) -> Tuple[AttackOutcome, DiceRoll, bool]:
        """Make a saving throw with full event phase transitions.

        Args:
            request: Saving throw request event targeting this entity.

        Returns:
            Outcome-like result, final roll, and success flag.
        """
        if request.target_entity_uuid != self.uuid:
            raise ValueError("Target entity uuid does not match")

        self.set_target_entity(request.source_entity_uuid)

        save_bonus = self.saving_throw_bonus(request.source_entity_uuid, request.ability_name)
        save_context: Dict[str, Any] = {}
        if request.condition_context is not None:
            save_context["condition_context"] = request.condition_context
        save_bonus.set_context(save_context)
        save_bonus.set_event_lineage(request.lineage_uuid)
        dc = request.get_dc()
        if dc is None:
            raise ValueError(f"DC is not set for {request.ability_name} saving throw with event id {request.uuid}")

        execution_event = request.phase_to(
            EventPhase.EXECUTION,
            bonus=save_bonus,
            status_message=f"Rolling {request.ability_name} save vs DC {dc}"
        )

        roll = self.roll_d20(
            save_bonus,
            RollType.SAVE,
            context=save_context,
            ability_name=request.ability_name,
            parent_event=request.uuid,
        )
        outcome = determine_attack_outcome(roll, dc)
        success = outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            dice_roll=roll,
            result=success,
            status_message=f"Rolled {roll.total} vs DC {dc}: {'Success' if success else 'Failure'}"
        )

        completion_event = effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{request.ability_name} save complete"
        )

        save_bonus.clear_event_lineage()
        save_bonus.clear_context()
        self.clear_target_entity()

        final_roll = completion_event.dice_roll or roll
        final_success = completion_event.result if completion_event.result is not None else success
        final_outcome = outcome
        if final_success != success:
            if final_success:
                final_outcome = AttackOutcome.HIT
            else:
                final_outcome = AttackOutcome.MISS

        return final_outcome, final_roll, final_success

    def skill_check(self, request: SkillCheckEvent) -> Tuple[AttackOutcome,DiceRoll,bool]:
        """Make a skill check with full event phase transitions.

        Args:
            request: Skill check request event targeting this entity.

        Returns:
            Outcome-like result, final roll, and success flag.
        """
        if request.target_entity_uuid != self.uuid:
            raise ValueError("Target entity uuid does not match")
        self.set_target_entity(request.source_entity_uuid)
        skill_check_bonus = self.skill_bonus(request.source_entity_uuid, request.skill_name)
        dc = request.get_dc()
        if dc is None:
            raise ValueError(f"DC is not set for {request.skill_name} skill check with event id {request.uuid}")

        execution_event = request.phase_to(
            EventPhase.EXECUTION,
            bonus=skill_check_bonus,
            status_message=f"Rolling {request.skill_name} check vs DC {dc}"
        )

        roll = self.roll_d20(skill_check_bonus, RollType.CHECK, skill_name=request.skill_name, parent_event=request.uuid)
        skill_check_outcome = determine_attack_outcome(roll, dc)
        success = skill_check_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            dice_roll=roll,
            result=success,
            status_message=f"Rolled {roll.total} vs DC {dc}: {'Success' if success else 'Failure'}"
        )

        final_roll = effect_event.dice_roll or roll
        final_outcome = determine_attack_outcome(final_roll, dc)
        final_success = final_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

        effect_event.phase_to(
            EventPhase.COMPLETION,
            dice_roll=final_roll,
            result=final_success,
            status_message=f"{request.skill_name} check complete"
        )

        self.clear_target_entity()
        return final_outcome, final_roll, final_success

    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """An entity blocks walking unless it is non-blocking or the requester is itself."""
        if requesting_entity_uuid == self.uuid:
            return False
        if self.non_blocking:
            return False
        return True

    def loot_item(self, item: BaseItem) -> bool:
        """Pick up item into inventory. Removes from GridMap if placed.

        Sets location tracking fields and calls lifecycle hook with entity context.
        Returns False if inventory is full.

        Stack-aware: if add_item merges the item into an existing stack, skips
        location tracking and lifecycle hook (the item object was consumed).
        """
        if not self.inventory.can_add(item):
            return False
        item_uuid = item.uuid
        item.source_entity_uuid = self.uuid
        self.inventory.add_item(item)
        merged = item_uuid not in self.inventory.items
        item.tile_uuid = None
        gridmap = get_map()
        if gridmap.get_object_position(item_uuid) is not None:
            gridmap.remove_object(item_uuid)
        if not merged:
            item.owner_uuid = self.uuid
            item.stored_in_uuid = self.inventory.uuid
            item.loot(entity_uuid=self.uuid, inventory_uuid=self.inventory.uuid)
        return True

    def drop_item(self, item_uuid: UUID, position: Optional[Tuple[int, int]] = None) -> Optional[BaseItem]:
        """Drop item from inventory to ground.

        Args:
            item_uuid: UUID of the item to drop. The item must be in inventory.
            position: Grid position to drop at. Defaults to entity's position.

        Returns:
            The dropped item, or None if not found in inventory.
        """
        item = self.inventory.remove_item(item_uuid)
        if item is None:
            return None
        drop_pos = position if position is not None else self.position
        gridmap = get_map()
        tile = gridmap.get_tile(drop_pos[0], drop_pos[1])
        item.owner_uuid = None
        item.stored_in_uuid = None
        item.position = drop_pos
        item.tile_uuid = tile.uuid if tile else None
        gridmap.place_object(item.uuid, drop_pos)
        item.drop(entity_uuid=self.uuid, position=drop_pos)
        return item

    def equip_item(self, item_uuid: UUID, slot: EquipmentSlot) -> bool:
        """Move item from inventory to equipment slot.

        If the target slot is occupied and the new equip succeeds, moves the
        replaced item back to inventory or drops it when inventory is full.

        Args:
            item_uuid: UUID of the inventory item to equip.
            slot: Equipment slot to place the item into.

        Returns:
            True if the item was equipped, False if the item was absent, not
            equippable, or the equipment event was canceled.
        """
        item = self.inventory.items.get(item_uuid)
        if item is None or not item.is_equippable:
            return False
        equipped_before = {
            equipped_item.uuid: equipped_item
            for equipped_item in self.equipment.get_all_equipped_items()
        }
        if not self.equipment.equip(cast(Union[Armor, Weapon, Shield], item), slot):
            return False

        self.inventory.remove_item(item_uuid)
        equipped_after = {
            equipped_item.uuid
            for equipped_item in self.equipment.get_all_equipped_items()
        }
        displaced_items = [
            equipped_item
            for equipped_uuid, equipped_item in equipped_before.items()
            if equipped_uuid not in equipped_after and equipped_uuid != item.uuid
        ]
        for displaced_item in displaced_items:
            if self.inventory.add_item(displaced_item):
                displaced_item.owner_uuid = self.uuid
                displaced_item.stored_in_uuid = self.inventory.uuid
            else:
                gridmap = get_map()
                displaced_item.owner_uuid = None
                displaced_item.stored_in_uuid = None
                displaced_item.position = self.position
                tile = gridmap.get_tile(self.position[0], self.position[1])
                displaced_item.tile_uuid = tile.uuid if tile else None
                gridmap.place_object(displaced_item.uuid, self.position)
                displaced_item.drop(entity_uuid=self.uuid, position=self.position)
        return True

    def unequip_item(self, slot: EquipmentSlot) -> Optional[BaseItem]:
        """Move item from equipment slot to inventory.

        If inventory is full, drops item to ground at entity position.

        Args:
            slot: Equipment slot to clear.

        Returns:
            The unequipped item, or None if slot was empty or unequip canceled.
        """
        item = self.equipment.unequip(slot)
        if item is None:
            return None
        if self.inventory.add_item(item):
            item.owner_uuid = self.uuid
            item.stored_in_uuid = self.inventory.uuid
        else:
            gridmap = get_map()
            item.owner_uuid = None
            item.stored_in_uuid = None
            item.position = self.position
            tile = gridmap.get_tile(self.position[0], self.position[1])
            item.tile_uuid = tile.uuid if tile else None
            gridmap.place_object(item.uuid, self.position)
        return item

    @staticmethod
    def _add_adjacent_senses_objects(
        visible_objects: Dict[UUID, Tuple[int, int]],
        observer_position: Tuple[int, int],
        observer_uuid: Optional[UUID],
    ) -> None:
        """Add adjacent interactable structural objects that block visibility into their own cell."""
        grid = get_map()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                position = (observer_position[0] + dx, observer_position[1] + dy)
                for obj_uuid in grid.get_objects_at(position):
                    if obj_uuid in visible_objects:
                        continue
                    obj = BaseBlock.get(obj_uuid)
                    if obj is None:
                        continue
                    if not obj.should_include_in_senses_objects():
                        continue
                    if not obj.should_include_in_adjacent_senses_objects():
                        continue
                    if not obj.is_perceivable_by(observer_uuid):
                        continue
                    visible_objects[obj_uuid] = position

    @staticmethod
    def compute_senses_from_position(
        position: Tuple[int, int],
        seen: Set[Tuple[int, int]],
        max_distance: int = 10,
        entity_uuid: Optional[UUID] = None,
        visibility_cache: Optional[VisibilityComputationCache] = None,
        path_max_distance: Optional[int] = None,
    ) -> Tuple[Dict[Tuple[int, int], bool], DefaultDict[Tuple[int, int], List[Tuple[int, int]]], Dict[Tuple[int, int], int], Dict[Tuple[int, int], bool], Dict[UUID, Tuple[int, int]], Dict[UUID, Tuple[int, int]], List[Tuple[int, int]], Dict[Tuple[int, int], List[Tuple[int, int]]], Dict[Tuple[int, int], int]]:
        """Compute observer-local senses data from a position.

        Args:
            position: Position to compute from.
            seen: Previously seen positions.
            max_distance: Maximum view and movement distance.
            entity_uuid: Optional observer UUID for subjective filtering.
            visibility_cache: Optional visibility-only computation result to
                reuse for an immediate full refresh at the same origin.
            path_max_distance: Optional movement-cost radius for pathfinding.
                When omitted, pathfinding uses `max_distance`.

        Returns:
            Visible cells, filtered paths and costs, walkability, visible
            entities, visible objects, full geometric FOV positions, safe
            paths, and safe path costs.
        """
        grid = get_map()
        timing = action_timing_enabled()
        if visibility_cache is not None:
            started = time.perf_counter() if timing else 0.0
            fov_positions = list(visibility_cache.fov_positions)
            visible_dict = dict(visibility_cache.visible)
            if timing:
                record_action_timing("senses.reuse_visibility_cache_ms", started)
        else:
            started = time.perf_counter() if timing else 0.0
            fov_positions = grid.compute_fov(position, max_distance, observer_uuid=entity_uuid)
            if timing:
                record_action_timing("senses.compute_fov_ms", started)

            started = time.perf_counter() if timing else 0.0
            visible_dict = Entity._filter_visible_positions_by_light(
                fov_positions,
                position,
                entity_uuid,
            )
            if timing:
                record_action_timing("senses.filter_visible_light_ms", started)

        started = time.perf_counter() if timing else 0.0
        collision: Set[Tuple[int, int]] = set()
        directional_collision: Set[Tuple[Tuple[int, int], str]] = set()
        ign_terrain = False
        if entity_uuid:
            ent = Entity._entity_registry.get(entity_uuid)
            if ent is not None:
                collision = ent.senses.collision_blocked
                directional_collision = ent.senses.directional_collision_blocked
                ign_terrain = ent.ignore_difficult_terrain
        if timing:
            record_action_timing("senses.prepare_path_context_ms", started)
        effective_path_max_distance = path_max_distance if path_max_distance is not None else max_distance
        started = time.perf_counter() if timing else 0.0
        distances, paths = grid.compute_paths(position, effective_path_max_distance, requesting_entity_uuid=entity_uuid,
                                              subjective=True, collision_blocked=collision,
                                              directional_collision_blocked=directional_collision,
                                              ignore_difficult_terrain=ign_terrain)
        if timing:
            record_action_timing("senses.compute_paths_ms", started)

        started = time.perf_counter() if timing else 0.0
        filtered_paths: DefaultDict[Tuple[int, int], List[Tuple[int, int]]] = defaultdict(list)
        path_costs: Dict[Tuple[int, int], int] = {}
        for pos, path in paths.items():
            if pos in visible_dict and all(step in seen or step in visible_dict for step in path):
                filtered_paths[pos] = path
                path_costs[pos] = int(distances[pos] * 5)
        if timing:
            record_action_timing("senses.filter_paths_ms", started)

        started = time.perf_counter() if timing else 0.0
        safe_paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        safe_path_costs: Dict[Tuple[int, int], int] = {}
        has_any_hazardous = False
        if grid.has_any_hazards():
            for pos, path in filtered_paths.items():
                for step in path[1:]:
                    if grid.is_position_hazardous_for(step[0], step[1], entity_uuid):
                        has_any_hazardous = True
                        break
                if has_any_hazardous:
                    break
        if timing:
            record_action_timing("senses.scan_hazards_ms", started)

        if has_any_hazardous:
            started = time.perf_counter() if timing else 0.0
            safe_distances, safe_raw = grid.compute_paths(
                position, effective_path_max_distance, requesting_entity_uuid=entity_uuid,
                walk_in_danger=False, subjective=True, collision_blocked=collision,
                directional_collision_blocked=directional_collision,
                ignore_difficult_terrain=ign_terrain
            )
            if timing:
                record_action_timing("senses.compute_safe_paths_ms", started)
            started = time.perf_counter() if timing else 0.0
            for pos, path in safe_raw.items():
                if pos in visible_dict and all(step in seen or step in visible_dict for step in path):
                    safe_paths[pos] = path
                    safe_path_costs[pos] = int(safe_distances[pos] * 5)
            if timing:
                record_action_timing("senses.filter_safe_paths_ms", started)

        if visibility_cache is not None:
            started = time.perf_counter() if timing else 0.0
            visible_entities = dict(visibility_cache.entities)
            visible_objects = dict(visibility_cache.objects)
            if timing:
                record_action_timing("senses.reuse_visible_entities_objects_ms", started)
        else:
            started = time.perf_counter() if timing else 0.0
            visible_entities: Dict[UUID, Tuple[int, int]] = {}
            for pos in visible_dict:
                entities = Entity.get_all_entities_at_position(pos)
                for entity in entities:
                    if entity_uuid and entity.uuid == entity_uuid:
                        continue
                    if entity.is_perceivable_by(entity_uuid):
                        visible_entities[entity.uuid] = pos
            if timing:
                record_action_timing("senses.collect_visible_entities_ms", started)

            started = time.perf_counter() if timing else 0.0
            visible_objects: Dict[UUID, Tuple[int, int]] = {}
            for pos in visible_dict:
                for obj_uuid in grid.get_objects_at(pos):
                    obj = BaseBlock.get(obj_uuid)
                    if obj is None:
                        continue
                    if not obj.should_include_in_senses_objects():
                        continue
                    if not obj.is_perceivable_by(entity_uuid):
                        continue
                    visible_objects[obj_uuid] = pos
            if timing:
                record_action_timing("senses.collect_visible_objects_ms", started)
            started = time.perf_counter() if timing else 0.0
            Entity._add_adjacent_senses_objects(visible_objects, position, entity_uuid)
            if timing:
                record_action_timing("senses.add_adjacent_objects_ms", started)

        started = time.perf_counter() if timing else 0.0
        walkable = {pos: grid.is_walkable(pos[0], pos[1]) for pos in fov_positions}
        if timing:
            record_action_timing("senses.walkable_map_ms", started)

        return (
            visible_dict,
            filtered_paths,
            path_costs,
            walkable,
            visible_entities,
            visible_objects,
            fov_positions,
            safe_paths,
            safe_path_costs,
        )

    @staticmethod
    def _filter_visible_positions_by_light(
        fov_positions: List[Tuple[int, int]],
        observer_position: Tuple[int, int],
        observer_uuid: Optional[UUID],
    ) -> Dict[Tuple[int, int], bool]:
        """Filter geometric FOV cells through the subjective light model.

        Bright-or-brighter cells are visible to every observer, so a fully
        bright FOV can skip per-cell sense-mode resolution. Darkness, dim
        light, and magical darkness still use `Tile.get_effective_light_for()`
        so darkvision and similar senses keep their normal behavior.
        """
        grid = get_map()
        fov_tiles = [
            (pos, tile)
            for pos in fov_positions
            if (tile := grid.get_tile(pos[0], pos[1])) is not None
        ]
        if observer_uuid is None:
            return {pos: True for pos, _ in fov_tiles}
        if all(
            tile.resolved_light_level.value >= LightLevel.BRIGHT_LIGHT.value
            for _, tile in fov_tiles
        ):
            return {pos: True for pos, _ in fov_tiles}

        visible_dict: Dict[Tuple[int, int], bool] = {}
        for pos, tile in fov_tiles:
            eff = tile.get_effective_light_for(
                observer_uuid,
                observer_position=observer_position,
            )
            if eff.value <= LightLevel.DARKNESS.value:
                continue
            visible_dict[pos] = True
        return visible_dict

    def create_senses_copy_at_position(self, position: Tuple[int, int], max_distance: int = 10) -> 'Senses':
        """Create a copy of senses as if entity were at a different position."""
        senses = self.senses.model_copy(deep=True)
        senses.position = position
        (
            visible_dict,
            filtered_paths,
            path_costs,
            walkable,
            visible_entities,
            visible_objects,
            _fov,
            safe_paths,
            safe_path_costs,
        ) = Entity.compute_senses_from_position(
            position, self.senses.seen, max_distance, entity_uuid=self.uuid
        )

        senses.update_senses(
            entities=visible_entities,
            visible=visible_dict,
            walkable=walkable,
            paths=filtered_paths,
            path_costs=path_costs,
            objects=visible_objects,
            safe_paths=safe_paths,
            safe_path_costs=safe_path_costs,
            path_max_distance=max_distance,
        )
        return senses

    def update_entity_senses(
        self,
        max_distance: int = 10,
        reuse_visibility_cache: bool = False,
        path_max_distance: Optional[int] = None,
    ) -> None:
        """Fully recompute the entity's senses and FOV subscriptions.

        This computes:
        - Visible cells within max_distance using shadowcast
        - Paths to reachable cells using dijkstra (excludes cells occupied by other entities)
        - Entities present in visible cells

        After updating, subscribes to visible cells so this entity
        receives SpatialChangeEvents when something changes in its FOV.

        Args:
            max_distance: Maximum view/movement distance (default 10)
            reuse_visibility_cache: Whether to reuse a matching one-shot
                visibility result from an immediately preceding movement step.
            path_max_distance: Optional movement-cost radius for paths. When
                omitted, pathfinding uses `max_distance`.
        """
        timing = action_timing_enabled()
        visibility_cache = None
        if reuse_visibility_cache:
            candidate = self.senses._visibility_cache
            if (
                candidate is not None
                and candidate.position == self.position
                and candidate.max_distance == max_distance
            ):
                visibility_cache = candidate

        started = time.perf_counter() if timing else 0.0
        (
            visible_dict,
            filtered_paths,
            path_costs,
            walkable,
            visible_entities,
            visible_objects,
            fov_positions,
            safe_paths,
            safe_path_costs,
        ) = Entity.compute_senses_from_position(
            self.position,
            self.senses.seen,
            max_distance,
            entity_uuid=self.uuid,
            visibility_cache=visibility_cache,
            path_max_distance=path_max_distance,
        )
        if timing:
            record_action_timing("entity.update_senses.compute_ms", started)
        started = time.perf_counter() if timing else 0.0
        self.senses.update_senses(
            entities=visible_entities,
            visible=visible_dict,
            walkable=walkable,
            paths=filtered_paths,
            path_costs=path_costs,
            objects=visible_objects,
            safe_paths=safe_paths,
            safe_path_costs=safe_path_costs,
            path_max_distance=path_max_distance if path_max_distance is not None else max_distance,
        )
        if timing:
            record_action_timing("entity.update_senses.apply_cache_ms", started)
        started = time.perf_counter() if timing else 0.0
        self.senses.snapshot_perception(self.get_passive_perception())
        if timing:
            record_action_timing("entity.update_senses.snapshot_perception_ms", started)
        started = time.perf_counter() if timing else 0.0
        get_map().subscribe_to_cells(self.uuid, set(fov_positions))
        spatial_senses_system.refresh_observer(self.uuid)
        if timing:
            record_action_timing("entity.update_senses.subscribe_cells_ms", started)

    @classmethod
    def update_all_entities_senses(cls, max_distance: int = 10) -> None:
        """Update the senses for all entities."""
        for entity in cls.get_all_entities():
            entity.update_entity_senses(max_distance)

    def update_entity_visibility(self, max_distance: int = 10) -> None:
        """Recompute visible cells, entities, and objects without paths.

        Used during movement to update what entity can see at each step
        without the cost of recomputing all paths (which is done once at end).

        This recomputes:
        - Visible cells from current position
        - Entities in visible cells

        Does NOT recompute paths (expensive, done once at movement end).

        Args:
            max_distance: Maximum view distance (default 10)
        """
        grid = get_map()
        timing = action_timing_enabled()
        started = time.perf_counter() if timing else 0.0
        fov_positions = grid.compute_fov(self.position, max_distance, observer_uuid=self.uuid)
        if timing:
            record_action_timing("entity.update_visibility.compute_fov_ms", started)

        started = time.perf_counter() if timing else 0.0
        visible_dict = Entity._filter_visible_positions_by_light(
            fov_positions,
            self.position,
            self.uuid,
        )
        if timing:
            record_action_timing("entity.update_visibility.filter_visible_light_ms", started)

        started = time.perf_counter() if timing else 0.0
        visible_entities: Dict[UUID, Tuple[int, int]] = {}
        for pos in visible_dict:
            for ent_uuid in grid.get_entities_at(pos):
                if ent_uuid != self.uuid:
                    block = BaseBlock.get(ent_uuid)
                    if block and block.is_perceivable_by(self.uuid):
                        visible_entities[ent_uuid] = pos
        if timing:
            record_action_timing("entity.update_visibility.collect_visible_entities_ms", started)

        started = time.perf_counter() if timing else 0.0
        visible_objects: Dict[UUID, Tuple[int, int]] = {}
        for pos in visible_dict:
            for obj_uuid in grid.get_objects_at(pos):
                obj = BaseBlock.get(obj_uuid)
                if obj is None:
                    continue
                if not obj.should_include_in_senses_objects():
                    continue
                if not obj.is_perceivable_by(self.uuid):
                    continue
                visible_objects[obj_uuid] = pos
        if timing:
            record_action_timing("entity.update_visibility.collect_visible_objects_ms", started)
        started = time.perf_counter() if timing else 0.0
        Entity._add_adjacent_senses_objects(visible_objects, self.position, self.uuid)
        if timing:
            record_action_timing("entity.update_visibility.add_adjacent_objects_ms", started)

        started = time.perf_counter() if timing else 0.0
        old_entities = set(self.senses.entities.keys())
        newly_spotted = set(visible_entities.keys()) - old_entities
        for spotted_uuid in newly_spotted:
            spotted = Entity.get(spotted_uuid)
            if (spotted and isinstance(spotted, Entity)
                    and spotted.stealth_dc is not None
                    and self.is_enemy(spotted)):
                pp = self.get_passive_perception()
                log_entry = CombatLogEntry(
                    entry_type=CombatLogEntryType.ENTITY_SPOTTED,
                    source_name=self.name,
                    source_uuid=str(self.uuid),
                    target_name=spotted.name,
                    target_uuid=str(spotted.uuid),
                    compact=f"{{cyan:{self.name}}} spots {{yellow:{spotted.name}}} (Perception {pp} vs Stealth DC {spotted.stealth_dc})",
                    verbose=f"{{cyan:{self.name}}} sees through {{yellow:{spotted.name}}}'s hiding (Passive Perception {pp} vs Stealth DC {spotted.stealth_dc})",
                    detailed=f"{{cyan:{self.name}}} sees through {{yellow:{spotted.name}}}'s hiding (Passive Perception {pp} vs Stealth DC {spotted.stealth_dc})",
                    perceiver_uuids={str(self.uuid)},
                    identified_entity_observer_uuids={
                        str(spotted.uuid): {str(self.uuid)},
                    },
                    data=EntitySpottedLogData(
                        observer_name=self.name,
                        observer_uuid=str(self.uuid),
                        target_name=spotted.name,
                        target_uuid=str(spotted.uuid),
                        target_position=spotted.position,
                        passive_perception=pp,
                        stealth_dc=spotted.stealth_dc
                    ).model_dump()
                )
                EventQueue.push_combat_log(log_entry, self.uuid)
        if timing:
            record_action_timing("entity.update_visibility.spotted_logs_ms", started)

        started = time.perf_counter() if timing else 0.0
        self.senses.visible = visible_dict
        self.senses.update_seen(visible_dict)
        self.senses.entities = visible_entities
        self.senses.objects = visible_objects
        self.senses._visibility_cache = VisibilityComputationCache(
            position=self.position,
            max_distance=max_distance,
            visible=dict(visible_dict),
            fov_positions=list(fov_positions),
            entities=dict(visible_entities),
            objects=dict(visible_objects),
        )
        if timing:
            record_action_timing("entity.update_visibility.apply_cache_ms", started)

        started = time.perf_counter() if timing else 0.0
        grid.subscribe_to_cells(self.uuid, set(fov_positions))
        spatial_senses_system.refresh_observer(self.uuid)
        if timing:
            record_action_timing("entity.update_visibility.subscribe_cells_ms", started)

    def register_action(self, action: BaseAction) -> None:
        """Register an action template.

        Args:
            action: Template action to register.

        Raises:
            ValueError: If the action is not a template.
        """
        if not action.template:
            raise ValueError("Can only register templates (template=True)")
        self.registered_actions.append(action)

    def unregister_action(self, name: str) -> None:
        """Remove an action template by name.

        Args:
            name: Template name to remove.
        """
        self.registered_actions = [a for a in self.registered_actions if a.name != name]

    def get_action_template(self, name: str) -> Optional[BaseAction]:
        """Get a registered action template by name.

        Args:
            name: Template name to look up.

        Returns:
            Matching action template, or `None`.
        """
        return next((a for a in self.registered_actions if a.name == name), None)

    @property
    def entity_actions(self) -> List[BaseAction]:
        """Actions that target other entities (Attack, multi-target spells)."""
        return [a for a in self.registered_actions
                if a.effective_target_type in (TargetType.ENTITY, TargetType.MULTI_ENTITY)]

    @property
    def position_actions(self) -> List[BaseAction]:
        """Actions that target positions (Move, Jump, AoE spells).

        Includes path-based movement, line-of-sight positions, and AoE previews.
        """
        return [a for a in self.registered_actions
                if a.effective_target_type in (TargetType.POSITION, TargetType.POSITION_PATH, TargetType.POSITION_LOS, TargetType.POSITION_AOE)]

    @property
    def self_actions(self) -> List[BaseAction]:
        """Actions that target self (Dash, Dodge, etc.)."""
        return [a for a in self.registered_actions if a.effective_target_type == TargetType.SELF]

    @property
    def object_actions(self) -> List[BaseAction]:
        """Actions that target objects on the grid (Pick Up, Attack Object)."""
        return [a for a in self.registered_actions if a.effective_target_type == TargetType.OBJECT]

    def _make_action_info(
        self,
        template_name: str,
        target_type: TargetType,
        valid_targets: List[AvailableTarget],
        can_afford: bool,
        template: BaseAction,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        weapon_slot: Optional[str] = None,
        weapon_name: Optional[str] = None,
        damage_types: Optional[List[str]] = None,
        is_item_use: bool = False,
        source_item_uuid: Optional[UUID] = None,
        item_stack_count: Optional[int] = None,
    ) -> AvailableActionInfo:
        """Build discovery metadata from a registered template.

        Args:
            template_name: Name used to execute the template.
            target_type: Effective target type exposed for discovery.
            valid_targets: Valid targets already validated for this template.
            can_afford: Whether the acting entity can pay the primary costs.
            template: Registered action template.
            display_name: Optional display label.
            description: Optional display description.
            weapon_slot: Optional weapon slot metadata for attacks.
            weapon_name: Optional weapon display metadata for attacks.
            damage_types: Known damage type labels this row can deal.
            is_item_use: Whether this action came from a usable item.
            source_item_uuid: UUID of the item that supplied the action.
            item_stack_count: Stack count to display for stackable items.

        Returns:
            Available action metadata for UI or controller selection.
        """
        eff_costs = template.effective_costs
        cost_type = eff_costs[0].cost_type if eff_costs else "actions"
        cost_amount = eff_costs[0].cost if eff_costs else 0
        discovery_template_name = template.get_discovery_template_name()
        base_template_name = template.name if template.name != discovery_template_name else None
        row_damage_types = list(damage_types or [])
        if not row_damage_types and template.is_spell:
            spell_damage_type = getattr(template, "spell_damage_type", None)
            if spell_damage_type is not None:
                row_damage_types.append(getattr(spell_damage_type, "value", str(spell_damage_type)))
        source_item = BaseBlock.get(source_item_uuid) if source_item_uuid is not None else None
        item_charge_cost = (
            template.charge_cost
            if is_item_use
            and isinstance(source_item, UsableItem)
            and source_item.charges != -1
            else 0
        )
        action_info = AvailableActionInfo(
            template_name=template_name,
            semantic_key=template.get_semantic_key(),
            target_type=target_type,
            valid_targets=valid_targets,
            can_afford=can_afford,
            display_name=display_name or template_name,
            description=description if description is not None else template.description,
            cost_type=cost_type,
            cost_amount=cost_amount,
            costs=[BaseCost.model_validate(cost) for cost in eff_costs],
            weapon_slot=weapon_slot,
            weapon_name=weapon_name,
            damage_types=row_damage_types,
            outcome_profile=template.get_outcome_profile(self),
            self_setup_profile=template.get_self_setup_profile(self),
            target_effect_profile=template.get_target_effect_profile(self),
            world_effect_profile=template.get_world_effect_profile(self),
            action_category=template.action_category,
            base_template_name=base_template_name,
            spell_level=getattr(template, "spell_level", None) if template.is_spell else None,
            cast_at_level=getattr(template, "cast_at_level", None) if template.is_spell else None,
            is_spell_variant=bool(getattr(template, "is_variant", False)) if template.is_spell else False,
            requires_concentration=template.requires_concentration,
            num_projectiles=template.get_multi_target_count() if target_type == TargetType.MULTI_ENTITY else None,
            allow_same_target=template.allow_same_target if target_type == TargetType.MULTI_ENTITY else None,
            is_item_use=is_item_use,
            source_item_uuid=source_item_uuid,
            item_stack_count=item_stack_count,
            item_charge_cost=item_charge_cost,
            fixed_healing=template.get_fixed_healing(self),
        )
        action_info.set_execution_template(template)
        return action_info

    @staticmethod
    def _timing_label(value: object) -> str:
        """Return a compact label suitable for timing phase keys."""
        text = str(value or "unnamed")
        label = "".join(char.lower() if char.isalnum() else "_" for char in text)
        while "__" in label:
            label = label.replace("__", "_")
        return label.strip("_")[:80] or "unnamed"

    def _compute_target_pool(
        self,
        action_filter: str,
        include_dead: bool,
        include_self: bool,
        default_pool: Dict[UUID, Tuple[int, int]],
        target_pool_cache: Optional[Dict[Tuple[str, bool, bool], Dict[UUID, Tuple[int, int]]]] = None,
    ) -> Dict[UUID, Tuple[int, int]]:
        """Compute entity target pool based on valid_target_filter.

        Args:
            action_filter: Relationship filter from the action template.
            include_dead: Whether zero-HP entities stay targetable.
            include_self: Whether to add the acting entity.
            default_pool: Precomputed pool from the outer discovery filter.
            target_pool_cache: Per-discovery cache for repeated spell variants.

        Returns:
            Visible target positions keyed by entity UUID.
        """
        cache_key = (action_filter, include_dead, include_self)
        if target_pool_cache is not None:
            cached = target_pool_cache.get(cache_key)
            if cached is not None:
                return cached

        if action_filter == "all":
            pool: Dict[UUID, Tuple[int, int]] = {}
            for k, v in self.senses.entities.items():
                if k == self.uuid:
                    continue
                if not include_dead:
                    other = Entity.get(k)
                    if other and not self._has_positive_normal_hp_for_discovery(other):
                        continue
                pool[k] = v
        elif action_filter in ("allies", "self_or_allies"):
            pool = dict(self.get_visible_allies(include_dead=include_dead))
        else:
            pool = dict(default_pool)

        if include_self:
            pool[self.uuid] = self.position
        if target_pool_cache is not None:
            target_pool_cache[cache_key] = pool
        return pool

    def _has_positive_normal_hp_for_discovery(self, entity: "Entity") -> bool:
        """Return whether action discovery should treat an entity as alive.

        This mirrors the normal-HP portion of `has_hp` without allocating the
        combined Constitution modifier object for every AoE preview target.
        Encounter death-save semantics are handled outside target discovery.
        """
        if "Dead" in entity.active_conditions:
            return False
        constitution = entity.ability_scores.get_ability("constitution")
        max_hp = (
            entity.health.get_max_hit_dices_points(constitution.modifier)
            + entity.health.max_hit_points_bonus.normalized_score
        )
        return max_hp - entity.health.damage_taken > 0

    def _validate_entity_targets(
        self,
        template: BaseAction,
        target_pool: Dict[UUID, Tuple[int, int]],
    ) -> List[AvailableTarget]:
        """Validate candidate entity targets against a template.

        Args:
            template: Action template being discovered.
            target_pool: Candidate positions keyed by target UUID.

        Returns:
            Valid targets with stable discovery indexes.
        """
        valid_targets: List[AvailableTarget] = []
        idx = 0
        for target_uuid, target_pos in target_pool.items():
            template.set_target_entity(target_uuid)
            if template.pre_validate():
                target_entity = Entity.get(target_uuid)
                valid_targets.append(AvailableTarget(
                    index=idx,
                    target_uuid=target_uuid,
                    position=target_pos,
                    target_name=target_entity.name if target_entity else None,
                    distance=self.senses.get_feet_distance(target_pos)
                ))
                idx += 1
        return valid_targets

    def _compute_aoe_at_position(
        self,
        shape: Any,
        shape_definition_key: Tuple[Any, ...],
        pos: Tuple[int, int],
        template: BaseAction,
        include_dead: bool,
        caster_visible_positions: AbstractSet[Tuple[int, int]],
        fov_cache: dict,
        barrier_positions: Set[Tuple[int, int]],
        idx: int,
    ) -> Optional[AvailableTarget]:
        """Compute AoE preview metadata for a candidate position.

        Args:
            shape: Reusable preview shape to aim at the candidate position.
            shape_definition_key: Precomputed immutable identity for the shape.
            pos: Candidate target position.
            template: Action template being discovered.
            include_dead: Whether zero-HP entities stay targetable.
            caster_visible_positions: Visibility snapshot shared by this query.
            fov_cache: Shared field-of-view cache for AoE computation.
            barrier_positions: Positions that block AoE projection.
            idx: Discovery index to assign if the position is valid.

        Returns:
            Available target with AoE metadata, or `None` if filtered out.
        """
        shape.target = pos
        footprint_key = (
            shape_definition_key,
            shape.footprint_target_key(self.position),
        )
        cache_started = time.perf_counter() if action_timing_enabled() else 0.0
        cached_footprint = self._aoe_footprint_cache.get(footprint_key)
        if cached_footprint is None:
            cached_footprint = frozenset(
                self._compute_aoe_propagation_footprint(
                    shape,
                    fov_cache,
                    barrier_positions,
                )
            )
            self._aoe_footprint_cache[footprint_key] = cached_footprint
            if cache_started:
                record_action_timing("available_actions.aoe_footprint_cache_miss_ms", cache_started)
        else:
            if cache_started:
                record_action_timing("available_actions.aoe_footprint_cache_hit_ms", cache_started)
        shape.set_subjective_footprint(
            self.position,
            self.senses,
            set(cached_footprint.intersection(caster_visible_positions)),
            caster_uuid=self.uuid,
        )

        affected_uuids = sorted(
            shape.affected_entity_uuids,
            key=target_resolution_sort_key,
        )

        if not template.include_self:
            affected_uuids = [uid for uid in affected_uuids if uid != self.uuid]

        vtf = template.valid_target_filter
        if vtf != "all":
            filtered = []
            for uid in affected_uuids:
                ent = Entity.get(uid)
                if ent:
                    if vtf == "enemies" and self.is_enemy(ent):
                        filtered.append(uid)
                    elif vtf == "allies" and self.is_ally(ent):
                        filtered.append(uid)
                    elif vtf == "self_or_allies":
                        if uid == self.uuid or self.is_ally(ent):
                            filtered.append(uid)
            affected_uuids = filtered

        template_include_dead = template.include_dead
        if not template_include_dead and not include_dead:
            affected_uuids = [
                uid for uid in affected_uuids
                if self._aoe_contact_alive.get(uid, False)
            ]

        if not affected_uuids and template.aoe_require_targets:
            return None

        affected_names = []
        for uid in affected_uuids:
            ent = Entity.get(uid)
            if ent:
                affected_names.append(ent.name or "Unknown")

        return AvailableTarget(
            index=idx,
            position=pos,
            distance=self.senses.get_feet_distance(pos),
            affected_entity_uuids=affected_uuids,
            affected_entity_names=affected_names,
            affected_count=len(affected_uuids),
            affected_positions=list(shape.affected_positions)
        )

    def _compute_aoe_propagation_footprint(
        self,
        shape: Any,
        fov_cache: dict,
        barrier_positions: Set[Tuple[int, int]],
    ) -> Set[Tuple[int, int]]:
        """Return shape geometry plus propagation before subjective visibility.

        The result is safe to cache inside authoritative engine state because
        it contains no target facts. Each discovery pass still intersects it
        with the actor's current visible cells before resolving entity UUIDs.
        """
        computed_origin = shape.get_origin(self.position)
        shape.computed_origin = computed_origin
        geometric = shape._get_positions_in_shape(computed_origin)
        if computed_origin == self.position:
            return set(geometric)
        if geometric.isdisjoint(barrier_positions):
            return set(geometric)
        grid = get_map()
        return grid.filter_propagation_positions(
            computed_origin,
            set(geometric),
            shape._get_max_radius_tiles(),
        )

    def _aoe_discovery_cache_key(
        self,
        template: BaseAction,
        valid_positions: List[Tuple[int, int]],
        include_dead: bool,
        shape_definition_key: Tuple[Any, ...],
    ) -> Tuple[Any, ...]:
        """Build a per-query cache key for AoE preview discovery.

        Args:
            template: AoE action template or generated spell variant.
            valid_positions: Candidate centers accepted by range and visibility.
            include_dead: Whether dead entities are included by the query.
            shape_definition_key: Precomputed immutable identity for the shape.

        Returns:
            Hashable key for the geometry and target filters that affect
            subjective AoE preview rows.
        """
        return (
            shape_definition_key,
            tuple(valid_positions),
            template.valid_target_filter,
            template.include_self,
            template.include_dead,
            include_dead,
            template.aoe_require_targets,
        )

    @staticmethod
    def _aoe_shape_definition_key(shape: Any) -> Tuple[Any, ...]:
        """Return every stable shape-definition field used by preview caches."""
        return (
            type(shape),
            shape.model_dump_json(
                exclude={
                    "target",
                    "computed_origin",
                    "affected_positions",
                    "affected_entity_uuids",
                },
                fallback=repr,
            ),
        )

    def _compact_aoe_candidate_positions(
        self,
        shape_template: Any,
        valid_positions: Sequence[Tuple[int, int]],
    ) -> List[Tuple[int, int]]:
        """Collapse target cells that resolve to the same AoE footprint."""
        if len(valid_positions) < 2:
            return list(valid_positions)

        original_target = shape_template.target
        positions_by_footprint: Dict[Tuple[object, ...], Tuple[int, int]] = {}
        try:
            for position in sorted(valid_positions):
                shape_template.target = position
                footprint_key = shape_template.footprint_target_key(self.position)
                positions_by_footprint.setdefault(footprint_key, position)
        finally:
            shape_template.target = original_target
        return list(positions_by_footprint.values())

    def _prepare_aoe_caches(
        self,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
    ) -> frozenset[Tuple[int, int]]:
        """Invalidate AoE caches and return the query visibility snapshot."""
        grid = get_map()
        visible_position_set = frozenset(
            caster_visible_positions
            if caster_visible_positions is not None
            else (
                position
                for position, visible in self.senses.visible.items()
                if visible
            )
        )
        visible_positions = tuple(sorted(visible_position_set))
        footprint_context = (
            self.position,
            grid.propagation_revision,
        )
        if footprint_context != self._aoe_footprint_cache_context:
            self._aoe_footprint_cache_context = footprint_context
            self._aoe_footprint_cache.clear()

        contact_facts: List[Tuple[Any, ...]] = []
        contact_alive: Dict[UUID, bool] = {
            self.uuid: self._has_positive_normal_hp_for_discovery(self)
        }
        for entity_uuid, perceived_position in self.senses.entities.items():
            entity = Entity.get(entity_uuid)
            if entity is None:
                contact_facts.append(
                    (str(entity_uuid), perceived_position, None, None, None)
                )
                continue
            alive = self._has_positive_normal_hp_for_discovery(entity)
            contact_alive[entity_uuid] = alive
            contact_facts.append(
                (
                    str(entity_uuid),
                    perceived_position,
                    entity.name,
                    entity.faction,
                    alive,
                )
            )
        self._aoe_contact_alive = contact_alive
        contact_facts.sort(key=lambda fact: fact[0])
        preview_context = (
            footprint_context,
            visible_positions,
            self.name,
            self.faction,
            self._has_positive_normal_hp_for_discovery(self),
            tuple(contact_facts),
        )
        if preview_context != self._aoe_preview_cache_context:
            self._aoe_preview_cache_context = preview_context
            self._aoe_preview_cache.clear()
            self._aoe_nearby_candidates_cache.clear()
        return visible_position_set

    def _aoe_required_target_prefilter_positions(
        self,
        template: BaseAction,
        include_dead: bool,
    ) -> Set[Tuple[int, int]]:
        """Return visible positions that can satisfy an AoE target requirement.

        Args:
            template: Position-AoE action whose required targets are being
                discovered.
            include_dead: Discovery-level dead-target override.

        Returns:
            Visible positions that can contribute at least one affected entity
            after the action relationship filter is applied.
        """
        positions: Set[Tuple[int, int]] = set()
        target_filter = template.valid_target_filter
        allow_dead = include_dead or template.include_dead

        for entity_uuid, perceived_position in self.senses.entities.items():
            entity = Entity.get(entity_uuid)
            if entity is None:
                if target_filter == "all":
                    positions.add(perceived_position)
                continue
            if not allow_dead and not self._has_positive_normal_hp_for_discovery(entity):
                continue

            if target_filter == "enemies":
                matches = self.is_enemy(entity)
            elif target_filter == "allies":
                matches = self.is_ally(entity)
            elif target_filter == "self_or_allies":
                matches = self.is_ally(entity)
            elif target_filter == "all":
                matches = True
            else:
                matches = True

            if matches:
                positions.add(perceived_position)

        if template.include_self and (allow_dead or self._has_positive_normal_hp_for_discovery(self)):
            if target_filter in {"all", "allies", "self_or_allies"} or target_filter not in {
                "enemies",
                "allies",
                "self_or_allies",
                "all",
            }:
                positions.add(self.position)

        return positions

    def _collect_self_actions(
        self,
        discovery_variants: Optional[Mapping[UUID, List[BaseAction]]] = None,
        legal_only: bool = False,
    ) -> List[AvailableActionInfo]:
        """Collect SELF-targeting actions (Dash, Dodge, etc.)."""
        actions: List[AvailableActionInfo] = []
        for registered_template in self.self_actions:
            variants = (
                discovery_variants.get(registered_template.uuid)
                if discovery_variants is not None
                else None
            )
            if variants is None:
                variants = registered_template.get_discovery_variants(self)
            for template in variants:
                template_name = template.get_discovery_template_name()
                display_name = template.get_discovery_display_name()
                can_afford = template.check_costs()
                if legal_only and not can_afford:
                    continue
                is_valid = can_afford and template.pre_validate()
                if is_valid or not can_afford:
                    actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=TargetType.SELF,
                        valid_targets=[AvailableTarget(index=0)] if is_valid else [],
                        can_afford=can_afford,
                        template=template,
                        display_name=display_name,
                    ))
        return actions

    def _collect_entity_actions(
        self,
        potential_targets: Dict[UUID, Tuple[int, int]],
        include_dead: bool,
        discovery_variants: Optional[Mapping[UUID, List[BaseAction]]] = None,
        legal_only: bool = False,
    ) -> List[AvailableActionInfo]:
        """Collect entity-targeting actions.

        Args:
            potential_targets: Outer discovery target pool keyed by UUID.
            include_dead: Whether zero-HP entities stay targetable.

        Returns:
            Available entity-targeting action metadata.
        """
        actions: List[AvailableActionInfo] = []
        timing = action_timing_enabled()
        started = time.perf_counter() if timing else 0.0
        registered_entity_actions = self.entity_actions
        target_pool_cache: Dict[Tuple[str, bool, bool], Dict[UUID, Tuple[int, int]]] = {}
        if timing:
            record_action_timing("available_actions.entity_actions.list_templates_ms", started)

        for registered_template in registered_entity_actions:
            base_label = self._timing_label(registered_template.name)
            started = time.perf_counter() if timing else 0.0
            variants = (
                discovery_variants.get(registered_template.uuid)
                if discovery_variants is not None
                else None
            )
            if variants is None:
                variants = registered_template.get_discovery_variants(self)
            if timing:
                record_action_timing(
                    f"available_actions.entity_actions.variant_generation.{base_label}_ms",
                    started,
                )

            for template in variants:
                started = time.perf_counter() if timing else 0.0
                template_name = template.get_discovery_template_name()
                template_label = self._timing_label(template_name)
                display_name = template.get_discovery_display_name()
                if timing:
                    record_action_timing(
                        f"available_actions.entity_actions.discovery_names.{template_label}_ms",
                        started,
                    )

                started = time.perf_counter() if timing else 0.0
                can_afford = template.check_costs()
                if timing:
                    record_action_timing(
                        f"available_actions.entity_actions.check_costs.{template_label}_ms",
                        started,
                    )
                    record_action_timing("available_actions.entity_actions.check_costs_total_ms", started)
                if legal_only and not can_afford:
                    continue

                started = time.perf_counter() if timing else 0.0
                target_pool = self._compute_target_pool(
                    template.valid_target_filter, include_dead,
                    template.include_self, potential_targets, target_pool_cache
                )
                if timing:
                    record_action_timing(
                        f"available_actions.entity_actions.target_pool.{template_label}_ms",
                        started,
                    )
                    record_action_timing("available_actions.entity_actions.target_pool_total_ms", started)

                started = time.perf_counter() if timing else 0.0
                valid_targets = self._validate_entity_targets(template, target_pool)
                if timing:
                    record_action_timing(
                        f"available_actions.entity_actions.validate_targets.{template_label}_ms",
                        started,
                    )
                    record_action_timing("available_actions.entity_actions.validate_targets_total_ms", started)

                if not valid_targets:
                    continue

                started = time.perf_counter() if timing else 0.0
                weapon_name: Optional[str] = None
                weapon_slot_str: Optional[str] = None
                damage_types: List[str] = []

                weapon_slot_attr = getattr(template, 'weapon_slot', None)
                if weapon_slot_attr is not None:
                    weapon_slot_str = weapon_slot_attr.value if isinstance(weapon_slot_attr, WeaponSlot) else str(weapon_slot_attr)
                    weapon = self.equipment._get_weapon_by_slot(weapon_slot_attr)
                    if isinstance(weapon, Weapon):
                        weapon_name = weapon.name
                        damage_types = [getattr(weapon.damage_type, "value", str(weapon.damage_type))]
                        damage_types.extend(getattr(extra, "value", str(extra)) for extra in weapon.extra_damage_type)
                        if template_name.startswith("Extra Attack"):
                            display_name = f"Extra Attack ({weapon_name})"
                        else:
                            display_name = weapon_name
                if timing:
                    record_action_timing(
                        f"available_actions.entity_actions.weapon_metadata.{template_label}_ms",
                        started,
                    )

                started = time.perf_counter() if timing else 0.0
                actions.append(self._make_action_info(
                    template_name=template_name,
                    target_type=template.effective_target_type,
                    valid_targets=valid_targets,
                    can_afford=can_afford,
                    template=template,
                    display_name=display_name,
                    weapon_slot=weapon_slot_str,
                    weapon_name=weapon_name,
                    damage_types=damage_types,
                ))
                if timing:
                    record_action_timing(
                        f"available_actions.entity_actions.make_info.{template_label}_ms",
                        started,
                    )
                    record_action_timing("available_actions.entity_actions.make_info_total_ms", started)
        return actions

    def _collect_declared_position_targets(
        self,
        template: BaseAction,
        contract: PositionDiscoveryContract,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
    ) -> List[AvailableTarget]:
        """Materialize plain-position candidates from subjective facts."""
        self._prepare_position_preview_cache(caster_visible_positions)
        action_range = template.get_range()
        max_range = action_range.normal if action_range is not None else 0
        remaining_movement = self.action_economy.movement.normalized_score
        threat_domains = (
            self._visible_hostile_threat_domains()
            if template.is_movement
            else []
        )
        threat_signature = tuple(
            (
                str(reactor.uuid),
                tuple(sorted(threatened_positions)),
            )
            for reactor, threatened_positions in threat_domains
        )
        cache_key = (
            template.get_semantic_key(),
            contract.model_dump_json(),
            max_range,
            remaining_movement if contract.bounded_by_remaining_movement else None,
            threat_signature,
        )
        cached_targets = self._position_preview_cache.get(cache_key)
        if cached_targets is not None:
            return list(cached_targets)

        if contract.candidate_source == "reachable":
            candidate_positions = self.senses.paths.keys()
        else:
            candidate_positions = self._get_subjective_visible_positions(
                template,
                caster_visible_positions,
            )

        perceived_occupancy = set(self.senses.entities.values())
        perceived_occupancy.add(self.position)
        targets: List[AvailableTarget] = []
        for position in sorted(candidate_positions):
            if contract.exclude_source_position and position == self.position:
                continue
            distance = self.senses.get_feet_distance(position)
            if max_range > 0 and distance > max_range:
                continue
            if (
                contract.bounded_by_remaining_movement
                and distance > remaining_movement
            ):
                continue
            if (
                contract.requires_subjective_walkable
                and not self._is_subjectively_walkable_position(position)
            ):
                continue
            if (
                contract.requires_subjective_unoccupied
                and position in perceived_occupancy
            ):
                continue
            disclosed_path = template.get_disclosed_movement_path(
                self.position,
                position,
            )
            targets.append(
                AvailableTarget(
                    index=len(targets),
                    position=position,
                    distance=distance,
                    path_cost=(
                        distance
                        if contract.distance_is_movement_cost
                        else None
                    ),
                    path=disclosed_path,
                    opportunity_attack_exposures=(
                        self._opportunity_attack_exposures_for_path(
                            disclosed_path,
                            threat_domains,
                        )
                        if disclosed_path is not None
                        else []
                    ),
                )
            )
        self._position_preview_cache[cache_key] = tuple(targets)
        return targets

    def _prepare_position_preview_cache(
        self,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
    ) -> None:
        """Invalidate position previews when subjective destination facts change."""
        visible_positions = tuple(
            sorted(
                caster_visible_positions
                if caster_visible_positions is not None
                else (
                    position
                    for position, visible in self.senses.visible.items()
                    if visible
                )
            )
        )
        walkable_facts = tuple(sorted(self.senses.walkable.items()))
        entity_facts = tuple(
            sorted(
                (str(entity_uuid), position)
                for entity_uuid, position in self.senses.entities.items()
            )
        )
        object_facts: List[Tuple[Any, ...]] = []
        for object_uuid, position in self.senses.objects.items():
            block = BaseBlock.get(object_uuid)
            object_facts.append(
                (
                    str(object_uuid),
                    position,
                    block.blocks_walking(self.uuid, MovementMode.WALKING)
                    if block is not None
                    else None,
                )
            )
        object_facts.sort(key=lambda fact: fact[0])
        context = (
            self.position,
            visible_positions,
            walkable_facts,
            entity_facts,
            tuple(object_facts),
            tuple(sorted(self.senses.collision_blocked)),
            self.senses.path_revision,
            get_map().movement_revision,
        )
        if context == self._position_preview_cache_context:
            return
        self._position_preview_cache_context = context
        self._position_preview_cache.clear()
        self._visible_position_cache.clear()

    def _get_subjective_visible_positions(
        self,
        template: BaseAction,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
    ) -> Tuple[Tuple[int, int], ...]:
        """Return cached visible candidate cells within an action's range."""
        action_range = template.get_range()
        max_range = action_range.normal if action_range is not None else 0
        cached = self._visible_position_cache.get(max_range)
        if cached is not None:
            return cached
        positions = tuple(
            sorted(
                position
                for position in (
                    caster_visible_positions
                    if caster_visible_positions is not None
                    else (
                        candidate_position
                        for candidate_position, visible in self.senses.visible.items()
                        if visible
                    )
                )
                if position != self.position
                and (
                    max_range <= 0
                    or self.senses.get_feet_distance(position) <= max_range
                )
            )
        )
        self._visible_position_cache[max_range] = positions
        return positions

    def _is_subjectively_walkable_position(self, position: Tuple[int, int]) -> bool:
        """Return whether perceived terrain and objects allow walking."""
        if not self.senses.walkable.get(position, False):
            return False
        if position in self.senses.collision_blocked:
            return False
        for object_uuid, object_position in self.senses.objects.items():
            if object_position != position:
                continue
            block = BaseBlock.get(object_uuid)
            if block is not None and block.blocks_walking(
                self.uuid,
                MovementMode.WALKING,
            ):
                return False
        return True

    def _collect_path_actions(
        self,
        remaining_movement: int,
        discovery_variants: Optional[Mapping[UUID, List[BaseAction]]] = None,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
        legal_only: bool = False,
    ) -> List[AvailableActionInfo]:
        """Collect path-based movement and plain-position actions.

        Args:
            remaining_movement: Remaining movement in feet for display.

        Returns:
            Available path-targeting action metadata.
        """
        grid = get_map()
        actions: List[AvailableActionInfo] = []
        for registered_template in self.position_actions:
            variants = (
                discovery_variants.get(registered_template.uuid)
                if discovery_variants is not None
                else None
            )
            if variants is None:
                variants = registered_template.get_discovery_variants(self)
            for template in variants:
                target_type = template.effective_target_type
                if target_type not in (TargetType.POSITION, TargetType.POSITION_PATH):
                    continue

                can_afford = template.check_costs()
                template_name = template.get_discovery_template_name()
                display_name = template.get_discovery_display_name()
                if not can_afford:
                    if legal_only:
                        continue
                    actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=target_type,
                        valid_targets=[],
                        can_afford=False,
                        template=template,
                        display_name=display_name,
                    ))
                    continue

                valid_positions: List[AvailableTarget] = []
                if target_type == TargetType.POSITION and template.position_discovery is not None:
                    valid_positions = self._collect_declared_position_targets(
                        template,
                        template.position_discovery,
                        caster_visible_positions,
                    )
                else:
                    movement_mode = getattr(template, "movement_mode", MovementMode.WALKING)
                    if template.is_movement and remaining_movement <= 0:
                        valid_positions = []
                    elif movement_mode == MovementMode.WALKING:
                        paths_by_position = self.senses.paths
                    else:
                        _, computed_paths = grid.compute_paths(
                            self.senses.position,
                            requesting_entity_uuid=self.uuid,
                            movement_mode=movement_mode,
                            subjective=True,
                            ignore_difficult_terrain=self.ignore_difficult_terrain,
                        )
                        paths_by_position = {
                            pos: path
                            for pos, path in computed_paths.items()
                            if pos in self.senses.visible
                            and all(
                                step in self.senses.seen or step in self.senses.visible
                                for step in path
                            )
                        }

                    if template.is_movement and remaining_movement <= 0:
                        pass
                    elif self._can_fast_collect_move_targets(template, movement_mode):
                        valid_positions = self._collect_fast_move_targets(
                            paths_by_position,
                            remaining_movement,
                            movement_mode,
                        )
                    else:
                        map_has_hazards = grid.has_any_hazards()
                        threat_domains = self._visible_hostile_threat_domains()
                        for position, normal_path in paths_by_position.items():
                            if position == self.senses.position:
                                continue
                            template.set_target_position(position)
                            if not template.pre_validate():
                                continue
                            path_cost = next(
                                (
                                    cost.cost
                                    for cost in template.effective_costs
                                    if cost.cost_type == "movement"
                                ),
                                0,
                            )
                            is_hazardous = (
                                map_has_hazards
                                and any(
                                    grid.is_position_hazardous_for(
                                        step[0],
                                        step[1],
                                        self.uuid,
                                    )
                                    for step in normal_path[1:]
                                )
                            )
                            safe_path_list: Optional[List[Tuple[int, int]]] = None
                            safe_cost: Optional[int] = None
                            if (
                                movement_mode == MovementMode.WALKING
                                and is_hazardous
                                and position in self.senses.safe_paths
                            ):
                                safe_path_list = list(self.senses.safe_paths[position])
                                safe_cost = self._movement_path_cost_feet(
                                    safe_path_list,
                                    MovementMode.WALKING,
                                )
                            valid_positions.append(AvailableTarget(
                                index=len(valid_positions),
                                position=position,
                                distance=self.senses.get_feet_distance(position),
                                path_cost=path_cost,
                                is_path_hazardous=is_hazardous,
                                safe_path_cost=safe_cost,
                                path=list(normal_path),
                                safe_path=safe_path_list,
                                opportunity_attack_exposures=self._opportunity_attack_exposures_for_path(
                                    normal_path,
                                    threat_domains,
                                ),
                                safe_path_opportunity_attack_exposures=(
                                    self._opportunity_attack_exposures_for_path(
                                        safe_path_list,
                                        threat_domains,
                                    )
                                    if safe_path_list is not None
                                    else []
                                ),
                            ))

                if valid_positions:
                    actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=target_type,
                        valid_targets=valid_positions,
                        can_afford=True,
                        template=template,
                        display_name=display_name,
                    ))
        return actions

    def _can_fast_collect_move_targets(self, template: BaseAction, movement_mode: MovementMode) -> bool:
        """Return whether path action discovery can use cached senses paths."""
        if template.effective_target_type != TargetType.POSITION_PATH:
            return False
        if template.effective_costs:
            return False
        return template.is_movement

    def _collect_fast_move_targets(
        self,
        paths_by_position: Mapping[Tuple[int, int], List[Tuple[int, int]]],
        remaining_movement: int,
        movement_mode: MovementMode,
    ) -> List[AvailableTarget]:
        """Build legal movement targets from already-computed subjective paths."""
        movement_blocked = (
            "Dead" in self.active_conditions
            or "Incapacitated" in self.active_conditions
        )
        grid = get_map()
        cache_revision = (self.senses.path_revision, grid.movement_revision)
        if cache_revision != self._fast_move_target_cache_revision:
            self._fast_move_target_cache_revision = cache_revision
            self._fast_move_target_cache.clear()
        path_signature: Optional[Tuple[Any, ...]] = None
        if movement_mode != MovementMode.WALKING:
            path_signature = tuple(
                (position, tuple(path))
                for position, path in paths_by_position.items()
            )
        cost_signature: Optional[Tuple[Tuple[Tuple[int, int], int], ...]] = None
        safe_cost_signature: Optional[Tuple[Tuple[Tuple[int, int], int], ...]] = None
        if paths_by_position is self.senses.paths:
            cost_signature = tuple(sorted(self.senses.path_costs.items()))
            safe_cost_signature = tuple(sorted(self.senses.safe_path_costs.items()))
        cache_context = (
            self.position,
            self.senses.position,
            remaining_movement,
            self.ignore_difficult_terrain,
            movement_blocked,
            movement_mode,
            path_signature,
            cost_signature,
            safe_cost_signature,
        )
        if movement_blocked:
            return []
        if remaining_movement <= 0:
            return []

        threat_domains = self._visible_hostile_threat_domains()
        threat_signature = tuple(
            (
                str(reactor.uuid),
                tuple(sorted(threatened_positions)),
            )
            for reactor, threatened_positions in threat_domains
        )
        cache_context = (*cache_context, threat_signature)
        cached_targets = self._fast_move_target_cache.get(cache_context)
        if cached_targets is not None:
            return list(cached_targets)

        valid_positions: List[AvailableTarget] = []
        idx = 0
        map_has_hazards = grid.has_any_hazards()
        step_cost_cache: Dict[Tuple[int, int], float] = {}

        def cached_path_cost_feet(path: List[Tuple[int, int]]) -> int:
            total_cost = 0.0
            for step in path[1:]:
                step_cost = step_cost_cache.get(step)
                if step_cost is None:
                    tile = grid.get_tile(*step)
                    step_cost = tile.get_movement_cost(movement_mode) if tile else 1.0
                    if movement_mode == MovementMode.WALKING and self.ignore_difficult_terrain:
                        step_cost = min(step_cost, 1.0)
                    if (
                        movement_mode == MovementMode.SWIMMING
                        and self.swimming_speed <= 0
                        and not self.ignore_underwater_penalties
                    ):
                        step_cost *= 2
                    step_cost_cache[step] = step_cost
                total_cost += step_cost
            return int(total_cost * 5)

        timing = action_timing_enabled()
        path_cost_seconds = 0.0
        hazard_seconds = 0.0
        safe_path_seconds = 0.0
        exposure_seconds = 0.0
        target_model_seconds = 0.0
        for pos, normal_path in paths_by_position.items():
            if pos == self.senses.position:
                continue
            phase_started = time.perf_counter() if timing else 0.0
            cached_path_cost = (
                self.senses.path_costs.get(pos)
                if paths_by_position is self.senses.paths
                else None
            )
            path_cost = (
                cached_path_cost
                if cached_path_cost is not None
                else cached_path_cost_feet(normal_path)
            )
            if timing:
                path_cost_seconds += time.perf_counter() - phase_started
            if path_cost > remaining_movement:
                continue

            phase_started = time.perf_counter() if timing else 0.0
            is_hazardous = (
                map_has_hazards
                and any(
                    grid.is_position_hazardous_for(step[0], step[1], self.uuid)
                    for step in normal_path[1:]
                )
            )
            if timing:
                hazard_seconds += time.perf_counter() - phase_started

            safe_cost: Optional[int] = None
            safe_path_list: Optional[List[Tuple[int, int]]] = None
            if (
                movement_mode == MovementMode.WALKING
                and is_hazardous
                and pos in self.senses.safe_paths
            ):
                phase_started = time.perf_counter() if timing else 0.0
                safe_path_list = list(self.senses.safe_paths[pos])
                safe_cost = self.senses.safe_path_costs.get(pos)
                if safe_cost is None:
                    safe_cost = cached_path_cost_feet(safe_path_list)
                if timing:
                    safe_path_seconds += time.perf_counter() - phase_started

            phase_started = time.perf_counter() if timing else 0.0
            opportunity_attack_exposures = self._opportunity_attack_exposures_for_path(
                normal_path,
                threat_domains,
            )
            safe_path_opportunity_attack_exposures = (
                self._opportunity_attack_exposures_for_path(
                    safe_path_list,
                    threat_domains,
                )
                if safe_path_list is not None
                else []
            )
            if timing:
                exposure_seconds += time.perf_counter() - phase_started
            phase_started = time.perf_counter() if timing else 0.0
            valid_positions.append(AvailableTarget(
                index=idx,
                position=pos,
                distance=self.senses.get_feet_distance(pos),
                path_cost=path_cost,
                is_path_hazardous=is_hazardous,
                safe_path_cost=safe_cost,
                path=list(normal_path),
                safe_path=safe_path_list,
                opportunity_attack_exposures=opportunity_attack_exposures,
                safe_path_opportunity_attack_exposures=safe_path_opportunity_attack_exposures,
            ))
            if timing:
                target_model_seconds += time.perf_counter() - phase_started
            idx += 1
        if timing:
            record_action_elapsed("available_actions.fast_move_targets.path_cost_ms", path_cost_seconds)
            record_action_elapsed("available_actions.fast_move_targets.hazard_ms", hazard_seconds)
            record_action_elapsed("available_actions.fast_move_targets.safe_path_ms", safe_path_seconds)
            record_action_elapsed("available_actions.fast_move_targets.opportunity_exposure_ms", exposure_seconds)
            record_action_elapsed("available_actions.fast_move_targets.target_model_ms", target_model_seconds)
        self._fast_move_target_cache[cache_context] = tuple(valid_positions)
        return valid_positions

    def _movement_path_cost_feet(
        self,
        path: List[Tuple[int, int]],
        movement_mode: MovementMode,
    ) -> int:
        """Return movement cost in feet for a known path."""
        grid = get_map()
        total_cost = 0.0
        for step in path[1:]:
            tile = grid.get_tile(*step)
            if tile:
                step_cost = tile.get_movement_cost(movement_mode)
            else:
                step_cost = 1.0
            if movement_mode == MovementMode.WALKING and self.ignore_difficult_terrain:
                step_cost = min(step_cost, 1.0)
            if (
                movement_mode == MovementMode.SWIMMING
                and self.swimming_speed <= 0
                and not self.ignore_underwater_penalties
            ):
                step_cost *= 2
            total_cost += step_cost
        return int(total_cost * 5)

    def _collect_los_actions(
        self,
        discovery_variants: Optional[Mapping[UUID, List[BaseAction]]] = None,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
        legal_only: bool = False,
    ) -> List[AvailableActionInfo]:
        """Collect line-of-sight position actions."""
        actions: List[AvailableActionInfo] = []
        for registered_template in self.position_actions:
            variants = (
                discovery_variants.get(registered_template.uuid)
                if discovery_variants is not None
                else None
            )
            if variants is None:
                variants = registered_template.get_discovery_variants(self)
            for template in variants:
                if template.effective_target_type != TargetType.POSITION_LOS:
                    continue
                can_afford = template.check_costs()
                if template.position_discovery is not None:
                    valid_positions = (
                        self._collect_declared_position_targets(
                            template,
                            template.position_discovery,
                            caster_visible_positions,
                        )
                        if can_afford
                        else []
                    )
                    if valid_positions or not can_afford:
                        if legal_only and not can_afford:
                            continue
                        actions.append(self._make_action_info(
                            template_name=template.get_discovery_template_name(),
                            target_type=TargetType.POSITION_LOS,
                            valid_targets=valid_positions,
                            can_afford=can_afford,
                            template=template,
                            display_name=template.get_discovery_display_name(),
                        ))
                    continue
                valid_pos_list = template.get_valid_positions()
                valid_positions: List[AvailableTarget] = []
                idx = 0
                if legal_only and not can_afford:
                    continue
                for pos in valid_pos_list:
                    template.set_target_position(pos)
                    if template.pre_validate():
                        valid_positions.append(AvailableTarget(
                            index=idx,
                            position=pos,
                            distance=self.senses.get_feet_distance(pos),
                            path_cost=None
                        ))
                        idx += 1

                if valid_positions:
                    actions.append(self._make_action_info(
                        template_name=template.get_discovery_template_name(),
                        target_type=TargetType.POSITION_LOS,
                        valid_targets=valid_positions,
                        can_afford=can_afford,
                        template=template,
                        display_name=template.get_discovery_display_name(),
                    ))
        return actions

    def _collect_aoe_actions(
        self,
        include_dead: bool,
        fov_cache: dict,
        barrier_positions: Set[Tuple[int, int]],
        discovery_variants: Optional[Mapping[UUID, List[BaseAction]]] = None,
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
        legal_only: bool = False,
    ) -> List[AvailableActionInfo]:
        """Collect position-AoE actions with preview metadata.

        Args:
            include_dead: Whether zero-HP entities stay targetable.
            fov_cache: Shared field-of-view cache for AoE computation.
            barrier_positions: Positions that block AoE projection.

        Returns:
            Available AoE action metadata.
        """
        actions: List[AvailableActionInfo] = []
        grid = get_map()
        visible_position_set = self._prepare_aoe_caches(caster_visible_positions)
        self._prepare_position_preview_cache(visible_position_set)

        for registered_template in self.position_actions:
            variants = (
                discovery_variants.get(registered_template.uuid)
                if discovery_variants is not None
                else None
            )
            if variants is None:
                variants = registered_template.get_discovery_variants(self)
            for template in variants:
                if template.effective_target_type != TargetType.POSITION_AOE:
                    continue

                shape_template = template.aoe_shape
                if shape_template is None:
                    continue

                can_afford = template.check_costs()
                template_name = template.get_discovery_template_name()
                display_name = template.get_discovery_display_name()

                if not can_afford:
                    if legal_only:
                        continue
                    actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=TargetType.POSITION_AOE,
                        valid_targets=[],
                        can_afford=False,
                        template=template,
                        display_name=display_name,
                    ))
                    continue

                if type(template).get_valid_positions is BaseAction.get_valid_positions:
                    valid_pos_list = list(
                        self._get_subjective_visible_positions(
                            template,
                            visible_position_set,
                        )
                    )
                else:
                    valid_pos_list = template.get_valid_positions()

                if template.aoe_require_targets:
                    prefilter_positions = self._aoe_required_target_prefilter_positions(
                        template,
                        include_dead,
                    )
                    if prefilter_positions:
                        radius = shape_template._get_max_radius_tiles()
                        nearby_key = (tuple(sorted(prefilter_positions)), radius)
                        candidates = self._aoe_nearby_candidates_cache.get(nearby_key)
                        if candidates is None:
                            candidates = frozenset(
                                grid.get_positions_near_entities(
                                    prefilter_positions,
                                    radius,
                                )
                            )
                            self._aoe_nearby_candidates_cache[nearby_key] = candidates
                        valid_pos_list = [pos for pos in valid_pos_list if pos in candidates]
                    else:
                        action_range = template.get_range()
                        if action_range and action_range.type == RangeType.SELF:
                            actions.append(self._make_action_info(
                                template_name=template_name,
                                target_type=TargetType.POSITION_AOE,
                                valid_targets=[],
                                can_afford=True,
                                template=template,
                                display_name=display_name,
                            ))
                        continue

                valid_pos_list = self._compact_aoe_candidate_positions(
                    shape_template,
                    valid_pos_list,
                )
                shape_definition_key = self._aoe_shape_definition_key(shape_template)
                cache_key = self._aoe_discovery_cache_key(
                    template,
                    valid_pos_list,
                    include_dead,
                    shape_definition_key,
                )
                if cache_key in self._aoe_preview_cache:
                    cached_targets = self._aoe_preview_cache[cache_key]
                    if cached_targets:
                        actions.append(self._make_action_info(
                            template_name=template_name,
                            target_type=TargetType.POSITION_AOE,
                            valid_targets=list(cached_targets),
                            can_afford=True,
                            template=template,
                            display_name=display_name,
                        ))
                    continue

                valid_positions: List[AvailableTarget] = []
                idx = 0
                preview_shape = shape_template.model_copy()
                for pos in valid_pos_list:
                    target = self._compute_aoe_at_position(
                        preview_shape, shape_definition_key, pos, template, include_dead,
                        visible_position_set, fov_cache, barrier_positions, idx
                    )
                    if target is not None:
                        valid_positions.append(target)
                        idx += 1

                self._aoe_preview_cache[cache_key] = tuple(valid_positions)
                if valid_positions:
                    actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=TargetType.POSITION_AOE,
                        valid_targets=valid_positions,
                        can_afford=True,
                        template=template,
                        display_name=display_name,
                    ))
        return actions

    def _collect_object_actions(self, legal_only: bool = False) -> List[AvailableActionInfo]:
        """Collect object-targeting actions."""
        actions: List[AvailableActionInfo] = []
        for template in self.object_actions:
            valid_targets: List[AvailableTarget] = []
            idx = 0
            can_afford = template.check_costs()
            if legal_only and not can_afford:
                continue

            for obj_uuid, obj_pos in self.senses.objects.items():
                obj_block = BaseBlock.get(obj_uuid)
                if obj_block is not None and not obj_block.should_include_in_available_object_actions():
                    continue
                template.set_target_entity(obj_uuid)
                if template.pre_validate():
                    obj_name = obj_block.name if obj_block else "Object"
                    distance = self.senses.get_feet_distance(obj_pos)
                    valid_targets.append(AvailableTarget(
                        index=idx,
                        target_uuid=obj_uuid,
                        position=obj_pos,
                        target_name=obj_name,
                        distance=distance
                    ))
                    idx += 1

            if valid_targets:
                template_name = template.name or "Unknown"
                actions.append(self._make_action_info(
                    template_name=template_name,
                    target_type=TargetType.OBJECT,
                    valid_targets=valid_targets,
                    can_afford=can_afford,
                    template=template,
                ))
        return actions

    def _collect_use_actions(
        self,
        result: AvailableActionsResult,
        potential_targets: Dict[UUID, Tuple[int, int]],
        include_dead: bool,
        fov_cache: dict,
        barrier_positions: Set[Tuple[int, int]],
        caster_visible_positions: Optional[AbstractSet[Tuple[int, int]]] = None,
        legal_only: bool = False,
    ) -> None:
        """Collect use actions from inventory and nearby environment objects.

        Args:
            result: Discovery result mutated in place.
            potential_targets: Outer discovery target pool keyed by UUID.
            include_dead: Whether zero-HP entities stay targetable.
            fov_cache: Shared field-of-view cache for AoE computation.
            barrier_positions: Positions that block AoE projection.
        """
        grid = get_map()
        visible_position_set = self._prepare_aoe_caches(caster_visible_positions)
        target_pool_cache: Dict[Tuple[str, bool, bool], Dict[UUID, Tuple[int, int]]] = {}

        use_sources: List[Tuple[BaseAction, Optional[UUID], str, Optional[int]]] = []

        inventory_use_actions = self.inventory.get_all_use_actions(self.uuid)
        result.set_inventory_use_action_sources(inventory_use_actions)
        for use_template in inventory_use_actions:
            item_uuid = use_template.source_item_uuid
            item = BaseBlock.get(item_uuid) if item_uuid else None
            item_name = item.name if item else "Item"
            item_stack = getattr(item, 'stack_count', None) if item else None
            use_sources.append((use_template, item_uuid, item_name, item_stack))

        for obj_uuid, obj_pos in self.senses.objects.items():
            obj = BaseBlock.get(obj_uuid)
            if not isinstance(obj, UsableItem):
                continue
            if not obj.should_include_in_available_object_actions():
                continue
            if self.senses.get_feet_distance(obj_pos) > 5:
                continue
            for use_template in obj.get_use_actions(self.uuid):
                use_sources.append((use_template, obj_uuid, obj.name, None))

        for use_template, item_uuid, item_name, item_stack in use_sources:
            source_item = BaseBlock.get(item_uuid) if item_uuid is not None else None
            if isinstance(source_item, UsableItem):
                current_uses = source_item.remaining_finite_uses()
                maximum_uses = source_item.maximum_finite_uses()
                if current_uses is not None and maximum_uses is not None:
                    result.set_item_charge_pool(
                        source_item.uuid,
                        current_uses,
                        maximum_uses,
                    )
            base_name = use_template.name or "Use"
            template_name = f"{base_name}__item_{item_uuid}"
            stack_suffix = f" x{item_stack}" if item_stack and item_stack > 1 else ""
            display_name = f"{base_name} ({item_name}{stack_suffix})"
            stack_count_field = item_stack if item_stack and item_stack > 1 else None
            can_afford = use_template.check_costs()
            if legal_only and not can_afford:
                continue

            if use_template.target_type == TargetType.SELF:
                if not use_template.pre_validate():
                    continue
                result.self_actions.append(self._make_action_info(
                    template_name=template_name,
                    target_type=TargetType.SELF,
                    valid_targets=[AvailableTarget(index=0)],
                    can_afford=can_afford,
                    template=use_template,
                    display_name=display_name,
                    is_item_use=True,
                    source_item_uuid=item_uuid,
                    item_stack_count=stack_count_field,
                ))

            elif use_template.target_type in (TargetType.ENTITY, TargetType.MULTI_ENTITY):
                target_pool = self._compute_target_pool(
                    use_template.valid_target_filter, include_dead,
                    use_template.include_self, potential_targets, target_pool_cache
                )
                valid_targets = self._validate_entity_targets(use_template, target_pool)
                if valid_targets:
                    result.entity_actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=use_template.effective_target_type,
                        valid_targets=valid_targets,
                        can_afford=can_afford,
                        template=use_template,
                        display_name=display_name,
                        is_item_use=True,
                        source_item_uuid=item_uuid,
                        item_stack_count=stack_count_field,
                    ))

            elif use_template.target_type == TargetType.POSITION_AOE:
                use_shape_template = use_template.aoe_shape
                if use_shape_template is None:
                    continue

                if not can_afford:
                    if legal_only:
                        continue
                    result.position_actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=TargetType.POSITION_AOE,
                        valid_targets=[],
                        can_afford=False,
                        template=use_template,
                        display_name=display_name,
                        is_item_use=True,
                        source_item_uuid=item_uuid,
                        item_stack_count=stack_count_field,
                    ))
                    continue

                valid_pos_list = use_template.get_valid_positions()

                if use_template.aoe_require_targets:
                    prefilter_positions = self._aoe_required_target_prefilter_positions(
                        use_template,
                        include_dead,
                    )
                    if prefilter_positions:
                        radius = use_shape_template._get_max_radius_tiles()
                        nearby_key = (tuple(sorted(prefilter_positions)), radius)
                        candidates = self._aoe_nearby_candidates_cache.get(nearby_key)
                        if candidates is None:
                            candidates = frozenset(
                                grid.get_positions_near_entities(
                                    prefilter_positions,
                                    radius,
                                )
                            )
                            self._aoe_nearby_candidates_cache[nearby_key] = candidates
                        valid_pos_list = [pos for pos in valid_pos_list if pos in candidates]
                    else:
                        use_action_range = use_template.get_range()
                        if use_action_range and use_action_range.type == RangeType.SELF:
                            result.position_actions.append(self._make_action_info(
                                template_name=template_name,
                                target_type=TargetType.POSITION_AOE,
                                valid_targets=[],
                                can_afford=True,
                                template=use_template,
                                display_name=display_name,
                                is_item_use=True,
                                source_item_uuid=item_uuid,
                                item_stack_count=stack_count_field,
                            ))
                        continue

                valid_pos_list = self._compact_aoe_candidate_positions(
                    use_shape_template,
                    valid_pos_list,
                )
                use_shape_definition_key = self._aoe_shape_definition_key(
                    use_shape_template
                )
                cache_key = self._aoe_discovery_cache_key(
                    use_template,
                    valid_pos_list,
                    include_dead,
                    use_shape_definition_key,
                )
                if cache_key in self._aoe_preview_cache:
                    cached_targets = self._aoe_preview_cache[cache_key]
                    if cached_targets:
                        result.position_actions.append(self._make_action_info(
                            template_name=template_name,
                            target_type=TargetType.POSITION_AOE,
                            valid_targets=list(cached_targets),
                            can_afford=True,
                            template=use_template,
                            display_name=display_name,
                            is_item_use=True,
                            source_item_uuid=item_uuid,
                            item_stack_count=stack_count_field,
                        ))
                    continue

                use_valid_positions: List[AvailableTarget] = []
                use_idx = 0
                use_preview_shape = use_shape_template.model_copy()
                for pos in valid_pos_list:
                    target = self._compute_aoe_at_position(
                        use_preview_shape,
                        use_shape_definition_key,
                        pos,
                        use_template,
                        include_dead,
                        visible_position_set,
                        fov_cache, barrier_positions, use_idx
                    )
                    if target is not None:
                        use_valid_positions.append(target)
                        use_idx += 1
                self._aoe_preview_cache[cache_key] = tuple(use_valid_positions)
                if use_valid_positions:
                    result.position_actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=TargetType.POSITION_AOE,
                        valid_targets=use_valid_positions,
                        can_afford=True,
                        template=use_template,
                        display_name=display_name,
                        is_item_use=True,
                        source_item_uuid=item_uuid,
                        item_stack_count=stack_count_field,
                    ))

            elif use_template.target_type == TargetType.POSITION_LOS:
                use_valid_pos_list = use_template.get_valid_positions()
                use_valid_positions_los: List[AvailableTarget] = []
                use_idx = 0
                for pos in use_valid_pos_list:
                    use_template.set_target_position(pos)
                    if use_template.pre_validate():
                        use_valid_positions_los.append(AvailableTarget(
                            index=use_idx,
                            position=pos,
                            distance=self.senses.get_feet_distance(pos),
                        ))
                        use_idx += 1
                if use_valid_positions_los:
                    result.position_actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=TargetType.POSITION_LOS,
                        valid_targets=use_valid_positions_los,
                        can_afford=can_afford,
                        template=use_template,
                        display_name=display_name,
                        is_item_use=True,
                        source_item_uuid=item_uuid,
                        item_stack_count=stack_count_field,
                    ))

            elif use_template.target_type in (TargetType.POSITION, TargetType.POSITION_PATH):
                use_valid_positions_pos: List[AvailableTarget] = []
                use_idx = 0
                action_range = use_template.get_range()
                max_range = action_range.normal if action_range else 0
                for pos, is_visible in self.senses.visible.items():
                    if not is_visible:
                        continue
                    if pos == self.senses.position:
                        continue
                    dist = self.senses.get_feet_distance(pos)
                    if max_range > 0 and dist > max_range:
                        continue
                    use_template.set_target_position(pos)
                    if use_template.pre_validate():
                        use_valid_positions_pos.append(AvailableTarget(
                            index=use_idx,
                            position=pos,
                            distance=dist,
                        ))
                        use_idx += 1
                if use_valid_positions_pos:
                    result.position_actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=use_template.effective_target_type,
                        valid_targets=use_valid_positions_pos,
                        can_afford=can_afford,
                        template=use_template,
                        display_name=display_name,
                        is_item_use=True,
                        source_item_uuid=item_uuid,
                        item_stack_count=stack_count_field,
                    ))

    def get_available_actions(
        self,
        target_filter: str = "enemies",
        include_dead: bool = False,
        legal_only: bool = False,
    ) -> AvailableActionsResult:
        """Get all available actions for this entity.

        Returns grouped actions the entity can currently perform. Each action
        includes indexed targets for controller commands.

        The method is agnostic of specific action subclasses; it iterates over
        registered templates by target type and calls `pre_validate()`.

        Args:
            target_filter: Which entities to show as targets for entity actions.
                Supports enemies, allies, and all.
            include_dead: If True, include dead entities as valid targets.
            legal_only: When true, omit unaffordable action rows and skip their
                expensive target discovery. Public/debug callers should keep the
                default to preserve explanatory unaffordable rows.

        Returns:
            Grouped discovery result for the acting entity.
        """
        timing = action_timing_enabled()
        started = time.perf_counter() if timing else 0.0
        remaining_movement = self.action_economy.movement.normalized_score
        if timing:
            record_action_timing("available_actions.remaining_movement_ms", started)

        started = time.perf_counter() if timing else 0.0
        result = AvailableActionsResult(
            entity_uuid=self.uuid,
            remaining_movement=remaining_movement
        )
        if timing:
            record_action_timing("available_actions.result_model_ms", started)

        started = time.perf_counter() if timing else 0.0
        discovery_variants = {
            template.uuid: template.get_discovery_variants(self)
            for template in self.registered_actions
        }
        result.set_registered_action_variants([
            variant
            for template in self.registered_actions
            for variant in discovery_variants[template.uuid]
        ])
        if timing:
            record_action_timing("available_actions.registered_variants_ms", started)

        started = time.perf_counter() if timing else 0.0
        if target_filter == "enemies":
            potential_targets = self.get_visible_enemies(include_dead=include_dead)
        elif target_filter == "allies":
            potential_targets = self.get_visible_allies(include_dead=include_dead)
        else:
            potential_targets: Dict[UUID, Tuple[int, int]] = {}
            for k, v in self.senses.entities.items():
                if k == self.uuid:
                    continue
                if not include_dead:
                    other = Entity.get(k)
                    if other and not other.has_hp:
                        continue
                potential_targets[k] = v
        if timing:
            record_action_timing("available_actions.potential_targets_ms", started)

        started = time.perf_counter() if timing else 0.0
        result.self_actions = self._collect_self_actions(discovery_variants, legal_only)
        if timing:
            record_action_timing("available_actions.collect_self_actions_ms", started)

        started = time.perf_counter() if timing else 0.0
        result.entity_actions = self._collect_entity_actions(
            potential_targets,
            include_dead,
            discovery_variants,
            legal_only,
        )
        if timing:
            record_action_timing("available_actions.collect_entity_actions_ms", started)

        required_path_distance = max(1, (remaining_movement + 4) // 5) if remaining_movement > 0 else 0
        paths_need_refresh = (
            required_path_distance > 0
            and not self.senses.has_clean_paths_for_distance(required_path_distance)
        )
        if paths_need_refresh:
            started = time.perf_counter() if timing else 0.0
            self.update_entity_senses(max_distance=20, path_max_distance=required_path_distance)
            if timing:
                record_action_timing("available_actions.update_dirty_senses_ms", started)
        elif self.senses._paths_dirty and timing:
            record_action_timing("available_actions.skip_dirty_senses_no_movement_ms", time.perf_counter())

        started = time.perf_counter() if timing else 0.0
        grid = get_map()
        if self._aoe_origin_fov_cache_revision != grid.propagation_revision:
            self._aoe_origin_fov_cache_revision = grid.propagation_revision
            self._aoe_origin_fov_cache.clear()
        fov_cache: dict = self._aoe_origin_fov_cache
        barrier_positions = grid.get_barrier_positions()
        caster_visible_positions = frozenset(
            position
            for position, visible in self.senses.visible.items()
            if visible
        )
        if timing:
            record_action_timing("available_actions.prepare_position_context_ms", started)

        started = time.perf_counter() if timing else 0.0
        result.position_actions = self._collect_path_actions(
            result.remaining_movement,
            discovery_variants,
            caster_visible_positions,
            legal_only,
        )
        if timing:
            record_action_timing("available_actions.collect_path_actions_ms", started)

        started = time.perf_counter() if timing else 0.0
        result.position_actions.extend(
            self._collect_los_actions(
                discovery_variants,
                caster_visible_positions,
                legal_only,
            )
        )
        if timing:
            record_action_timing("available_actions.collect_los_actions_ms", started)

        started = time.perf_counter() if timing else 0.0
        result.position_actions.extend(
            self._collect_aoe_actions(
                include_dead,
                fov_cache,
                barrier_positions,
                discovery_variants,
                caster_visible_positions,
                legal_only,
            )
        )
        if timing:
            record_action_timing("available_actions.collect_aoe_actions_ms", started)

        started = time.perf_counter() if timing else 0.0
        result.object_actions = self._collect_object_actions(legal_only)
        if timing:
            record_action_timing("available_actions.collect_object_actions_ms", started)

        started = time.perf_counter() if timing else 0.0
        self._collect_use_actions(
            result,
            potential_targets,
            include_dead,
            fov_cache,
            barrier_positions,
            caster_visible_positions,
            legal_only,
        )
        if timing:
            record_action_timing("available_actions.collect_use_actions_ms", started)

        started = time.perf_counter() if timing else 0.0
        for handler in self.event_handlers.values():
            if not handler.player_toggleable:
                continue
            trigger_event = ""
            if handler.trigger_conditions:
                trigger_event = handler.trigger_conditions[0].event_type.value
            result.handler_details.append(AvailableHandlerInfo(
                name=handler.name,
                uuid=handler.uuid,
                enabled=handler.enabled,
                trigger_event=trigger_event,
            ))
        if timing:
            record_action_timing("available_actions.handler_details_ms", started)

        return result

    def get_equippable_items(self) -> Dict[str, list]:
        """Returns inventory items that can be equipped, grouped by valid slot.

        For each EquippableItem in inventory, determines which slots it can go into
        and whether that slot is currently occupied (includes swap info).

        Returns:
            Dict mapping slot name -> list of dicts with item info and swap details.
        """
        from dnd.blocks.base_item import EquippableItem
        from dnd.blocks.equipment import Weapon, Armor, Shield, Ring, WeaponProperty, slot_mapping
        from dnd.core.events import WeaponSlot, BodyPart, RingSlot

        result: Dict[str, list] = {}

        slot_attr_map = {
            "weapon_melee_main": WeaponSlot.MELEE_MAIN,
            "weapon_melee_off": WeaponSlot.MELEE_OFF,
            "weapon_ranged_main": WeaponSlot.RANGED_MAIN,
            "weapon_ranged_off": WeaponSlot.RANGED_OFF,
            "helmet": BodyPart.HEAD,
            "body_armor": BodyPart.BODY,
            "gauntlets": BodyPart.HANDS,
            "greaves": BodyPart.LEGS,
            "boots": BodyPart.FEET,
            "amulet": BodyPart.AMULET,
            "cloak": BodyPart.CLOAK,
            "ring_left": RingSlot.LEFT,
            "ring_right": RingSlot.RIGHT,
        }

        for item in self.inventory.items.values():
            if not isinstance(item, EquippableItem):
                continue

            valid_slots: List[str] = []

            if isinstance(item, Weapon):
                is_ranged = WeaponProperty.RANGED in item.properties
                is_light = WeaponProperty.LIGHT in item.properties
                if is_ranged:
                    valid_slots.append("weapon_ranged_main")
                    if is_light:
                        valid_slots.append("weapon_ranged_off")
                else:
                    valid_slots.append("weapon_melee_main")
                    if is_light:
                        valid_slots.append("weapon_melee_off")
            elif isinstance(item, Shield):
                valid_slots.append("weapon_melee_off")
            elif isinstance(item, Ring):
                valid_slots.extend(["ring_left", "ring_right"])
            elif isinstance(item, Armor):
                for bp, attr_name in slot_mapping.items():
                    if item.body_part == bp:
                        valid_slots.append(attr_name)
                        break

            for slot_name in valid_slots:
                if slot_name not in result:
                    result[slot_name] = []
                current_item = self.equipment.get_item_by_slot(slot_attr_map[slot_name])
                entry = {
                    "item_uuid": str(item.uuid),
                    "item_name": item.name,
                    "swap_item_name": current_item.name if current_item else None,
                    "swap_item_uuid": str(current_item.uuid) if current_item else None,
                }
                result[slot_name].append(entry)

        return result
