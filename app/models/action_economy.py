# dnd/interfaces/action_economy.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from app.models.values import ModifiableValueSnapshot
from app.models.modifiers import NumericalModifierSnapshot
from dnd.core.base_actions import CostType

class ActionEconomySnapshot(BaseModel):
    """Interface model for ActionEconomy"""
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    
    # Core action values
    actions: ModifiableValueSnapshot
    bonus_actions: ModifiableValueSnapshot
    reactions: ModifiableValueSnapshot
    movement: ModifiableValueSnapshot
    
    # Base values
    base_actions: int
    base_bonus_actions: int
    base_reactions: int
    base_movement: int
    
    # Cost modifiers
    action_costs: List[NumericalModifierSnapshot]
    bonus_action_costs: List[NumericalModifierSnapshot]
    reaction_costs: List[NumericalModifierSnapshot]
    movement_costs: List[NumericalModifierSnapshot]
    
    # Computed values for quick reference
    available_actions: int
    available_bonus_actions: int
    available_reactions: int
    available_movement: int
    
    @classmethod
    def from_engine(cls, action_economy, entity=None):
        """
        Create a snapshot from an engine ActionEconomy object
        
        Args:
            action_economy: The engine ActionEconomy object
            entity: Optional Entity object for additional context
        """
        return cls(
            uuid=action_economy.uuid,
            name=action_economy.name,
            source_entity_uuid=action_economy.source_entity_uuid,
            source_entity_name=action_economy.source_entity_name,
            
            # Core values as snapshots
            actions=ModifiableValueSnapshot.from_engine(action_economy.actions),
            bonus_actions=ModifiableValueSnapshot.from_engine(action_economy.bonus_actions),
            reactions=ModifiableValueSnapshot.from_engine(action_economy.reactions),
            movement=ModifiableValueSnapshot.from_engine(action_economy.movement),
            
            # Base values
            base_actions=action_economy.get_base_value("actions"),
            base_bonus_actions=action_economy.get_base_value("bonus_actions"),
            base_reactions=action_economy.get_base_value("reactions"),
            base_movement=action_economy.get_base_value("movement"),
            
            # Cost modifiers
            action_costs=[NumericalModifierSnapshot.from_engine(mod) for mod in action_economy.get_cost_modifiers("actions")],
            bonus_action_costs=[NumericalModifierSnapshot.from_engine(mod) for mod in action_economy.get_cost_modifiers("bonus_actions")],
            reaction_costs=[NumericalModifierSnapshot.from_engine(mod) for mod in action_economy.get_cost_modifiers("reactions")],
            movement_costs=[NumericalModifierSnapshot.from_engine(mod) for mod in action_economy.get_cost_modifiers("movement")],
            
            # Computed normalized scores for quick reference
            available_actions=action_economy.actions.normalized_score,
            available_bonus_actions=action_economy.bonus_actions.normalized_score,
            available_reactions=action_economy.reactions.normalized_score,
            available_movement=action_economy.movement.normalized_score
        ) 