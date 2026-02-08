from typing import DefaultDict, Dict, Optional, Any, List, ClassVar, Union, Tuple, Set, cast
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from collections import defaultdict

from dnd.core.values import ModifiableValue, AdvantageStatus
from dnd.core.modifiers import NumericalModifier, CreatureType, DamageType
from dnd.core.values import CriticalStatus, AutoHitStatus
from dnd.core.base_conditions import BaseCondition
from dnd.core.dice import Dice, RollType, DiceRoll, AttackOutcome


from dnd.core.events import (
    Event, EventPhase, EventQueue, RangeType, SavingThrowEvent, SkillCheckEvent, TurnStartEvent, TurnEndEvent,
    D20RollResultEvent, AttackD20RollResultEvent, SavingThrowD20RollResultEvent, SkillCheckD20RollResultEvent,
    TakeDamageEvent, DeathEvent, EquipmentSlot
)
from dnd.core.base_block import BaseBlock, MovementMode
from dnd.blocks.abilities import AbilityScoresConfig, AbilityScores
from dnd.blocks.saving_throws import SavingThrowSetConfig, SavingThrowSet
from dnd.blocks.health import HealthConfig, Health
from dnd.blocks.equipment import EquipmentConfig, Equipment, WeaponSlot, WeaponProperty, Range, Shield, Damage, Armor, Weapon
from dnd.blocks.action_economy import ActionEconomyConfig, ActionEconomy
from dnd.blocks.skills import SkillSetConfig, SkillSet
from dnd.blocks.sensory import Senses
from dnd.blocks.inventory import Inventory
from dnd.blocks.spellcasting import SpellcastingBlock, SpellcastingConfig
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.events import AbilityName, SkillName
from dnd.core.gridmap import get_map
from dnd.core.base_actions import (
    BaseAction, TargetType,
    AvailableTarget, AvailableActionInfo, AvailableActionsResult
)



def get_natural_roll(roll: DiceRoll) -> int:
    """Get the natural d20 value that was used for the attack.

    For single rolls, returns the result directly.
    For advantage, returns the higher roll.
    For disadvantage, returns the lower roll.
    """
    if isinstance(roll.results, int):
        return roll.results
    # For advantage/disadvantage, determine which die was used
    if roll.advantage_status == AdvantageStatus.ADVANTAGE:
        return max(roll.results)
    elif roll.advantage_status == AdvantageStatus.DISADVANTAGE:
        return min(roll.results)
    else:
        # No advantage, first roll
        return roll.results[0] if roll.results else 0
    

def determine_attack_outcome(
    roll: DiceRoll,
    ac: Union[int, ModifiableValue],
    crit_threshold: int = 20
) -> AttackOutcome:
        """
        Determine attack outcome based on roll and AC.

        Args:
            roll: The dice roll result
            ac: The armor class to check against
            crit_threshold: Minimum natural roll for a critical hit (default 20,
                           19 for Improved Critical, 18 for Superior Critical)

        Returns:
            AttackOutcome: The outcome of the attack
        """
        target_ac = ac.normalized_score if isinstance(ac, ModifiableValue) else ac

        # Get the natural roll value (handles advantage/disadvantage)
        natural_roll = get_natural_roll(roll)

        # First check auto miss which overrides everything else
        if roll.auto_hit_status == AutoHitStatus.AUTOMISS:
            return AttackOutcome.MISS
        # Second check if the roll is an auto hit (with critical check)
        elif roll.auto_hit_status == AutoHitStatus.AUTOHIT:
            if roll.critical_status == CriticalStatus.AUTOCRIT or natural_roll >= crit_threshold:
                return AttackOutcome.CRIT
            else:
                return AttackOutcome.HIT
        # Check for natural 1 (critical miss)
        elif natural_roll == 1:
            return AttackOutcome.CRIT_MISS
        # Check if roll meets or exceeds AC (with critical check)
        elif roll.total >= target_ac:
            if roll.critical_status == CriticalStatus.AUTOCRIT or natural_roll >= crit_threshold:
                return AttackOutcome.CRIT
            else:
                return AttackOutcome.HIT
        # Finally, it's a miss
        else:
            return AttackOutcome.MISS
        
class EntityConfig(BaseModel):
    ability_scores: AbilityScoresConfig = Field(default_factory=AbilityScoresConfig,description="Ability scores for the entity")
    skill_set: SkillSetConfig = Field(default_factory=SkillSetConfig,description="Skill set for the entity")
    saving_throws: SavingThrowSetConfig = Field(default_factory=SavingThrowSetConfig,description="Saving throws for the entity")
    health: HealthConfig = Field(default_factory=HealthConfig,description="Health for the entity")
    equipment: EquipmentConfig = Field(default_factory=EquipmentConfig,description="Equipment for the entity")
    action_economy: ActionEconomyConfig = Field(default_factory=ActionEconomyConfig,description="Action economy for the entity")
    proficiency_bonus: int = Field(default=0,description="Proficiency bonus for the entity")
    proficiency_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list,description="Any additional static modifiers applied to the proficiency bonus")
    initiative_modifiers: List[Tuple[str, int]] = Field(default_factory=list,description="Any additional static modifiers applied to initiative (e.g., Alert feat +5)")
    position: Tuple[int,int] = Field(default_factory=lambda: (0,0),description="Position of the entity")
    sprite_name: Optional[str] = Field(default=None,description="The name of the sprite to use for the entity")
    faction: Optional[str] = Field(default=None, description="Faction identifier. None = enemy to everyone")
    spellcasting: Optional[SpellcastingConfig] = Field(default=None, description="Spellcasting configuration (None = non-caster)")
    weight: int = Field(default=150, description="Weight in pounds (default 150 for Medium humanoid)")
    creature_type: CreatureType = Field(default=CreatureType.HUMANOID, description="Creature type (default humanoid)")

class Entity(BaseBlock):
    """ Base class for dnd entities in the game it acts as container for blocks and implements common functionalities that
    require interactions between blocks """

    name: str = Field(default="Entity")
    ability_scores: AbilityScores = Field(default_factory=lambda: AbilityScores.create(source_entity_uuid=uuid4()))
    skill_set: SkillSet = Field(default_factory=lambda: SkillSet.create(source_entity_uuid=uuid4()))
    saving_throws: SavingThrowSet = Field(default_factory=lambda: SavingThrowSet.create(source_entity_uuid=uuid4()))
    health: Health = Field(default_factory=lambda: Health.create(source_entity_uuid=uuid4()))
    equipment: Equipment = Field(default_factory=lambda: Equipment.create(source_entity_uuid=uuid4()))
    action_economy: ActionEconomy = Field(default_factory=lambda: ActionEconomy.create(source_entity_uuid=uuid4()))
    proficiency_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), value_name="proficiency_bonus", base_value=2))
    initiative: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), value_name="initiative", base_value=0))
    senses: Senses = Field(default_factory=lambda: Senses.create(source_entity_uuid=uuid4()))
    inventory: Inventory = Field(default_factory=lambda: Inventory(source_entity_uuid=uuid4()))
    spellcasting: SpellcastingBlock = Field(
        default_factory=lambda: SpellcastingBlock.create(source_entity_uuid=uuid4()),
        description="Spellcasting block (always present, defaults are harmless for non-casters)"
    )
    allow_events_conditions: bool = Field(default=True, description="If True, events and conditions will be allowed to be added to the block")
    sprite_name: Optional[str] = Field(default=None, description="The name of the sprite to use for the entity")
    faction: Optional[str] = Field(default=None, description="Faction identifier. None = enemy to everyone")
    weight: int = Field(default=150, description="Weight in pounds (default 150 for Medium humanoid)")
    creature_type: CreatureType = Field(default=CreatureType.HUMANOID, description="Creature type (default humanoid)")

    # Turn tracking - True during this entity's turn (set by on_turn_start, cleared by on_turn_end)
    is_my_turn: bool = Field(default=False, description="True when it's this entity's turn")

    # Movement blocking - when True, this entity does not block walking (set by death handler, incorporeal, etc.)
    non_blocking: bool = Field(default=False, description="When True, entity does not block movement through its cell")

    # Action registry - stores action templates for this entity
    registered_actions: List[BaseAction] = Field(default_factory=list, description="Registered action templates for this entity")

    _entity_registry: ClassVar[Dict[UUID, 'Entity']] = {}
    _entity_by_position: ClassVar[DefaultDict[Tuple[int, int], List['Entity']]] = defaultdict(list)

    def __init__(self, **data):
        """
        Initialize the BaseBlock and register it in the class registry.

        Args:
            **data: Keyword arguments to initialize the BaseBlock attributes.
        """
        super().__init__(**data)
        self.__class__._entity_registry[self.uuid] = self
        self.__class__._entity_by_position[self.position].append(self)
        # Also register with GridMap for spatial queries
        get_map().register_entity(self.uuid, self.position)
        # Note: Action templates are set up via actions_functional.setup_standard_actions()
        # Called from entity factories (e.g., bestiary.py) after entity creation

        # Register spatial callback for reactive senses updates
        # This callback fires on SPATIAL events (entity movement, tile changes)
        # and triggers full senses recalculation for real-time FOV/paths updates
        # Using callbacks instead of EventHandlers because spatial events
        # fire at COMPLETION phase and handlers don't fire for COMPLETION events
        if self.senses is not None:
            # Pass update functions so callback can trigger appropriate updates
            # Using lambda to capture self and provide default max_distance
            update_senses_func = lambda: self.update_entity_senses(max_distance=20)
            update_visibility_func = lambda: self.update_entity_visibility(max_distance=20)
            spatial_callback = self.senses.create_spatial_callback(
                self.uuid,
                update_senses_func=update_senses_func,
                update_visibility_func=update_visibility_func
            )
            EventQueue.add_on_event_callback(spatial_callback)

    @classmethod
    def update_entity_position(
        cls,
        entity: 'Entity',
        new_position: Tuple[int, int],
        parent_event: Optional[UUID] = None
    ):
        """Update entity position in both class registry and GridMap.

        Args:
            entity: The entity to move
            new_position: New grid position
            parent_event: Optional parent event UUID for lineage (e.g., StepMovementEvent)
        """
        cls._entity_by_position[entity.position].remove(entity)
        cls._entity_by_position[new_position].append(entity)
        entity._set_position(new_position)
        # Also update GridMap (handles dirty tracking)
        get_map().move_entity(entity.uuid, new_position, parent_event=parent_event)

    @classmethod
    def register_entity(cls, entity: 'Entity'):
        cls._entity_registry[entity.uuid] = entity

    @classmethod
    def get_all_entities(cls) -> List['Entity']:
        return list(cls._entity_registry.values())
    
    @classmethod
    def get_all_entities_at_position(cls, position: Tuple[int,int]) -> List['Entity']:
        return cls._entity_by_position[position]
    
    @classmethod
    def get(cls, uuid: UUID) -> Optional['Entity']:
        return cls._entity_registry.get(uuid)
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "Entity",description: Optional[str] = None,config: Optional[EntityConfig] = None) -> 'Entity':
        """
        Create a new Entity instance with the given parameters. All sub-blocks will share
        the same source_entity_uuid as the entity itself.

        Args:
            source_entity_uuid (UUID): The UUID that will be used as both the entity's UUID and source_entity_uuid
            name (str): The name of the entity. Defaults to "Entity"

        Returns: 
            Entity: The newly created Entity instance
        """
        if config is None:
            return cls(
                uuid=source_entity_uuid,
                source_entity_uuid=source_entity_uuid,
                name=name)
        else:
            ability_scores = AbilityScores.create(source_entity_uuid=source_entity_uuid,config=config.ability_scores)
            skill_set = SkillSet.create(source_entity_uuid=source_entity_uuid,config=config.skill_set)
            saving_throws = SavingThrowSet.create(source_entity_uuid=source_entity_uuid,config=config.saving_throws)
            health = Health.create(source_entity_uuid=source_entity_uuid,config=config.health)
            equipment = Equipment.create(source_entity_uuid=source_entity_uuid,config=config.equipment)
            senses = Senses.create(source_entity_uuid=source_entity_uuid,position=config.position)
            action_economy = ActionEconomy.create(source_entity_uuid=source_entity_uuid,config=config.action_economy)
            proficiency_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=config.proficiency_bonus)
            for modifier in config.proficiency_bonus_modifiers:
                proficiency_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid,name=modifier[0],value=modifier[1]))

            # Initiative base is DEX modifier
            dex_mod = ability_scores.get_ability("dexterity").modifier
            initiative = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=dex_mod,value_name="initiative")
            for modifier in config.initiative_modifiers:
                initiative.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid,name=modifier[0],value=modifier[1]))

            # Spellcasting (always created - defaults are harmless for non-casters)
            spellcasting = SpellcastingBlock.create(
                source_entity_uuid=source_entity_uuid,
                config=config.spellcasting  # None → uses defaults
            )

            # Inventory (always created - empty by default)
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
                action_economy=action_economy,
                proficiency_bonus=proficiency_bonus,
                initiative=initiative,
                spellcasting=spellcasting,
                position=config.position,
                sprite_name=config.sprite_name,
                faction=config.faction,
                weight=config.weight,
                creature_type=config.creature_type
            )

    def _set_position(self,new_position: Tuple[int,int]):
        """ move the entity to a new position without updating the registry  - should not be used directly"""
        self.position = new_position
        self.senses.position = new_position 

    def move(self,new_position: Tuple[int,int], update_senses: bool = True):
        """ move the entity to a new position """
        
        Entity.update_entity_position(self,new_position)
        if update_senses:
            Entity.update_all_entities_senses()
        
    def get_target_entity(self,copy: bool = False) -> Optional['Entity']:
        if self.target_entity_uuid is None:
            return None
        target_entity = Entity.get(self.target_entity_uuid)
        assert isinstance(target_entity, Entity)
        return target_entity if not copy else target_entity.model_copy(deep=True)
    
    def check_condition_immunity(self, condition_name: str) -> bool:
        #first check static immunities
        for static_immunity in self.condition_immunities:
            if static_immunity[0] == condition_name:
                return True
        #then check contextual immunities
        condition_contextual_immunities = self.contextual_condition_immunities.get(condition_name,[])
        for _, immunity_check in condition_contextual_immunities:
            if immunity_check(self,self.get_target_entity(copy=True),self.context):
                return True
        return False
    

    
    def add_condition(self, condition: BaseCondition, context: Optional[Dict[str, Any]] = None, check_save_throw: bool = True, parent_event: Optional[Event] = None)  -> Optional[Event]:
        """ Overrides the base method of BaseBlock to add the saving throw checks"""
        if condition.name is None:
            raise ValueError("BaseCondition name is not set")
        if condition.target_entity_uuid is None:
            condition.target_entity_uuid = self.uuid
        if context is not None:
            condition.set_context(context)
        
        declaration_event = condition.declare_event(parent_event)

        if self.check_condition_immunity(condition.name):
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
                #already present we need to remove the old one and add the new one for now not stackable
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
            True if condition was removed (via save or expiration)
        """
        condition = self.active_conditions.get(condition_name)
        if condition is None:
            return False

        # Check removal saving throw
        if not skip_save_throw and condition.removal_saving_throw is not None:
            (_, _, success) = self.saving_throw(condition.removal_saving_throw)
            if success:
                self.remove_condition(condition_name)
                return True

        # Progress duration (just checks expiration, doesn't auto-remove)
        expired = condition.progress()
        if expired:
            self.remove_condition(condition_name, expire=True)
        return expired

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
        # Create event at DECLARATION phase
        event = TurnStartEvent(
            source_entity_uuid=self.uuid,
            source_entity_name=self.name,
            target_entity_uuid=self.uuid,
            entity_uuid=self.uuid,
            encounter_uuid=encounter_uuid or self.uuid,  # Use entity UUID if no encounter
            round_number=round_number,
            turn_index=turn_index,
            phase=EventPhase.DECLARATION
        )

        # Advance to EXECUTION - handlers like Survivor, Grease turn start trigger here
        event = event.phase_to(EventPhase.EXECUTION)

        # Advance condition durations (at start of turn per SRD)
        # This makes Dodge work correctly ("until start of your next turn")
        condition_names = list(self.active_conditions.keys())
        for condition_name in condition_names:
            self.advance_duration_condition(condition_name)

        # Advance conditions on all owned items (equipped + inventory)
        # Items are BaseBlocks with full condition lifecycle
        for item in self.equipment.get_all_equipped_items():
            for cond_name in list(item.active_conditions.keys()):
                item.advance_duration(cond_name)
        for item in self.inventory.items.values():
            for cond_name in list(item.active_conditions.keys()):
                item.advance_duration(cond_name)

        # Reset action economy
        self.action_economy.reset_all_costs()
        self.action_economy.on_turn_start()  # Recharge TURN_START resources

        # Set turn flag AFTER action economy reset (cleared in on_turn_end)
        # This ensures is_my_turn is only True when entity has full action economy
        self.is_my_turn = True

        # Get current action economy values for event
        actions = self.action_economy.actions.normalized_score
        bonus_actions = self.action_economy.bonus_actions.normalized_score
        movement = self.action_economy.movement.normalized_score
        reactions = self.action_economy.reactions.normalized_score

        # Continue through phases with action economy info
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
        # Calculate used resources for event
        actions_used = max(0, 1 - self.action_economy.actions.normalized_score)
        bonus_used = max(0, 1 - self.action_economy.bonus_actions.normalized_score)
        base_mod = self.action_economy.movement.get_base_modifier()
        base_movement = base_mod.value if base_mod else 30
        movement_used = max(0, base_movement - self.action_economy.movement.normalized_score)

        # Create event at DECLARATION
        event = TurnEndEvent(
            source_entity_uuid=self.uuid,
            source_entity_name=self.name,
            target_entity_uuid=self.uuid,
            entity_uuid=self.uuid,
            encounter_uuid=encounter_uuid or self.uuid,  # Use entity UUID if no encounter
            round_number=round_number,
            turn_index=turn_index,
            actions_used=actions_used,
            bonus_actions_used=bonus_used,
            movement_used=movement_used,
            phase=EventPhase.DECLARATION
        )

        # EXECUTION - handlers like rage maintenance run here
        event = event.phase_to(EventPhase.EXECUTION)

        # EFFECT
        event = event.phase_to(EventPhase.EFFECT)

        # COMPLETION
        event = event.phase_to(EventPhase.COMPLETION)

        # Clear turn flag
        self.is_my_turn = False

        return event

    def _get_bonuses_for_skill(self, skill_name: SkillName) -> Tuple[ModifiableValue,ModifiableValue,ModifiableValue,ModifiableValue]:
        proficiency_bonus = self.proficiency_bonus
        skill = self.skill_set.get_skill(skill_name)
        skill_bonus = skill.skill_bonus
        proficiency_bonus_multiplier_callable = skill._get_proficiency_converter()
        ability_name = skill.ability
        ability = self.ability_scores.get_ability(ability_name)
        ability_bonus = ability.ability_score
        ability_modifier_bonus = ability.modifier_bonus
        normalized_proficiency_bonus = proficiency_bonus.model_copy(deep=True)
        normalized_proficiency_bonus.update_normalizers(proficiency_bonus_multiplier_callable)
        return normalized_proficiency_bonus, skill_bonus, ability_bonus, ability_modifier_bonus
    
    def _get_bonuses_for_saving_throw(self, ability_name: AbilityName) -> Tuple[ModifiableValue,ModifiableValue,ModifiableValue,ModifiableValue]:
        saving_throw = self.saving_throws.get_saving_throw(ability_name)
        saving_throw_bonus = saving_throw.bonus
        proficiency_bonus_multiplier_callable = saving_throw._get_proficiency_converter()
        proficiency_bonus = self.proficiency_bonus
        ability_bonus = self.ability_scores.get_ability(ability_name).ability_score
        ability_modifier_bonus = self.ability_scores.get_ability(ability_name).modifier_bonus

        normalized_proficiency_bonus = proficiency_bonus.model_copy(deep=True)
        normalized_proficiency_bonus.update_normalizers(proficiency_bonus_multiplier_callable)
        return normalized_proficiency_bonus, saving_throw_bonus, ability_bonus,ability_modifier_bonus
    
    def _get_attack_bonuses(self,weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> Tuple[ModifiableValue,ModifiableValue,List[ModifiableValue],List[ModifiableValue],Range ]:
        """ We have to get from weapon and then from equipment
        attack_bonus
        ability bonuses
        weapon attack bonus """
        weapon = self.equipment._get_weapon_by_slot(weapon_slot)

        ability_bonuses : List[ModifiableValue] = []
        dexterity_bonus = self.ability_scores.get_ability("dexterity").ability_score
        dexterity_modifier_bonus = self.ability_scores.get_ability("dexterity").modifier_bonus
        strength_bonus = self.ability_scores.get_ability("strength").ability_score
        strength_modifier_bonus = self.ability_scores.get_ability("strength").modifier_bonus
        attack_bonuses : List[ModifiableValue] = [self.equipment.attack_bonus]
        if weapon is None or isinstance(weapon, Shield):
            weapon_bonus=self.equipment.unarmed_attack_bonus
            attack_bonuses.append(self.equipment.melee_attack_bonus)
            ability_bonuses.append(strength_bonus)
            ability_bonuses.append(strength_modifier_bonus)
            range = Range(type=RangeType.REACH,normal=5)
        else:
            weapon_bonus=weapon.attack_bonus
            range = weapon.range
            if range.type == RangeType.RANGE:

                attack_bonuses.append(self.equipment.ranged_attack_bonus)
                ability_bonuses.append(dexterity_bonus)
                ability_bonuses.append(dexterity_modifier_bonus)
            elif range.type == RangeType.REACH and WeaponProperty.FINESSE in weapon.properties:
                attack_bonuses.append(self.equipment.melee_attack_bonus)
                combined_strength_bonus = strength_bonus.combine_values([strength_modifier_bonus])
                combined_dexterity_bonus = dexterity_bonus.combine_values([dexterity_modifier_bonus])
                if combined_strength_bonus.normalized_score >= combined_dexterity_bonus.normalized_score:
                    ability_bonuses.append(strength_bonus)
                    ability_bonuses.append(strength_modifier_bonus)
                else:
                    ability_bonuses.append(dexterity_bonus)
                    ability_bonuses.append(dexterity_modifier_bonus)
            else:
                attack_bonuses.append(self.equipment.melee_attack_bonus)
                ability_bonuses.append(strength_bonus)
                ability_bonuses.append(strength_modifier_bonus)
        proficiency_bonus = self.proficiency_bonus
        
        return proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, range
      
    

    
    def saving_throw_bonus(self, target_entity_uuid: Optional[UUID], ability_name: AbilityName) -> ModifiableValue:
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

        saving_throw_bonuses_source =self._get_bonuses_for_saving_throw(ability_name)
        # Only cross-propagate when target is a DIFFERENT entity
        # Self-targeting (e.g., caster in own Fireball AoE) doesn't need cross-propagation:
        # - The caster's own conditions are already in self_static
        # - There's no "other entity imposing effects" relationship
        if target_entity is not None and self.target_entity_uuid != self.uuid:
            for mod_source,mod_target in zip(saving_throw_bonuses_source,saving_throw_bonuses_target):
                mod_source.set_from_target(mod_target)    
        total_bonus_source = saving_throw_bonuses_source[0].combine_values(list(saving_throw_bonuses_source)[1:]).model_copy(deep=True)
        
        if should_clear_target:
            self.clear_target_entity()

        return total_bonus_source

    def skill_bonus(self, target_entity_uuid: Optional[UUID], skill_name: SkillName) -> ModifiableValue:
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
        # Only cross-propagate when target is a DIFFERENT entity
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
        """Calculate passive skill for contested checks (BG3-style).

        Formula: 10 + skill bonus + advantage modifier
        - Advantage on the skill: +5
        - Disadvantage on the skill: -5

        Used for Shove target DC and other contested checks where
        the defender uses passive resistance.

        Args:
            skill_name: The skill to calculate passive for

        Returns:
            int: The passive skill value (10 + bonus + adv/disadv modifier)
        """
        skill_bonus = self.skill_bonus(target_entity_uuid=None, skill_name=skill_name)
        base = 10 + skill_bonus.normalized_score

        # BG3 passive skill includes advantage/disadvantage
        if skill_bonus.advantage == AdvantageStatus.ADVANTAGE:
            base += 5
        elif skill_bonus.advantage == AdvantageStatus.DISADVANTAGE:
            base -= 5

        return base

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
        """ missing effects from target attack bonus"""
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True

        if self.equipment.is_unarmored():
            unarmored_values = self.equipment.get_unarmored_ac_values()
            abilities = self.equipment.get_unarmored_abilities()
            ability_bonuses = [self.ability_scores.get_ability(ability).ability_score for ability in abilities]
            ability_modifier_bonuses = [self.ability_scores.get_ability(ability).modifier_bonus for ability in abilities]
            ac_bonus = unarmored_values[0].combine_values(unarmored_values[1:]+ability_bonuses+ability_modifier_bonuses)
        else:
            armored_values = self.equipment.get_armored_ac_values()
            max_dexterity_bonus = self.equipment.get_armored_max_dex_bonus()
            dexterity_bonus = self.ability_scores.get_ability("dexterity").ability_score
            dexterity_modifier_bonus = self.ability_scores.get_ability("dexterity").modifier_bonus
            combined_dexterity_bonus = dexterity_bonus.combine_values([dexterity_modifier_bonus])
            
            # Only cap dexterity if there's a max_dexterity_bonus
            if max_dexterity_bonus is not None and combined_dexterity_bonus.normalized_score > max_dexterity_bonus.normalized_score:
                combined_dexterity_bonus = max_dexterity_bonus
            
            ac_bonus = armored_values[0].combine_values(armored_values[1:]+[combined_dexterity_bonus])
        
        if should_clear_target:
            self.clear_target_entity()
        return ac_bonus
    
    
    def attack_bonus(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN, target_entity_uuid: Optional[UUID] = None) -> ModifiableValue:
        """ missing effects from target armor bonus"""
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True

        proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, _ = self._get_attack_bonuses(weapon_slot)
        bonuses = [weapon_bonus] + attack_bonuses + ability_bonuses
        source_attack_bonus = proficiency_bonus.combine_values(bonuses)

        if should_clear_target:
            self.clear_target_entity()
        return source_attack_bonus

    def get_crit_threshold(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> int:
        """Get the minimum natural roll needed for a critical hit.

        Args:
            weapon_slot: Which weapon slot to check (determines melee vs ranged)

        Returns:
            int: The minimum natural d20 roll for a critical hit.
                 Default is 20, Improved Critical = 19, Superior Critical = 18.
        """
        # General threshold applies to all attacks
        general = self.equipment.crit_threshold.normalized_score

        # Specific threshold stacks (for melee-only or ranged-only bonuses)
        if weapon_slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF]:
            specific = self.equipment.crit_threshold_melee.normalized_score
        else:
            specific = self.equipment.crit_threshold_ranged.normalized_score

        return 20 - (general + specific)  # Default 20, +1 = 19, +2 = 18

    def get_crit_extra_dice(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> int:
        """Get the number of extra dice to roll on critical hits.

        Combines general extra dice with weapon-type specific extra dice.
        Used by Brutal Critical and similar features.

        Args:
            weapon_slot: The weapon slot being used for the attack.

        Returns:
            int: Extra dice count (0 by default, +1/+2/+3 for Brutal Critical).
        """
        # General modifier applies to all attacks
        general = self.equipment.crit_extra_dice.normalized_score

        # Specific modifier based on weapon type
        if weapon_slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF]:
            specific = self.equipment.crit_extra_dice_melee.normalized_score
        else:
            specific = self.equipment.crit_extra_dice_ranged.normalized_score

        return general + specific

    def get_damages(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN, target_entity_uuid: Optional[UUID] = None) -> List[Damage]:
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True
        damages = self.equipment.get_damages(weapon_slot, self.ability_scores)
        if should_clear_target:
            self.clear_target_entity()
        return damages
    
    def take_damage(self, damages: List[Damage], attack_outcome: AttackOutcome) -> List[DiceRoll]:
        """ From each damage we get the dice and damage type and we roll it """

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
        parent_event: Optional[UUID] = None
    ) -> int:
        """
        Apply damage with proper event firing.

        Fires TakeDamageEvent through phases, allowing handlers to:
        - Track damage (HasTakenDamage, Concentration)
        - Modify damage (Relentless Rage)
        - Cancel damage (future features)
        - React to damage (Retaliation, Sleep wake)

        Also handles:
        - Adding combat log entry
        - Applying Dead condition when HP <= 0
        - Firing DeathEvent when entity dies

        Args:
            amount: Damage amount (pre-resistance)
            damage_type: Type of damage
            source_entity_uuid: Who/what dealt the damage
            damage_rolls: Optional dice roll details for combat log
            damages: Optional damage specifications
            parent_event: Optional parent event UUID for lineage

        Returns:
            Actual damage taken after resistances (0 if canceled)
        """
        # Create damages list for combat log if not provided
        # This ensures damage type is shown even for simple receive_damage calls
        event_damages = damages if damages else [
            Damage(
                damage_type=damage_type,
                dice_numbers=1,  # Placeholder for combat log
                damage_dice=4,   # Placeholder for combat log
                source_entity_uuid=source_entity_uuid
            )
        ]

        # Create event at DECLARATION phase
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

        # Progress through phases - handlers can intercept at EFFECT
        # (e.g., Relentless Rage can modify damage to keep entity at 1 HP)
        take_damage_event = take_damage_event.phase_to(EventPhase.EXECUTION)
        take_damage_event = take_damage_event.phase_to(EventPhase.EFFECT)

        # Apply damage if not canceled
        actual_damage = 0
        if not take_damage_event.canceled:
            effective_damage = take_damage_event.get_effective_damage()
            actual_damage = self.health.take_damage(
                effective_damage,
                damage_type,
                source_entity_uuid=source_entity_uuid
            )

        # Complete the event
        # NOTE: Combat log auto-captured via callback in phase_to() for top-level events.
        # Sub-events (with parent_event) are collected by their parent's sub_entries.
        take_damage_event = take_damage_event.phase_to(EventPhase.COMPLETION)

        # Handle death if HP <= 0
        # Note: Relentless Rage already had its chance at EFFECT phase
        # If HP <= 0 here, the save either failed or wasn't triggered
        if self.get_hp() <= 0 and "Dead" not in self.active_conditions:
            # Fire DeathEvent through phases - death_handler applies Dead condition at EXECUTION
            # NOTE: Combat log auto-captured via callback in phase_to() at COMPLETION
            # DeathEvent is a child of the TakeDamageEvent that caused it
            death_event = DeathEvent(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=self.uuid,
                entity_uuid=self.uuid,
                entity_name=self.name,
                killer_uuid=source_entity_uuid,
                final_hp=self.get_hp(),
                phase=EventPhase.DECLARATION,
                parent_event=take_damage_event.uuid
            )
            # Progress through phases - death_handler applies Dead condition at EXECUTION
            death_event = death_event.phase_to(EventPhase.EXECUTION)
            death_event = death_event.phase_to(EventPhase.EFFECT)
            # phase_to(COMPLETION) auto-generates combat_log and calls callback
            death_event = death_event.phase_to(EventPhase.COMPLETION)

        return actual_damage

    def get_hp(self) -> int:
        """ total health of the entity """
        con_modifier = self.ability_scores.get_ability("constitution").get_combined_values()
        return self.health.get_total_hit_points(constitution_modifier=con_modifier.normalized_score)
    
    def get_weapon_range(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> Range:
        """
        Get the range of a weapon without calculating attack bonuses.

        Args:
            weapon_slot: Which weapon slot to check

        Returns:
            Range: The range of the weapon
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
            bool: True if any visible enemy threatens this entity's position
        """
        my_position = self.senses.position
        for entity_uuid in self.senses.entities.keys():
            other_entity = Entity.get(entity_uuid)
            if other_entity and self.is_enemy(other_entity):  # Only enemies threaten
                if my_position in other_entity.senses.get_threathened_positions():
                    return True
        return False

    # =========================================================================
    # Spellcasting System
    # =========================================================================

    def spell_attack_bonus(self, target_entity_uuid: Optional[UUID] = None) -> ModifiableValue:
        """Build combined spell attack bonus.

        Combines (stacks):
        1. Proficiency bonus
        2. Spellcasting ability modifier (CHA/INT/WIS)
        3. Equipment.attack_bonus (Blinded, Poisoned, etc.) ← CONDITIONS APPLY
        4. SpellcastingBlock.spell_attack_bonus (Wand of War Mage) ← SPELL-SPECIFIC

        Uses combine_values() to merge all 6 channels properly.

        Args:
            target_entity_uuid: Optional target for cross-propagation

        Returns:
            Combined ModifiableValue for spell attacks
        """
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True

        # Get ability (uses normalizer to calculate modifier from score)
        ability = self.ability_scores.get_ability(self.spellcasting.spellcasting_ability)
        # Need both ability_score (with normalizer) AND modifier_bonus (for additional bonuses)
        ability_score = ability.ability_score
        ability_modifier_bonus = ability.modifier_bonus

        combined = self.proficiency_bonus.combine_values([
            ability_score,                         # ← Base ability (normalized to modifier)
            ability_modifier_bonus,                # ← Additional modifier bonuses
            self.equipment.attack_bonus,           # ← Generic (conditions here)
            self.spellcasting.spell_attack_bonus,  # ← Spell-specific
        ])

        if should_clear_target:
            self.clear_target_entity()

        return combined

    def spell_save_dc(self) -> int:
        """Calculate spell save DC.

        DC = 8 + proficiency + ability_modifier + spell_dc_bonus

        Returns:
            The spell save DC as an integer
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
            Number to roll >= for a crit (default 20)
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
            Number of extra dice to roll on spell crits
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
            Combined ModifiableValue for spell damage
        """
        return self.equipment.damage_bonus.combine_values([
            self.spellcasting.spell_damage_bonus,
        ])

    def has_spell_slot(self, level: int) -> bool:
        """Check if entity has an available spell slot of given level.

        Args:
            level: The spell slot level (1-9)

        Returns:
            True if at least one slot of that level is available
        """
        if level < 1 or level > 9:
            return False
        # Use getattr to check the specific spell slot ModifiableValue
        slot_attr = getattr(self.action_economy, f"spell_slot_{level}", None)
        if slot_attr is None:
            return False
        return slot_attr.normalized_score >= 1

    def get_lowest_spell_slot(self, min_level: int) -> Optional[int]:
        """Find lowest available slot at or above min_level.

        Args:
            min_level: Minimum slot level to consider

        Returns:
            The lowest available slot level, or None if none available
        """
        for level in range(min_level, 10):
            if self.has_spell_slot(level):
                return level
        return None

    @property
    def is_spellcaster(self) -> bool:
        """True if entity has any spell slots or known spells.

        An entity is considered a spellcaster if:
        1. It has any spell slots (non-zero base value), OR
        2. It has any SpellAction registered

        Returns:
            True if this entity can cast spells
        """
        # Check for spell slots
        for level in range(1, 10):
            slot_attr = getattr(self.action_economy, f"spell_slot_{level}", None)
            if slot_attr is not None:
                base_mod = slot_attr.get_base_modifier()
                if base_mod and base_mod.value > 0:
                    return True
        # Note: SpellAction check would go here once SpellAction is implemented
        # For now, just check spell slots
        return False

    # =========================================================================
    # Faction System
    # =========================================================================

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
            return True  # Always ally of self
        if self.faction is None or other.faction is None:
            return False  # No faction = no allies (except self)
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
            return False  # Not enemy to self
        if self.faction is None or other.faction is None:
            return True  # No faction = enemy to everyone
        return self.faction != other.faction

    def get_visible_enemies(self, include_dead: bool = False) -> Dict[UUID, Tuple[int, int]]:
        """Get visible entities that are enemies.

        Args:
            include_dead: If True, include dead enemies (HP <= 0). Default False.
                         Useful for resurrection or corpse-targeting spells.

        Returns:
            Dict mapping enemy UUID to their position
        """
        enemies: Dict[UUID, Tuple[int, int]] = {}
        for entity_uuid, pos in self.senses.entities.items():
            other = Entity.get(entity_uuid)
            if other and self.is_enemy(other):
                # Filter dead entities unless include_dead is True
                if not include_dead and other.get_hp() <= 0:
                    continue
                enemies[entity_uuid] = pos
        return enemies

    def get_visible_allies(self, include_dead: bool = False) -> Dict[UUID, Tuple[int, int]]:
        """Get visible entities that are allies (same faction, not self).

        Args:
            include_dead: If True, include dead allies (HP <= 0). Default False.
                         Useful for resurrection spells.

        Returns:
            Dict mapping ally UUID to their position
        """
        allies: Dict[UUID, Tuple[int, int]] = {}
        for entity_uuid, pos in self.senses.entities.items():
            other = Entity.get(entity_uuid)
            if other and self.is_ally(other):
                # Filter dead entities unless include_dead is True
                if not include_dead and other.get_hp() <= 0:
                    continue
                allies[entity_uuid] = pos
        return allies

    @classmethod
    def get_entities_by_faction(cls, faction: str) -> List['Entity']:
        """Get all entities with the given faction.

        Args:
            faction: The faction identifier

        Returns:
            List of entities with that faction
        """
        return [e for e in cls._entity_registry.values() if e.faction == faction]

    @classmethod
    def get_alive_by_faction(cls, faction: str) -> List['Entity']:
        """Get all alive entities with the given faction.

        Args:
            faction: The faction identifier

        Returns:
            List of alive entities with that faction
        """
        return [e for e in cls._entity_registry.values()
                if e.faction == faction and e.get_hp() > 0]

    def roll_d20(
        self,
        bonus: ModifiableValue,
        roll_type: RollType = RollType.ATTACK,
        context: Optional[Dict[str, Any]] = None,
        ability_name: Optional[AbilityName] = None,
        skill_name: Optional[SkillName] = None,
        weapon_slot: Optional[WeaponSlot] = None
    ) -> DiceRoll:
        """
        Roll a d20 with the given bonus.

        Fires the appropriate D20RollResultEvent subclass allowing handlers to intercept.
        - RollType.ATTACK → AttackD20RollResultEvent
        - RollType.SAVE → SavingThrowD20RollResultEvent
        - RollType.CHECK → SkillCheckD20RollResultEvent

        Args:
            bonus: The modifier value to add to the roll
            roll_type: Type of roll (ATTACK, SAVE, CHECK)
            context: Optional context dict for handler decisions
            ability_name: Required for SAVE rolls
            skill_name: Required for CHECK rolls
            weapon_slot: Optional for ATTACK rolls

        Returns:
            DiceRoll: The result of the roll (possibly modified by handlers)
        """
        # 1. Create the actual roll
        dice = Dice(count=1, value=20, bonus=bonus, roll_type=roll_type)
        initial_roll = dice.roll

        # 2. Create appropriate event subclass based on roll_type
        common_fields = {
            "source_entity_uuid": self.uuid,
            "target_entity_uuid": bonus.target_entity_uuid,
            "roll": initial_roll,
            "original_roll": initial_roll,
            "bonus": bonus,
            "context": context or {},
            "phase": EventPhase.DECLARATION,
            "roll_type": roll_type
        }

        if roll_type == RollType.ATTACK:
            event: D20RollResultEvent = AttackD20RollResultEvent(
                **common_fields,
                weapon_slot=weapon_slot
            )
        elif roll_type == RollType.SAVE:
            if ability_name is None:
                # Fallback to base class if ability_name not provided
                event = D20RollResultEvent(**common_fields)
            else:
                event = SavingThrowD20RollResultEvent(
                    **common_fields,
                    ability_name=ability_name
                )
        elif roll_type == RollType.CHECK:
            if skill_name is None:
                # Fallback to base class if skill_name not provided
                event = D20RollResultEvent(**common_fields)
            else:
                event = SkillCheckD20RollResultEvent(
                    **common_fields,
                    skill_name=skill_name
                )
        else:
            # Fallback to base class
            event = D20RollResultEvent(**common_fields)

        # 3. Transition to EFFECT phase - handlers intercept here
        event = event.phase_to(EventPhase.EFFECT, status_message="D20 rolled, handlers may modify")

        # 4. Complete the event
        event = event.phase_to(EventPhase.COMPLETION)

        # 5. Return effective roll (possibly modified)
        return event.get_effective_roll()
        
    
    def create_saving_throw_request(
        self,
        target_entity_uuid: UUID,
        ability_name: AbilityName,
        dc: Union[int, UUID],
        parent_event: Optional[UUID] = None
    ) -> SavingThrowEvent:
        """ request a saving throw from the target entity """
        #if dc is a uuid get the modifiable value ensure is coming from self (has self.uuid as source entity uuid)
        if isinstance(dc,UUID):

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

        # Get target entity name for combat log generation
        target_entity = Entity.get(target_entity_uuid)
        target_entity_name = target_entity.name if target_entity else None

        return SavingThrowEvent(
            source_entity_uuid=self.uuid,
            target_entity_uuid=target_entity_uuid,
            ability_name=ability_name,
            dc=int_dc,
            source_entity_name=self.name,
            target_entity_name=target_entity_name,
            parent_event=parent_event
        )
    

    def create_skill_check_request(
        self,
        target_entity_uuid: UUID,
        skill_name: SkillName,
        dc: Union[int, UUID],
        parent_event: Optional[UUID] = None
    ) -> SkillCheckEvent:
        """ request a skill check from the target entity """
        if isinstance(dc,UUID):
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

        # Get target entity name for combat log generation
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

        This enables event handlers (like Indomitable) to intercept and modify
        saving throw results at the EFFECT phase.
        """
        if request.target_entity_uuid != self.uuid:
            raise ValueError("Target entity uuid does not match")

        self.set_target_entity(request.source_entity_uuid)

        # Get save bonus and DC
        save_bonus = self.saving_throw_bonus(request.source_entity_uuid, request.ability_name)
        dc = request.get_dc()
        if dc is None:
            raise ValueError(f"DC is not set for {request.ability_name} saving throw with event id {request.uuid}")

        # EXECUTION phase - bonus calculated, about to roll
        execution_event = request.phase_to(
            EventPhase.EXECUTION,
            bonus=save_bonus,
            status_message=f"Rolling {request.ability_name} save vs DC {dc}"
        )

        # Roll the dice (with ability_name for event handlers)
        roll = self.roll_d20(save_bonus, RollType.SAVE, ability_name=request.ability_name)
        outcome = determine_attack_outcome(roll, dc)
        success = outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

        # EFFECT phase - roll made, result determined (Indomitable hooks here!)
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            dice_roll=roll,
            result=success,
            status_message=f"Rolled {roll.total} vs DC {dc}: {'Success' if success else 'Failure'}"
        )

        # COMPLETION phase - finalized
        completion_event = effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{request.ability_name} save complete"
        )

        self.clear_target_entity()

        # Return from final event (may have been modified by handlers)
        final_roll = completion_event.dice_roll or roll
        final_success = completion_event.result if completion_event.result is not None else success
        final_outcome = outcome
        # Recalculate outcome if result was changed by a handler
        if final_success != success:
            if final_success:
                final_outcome = AttackOutcome.HIT  # Success
            else:
                final_outcome = AttackOutcome.MISS  # Failure

        return final_outcome, final_roll, final_success
    
    def skill_check(self, request: SkillCheckEvent) -> Tuple[AttackOutcome,DiceRoll,bool]:
        """ make a skill check """
        if request.target_entity_uuid != self.uuid:
            raise ValueError("Target entity uuid does not match")
        self.set_target_entity(request.source_entity_uuid)
        skill_check = self.skill_bonus(request.source_entity_uuid, request.skill_name)
        dc = request.get_dc()
        if dc is None:
            raise ValueError(f"DC is not set for {request.skill_name} skill check with event id {request.uuid}")
        #create the dice (with skill_name for event handlers)
        roll = self.roll_d20(skill_check, RollType.CHECK, skill_name=request.skill_name)
        skill_check_outcome = determine_attack_outcome(roll, dc)
        self.clear_target_entity()
        return skill_check_outcome, roll, True if skill_check_outcome not in [AttackOutcome.MISS,AttackOutcome.CRIT_MISS] else False


    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """An entity blocks walking unless it is non-blocking or the requester is itself."""
        if requesting_entity_uuid == self.uuid:
            return False
        if self.non_blocking:
            return False
        return True

    # =========================================================================
    # Inventory / Loot / Drop
    # =========================================================================

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
        # Remove from grid regardless of merge (item is leaving the floor)
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
            item_uuid: UUID of the item to drop (must be in inventory)
            position: Grid position to drop at. Defaults to entity's position.
                      Must be within distance 1 (5ft) of entity.

        Returns the dropped item, or None if not found in inventory.
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
        gridmap.place_object(item.uuid, drop_pos)  # fires SPATIAL_OBJECT_PLACED
        item.drop(entity_uuid=self.uuid, position=drop_pos)
        return item

    def equip_item(self, item_uuid: UUID, slot: EquipmentSlot) -> bool:
        """Move item from inventory to equipment slot.

        If the target slot is occupied, unequips the existing item to inventory first.
        Returns True on success, False if item not found or not equippable.
        """
        item = self.inventory.items.get(item_uuid)
        if item is None or not item.is_equippable:
            return False
        # If slot occupied, unequip existing item to inventory first
        existing = self.equipment.get_item_by_slot(slot)
        if existing is not None:
            self.unequip_item(slot)
        self.inventory.remove_item(item_uuid)
        self.equipment.equip(cast(Union[Armor, Weapon, Shield], item), slot)
        # Equipment.equip() sets owner_uuid, stored_in_uuid, is_equipped, equipped_slot
        return True

    def unequip_item(self, slot: EquipmentSlot) -> Optional[BaseItem]:
        """Move item from equipment slot to inventory.

        If inventory is full, drops item to ground at entity position.
        Returns the item, or None if slot was empty.
        """
        item = self.equipment.unequip(slot)
        # Equipment.unequip() calls item.unequip(slot, entity_uuid)
        # which clears is_equipped and equipped_slot. owner_uuid/stored_in_uuid still set.
        if item is None:
            return None
        if self.inventory.add_item(item):
            item.owner_uuid = self.uuid
            item.stored_in_uuid = self.inventory.uuid
        else:
            # Inventory full — drop to ground
            gridmap = get_map()
            item.owner_uuid = None
            item.stored_in_uuid = None
            item.position = self.position
            tile = gridmap.get_tile(self.position[0], self.position[1])
            item.tile_uuid = tile.uuid if tile else None
            gridmap.place_object(item.uuid, self.position)
        return item

    @staticmethod
    def compute_senses_from_position(
        position: Tuple[int, int],
        seen: Set[Tuple[int, int]],
        max_distance: int = 10,
        entity_uuid: Optional[UUID] = None
    ) -> Tuple[Dict[Tuple[int, int], bool], DefaultDict[Tuple[int, int], List[Tuple[int, int]]], Dict[Tuple[int, int], bool], Dict[UUID, Tuple[int, int]], Dict[UUID, Tuple[int, int]]]:
        """
        Compute senses data from a position.

        Args:
            position: The position to compute from
            seen: Set of previously seen positions
            max_distance: Maximum view/movement distance
            entity_uuid: If provided, pathfinding will exclude cells occupied by other entities

        Returns:
            (visible_dict, paths, walkable, visible_entities, visible_objects)
        """
        grid = get_map()

        # Get visible cells using shadowcast
        visible_positions = grid.compute_fov(position, max_distance)
        visible_dict = {pos: True for pos in visible_positions}

        # Get walkable paths using dijkstra (with occupancy check if entity_uuid provided)
        _, paths = grid.compute_paths(position, max_distance, requesting_entity_uuid=entity_uuid)

        # Filter paths to only include those where:
        # 1. The destination is currently visible
        # 2. All positions in the path are either seen before OR currently visible
        filtered_paths: DefaultDict[Tuple[int, int], List[Tuple[int, int]]] = defaultdict(list)
        for pos, path in paths.items():
            # Check if destination is visible and all path positions are known (seen or visible)
            if pos in visible_dict and all(step in seen or step in visible_dict for step in path):
                filtered_paths[pos] = path

        # Get entities at visible positions
        visible_entities: Dict[UUID, Tuple[int, int]] = {}
        for pos in visible_positions:
            entities = Entity.get_all_entities_at_position(pos)
            for entity in entities:
                visible_entities[entity.uuid] = pos

        # Get objects at visible positions
        visible_objects: Dict[UUID, Tuple[int, int]] = {}
        for pos in visible_positions:
            for obj_uuid in grid.get_objects_at(pos):
                visible_objects[obj_uuid] = pos

        # Build walkable dict from grid
        walkable = {pos: grid.is_walkable(pos[0], pos[1]) for pos in visible_positions}

        return visible_dict, filtered_paths, walkable, visible_entities, visible_objects

    def create_senses_copy_at_position(self, position: Tuple[int, int], max_distance: int = 10) -> 'Senses':
        """Create a copy of senses as if entity were at a different position."""
        senses = self.senses.model_copy(deep=True)
        senses.position = position
        visible_dict, filtered_paths, walkable, visible_entities, visible_objects = Entity.compute_senses_from_position(
            position, self.senses.seen, max_distance, entity_uuid=self.uuid
        )

        senses.update_senses(
            entities=visible_entities,
            visible=visible_dict,
            walkable=walkable,
            paths=filtered_paths,
            objects=visible_objects
        )
        return senses

    def update_entity_senses(self, max_distance: int = 10):
        """
        Update the entity's senses using shadowcasting and pathfinding.

        This computes:
        - Visible cells within max_distance using shadowcast
        - Paths to reachable cells using dijkstra (excludes cells occupied by other entities)
        - Entities present in visible cells

        After updating, subscribes to visible cells so this entity
        receives SpatialChangeEvents when something changes in its FOV.

        Args:
            max_distance: Maximum view/movement distance (default 10)
        """
        visible_dict, filtered_paths, walkable, visible_entities, visible_objects = Entity.compute_senses_from_position(
            self.position, self.senses.seen, max_distance, entity_uuid=self.uuid
        )
        # Update the senses block
        self.senses.update_senses(
            entities=visible_entities,
            visible=visible_dict,
            walkable=walkable,
            paths=filtered_paths,
            objects=visible_objects
        )
        # Subscribe to visible cells for spatial change notifications
        visible_cells = set(visible_dict.keys())
        get_map().subscribe_to_cells(self.uuid, visible_cells)

    @classmethod
    def update_all_entities_senses(cls, max_distance: int = 10):
        """Update the senses for all entities."""
        for entity in cls.get_all_entities():
            entity.update_entity_senses(max_distance)

    def update_entity_visibility(self, max_distance: int = 10):
        """
        Lightweight FOV-only update (no path recomputation).

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
        # Compute FOV only - returns list of visible positions
        visible_positions = grid.compute_fov(self.position, max_distance)

        # Convert to dict format expected by Senses
        visible_dict: Dict[Tuple[int, int], bool] = {pos: True for pos in visible_positions}

        # Find entities in visible cells
        visible_entities: Dict[UUID, Tuple[int, int]] = {}
        for pos in visible_positions:
            for ent_uuid in grid.get_entities_at(pos):
                if ent_uuid != self.uuid:
                    visible_entities[ent_uuid] = pos

        # Find objects in visible cells
        visible_objects: Dict[UUID, Tuple[int, int]] = {}
        for pos in visible_positions:
            for obj_uuid in grid.get_objects_at(pos):
                visible_objects[obj_uuid] = pos

        # Update visibility, entities, and objects (keep existing paths)
        self.senses.visible = visible_dict
        self.senses.update_seen(visible_dict)
        self.senses.entities = visible_entities
        self.senses.objects = visible_objects

        # Update subscriptions to newly visible cells
        visible_cells = set(visible_positions)
        grid.subscribe_to_cells(self.uuid, visible_cells)

    # =========================================================================
    # Action Registry System
    # =========================================================================

    def register_action(self, action: BaseAction) -> None:
        """Register an action template.

        Args:
            action: The action template to register (must have template=True)

        Raises:
            ValueError: If the action is not a template
        """
        if not action.template:
            raise ValueError("Can only register templates (template=True)")
        self.registered_actions.append(action)

    def unregister_action(self, name: str) -> None:
        """Remove an action template by name.

        Args:
            name: The name of the action template to remove
        """
        self.registered_actions = [a for a in self.registered_actions if a.name != name]

    def get_action_template(self, name: str) -> Optional[BaseAction]:
        """Get a registered action template by name.

        Args:
            name: The name of the action template

        Returns:
            The action template, or None if not found
        """
        return next((a for a in self.registered_actions if a.name == name), None)

    @property
    def entity_actions(self) -> List[BaseAction]:
        """Actions that target other entities (Attack, multi-target spells)."""
        return [a for a in self.registered_actions
                if a.target_type in (TargetType.ENTITY, TargetType.MULTI_ENTITY)]

    @property
    def position_actions(self) -> List[BaseAction]:
        """Actions that target positions (Move, Jump, AoE spells).

        Includes POSITION_PATH (uses senses.paths), POSITION_LOS (uses senses.visible),
        and POSITION_AOE (AoE spells with shape preview).
        """
        return [a for a in self.registered_actions
                if a.target_type in (TargetType.POSITION, TargetType.POSITION_PATH, TargetType.POSITION_LOS, TargetType.POSITION_AOE)]

    @property
    def self_actions(self) -> List[BaseAction]:
        """Actions that target self (Dash, Dodge, etc.)."""
        return [a for a in self.registered_actions if a.target_type == TargetType.SELF]

    @property
    def object_actions(self) -> List[BaseAction]:
        """Actions that target objects on the grid (Pick Up, Attack Object)."""
        return [a for a in self.registered_actions if a.target_type == TargetType.OBJECT]

    def get_available_actions(
        self,
        target_filter: str = "enemies",
        include_dead: bool = False
    ) -> AvailableActionsResult:
        """Get all available actions for this entity.

        Returns an AvailableActionsResult with all actions the entity can currently
        perform, grouped by target type. Each action includes valid targets with
        indices for easy selection (e.g., 'attack 0', 'move 3').

        This method is agnostic of specific action subclasses - it simply iterates
        over registered actions by target type and calls pre_validate() on each.

        Args:
            target_filter: Which entities to show as targets for entity actions.
                - "enemies": Only enemies (different faction) - default
                - "allies": Only allies (same faction)
                - "all": All visible entities
            include_dead: If True, include dead entities as valid targets.
                Default False. Set to True for resurrection or corpse-targeting spells.
        """
        result = AvailableActionsResult(
            entity_uuid=self.uuid,
            remaining_movement=self.action_economy.movement.normalized_score
        )

        # SELF actions - validate once, no targets needed
        # Include all registered self actions, set can_afford based on check_costs()
        for template in self.self_actions:
            template_name = template.name or "Unknown"
            can_afford = template.check_costs()
            # Only check pre_validate if costs are affordable (avoid duplicate work)
            is_valid = can_afford and template.pre_validate()
            # Include action if it's valid OR if it just can't be afforded
            # This allows UI to show grayed-out actions that exist but can't be used
            if is_valid or not can_afford:
                result.self_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=TargetType.SELF,
                    valid_targets=[AvailableTarget(index=0)] if is_valid else [],
                    can_afford=can_afford,
                    display_name=template_name,
                    description=template.description,
                    cost_type=template.costs[0].cost_type if template.costs else "actions",
                    cost_amount=template.costs[0].cost if template.costs else 0,
                    action_category=template.action_category,
                ))

        # ENTITY actions - filter targets based on target_filter
        if target_filter == "enemies":
            potential_targets = self.get_visible_enemies(include_dead=include_dead)
        elif target_filter == "allies":
            potential_targets = self.get_visible_allies(include_dead=include_dead)
        else:  # "all"
            # For "all" filter, still apply dead filtering unless include_dead is True
            potential_targets = {}
            for k, v in self.senses.entities.items():
                if k == self.uuid:
                    continue
                if not include_dead:
                    other = Entity.get(k)
                    if other and other.get_hp() <= 0:
                        continue
                potential_targets[k] = v

        for template in self.entity_actions:
            valid_targets: List[AvailableTarget] = []
            idx = 0

            # Build targets for THIS template (may include self if include_self=True)
            template_targets = dict(potential_targets)
            if getattr(template, 'include_self', False):
                template_targets[self.uuid] = self.position

            for target_uuid, target_pos in template_targets.items():
                template.set_target_entity(target_uuid)
                if template.pre_validate():
                    target_entity = Entity.get(target_uuid)
                    valid_targets.append(AvailableTarget(
                        index=idx,
                        target_uuid=target_uuid,
                        target_name=target_entity.name if target_entity else None,
                        distance=self.senses.get_feet_distance(target_pos)
                    ))
                    idx += 1

            if valid_targets:
                template_name = template.name or "Unknown"

                # Extract weapon info for attacks
                weapon_name: Optional[str] = None
                weapon_slot_str: Optional[str] = None
                display_name = template_name

                # Check if template has weapon_slot (Attack actions)
                weapon_slot_attr = getattr(template, 'weapon_slot', None)
                if weapon_slot_attr is not None:
                    weapon_slot_str = weapon_slot_attr.value if hasattr(weapon_slot_attr, 'value') else str(weapon_slot_attr)
                    weapon = self.equipment._get_weapon_by_slot(weapon_slot_attr)
                    if weapon and hasattr(weapon, 'name'):
                        weapon_name = weapon.name
                        display_name = weapon_name  # Use weapon name as display name

                result.entity_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=template.target_type,  # Use actual target type (ENTITY or MULTI_ENTITY)
                    valid_targets=valid_targets,
                    can_afford=template.check_costs(),
                    display_name=display_name,
                    description=template.description,
                    cost_type=template.costs[0].cost_type if template.costs else "actions",
                    cost_amount=template.costs[0].cost if template.costs else 0,
                    weapon_slot=weapon_slot_str,
                    weapon_name=weapon_name,
                    action_category=template.action_category,
                ))

        # POSITION_PATH actions (Move) - validate for each reachable position via path
        for template in self.position_actions:
            if template.target_type not in (TargetType.POSITION, TargetType.POSITION_PATH):
                continue
            valid_positions: List[AvailableTarget] = []
            idx = 0
            for pos, _ in self.senses.paths.items():
                if pos == self.senses.position:
                    continue
                template.set_target_position(pos)
                if template.pre_validate():
                    # Get actual terrain-based movement cost from template's computed costs
                    path_cost = 0
                    for cost in template.costs:
                        if cost.cost_type == "movement":
                            path_cost = cost.cost
                            break
                    valid_positions.append(AvailableTarget(
                        index=idx,
                        position=pos,
                        distance=self.senses.get_feet_distance(pos),
                        path_cost=path_cost
                    ))
                    idx += 1

            if valid_positions:
                template_name = template.name or "Unknown"
                result.position_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=template.target_type,
                    valid_targets=valid_positions,
                    can_afford=True,
                    display_name=template_name,
                    description=f"{result.remaining_movement}ft remaining",
                    cost_type="movement",
                    cost_amount=0,
                    action_category=template.action_category,
                ))

        # POSITION_LOS actions (Jump, Teleport) - use action's get_valid_positions()
        for template in self.position_actions:
            if template.target_type != TargetType.POSITION_LOS:
                continue

            # Let the action compute its own valid positions
            valid_pos_list = template.get_valid_positions()
            valid_positions = []
            idx = 0
            for pos in valid_pos_list:
                template.set_target_position(pos)
                if template.pre_validate():
                    valid_positions.append(AvailableTarget(
                        index=idx,
                        position=pos,
                        distance=self.senses.get_feet_distance(pos),
                        path_cost=None  # LOS actions don't use path cost
                    ))
                    idx += 1

            if valid_positions:
                template_name = template.name or "Unknown"
                cost_type = template.costs[0].cost_type if template.costs else "bonus_actions"
                cost_amount = template.costs[0].cost if template.costs else 1
                result.position_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=TargetType.POSITION_LOS,
                    valid_targets=valid_positions,
                    can_afford=template.check_costs(),
                    display_name=template_name,
                    description=template.description,
                    cost_type=cost_type,
                    cost_amount=cost_amount,
                    action_category=template.action_category,
                ))

        # POSITION_AOE actions - compute affected entities for each valid position
        for template in self.position_actions:
            if template.target_type != TargetType.POSITION_AOE:
                continue

            shape_template = template.aoe_shape
            if shape_template is None:
                continue

            valid_pos_list = template.get_valid_positions()
            valid_positions = []
            idx = 0

            for pos in valid_pos_list:
                template.set_target_position(pos)
                if not template.pre_validate():
                    continue

                # Compute shape for this position
                shape = shape_template.model_copy(update={'target': pos})
                shape.compute_subjective(self.position, self.senses)

                affected_uuids = list(shape.affected_entity_uuids)

                # Apply include_self filter (match get_all_targets behavior)
                if not getattr(template, 'include_self', False):
                    affected_uuids = [uid for uid in affected_uuids if uid != self.uuid]

                # Apply valid_target_filter (match _validate behavior)
                target_filter = getattr(template, 'valid_target_filter', 'enemies')
                if target_filter != "all":
                    filtered = []
                    for uid in affected_uuids:
                        ent = Entity.get(uid)
                        if ent:
                            if target_filter == "enemies" and self.is_enemy(ent):
                                filtered.append(uid)
                            elif target_filter == "allies" and self.is_ally(ent):
                                filtered.append(uid)
                            elif target_filter == "self_or_allies":
                                if uid == self.uuid or self.is_ally(ent):
                                    filtered.append(uid)
                    affected_uuids = filtered

                # Filter dead entities (unless include_dead=True on template)
                template_include_dead = getattr(template, 'include_dead', False)
                if not template_include_dead and not include_dead:
                    affected_uuids = [
                        uid for uid in affected_uuids
                        if (ent := Entity.get(uid)) and ent.get_hp() > 0
                    ]

                affected_names = []
                for uuid in affected_uuids:
                    ent = Entity.get(uuid)
                    if ent:
                        affected_names.append(ent.name or "Unknown")

                valid_positions.append(AvailableTarget(
                    index=idx,
                    position=pos,
                    distance=self.senses.get_feet_distance(pos),
                    affected_entity_uuids=affected_uuids,
                    affected_entity_names=affected_names,
                    affected_count=len(affected_uuids),
                    affected_positions=list(shape.affected_positions)
                ))
                idx += 1

            if valid_positions:
                template_name = template.name or "Unknown"
                cost_type = template.costs[0].cost_type if template.costs else "actions"
                result.position_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=TargetType.POSITION_AOE,
                    valid_targets=valid_positions,
                    can_afford=template.check_costs(),
                    display_name=template_name,
                    description=template.description,
                    cost_type=cost_type,
                    cost_amount=template.costs[0].cost if template.costs else 1,
                    action_category=template.action_category,
                ))

        # OBJECT actions - discover from templates + nearby visible objects
        for template in self.object_actions:
            valid_targets: List[AvailableTarget] = []
            idx = 0
            can_afford = template.check_costs()

            for obj_uuid, obj_pos in self.senses.objects.items():
                template.set_target_entity(obj_uuid)
                if template.pre_validate():
                    obj_block = BaseBlock.get(obj_uuid)
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
                result.object_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=TargetType.OBJECT,
                    valid_targets=valid_targets,
                    can_afford=can_afford,
                    display_name=template_name,
                    description=template.description,
                    cost_type=template.costs[0].cost_type if template.costs else "actions",
                    cost_amount=template.costs[0].cost if template.costs else 0,
                    action_category=template.action_category,
                ))

        # USE ACTIONS — from inventory items + nearby environment UsableItems
        use_sources: list = []  # List of (template, item_uuid, item_name, item_stack)

        # A) Inventory use actions
        for use_template in self.inventory.get_all_use_actions(self.uuid):
            item_uuid = use_template.source_item_uuid
            item = BaseBlock.get(item_uuid) if item_uuid else None
            item_name = item.name if item else "Item"
            item_stack = getattr(item, 'stack_count', None) if item else None
            use_sources.append((use_template, item_uuid, item_name, item_stack))

        # B) Environment use actions (≤5ft objects, no stacking)
        for obj_uuid, obj_pos in self.senses.objects.items():
            obj = BaseBlock.get(obj_uuid)
            if not isinstance(obj, UsableItem):
                continue
            if self.senses.get_feet_distance(obj_pos) > 5:
                continue
            for use_template in obj.get_use_actions(self.uuid):
                use_sources.append((use_template, obj_uuid, obj.name, None))

        # Route each use template by target_type
        for use_template, item_uuid, item_name, item_stack in use_sources:
            template_name = use_template.name or "Use"
            stack_suffix = f" x{item_stack}" if item_stack and item_stack > 1 else ""
            display_name = f"{template_name} ({item_name}{stack_suffix})"
            stack_count_field = item_stack if item_stack and item_stack > 1 else None
            can_afford = use_template.check_costs()
            cost_type = use_template.costs[0].cost_type if use_template.costs else "actions"
            cost_amount = use_template.costs[0].cost if use_template.costs else 0

            if use_template.target_type == TargetType.SELF:
                if not use_template.pre_validate():
                    continue
                result.self_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=TargetType.SELF,
                    valid_targets=[AvailableTarget(index=0)],
                    can_afford=can_afford,
                    display_name=display_name,
                    description=use_template.description,
                    cost_type=cost_type,
                    cost_amount=cost_amount,
                    is_item_use=True,
                    source_item_uuid=item_uuid,
                    action_category=use_template.action_category,
                    item_stack_count=stack_count_field,
                ))

            elif use_template.target_type in (TargetType.ENTITY, TargetType.MULTI_ENTITY):
                use_valid_targets: List[AvailableTarget] = []
                use_idx = 0
                # Build targets pool (reuse potential_targets computed earlier)
                use_target_pool = dict(potential_targets)
                if getattr(use_template, 'include_self', False):
                    use_target_pool[self.uuid] = self.position
                for target_uuid, target_pos in use_target_pool.items():
                    use_template.set_target_entity(target_uuid)
                    if use_template.pre_validate():
                        target_entity = Entity.get(target_uuid)
                        use_valid_targets.append(AvailableTarget(
                            index=use_idx,
                            target_uuid=target_uuid,
                            target_name=target_entity.name if target_entity else None,
                            distance=self.senses.get_feet_distance(target_pos)
                        ))
                        use_idx += 1
                if use_valid_targets:
                    result.entity_actions.append(AvailableActionInfo(
                        template_name=template_name,
                        target_type=use_template.target_type,
                        valid_targets=use_valid_targets,
                        can_afford=can_afford,
                        display_name=display_name,
                        description=use_template.description,
                        cost_type=cost_type,
                        cost_amount=cost_amount,
                        is_item_use=True,
                        source_item_uuid=item_uuid,
                        action_category=use_template.action_category,
                        item_stack_count=stack_count_field,
                    ))

            elif use_template.target_type == TargetType.POSITION_AOE:
                use_shape_template = use_template.aoe_shape
                if use_shape_template is None:
                    continue
                use_valid_pos_list = use_template.get_valid_positions()
                use_valid_positions: List[AvailableTarget] = []
                use_idx = 0
                for pos in use_valid_pos_list:
                    use_template.set_target_position(pos)
                    if not use_template.pre_validate():
                        continue
                    shape = use_shape_template.model_copy(update={'target': pos})
                    shape.compute_subjective(self.position, self.senses)
                    affected_uuids = list(shape.affected_entity_uuids)
                    if not getattr(use_template, 'include_self', False):
                        affected_uuids = [uid for uid in affected_uuids if uid != self.uuid]
                    vtf = getattr(use_template, 'valid_target_filter', 'enemies')
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
                    template_include_dead = getattr(use_template, 'include_dead', False)
                    if not template_include_dead and not include_dead:
                        affected_uuids = [
                            uid for uid in affected_uuids
                            if (ent := Entity.get(uid)) and ent.get_hp() > 0
                        ]
                    affected_names = []
                    for uid in affected_uuids:
                        ent = Entity.get(uid)
                        if ent:
                            affected_names.append(ent.name or "Unknown")
                    use_valid_positions.append(AvailableTarget(
                        index=use_idx,
                        position=pos,
                        distance=self.senses.get_feet_distance(pos),
                        affected_entity_uuids=affected_uuids,
                        affected_entity_names=affected_names,
                        affected_count=len(affected_uuids),
                        affected_positions=list(shape.affected_positions)
                    ))
                    use_idx += 1
                if use_valid_positions:
                    result.position_actions.append(AvailableActionInfo(
                        template_name=template_name,
                        target_type=TargetType.POSITION_AOE,
                        valid_targets=use_valid_positions,
                        can_afford=can_afford,
                        display_name=display_name,
                        description=use_template.description,
                        cost_type=cost_type,
                        cost_amount=cost_amount,
                        is_item_use=True,
                        source_item_uuid=item_uuid,
                        action_category=use_template.action_category,
                        item_stack_count=stack_count_field,
                    ))

            elif use_template.target_type == TargetType.POSITION_LOS:
                use_valid_pos_list = use_template.get_valid_positions()
                use_valid_positions = []
                use_idx = 0
                for pos in use_valid_pos_list:
                    use_template.set_target_position(pos)
                    if use_template.pre_validate():
                        use_valid_positions.append(AvailableTarget(
                            index=use_idx,
                            position=pos,
                            distance=self.senses.get_feet_distance(pos),
                        ))
                        use_idx += 1
                if use_valid_positions:
                    result.position_actions.append(AvailableActionInfo(
                        template_name=template_name,
                        target_type=TargetType.POSITION_LOS,
                        valid_targets=use_valid_positions,
                        can_afford=can_afford,
                        display_name=display_name,
                        description=use_template.description,
                        cost_type=cost_type,
                        cost_amount=cost_amount,
                        is_item_use=True,
                        source_item_uuid=item_uuid,
                        action_category=use_template.action_category,
                        item_stack_count=stack_count_field,
                    ))

            elif use_template.target_type in (TargetType.POSITION, TargetType.POSITION_PATH):
                # POSITION type spells (e.g., Spike Growth) — use visible positions within range
                use_valid_positions = []
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
                        use_valid_positions.append(AvailableTarget(
                            index=use_idx,
                            position=pos,
                            distance=dist,
                        ))
                        use_idx += 1
                if use_valid_positions:
                    result.position_actions.append(AvailableActionInfo(
                        template_name=template_name,
                        target_type=use_template.target_type,
                        valid_targets=use_valid_positions,
                        can_afford=can_afford,
                        display_name=display_name,
                        description=use_template.description,
                        cost_type=cost_type,
                        cost_amount=cost_amount,
                        is_item_use=True,
                        source_item_uuid=item_uuid,
                        action_category=use_template.action_category,
                        item_stack_count=stack_count_field,
                    ))

        return result
