from typing import List, Dict, Optional, Set, Tuple, Any, Callable, Union
from pydantic import BaseModel, Field, computed_field
import uuid
from dnd.core import Ability, SkillSet, AbilityScores, Speed, SavingThrows, DamageType, Dice, Skills, ActionEconomy, Sensory, Health
from dnd.contextual import ModifiableValue, BaseValue
from dnd.conditions import Condition, ConditionLog
from dnd.actions import Action, Attack, MovementAction
from dnd.equipment import Armor, Shield, Weapon, ArmorClass
from dnd.dnd_enums import Size, MonsterType, Alignment, Language
from dnd.logger import Logger, SkillCheckLog, SavingThrowLog

ContextAwareImmunity = Callable[['StatsBlock', Optional['StatsBlock']], bool]

class MetaData(BaseModel):
    name: str = Field(default="Unnamed")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    size: Size = Field(default=Size.MEDIUM)
    type: MonsterType = Field(default=MonsterType.HUMANOID)
    alignment: Alignment = Field(default=Alignment.TRUE_NEUTRAL)
    languages: List[Language] = Field(default_factory=list)

class StatsBlock(BaseModel):
    meta: MetaData = Field(default_factory=MetaData)
    proficiency_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=1))
    speed: Speed = Field(default_factory=lambda: Speed(walk=ModifiableValue(base_value=BaseValue(base_value=30))))
    ability_scores: AbilityScores = Field(default_factory=AbilityScores)
    
    skillset: SkillSet = Field(default_factory=SkillSet)
    
    saving_throws: SavingThrows = Field(default_factory=SavingThrows)
    challenge: float = Field(default=0.0)
    experience_points: int = Field(default=0)
    actions: List[Action] = Field(default_factory=list)
    reactions: List[Action] = Field(default_factory=list)
    legendary_actions: List[Action] = Field(default_factory=list)
    armor_class: ArmorClass = Field(default_factory=lambda: ArmorClass(base_ac=ModifiableValue(base_value=BaseValue(base_value=10))))
    weapons: List[Weapon] = Field(default_factory=list)
    action_economy: ActionEconomy = Field(default_factory=lambda: ActionEconomy())
    active_conditions: Dict[str, Condition] = Field(default_factory=dict)
    sensory: Sensory = Field(default_factory=Sensory)
    health: Health = Field(default_factory=lambda: Health(hit_dice=Dice(dice_count=1, dice_value=8, modifier=0)))
    condition_immunities: Set[str] = Field(default_factory=set)
    contextual_condition_immunities: Dict[str, List[Tuple[str, ContextAwareImmunity]]] = Field(default_factory=dict)
    hit_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))

    def __init__(self, **data):
        super().__init__(**data)
        self._recompute_fields()

    @computed_field
    def hp(self) -> int:
        return self.health.total_hit_points

    @computed_field
    def armor_class_value(self) -> int:
        return self.armor_class.get_value(self)


    @computed_field
    def initiative(self) -> int:
        return self.ability_scores.dexterity.get_modifier(self)

    def apply_condition(self, condition: Condition, source: Optional['StatsBlock'] = None) -> Optional[ConditionLog]:
        log = condition.apply(self, source)
        if log.applied:
            self.active_conditions[condition.name] = condition
            self._recompute_fields()
        return log

    def remove_condition(self, condition_name: str) -> Optional[ConditionLog]:
        condition = self.active_conditions.get(condition_name)
        if condition:
            log = condition.remove(self)
            return log
        return None

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

        # Update health's hit point bonus based on Constitution modifier
        con_modifier = self.ability_scores.constitution.get_modifier(self)
        self.health.hit_point_bonus.base_value = con_modifier * self.health.hit_dice.dice_count

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

    def add_condition_immunity(self, condition_name: str):
        self.condition_immunities.add(condition_name)

    def remove_condition_immunity(self, condition_name: str):
        self.condition_immunities.discard(condition_name)

    def add_contextual_condition_immunity(self, condition_name: str, immunity_name: str, immunity_check: ContextAwareImmunity):
        if condition_name not in self.contextual_condition_immunities:
            self.contextual_condition_immunities[condition_name] = []
        self.contextual_condition_immunities[condition_name].append((immunity_name, immunity_check))

    def remove_contextual_condition_immunity(self, condition_name: str, immunity_name: str):
        if condition_name in self.contextual_condition_immunities:
            self.contextual_condition_immunities[condition_name] = [
                (name, check) for name, check in self.contextual_condition_immunities[condition_name]
                if name != immunity_name
            ]
            if not self.contextual_condition_immunities[condition_name]:
                del self.contextual_condition_immunities[condition_name]

    def perform_ability_check(self, ability: Ability, dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SkillCheckLog]:
        return self.ability_scores.perform_ability_check(ability, self, dc, target, context, return_log)

    def perform_skill_check(self, skill: Skills, dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SkillCheckLog]:
        return self.skills.perform_skill_check(skill, self, dc, target, context, return_log)

    def perform_saving_throw(self, ability: Ability, dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SavingThrowLog]:
        return self.saving_throws.perform_save(ability, self, dc, target, context, return_log)

ModifiableValue.model_rebuild()
Attack.model_rebuild()
MovementAction.model_rebuild()