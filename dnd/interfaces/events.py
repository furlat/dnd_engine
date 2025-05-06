# dnd/interfaces/events.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID
from datetime import datetime

from dnd.core.events import (
    EventType, EventPhase, WeaponSlot, RangeType,
    AbilityName, SkillName
)

from dnd.interfaces.values import ModifiableValueSnapshot
from dnd.core.modifiers import DamageType, AdvantageStatus, CriticalStatus, AutoHitStatus
from dnd.core.dice import DiceRoll, AttackOutcome

class RangeSnapshot(BaseModel):
    """Interface model for Range"""
    type: RangeType
    normal: int
    long: Optional[int] = None
    
    @classmethod
    def from_engine(cls, range_obj):
        """Create a snapshot from an engine Range object"""
        return cls(
            type=range_obj.type,
            normal=range_obj.normal,
            long=range_obj.long
        )

class DamageSnapshot(BaseModel):
    """Interface model for Damage"""
    name: str
    damage_dice: int
    dice_numbers: int
    damage_bonus: Optional[ModifiableValueSnapshot] = None
    damage_type: DamageType
    
    @classmethod
    def from_engine(cls, damage):
        """Create a snapshot from an engine Damage object"""
        return cls(
            name=damage.name,
            damage_dice=damage.damage_dice,
            dice_numbers=damage.dice_numbers,
            damage_bonus=ModifiableValueSnapshot.from_engine(damage.damage_bonus) if damage.damage_bonus else None,
            damage_type=damage.damage_type
        )

class EventSnapshot(BaseModel):
    """Base interface model for all game events"""
    uuid: UUID
    name: str
    lineage_uuid: UUID
    timestamp: datetime
    event_type: EventType
    phase: EventPhase
    modified: bool
    canceled: bool
    parent_event: Optional[UUID] = None
    status_message: Optional[str] = None
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    target_entity_uuid: Optional[UUID] = None
    target_entity_name: Optional[str] = None
    
    # Child events
    child_events: List['EventSnapshot'] = Field(default_factory=list)
    
    @classmethod
    def from_engine(cls, event, include_children: bool = False):
        """Create a snapshot from an engine Event object"""
        snapshot = cls(
            uuid=event.uuid,
            name=event.name,
            lineage_uuid=event.lineage_uuid,
            timestamp=event.timestamp,
            event_type=event.event_type,
            phase=event.phase,
            modified=event.modified,
            canceled=event.canceled,
            parent_event=event.parent_event,
            status_message=event.status_message,
            source_entity_uuid=event.source_entity_uuid,
            source_entity_name=event.source_entity_name,
            target_entity_uuid=event.target_entity_uuid,
            target_entity_name=event.target_entity_name,
            child_events=[]
        )
        
        # Include child events if requested
        if include_children:
            snapshot.child_events = [
                cls.from_engine(child_event, include_children=True)
                for child_event in event.get_children_events()
            ]
        
        return snapshot

class D20EventSnapshot(EventSnapshot):
    """Interface model for D20Event"""
    dc: Optional[Union[int, ModifiableValueSnapshot]] = None
    bonus: Optional[Union[int, ModifiableValueSnapshot]] = Field(default=0)
    dice_roll: Optional[DiceRoll] = None
    result: Optional[bool] = None
    
    @classmethod
    def from_engine(cls, event, include_children: bool = False):
        """Create a snapshot from an engine D20Event object"""
        snapshot = super().from_engine(event, include_children)
        snapshot.dc = (
            ModifiableValueSnapshot.from_engine(event.dc)
            if hasattr(event.dc, 'normalized_score')
            else event.dc
        )
        snapshot.bonus = (
            ModifiableValueSnapshot.from_engine(event.bonus)
            if hasattr(event.bonus, 'normalized_score')
            else event.bonus
        )
        snapshot.dice_roll = event.dice_roll
        snapshot.result = event.result
        return snapshot

class SavingThrowEventSnapshot(D20EventSnapshot):
    """Interface model for SavingThrowEvent"""
    ability_name: AbilityName
    
    @classmethod
    def from_engine(cls, event, include_children: bool = False):
        """Create a snapshot from an engine SavingThrowEvent object"""
        snapshot = super().from_engine(event, include_children)
        snapshot.ability_name = event.ability_name
        return snapshot

class SkillCheckEventSnapshot(D20EventSnapshot):
    """Interface model for SkillCheckEvent"""
    skill_name: SkillName
    
    @classmethod
    def from_engine(cls, event, include_children: bool = False):
        """Create a snapshot from an engine SkillCheckEvent object"""
        snapshot = super().from_engine(event, include_children)
        snapshot.skill_name = event.skill_name
        return snapshot

class AttackEventSnapshot(EventSnapshot):
    """Interface model for AttackEvent"""
    weapon_slot: WeaponSlot
    range: Optional[RangeSnapshot] = None
    attack_bonus: Optional[ModifiableValueSnapshot] = None
    ac: Optional[ModifiableValueSnapshot] = None
    dice_roll: Optional[DiceRoll] = None
    attack_outcome: Optional[AttackOutcome] = None
    damages: Optional[List[DamageSnapshot]] = None
    damage_rolls: Optional[List[DiceRoll]] = None
    
    @classmethod
    def from_engine(cls, event, include_children: bool = False):
        """Create a snapshot from an engine AttackEvent object"""
        snapshot = super().from_engine(event, include_children)
        snapshot.weapon_slot = event.weapon_slot
        snapshot.range = RangeSnapshot.from_engine(event.range) if event.range else None
        snapshot.attack_bonus = ModifiableValueSnapshot.from_engine(event.attack_bonus) if event.attack_bonus else None
        snapshot.ac = ModifiableValueSnapshot.from_engine(event.ac) if event.ac else None
        snapshot.dice_roll = event.dice_roll
        snapshot.attack_outcome = event.attack_outcome
        snapshot.damages = [DamageSnapshot.from_engine(damage) for damage in event.damages] if event.damages else None
        snapshot.damage_rolls = event.damage_rolls
        return snapshot 