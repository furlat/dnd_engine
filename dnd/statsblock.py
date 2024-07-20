from typing import List, Dict, Optional, Set, Tuple, Any, Callable, Union
from pydantic import BaseModel, Field, computed_field
import uuid
from dnd.core import Condition,Ability,ConditionManager, SkillSet, AbilityScores, Speed, SavingThrows, DamageType, Skills, ActionEconomy, Sensory, Health, ArmorClass
from dnd.contextual import ModifiableValue, BaseValue
from dnd.actions import Action, Attack, MovementAction, Weapon
from dnd.dnd_enums import Size, MonsterType, Alignment, Language,Abilities
from dnd.logger import Logger
from dnd.spatial import RegistryHolder

class MetaData(BaseModel):
    name: str = Field(default="Unnamed")
    
    size: Size = Field(default=Size.MEDIUM)
    type: MonsterType = Field(default=MonsterType.HUMANOID)
    alignment: Alignment = Field(default=Alignment.TRUE_NEUTRAL)
    languages: List[Language] = Field(default_factory=list)

class StatsBlock(BaseModel, RegistryHolder):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
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
    
    action_economy: ActionEconomy = Field(default_factory=lambda: ActionEconomy())
    sensory: Sensory = Field(default_factory=Sensory)
    health: Health = Field(default_factory=lambda: Health(hit_dice=Dice(dice_count=1, dice_value=8, modifier=0)))
    spellcasting_ability: Ability = Field(default=Ability.CHA)
    
    
       
    condition_manager: ConditionManager = Field(default_factory=ConditionManager)

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


    def perform_ability_check(self, ability: Ability, dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SkillCheckLog]:
        return self.ability_scores.perform_ability_check(ability, self, dc, target, context, return_log)

    def perform_skill_check(self, skill: Skills, dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SkillCheckLog]:
        return self.skills.perform_skill_check(skill, self, dc, target, context, return_log)

    def perform_saving_throw(self, ability: Ability, dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SavingThrowLog]:
        return self.saving_throws.perform_save(ability, self, dc, target, context, return_log)

ModifiableValue.model_rebuild()
Attack.model_rebuild()
MovementAction.model_rebuild()