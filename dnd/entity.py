from typing import DefaultDict, Dict, Optional, Any, List, ClassVar, Union, Tuple, Set, cast
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from collections import defaultdict

from dnd.core.values import ModifiableValue, AdvantageStatus
from dnd.core.modifiers import NumericalModifier, CreatureType, DamageType, Size
from dnd.core.values import CriticalStatus, AutoHitStatus
from dnd.core.base_conditions import BaseCondition, ConditionTag
from dnd.core.dice import Dice, RollType, DiceRoll, AttackOutcome

from dnd.core.events import (
    Event, EventPhase, EventQueue, RangeType, SavingThrowEvent, SkillCheckEvent, TurnStartEvent, TurnEndEvent,
    D20RollResultEvent, AttackD20RollResultEvent, SavingThrowD20RollResultEvent, SkillCheckD20RollResultEvent,
    TakeDamageEvent, DeathSaveEvent, InstantDeathEvent, DeathEvent, HealEvent, EquipmentSlot
)
from dnd.core.base_block import BaseBlock, MovementMode
from dnd.blocks.abilities import AbilityScoresConfig, AbilityScores
from dnd.blocks.saving_throws import SavingThrowSetConfig, SavingThrowSet
from dnd.blocks.health import HealthConfig, Health, HitDiceHealingResult
from dnd.blocks.equipment import EquipmentConfig, Equipment, WeaponSlot, WeaponProperty, Range, Shield, Damage, Armor, Weapon
from dnd.blocks.action_economy import ActionEconomyConfig, ActionEconomy
from dnd.blocks.skills import SkillSetConfig, SkillSet
from dnd.blocks.sensory import Senses
from dnd.core.base_block import SensesType, SenseMode, LightLevel
from dnd.blocks.inventory import Inventory
from dnd.blocks.spellcasting import SpellcastingBlock, SpellcastingConfig
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.blocks.appearance import Appearance, AppearanceConfig
from dnd.core.events import AbilityName, SkillName
from dnd.core.gridmap import get_map
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EntitySpottedLogData
from dnd.core.base_actions import (
    BaseAction, TargetType,
    AvailableTarget, AvailableActionInfo, AvailableActionsResult
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
            EventQueue.add_pre_completion_callback(spatial_callback)

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
            if immunity_check(self, self.get_target_entity(copy=True), immunity_context):
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
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True
        target_entity = None
        if self.target_entity_uuid:
            target_entity = self.get_target_entity(copy=True)
            assert isinstance(target_entity, Entity)
            if target_entity.target_entity_uuid != self.uuid:
                target_entity.set_target_entity(self.uuid)
            saving_throw_bonuses_target = target_entity._get_bonuses_for_saving_throw(ability_name)

        saving_throw_bonuses_source = self._get_bonuses_for_saving_throw(ability_name)
        if target_entity is not None and self.target_entity_uuid != self.uuid:
            for mod_source, mod_target in zip(saving_throw_bonuses_source, saving_throw_bonuses_target):
                mod_source.set_from_target(mod_target)
        total_bonus_source = saving_throw_bonuses_source[0].combine_values(list(saving_throw_bonuses_source)[1:]).model_copy(deep=True)

        if should_clear_target:
            self.clear_target_entity()

        return total_bonus_source

    def skill_bonus(self, target_entity_uuid: Optional[UUID], skill_name: SkillName) -> ModifiableValue:
        """Build the complete skill bonus for a skill.

        Args:
            target_entity_uuid: Optional opposing entity whose outgoing
                modifiers should be propagated.
            skill_name: Skill to assemble.

        Returns:
            Combined skill bonus.
        """
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True

        target_entity = None
        if self.target_entity_uuid:
            target_entity = self.get_target_entity(copy=True)
            assert isinstance(target_entity, Entity)
            if target_entity.target_entity_uuid != self.uuid:
                target_entity.set_target_entity(self.uuid)
            skill_bonuses_target = target_entity._get_bonuses_for_skill(skill_name)

        skill_bonuses_source = self._get_bonuses_for_skill(skill_name)
        if target_entity is not None and self.target_entity_uuid != self.uuid:
            for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
                mod_source.set_from_target(mod_target)

        total_bonus_source = skill_bonuses_source[0].combine_values(list(skill_bonuses_source)[1:]).model_copy(deep=True)

        if should_clear_target:
            self.clear_target_entity()
            if target_entity is not None:
                target_entity.clear_target_entity()
            for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
                mod_source.reset_from_target()
                mod_target.reset_from_target()

        return total_bonus_source

    def passive_skill(self, skill_name: SkillName) -> int:
        """Calculate passive skill score for a skill.

        Advantage adds 5 and disadvantage subtracts 5 from the passive score.

        Args:
            skill_name: Skill to calculate.

        Returns:
            Passive score for the skill.
        """
        skill_bonus = self.skill_bonus(target_entity_uuid=None, skill_name=skill_name)
        base = 10 + skill_bonus.normalized_score

        if skill_bonus.advantage == AdvantageStatus.ADVANTAGE:
            base += 5
        elif skill_bonus.advantage == AdvantageStatus.DISADVANTAGE:
            base -= 5

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
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True

        target_entity = self.get_target_entity(copy=True)
        assert isinstance(target_entity, Entity)
        if target_entity.target_entity_uuid != self.uuid:
            target_entity.set_target_entity(self.uuid)

        skill_bonuses_source = self._get_bonuses_for_skill(skill_name)
        skill_bonuses_target = target_entity._get_bonuses_for_skill(skill_name)

        for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
            mod_target.set_from_target(mod_source)
            mod_source.set_from_target(mod_target)

        total_bonus_source = skill_bonuses_source[0].combine_values(list(skill_bonuses_source)[1:]).model_copy(deep=True)
        total_bonus_target = skill_bonuses_target[0].combine_values(list(skill_bonuses_target)[1:]).model_copy(deep=True)

        if should_clear_target:
            self.clear_target_entity()
            target_entity.clear_target_entity()
        for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
            mod_source.reset_from_target()
            mod_target.reset_from_target()

        return total_bonus_source, total_bonus_target

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
            damages.append(Damage(
                source_entity_uuid=self.uuid,
                target_entity_uuid=target_entity_uuid or self.target_entity_uuid,
                damage_dice=4,
                dice_numbers=size_dice,
                damage_type=primary_type
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

    def receive_damage(
        self,
        amount: int,
        damage_type: DamageType,
        source_entity_uuid: UUID,
        damage_rolls: Optional[List[DiceRoll]] = None,
        damages: Optional[List[Damage]] = None,
        parent_event: Optional[UUID] = None,
        critical_hit: bool = False
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

        Returns:
            Actual HP lost after handlers, cancellation, and resistances.
        """
        normal_hp_before = self.get_normal_hp()
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
            parent_event=parent_event,
            phase=EventPhase.DECLARATION
        )

        take_damage_event = take_damage_event.phase_to(EventPhase.EXECUTION)
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
                    source_entity_uuid=source_entity_uuid
                )
            else:
                actual_damage = self.health.take_damage(
                    effective_damage,
                    damage_type,
                    source_entity_uuid=source_entity_uuid
                )
        else:
            actual_damage = 0

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
                "final_damage": actual_damage,
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

        heal_event = heal_event.model_copy(update={"actual_healing": actual_healing, "resulting_hp": self.get_hp()})
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
                if not include_dead and not other.has_hp:
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
                if not include_dead and not other.has_hp:
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
        entity_uuid: Optional[UUID] = None
    ) -> Tuple[Dict[Tuple[int, int], bool], DefaultDict[Tuple[int, int], List[Tuple[int, int]]], Dict[Tuple[int, int], bool], Dict[UUID, Tuple[int, int]], Dict[UUID, Tuple[int, int]], List[Tuple[int, int]], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
        """Compute observer-local senses data from a position.

        Args:
            position: Position to compute from.
            seen: Previously seen positions.
            max_distance: Maximum view and movement distance.
            entity_uuid: Optional observer UUID for subjective filtering.

        Returns:
            Visible cells, filtered paths, walkability, visible entities,
            visible objects, full geometric FOV positions, and safe paths.
        """
        grid = get_map()

        fov_positions = grid.compute_fov(position, max_distance, observer_uuid=entity_uuid)

        visible_dict: Dict[Tuple[int, int], bool] = {}
        for pos in fov_positions:
            tile = grid.get_tile(pos[0], pos[1])
            if not tile:
                continue
            if entity_uuid:
                eff = tile.get_effective_light_for(entity_uuid, observer_position=position)
                if eff.value <= LightLevel.DARKNESS.value:
                    continue
            visible_dict[pos] = True

        collision: Set[Tuple[int, int]] = set()
        directional_collision: Set[Tuple[Tuple[int, int], str]] = set()
        ign_terrain = False
        if entity_uuid:
            ent = Entity._entity_registry.get(entity_uuid)
            if ent is not None:
                collision = ent.senses.collision_blocked
                directional_collision = ent.senses.directional_collision_blocked
                ign_terrain = ent.ignore_difficult_terrain
        _, paths = grid.compute_paths(position, max_distance, requesting_entity_uuid=entity_uuid,
                                      subjective=True, collision_blocked=collision,
                                      directional_collision_blocked=directional_collision,
                                      ignore_difficult_terrain=ign_terrain)

        filtered_paths: DefaultDict[Tuple[int, int], List[Tuple[int, int]]] = defaultdict(list)
        for pos, path in paths.items():
            if pos in visible_dict and all(step in seen or step in visible_dict for step in path):
                filtered_paths[pos] = path

        safe_paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        has_any_hazardous = False
        for pos, path in filtered_paths.items():
            for step in path[1:]:
                if grid.is_position_hazardous_for(step[0], step[1], entity_uuid):
                    has_any_hazardous = True
                    break
            if has_any_hazardous:
                break

        if has_any_hazardous:
            _, safe_raw = grid.compute_paths(
                position, max_distance, requesting_entity_uuid=entity_uuid,
                walk_in_danger=False, subjective=True, collision_blocked=collision,
                directional_collision_blocked=directional_collision,
                ignore_difficult_terrain=ign_terrain
            )
            for pos, path in safe_raw.items():
                if pos in visible_dict and all(step in seen or step in visible_dict for step in path):
                    safe_paths[pos] = path

        visible_entities: Dict[UUID, Tuple[int, int]] = {}
        for pos in visible_dict:
            entities = Entity.get_all_entities_at_position(pos)
            for entity in entities:
                if entity_uuid and entity.uuid == entity_uuid:
                    continue
                if entity.is_perceivable_by(entity_uuid):
                    visible_entities[entity.uuid] = pos

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
        Entity._add_adjacent_senses_objects(visible_objects, position, entity_uuid)

        walkable = {pos: grid.is_walkable(pos[0], pos[1]) for pos in fov_positions}

        return visible_dict, filtered_paths, walkable, visible_entities, visible_objects, fov_positions, safe_paths

    def create_senses_copy_at_position(self, position: Tuple[int, int], max_distance: int = 10) -> 'Senses':
        """Create a copy of senses as if entity were at a different position."""
        senses = self.senses.model_copy(deep=True)
        senses.position = position
        visible_dict, filtered_paths, walkable, visible_entities, visible_objects, _fov, safe_paths = Entity.compute_senses_from_position(
            position, self.senses.seen, max_distance, entity_uuid=self.uuid
        )

        senses.update_senses(
            entities=visible_entities,
            visible=visible_dict,
            walkable=walkable,
            paths=filtered_paths,
            objects=visible_objects
        )
        senses.safe_paths = safe_paths
        return senses

    def update_entity_senses(self, max_distance: int = 10) -> None:
        """Fully recompute the entity's senses and FOV subscriptions.

        This computes:
        - Visible cells within max_distance using shadowcast
        - Paths to reachable cells using dijkstra (excludes cells occupied by other entities)
        - Entities present in visible cells

        After updating, subscribes to visible cells so this entity
        receives SpatialChangeEvents when something changes in its FOV.

        Args:
            max_distance: Maximum view/movement distance (default 10)
        """
        visible_dict, filtered_paths, walkable, visible_entities, visible_objects, fov_positions, safe_paths = Entity.compute_senses_from_position(
            self.position, self.senses.seen, max_distance, entity_uuid=self.uuid
        )
        self.senses.update_senses(
            entities=visible_entities,
            visible=visible_dict,
            walkable=walkable,
            paths=filtered_paths,
            objects=visible_objects
        )
        self.senses.safe_paths = safe_paths
        self.senses.snapshot_perception(self.get_passive_perception())
        get_map().subscribe_to_cells(self.uuid, set(fov_positions))

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
        fov_positions = grid.compute_fov(self.position, max_distance, observer_uuid=self.uuid)

        visible_dict: Dict[Tuple[int, int], bool] = {}
        for pos in fov_positions:
            tile = grid.get_tile(pos[0], pos[1])
            if not tile:
                continue
            eff = tile.get_effective_light_for(self.uuid, observer_position=self.position)
            if eff.value <= LightLevel.DARKNESS.value:
                continue
            visible_dict[pos] = True

        visible_entities: Dict[UUID, Tuple[int, int]] = {}
        for pos in visible_dict:
            for ent_uuid in grid.get_entities_at(pos):
                if ent_uuid != self.uuid:
                    block = BaseBlock.get(ent_uuid)
                    if block and block.is_perceivable_by(self.uuid):
                        visible_entities[ent_uuid] = pos

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
        Entity._add_adjacent_senses_objects(visible_objects, self.position, self.uuid)

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

        self.senses.visible = visible_dict
        self.senses.update_seen(visible_dict)
        self.senses.entities = visible_entities
        self.senses.objects = visible_objects

        grid.subscribe_to_cells(self.uuid, set(fov_positions))

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
        return AvailableActionInfo(
            template_name=template_name,
            target_type=target_type,
            valid_targets=valid_targets,
            can_afford=can_afford,
            display_name=display_name or template_name,
            description=description if description is not None else template.description,
            cost_type=cost_type,
            cost_amount=cost_amount,
            weapon_slot=weapon_slot,
            weapon_name=weapon_name,
            action_category=template.action_category,
            base_template_name=base_template_name,
            spell_level=getattr(template, "spell_level", None) if template.is_spell else None,
            cast_at_level=getattr(template, "cast_at_level", None) if template.is_spell else None,
            is_spell_variant=bool(getattr(template, "is_variant", False)) if template.is_spell else False,
            num_projectiles=template.get_multi_target_count() if target_type == TargetType.MULTI_ENTITY else None,
            allow_same_target=template.allow_same_target if target_type == TargetType.MULTI_ENTITY else None,
            is_item_use=is_item_use,
            source_item_uuid=source_item_uuid,
            item_stack_count=item_stack_count,
        )

    def _compute_target_pool(
        self,
        action_filter: str,
        include_dead: bool,
        include_self: bool,
        default_pool: Dict[UUID, Tuple[int, int]],
    ) -> Dict[UUID, Tuple[int, int]]:
        """Compute entity target pool based on valid_target_filter.

        Args:
            action_filter: Relationship filter from the action template.
            include_dead: Whether zero-HP entities stay targetable.
            include_self: Whether to add the acting entity.
            default_pool: Precomputed pool from the outer discovery filter.

        Returns:
            Visible target positions keyed by entity UUID.
        """
        if action_filter == "all":
            pool: Dict[UUID, Tuple[int, int]] = {}
            for k, v in self.senses.entities.items():
                if k == self.uuid:
                    continue
                if not include_dead:
                    other = Entity.get(k)
                    if other and not other.has_hp:
                        continue
                pool[k] = v
        elif action_filter in ("allies", "self_or_allies"):
            pool = dict(self.get_visible_allies(include_dead=include_dead))
        else:
            pool = dict(default_pool)

        if include_self:
            pool[self.uuid] = self.position
        return pool

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
        shape_template: Any,
        pos: Tuple[int, int],
        template: BaseAction,
        include_dead: bool,
        fov_cache: dict,
        barrier_positions: Set[Tuple[int, int]],
        idx: int,
    ) -> Optional[AvailableTarget]:
        """Compute AoE preview metadata for a candidate position.

        Args:
            shape_template: AoE shape to copy and aim.
            pos: Candidate target position.
            template: Action template being discovered.
            include_dead: Whether zero-HP entities stay targetable.
            fov_cache: Shared field-of-view cache for AoE computation.
            barrier_positions: Positions that block AoE projection.
            idx: Discovery index to assign if the position is valid.

        Returns:
            Available target with AoE metadata, or `None` if filtered out.
        """
        shape = shape_template.model_copy(update={'target': pos})
        shape.compute_subjective(
            self.position, self.senses,
            fov_cache=fov_cache, barrier_positions=barrier_positions,
            caster_uuid=self.uuid,
        )

        affected_uuids = list(shape.affected_entity_uuids)

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
                if (ent := Entity.get(uid)) and ent.has_hp
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

    def _collect_self_actions(self) -> List[AvailableActionInfo]:
        """Collect SELF-targeting actions (Dash, Dodge, etc.)."""
        actions: List[AvailableActionInfo] = []
        for registered_template in self.self_actions:
            for template in registered_template.get_discovery_variants(self):
                template_name = template.get_discovery_template_name()
                display_name = template.get_discovery_display_name()
                can_afford = template.check_costs()
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
        ) -> List[AvailableActionInfo]:
        """Collect entity-targeting actions.

        Args:
            potential_targets: Outer discovery target pool keyed by UUID.
            include_dead: Whether zero-HP entities stay targetable.

        Returns:
            Available entity-targeting action metadata.
        """
        actions: List[AvailableActionInfo] = []
        for registered_template in self.entity_actions:
            for template in registered_template.get_discovery_variants(self):
                target_pool = self._compute_target_pool(
                    template.valid_target_filter, include_dead,
                    template.include_self, potential_targets
                )
                valid_targets = self._validate_entity_targets(template, target_pool)

                if not valid_targets:
                    continue

                template_name = template.get_discovery_template_name()
                display_name = template.get_discovery_display_name()

                weapon_name: Optional[str] = None
                weapon_slot_str: Optional[str] = None

                weapon_slot_attr = getattr(template, 'weapon_slot', None)
                if weapon_slot_attr is not None:
                    weapon_slot_str = weapon_slot_attr.value if isinstance(weapon_slot_attr, WeaponSlot) else str(weapon_slot_attr)
                    weapon = self.equipment._get_weapon_by_slot(weapon_slot_attr)
                    if weapon:
                        weapon_name = weapon.name
                        if template_name.startswith("Extra Attack"):
                            display_name = f"Extra Attack ({weapon_name})"
                        else:
                            display_name = weapon_name

                actions.append(self._make_action_info(
                    template_name=template_name,
                    target_type=template.effective_target_type,
                    valid_targets=valid_targets,
                    can_afford=template.check_costs(),
                    template=template,
                    display_name=display_name,
                    weapon_slot=weapon_slot_str,
                    weapon_name=weapon_name,
                ))
        return actions

    def _collect_path_actions(self, remaining_movement: int) -> List[AvailableActionInfo]:
        """Collect path-based position actions.

        Args:
            remaining_movement: Remaining movement in feet for display.

        Returns:
            Available path-targeting action metadata.
        """
        grid = get_map()
        actions: List[AvailableActionInfo] = []
        for template in self.position_actions:
            if template.effective_target_type not in (TargetType.POSITION, TargetType.POSITION_PATH):
                continue
            movement_mode = getattr(template, "movement_mode", MovementMode.WALKING)
            if movement_mode == MovementMode.WALKING:
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
                    if pos in self.senses.visible and all(step in self.senses.seen or step in self.senses.visible for step in path)
                }
            valid_positions: List[AvailableTarget] = []
            idx = 0
            for pos, normal_path in paths_by_position.items():
                if pos == self.senses.position:
                    continue
                template.set_target_position(pos)
                if template.pre_validate():
                    path_cost = 0
                    for cost in template.costs:
                        if cost.cost_type == "movement":
                            path_cost = cost.cost
                            break

                    is_hazardous = any(
                        grid.is_position_hazardous_for(step[0], step[1], self.uuid)
                        for step in normal_path[1:]
                    )

                    safe_cost: Optional[int] = None
                    safe_path_list: Optional[List[Tuple[int, int]]] = None
                    if movement_mode == MovementMode.WALKING and is_hazardous and pos in self.senses.safe_paths:
                        safe_path_list = list(self.senses.safe_paths[pos])
                        safe_cost = 0
                        for step in safe_path_list[1:]:
                            tile = grid.get_tile(*step)
                            if tile:
                                safe_cost += int(tile.get_movement_cost(MovementMode.WALKING))
                            else:
                                safe_cost += 1
                        safe_cost *= 5

                    valid_positions.append(AvailableTarget(
                        index=idx,
                        position=pos,
                        distance=self.senses.get_feet_distance(pos),
                        path_cost=path_cost,
                        is_path_hazardous=is_hazardous,
                        safe_path_cost=safe_cost,
                        path=list(normal_path),
                        safe_path=safe_path_list,
                    ))
                    idx += 1

            if valid_positions:
                template_name = template.name or "Unknown"
                actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=template.effective_target_type,
                    valid_targets=valid_positions,
                    can_afford=True,
                    display_name=template_name,
                    description=f"{remaining_movement}ft remaining",
                    cost_type="movement",
                    cost_amount=0,
                    action_category=template.action_category,
                ))
        return actions

    def _collect_los_actions(self) -> List[AvailableActionInfo]:
        """Collect line-of-sight position actions."""
        actions: List[AvailableActionInfo] = []
        for registered_template in self.position_actions:
            for template in registered_template.get_discovery_variants(self):
                if template.effective_target_type != TargetType.POSITION_LOS:
                    continue
                valid_pos_list = template.get_valid_positions()
                valid_positions: List[AvailableTarget] = []
                idx = 0
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
                        can_afford=template.check_costs(),
                        template=template,
                        display_name=template.get_discovery_display_name(),
                    ))
        return actions

    def _collect_aoe_actions(
        self,
        include_dead: bool,
        fov_cache: dict,
        barrier_positions: Set[Tuple[int, int]],
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

        entity_positions: Set[Tuple[int, int]] = set()
        for uid, pos in self.senses.entities.items():
            if uid == self.uuid:
                continue
            entity_positions.add(pos)

        for registered_template in self.position_actions:
            for template in registered_template.get_discovery_variants(self):
                if template.effective_target_type != TargetType.POSITION_AOE:
                    continue

                shape_template = template.aoe_shape
                if shape_template is None:
                    continue

                can_afford = template.check_costs()
                template_name = template.get_discovery_template_name()
                display_name = template.get_discovery_display_name()

                if not can_afford:
                    actions.append(self._make_action_info(
                        template_name=template_name,
                        target_type=TargetType.POSITION_AOE,
                        valid_targets=[],
                        can_afford=False,
                        template=template,
                        display_name=display_name,
                    ))
                    continue

                valid_pos_list = template.get_valid_positions()

                if template.aoe_require_targets:
                    prefilter_positions = set(entity_positions)
                    if template.include_self:
                        prefilter_positions.add(self.position)
                    if prefilter_positions:
                        radius = shape_template._get_max_radius_tiles()
                        candidates = grid.get_positions_near_entities(prefilter_positions, radius)
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

                valid_positions: List[AvailableTarget] = []
                idx = 0
                for pos in valid_pos_list:
                    target = self._compute_aoe_at_position(
                        shape_template, pos, template, include_dead,
                        fov_cache, barrier_positions, idx
                    )
                    if target is not None:
                        valid_positions.append(target)
                        idx += 1

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

    def _collect_object_actions(self) -> List[AvailableActionInfo]:
        """Collect object-targeting actions."""
        actions: List[AvailableActionInfo] = []
        for template in self.object_actions:
            valid_targets: List[AvailableTarget] = []
            idx = 0
            can_afford = template.check_costs()

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

        use_sources: List[Tuple[BaseAction, Optional[UUID], str, Optional[int]]] = []

        for use_template in self.inventory.get_all_use_actions(self.uuid):
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

        entity_positions: Set[Tuple[int, int]] = set()
        for uid, pos in self.senses.entities.items():
            if uid == self.uuid:
                continue
            entity_positions.add(pos)

        for use_template, item_uuid, item_name, item_stack in use_sources:
            base_name = use_template.name or "Use"
            template_name = f"{base_name}__item_{item_uuid}"
            stack_suffix = f" x{item_stack}" if item_stack and item_stack > 1 else ""
            display_name = f"{base_name} ({item_name}{stack_suffix})"
            stack_count_field = item_stack if item_stack and item_stack > 1 else None
            can_afford = use_template.check_costs()

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
                    use_template.include_self, potential_targets
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
                    prefilter_positions = set(entity_positions)
                    if use_template.include_self:
                        prefilter_positions.add(self.position)
                    if prefilter_positions:
                        radius = use_shape_template._get_max_radius_tiles()
                        candidates = grid.get_positions_near_entities(prefilter_positions, radius)
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

                use_valid_positions: List[AvailableTarget] = []
                use_idx = 0
                for pos in valid_pos_list:
                    target = self._compute_aoe_at_position(
                        use_shape_template, pos, use_template, include_dead,
                        fov_cache, barrier_positions, use_idx
                    )
                    if target is not None:
                        use_valid_positions.append(target)
                        use_idx += 1
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
        include_dead: bool = False
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

        Returns:
            Grouped discovery result for the acting entity.
        """
        result = AvailableActionsResult(
            entity_uuid=self.uuid,
            remaining_movement=self.action_economy.movement.normalized_score
        )

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

        result.self_actions = self._collect_self_actions()
        result.entity_actions = self._collect_entity_actions(potential_targets, include_dead)

        if self.senses._paths_dirty:
            self.update_entity_senses(max_distance=20)

        fov_cache: dict = {}
        barrier_positions = get_map().get_barrier_positions()

        result.position_actions = self._collect_path_actions(result.remaining_movement)
        result.position_actions.extend(self._collect_los_actions())
        result.position_actions.extend(
            self._collect_aoe_actions(include_dead, fov_cache, barrier_positions)
        )
        result.object_actions = self._collect_object_actions()
        self._collect_use_actions(result, potential_targets, include_dead, fov_cache, barrier_positions)

        for handler in self.event_handlers.values():
            if not handler.player_toggleable:
                continue
            trigger_event = ""
            if handler.trigger_conditions:
                trigger_event = handler.trigger_conditions[0].event_type.value
            result.handler_details.append({
                "name": handler.name,
                "uuid": str(handler.uuid),
                "enabled": handler.enabled,
                "trigger_event": trigger_event,
            })

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
