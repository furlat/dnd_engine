from typing import List, Dict, Optional, Set, Tuple, Any, Union
from pydantic import BaseModel, Field, computed_field
import uuid
from dnd.core import BlockComponent,Condition, SavingThrows, Ability, ConditionManager, SkillSet, AbilityScores, Speed, SavingThrow , ActionEconomy, Sensory, Health, ArmorClass,AttacksManager, Weapon
from dnd.contextual import ModifiableValue, BaseValue
from dnd.dnd_enums import Size, MonsterType, Alignment, Language, AttackHand, Skills
from dnd.logger import Logger, SkillRollOut, SavingThrowRollOut, AttackRollOut, DamageRollOut
from dnd.spatial import RegistryHolder

class MetaData(BaseModel):
    name: str = Field(default="Unnamed")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  
    size: Size = Field(default=Size.MEDIUM)
    type: MonsterType = Field(default=MonsterType.HUMANOID)
    alignment: Alignment = Field(default=Alignment.TRUE_NEUTRAL)
    languages: List[Language] = Field(default_factory=list)
    challenge: float = Field(default=0.0)
    experience_points: int = Field(default=0)

class StatsBlock(BaseModel, RegistryHolder):
    meta: MetaData = Field(default_factory=MetaData)
    proficiency_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="proficiency_bonus",
        base_value=BaseValue(name="base_proficiency_bonus", base_value=2)
    ))
    speed: Speed = Field(default_factory=Speed)
    ability_scores: AbilityScores = Field(default_factory=AbilityScores)
    skillset: SkillSet = Field(default_factory=SkillSet)
    saving_throws: SavingThrows = Field(default_factory=SavingThrows)
    armor_class: ArmorClass = Field(default_factory=ArmorClass)
    action_economy: ActionEconomy = Field(default_factory=ActionEconomy)
    sensory: Sensory = Field(default_factory=Sensory)
    health: Health = Field(default_factory=Health)
    spellcasting_ability: Ability = Field(default=Ability.CHA)
    condition_manager: ConditionManager = Field(default_factory=ConditionManager)
    attacks_manager: AttacksManager = Field(default_factory=AttacksManager)

    def __init__(self, **data):
        super().__init__(**data)
        self.register(self,self.id)
        self._initialize_components()
        self._recompute_fields()

    def _initialize_components(self):
        components : List[BlockComponent] = [
            self.speed, self.ability_scores, self.skillset, self.saving_throws,
            self.armor_class, self.action_economy, self.sensory, self.health,
            self.condition_manager, self.attacks_manager
        ]
        for component in components:
            component.set_owner(self.meta.id)
            self.register(component,component.id)


    @computed_field
    @property
    def id(self) -> str:
        return self.meta.id

    @computed_field
    @property
    def name(self) -> str:
        return self.meta.name
    @computed_field
    @property
    def hp(self) -> int:
        return self.health.current_hit_points

    @computed_field
    @property
    def ac(self) -> int:
        return self.armor_class.total_ac

    @computed_field
    @property
    def initiative(self) -> int:
        return self.ability_scores.get_ability_modifier(Ability.DEX)
    
    @computed_field
    @property
    def position(self) -> Optional[Tuple[int, int]]:
        return self.sensory.origin

    def _recompute_fields(self):
        self.armor_class.update_ac()
        self.action_economy._sync_movement_with_speed()
        self.action_economy.reset()

    def update_sensory(self, battlemap_id: str, origin: Tuple[int, int]):
        self.sensory.update_battlemap(battlemap_id)
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

    def perform_ability_check(self, ability: Ability, dc: int, target_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> int:
        ability_score = self.ability_scores.get_ability(ability)
        return ability_score.apply(target_id, context).total_bonus

    def perform_skill_check(self, skill: Skills, dc: int, target_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> SkillRollOut:
        return self.skillset.perform_skill_check(skill, dc, target_id, context)

    def perform_saving_throw(self, ability: Ability, dc: int, target_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> SavingThrowRollOut:
        return self.saving_throws.perform_save(ability, dc, target_id, context)

    def perform_attack(self, hand: AttackHand, target_id: str, context: Optional[Dict[str, Any]] = None) -> AttackRollOut:
        return self.attacks_manager.roll_to_hit(hand, target_id, context)

    def roll_damage(self, attack_roll: AttackRollOut, context: Optional[Dict[str, Any]] = None) -> DamageRollOut:
        
        return self.attacks_manager.roll_damage(attack_roll, context)

    def perform_melee_attack(self, target_id: str, context: Optional[Dict[str, Any]] = None) -> AttackRollOut:
        hand = AttackHand.MELEE_RIGHT
        return self.perform_attack(hand, target_id, context)
    
    def perform_ranged_attack(self, target_id: str, context: Optional[Dict[str, Any]] = None) -> AttackRollOut:
        hand = AttackHand.RANGED_RIGHT
        return self.perform_attack(hand, target_id, context)
    
    def melee_attack(self, target_id: str, context: Optional[Dict[str, Any]] = None) -> Union[DamageRollOut, AttackRollOut]:
        attack_roll = self.perform_melee_attack(target_id, context)
        if attack_roll.success:
            return self.roll_damage(attack_roll, context)
        return attack_roll
        
    
    def ranged_attack(self, target_id: str, context: Optional[Dict[str, Any]] = None) -> Union[DamageRollOut, AttackRollOut]:
        attack_roll = self.perform_ranged_attack(target_id, context)
        if attack_roll.success:
            return self.roll_damage(attack_roll, context)
        return attack_roll
    
    def take_damage(self, damage_rolls: Union[DamageRollOut, List[DamageRollOut]], attacker_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        return self.health.take_damage(damage_rolls, attacker_id, context)

    def heal(self, amount: int, healer_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        return self.health.heal(amount, healer_id, context)

    def equip_weapon(self, weapon: Weapon, hand: AttackHand):
        if hand in [AttackHand.MELEE_RIGHT, AttackHand.MELEE_LEFT]:
            if hand == AttackHand.MELEE_RIGHT:
                self.attacks_manager.equip_right_hand_melee_weapon(weapon)
            else:
                self.attacks_manager.equip_left_hand_melee_weapon(weapon)
        elif hand in [AttackHand.RANGED_RIGHT, AttackHand.RANGED_LEFT]:
            if hand == AttackHand.RANGED_RIGHT:
                self.attacks_manager.equip_right_hand_ranged_weapon(weapon)
            else:
                self.attacks_manager.equip_left_hand_ranged_weapon(weapon)

    def add_condition(self, condition: Condition, context: Optional[Dict[str, Any]] = None):
        return self.condition_manager.add_condition(condition, context)

    def remove_condition(self, condition_name: str, external_source: str = "manager"):
        return self.condition_manager.remove(condition_name, external_source)

