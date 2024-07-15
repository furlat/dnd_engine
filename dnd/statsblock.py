from typing import List, Dict, Optional, Set, Tuple, Any
from pydantic import BaseModel, Field, computed_field
import uuid
from dnd.core import Ability, SkillSet, AbilityScores, Speed, SavingThrows, DamageType, Dice, Skills, ActionEconomy, Sensory
from dnd.contextual import ModifiableValue
from dnd.conditions import Condition
from dnd.actions import Action, Attack,MovementAction
from dnd.equipment import Armor, Shield, Weapon, ArmorClass
from dnd.dnd_enums import Size, MonsterType, Alignment, Language

class StatsBlock(BaseModel):
    name: str = Field(default="Unnamed")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    size: Size = Field(default=Size.MEDIUM)
    type: MonsterType = Field(default=MonsterType.HUMANOID)
    alignment: Alignment = Field(default=Alignment.TRUE_NEUTRAL)
    speed: Speed = Field(default_factory=lambda: Speed(walk=ModifiableValue(base_value=30)))
    ability_scores: AbilityScores = Field(default_factory=AbilityScores)
    saving_throws: SavingThrows = Field(default_factory=SavingThrows)
    skills: SkillSet = Field(default_factory=SkillSet)
    vulnerabilities: List[DamageType] = Field(default_factory=list)
    resistances: List[DamageType] = Field(default_factory=list)
    immunities: List[DamageType] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    challenge: float = Field(default=0.0)
    experience_points: int = Field(default=0)
    actions: List[Action] = Field(default_factory=list)
    reactions: List[Action] = Field(default_factory=list)
    legendary_actions: List[Action] = Field(default_factory=list)
    armor_class: ArmorClass = Field(default_factory=lambda: ArmorClass(base_ac=ModifiableValue(base_value=10)))
    weapons: List[Weapon] = Field(default_factory=list)
    hit_dice: Dice = Field(default_factory=lambda: Dice(dice_count=1, dice_value=8, modifier=0))
    hit_point_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    current_hit_points: int = Field(default=0)
    action_economy: ActionEconomy = Field(default_factory=lambda: ActionEconomy(speed=30))
    active_conditions: Dict[str, Condition] = Field(default_factory=dict)
    sensory: Sensory = Field(default_factory=Sensory)

    def __init__(self, **data):
        super().__init__(**data)
        if self.current_hit_points == 0:
            self.current_hit_points = self.max_hit_points
        self._recompute_fields()

    @computed_field
    def max_hit_points(self) -> int:
        con_modifier = self.ability_scores.constitution.get_modifier(self)
        average_hp = (self.hit_dice.expected_value()) + \
                     (con_modifier * self.hit_dice.dice_count) + \
                     self.hit_point_bonus.get_value(self)
        return max(1, int(average_hp))

    @computed_field
    def armor_class_value(self) -> int:
        return self.armor_class.get_value(self)

    @computed_field
    def proficiency_bonus(self) -> int:
        return self.ability_scores.proficiency_bonus.get_value(self)

    @computed_field
    def initiative(self) -> int:
        return self.ability_scores.dexterity.get_modifier(self)

    def apply_condition(self, condition: Condition):
        self.active_conditions[condition.name] = condition
        self._recompute_fields()

    def remove_condition(self, condition_name: str):
        if condition_name in self.active_conditions:
            del self.active_conditions[condition_name]
        self._recompute_fields()

    def add_action(self, action: Action):
        if action.name not in [a.name for a in self.actions]:
            action.stats_block = self
            self.actions.append(action)

    def add_reaction(self, reaction: Action):
        reaction.stats_block = self
        self.reactions.append(reaction)

    def add_legendary_action(self, legendary_action: Action):
        legendary_action.stats_block = self
        self.legendary_actions.append(legendary_action)

    def _recompute_fields(self):
        self.armor_class.compute_base_ac(self.ability_scores)
        self.action_economy.movement.base_value = self.speed.walk.get_value(self)
        self.action_economy.reset()
        for action in self.actions:
            if isinstance(action, Attack):
                action.update_hit_bonus()

    def take_damage(self, damage: int):
        self.current_hit_points = max(0, self.current_hit_points - damage)

    def heal(self, healing: int):
        self.current_hit_points = min(self.max_hit_points, self.current_hit_points + healing)

    def update_sensory(self, battlemap_id: str, origin: Tuple[int, int]):
        self.sensory.battlemap_id = battlemap_id
        self.sensory.update_origin(origin)

    def update_fov(self, visible_tiles: Set[Tuple[int, int]]):
        self.sensory.update_fov(visible_tiles)

    def update_distance_matrix(self, distances: Dict[Tuple[int, int], int]):
        self.sensory.update_distance_matrix(distances)

    def update_paths(self, paths: Dict[Tuple[int, int], List[Tuple[int, int]]]):
        self.sensory.update_paths(paths)

    def is_visible(self, position: Tuple[int, int]) -> bool:
        return self.sensory.is_visible(position)

    def get_distance(self, position: Tuple[int, int]) -> Optional[int]:
        return self.sensory.get_distance(position)

    def get_path_to(self, destination: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        return self.sensory.get_path_to(destination)
    
ModifiableValue.model_rebuild()
# SelfCondition.model_rebuild()
# Dodge.model_rebuild()
# # # Disengage.model_rebuild()
# Dash.model_rebuild()
# Hide.model_rebuild()
# Help.model_rebuild()
Attack.model_rebuild()
MovementAction.model_rebuild()