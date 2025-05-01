""" This is the most "designed" and hardcoded part of the codebase it contains most of the dynamics possible in DND 5e and will be constantly expanded
it introduces and Event qeueue which is the source of ground truth information flow between entities, it allows each action to broadcast its intent and results
 and allow it to be intercepted by reactions and or trigger cascade effects at any point in the game"""


from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal as TypeLiteral, Union,List, Optional, Dict, Any, Self, Literal
from dnd.core.values import ModifiableValue
from uuid import UUID, uuid4
from dnd.core.dice import Dice, DiceRoll, AttackOutcome, RollType
from datetime import datetime
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier

AbilityName = TypeLiteral[
    'strength', 'dexterity', 'constitution', 
    'intelligence', 'wisdom', 'charisma'
]

SkillName = TypeLiteral[
    'acrobatics', 'animal_handling', 'arcana', 'athletics', 
    'deception', 'history', 'insight', 'intimidation', 
    'investigation', 'medicine', 'nature', 'perception', 
    'performance', 'persuasion', 'religion', 'sleight_of_hand', 
    'stealth', 'survival'
]

class WeaponSlot(str, Enum):
    MAIN_HAND = "Main Hand"
    OFF_HAND = "Off Hand"

class EventType(str, Enum):
    # Core events
    ATTACK = "attack"
    MOVEMENT = "movement"
    ABILITY_CHECK = "ability_check"
    SAVING_THROW = "saving_throw"
    INFLICT_DAMAGE = "inflicted_damage"
    TAKE_DAMAGE = "take_damage"
    HEAL = "heal"
    CAST_SPELL = "cast_spell"
    ATTACK_MISS = "attack_miss"
    ATTACK_HIT = "attack_hit"
    ATTACK_CRITICAL = "attack_critical"
    
    #Dice roll events
    DICE_ROLL = "dice_roll"
    DICE_ROLL_RESULT = "dice_roll_result"

    # Combat events
    ENEMY_SPOTTED = "enemy_spotted"
    ENEMY_KILLED = "enemy_killed"
    ENEMY_ENGAGED = "enemy_engaged"


class EventPhase(str, Enum):
    # Progression of an event
    DECLARATION = "declaration"  # Initial creation
    EXECUTION = "execution"      # Main action
    EFFECT = "effect"            # Applying effects
    COMPLETION = "completion"    # Finalizing
    CANCEL = "cancel"            # Canceling

ordered_event_phases = [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT, EventPhase.COMPLETION]


class Event(BaseObject):
    """Base class for all game events"""
    name: str = Field(default="Event",description="The name of the event")
    #human readable timestamp in typed format
    timestamp : datetime = Field(default_factory=datetime.now,description="The timestamp of the event")
    event_type: EventType = Field(description="The type of event")
    phase: EventPhase = Field(default=EventPhase.DECLARATION,description="The phase of the event")
    
    
    # Flag to indicate if event was modified by reactions
    modified: bool = Field(default=False,description="Flag to indicate if event was modified by reactions")
    
    # Flag to indicate if event should be canceled
    canceled: bool = Field(default=False,description="Flag to indicate if event should be canceled")
    parent_event: Optional["Event"] = Field(default=None,description="The parent event of the current event")
    status_message: Optional[str] = Field(default=None,description="A status message for the event")
    def set_target_entity(self, target_entity_uuid: UUID):
        """Set the target entity for the event"""
        self.target_entity_uuid = target_entity_uuid
       
    
    def phase_to(self, status_message: Optional[str] = None, new_phase: Optional[EventPhase] = None) -> 'Event':
        """Create a copy of this event with a new phase"""
        if self.phase == EventPhase.COMPLETION:
            return self
        modify_dict = {}
        if new_phase:
            modify_dict["phase"] = new_phase
        else:
            modify_dict["phase"] = ordered_event_phases[ordered_event_phases.index(self.phase) + 1]
        if status_message:
            modify_dict["status_message"] = status_message
        elif self.status_message:
            modify_dict["status_message"] = None
        modify_dict["timestamp"] = datetime.now()
        new_event = self.model_copy(update=modify_dict)
        return new_event
    
    def cancel(self, status_message: Optional[str] = None):
        """Mark this event as canceled"""
        modify_dict = {}
        if status_message:
            modify_dict["status_message"] = status_message
        modify_dict["canceled"] = True
        modify_dict["timestamp"] = datetime.now()
        new_event = self.model_copy(update=modify_dict)
        return new_event
    

class D20Event(Event):
    """A d20 event"""
    name: str = Field(default="D20",description="A d20 event")
    dc: Optional[Union[int, ModifiableValue]] = Field(default=None,description="The dc of the d20")
    bonus: Optional[Union[int, ModifiableValue]] = Field(default=0,description="The bonus to the d20")
    dice: Optional[Dice] = Field(default=None,description="The dice used to roll the d20")
    dice_roll: Optional[DiceRoll] = Field(default_factory=DiceRoll,description="The result of the dice roll")
    result: Optional[bool] = Field(default=None,description="Whether the d20 event was successful")

class SavingThrowEvent(D20Event):
    """An event that represents a saving throw"""
    name: str = Field(default="Saving Throw",description="A saving throw event")
    ability_name: AbilityName = Field(description="The ability that is being saved against")

class SkillCheckEvent(D20Event):
    """An event that represents a skill check"""
    name: str = Field(default="Skill Check",description="A skill check event")
    skill_name: SkillName = Field(description="The skill that is being checked")


class RangeType(str, Enum):
    REACH = "Reach"
    RANGE = "Range"

class Range(BaseModel):
    type: RangeType = Field(
        description="The type of range (Reach or Range)"
    )
    normal: int = Field(
        description="Normal range in feet"
    )
    long: Optional[int] = Field(
        default=None,
        description="Long range in feet, only applicable for ranged weapons"
    )

    def __str__(self):
        if self.type == RangeType.REACH:
            return f"{self.normal} ft."
        elif self.type == RangeType.RANGE:
            return f"{self.normal}/{self.long} ft." if self.long else f"{self.normal} ft."
        
class Damage(BaseObject):
    name: str = Field(default="Damage", description="Name of the damage")
    damage_dice: Literal[4,6,8,10,12,20] = Field(
        description="Number of sides on the damage dice (e.g., 6 for d6)"
    )
    dice_numbers: int = Field(
        description="Number of dice to roll for damage (e.g., 2 for 2d6)"
    )
    damage_bonus: Optional[ModifiableValue] = Field(
        default=None,
        description="Fixed bonus to damage rolls"
    )
    damage_type: DamageType = Field(
        description="Type of damage dealt by the weapon"
    )
    
    def get_dice(self, attack_outcome: AttackOutcome) -> Dice:
        return Dice(count=self.dice_numbers, value=self.damage_dice, bonus=self.damage_bonus, roll_type=RollType.DAMAGE, attack_outcome=attack_outcome)


class AttackEvent(Event):
    """An event that represents an attack"""
    name: str = Field(default="Attack",description="An attack event")
    weapon_slot: WeaponSlot = Field(description="The slot of the weapon used to attack")
    range: Optional[Range] = Field(default=None,description="The range of the attack")
    attack_bonus: Optional[ModifiableValue] = Field(default=None,description="The attack bonus of the attack")
    ac: Optional[ModifiableValue] = Field(default=None,description="The ac of the target")
    dice_roll: Optional[DiceRoll] = Field(default_factory=DiceRoll,description="The result of the dice roll")
    attack_outcome: Optional[AttackOutcome] = Field(default=None,description="The outcome of the attack")
    damages: Optional[List[Damage]] = Field(default=None,description="The damages of the attack")
    damage_rolls: Optional[List[DiceRoll]] = Field(default=None,description="The rolls of the damages")
