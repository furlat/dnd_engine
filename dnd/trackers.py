from pydantic import BaseModel, Field, computed_field
from typing import List, Tuple, Dict, Callable, Optional
from dnd.dnd_enums import AdvantageStatus, CriticalStatus, AutoHitStatus
from dnd.utils import update_or_concat_to_dict, update_or_sum_to_dict

class AdvantageTracker(BaseModel):
    active_sources: Dict[str,list[AdvantageStatus]] = Field(default_factory=dict)

    @computed_field
    def counter(self) -> int:
        counter = 0
        for status_list in self.active_sources.values():
            for status in status_list:
                if status == AdvantageStatus.ADVANTAGE:
                    counter += 1
                elif status == AdvantageStatus.DISADVANTAGE:
                    counter -= 1
        return counter

    @computed_field
    def status(self) -> AdvantageStatus:
        if self.counter > 0:
            return AdvantageStatus.ADVANTAGE
        elif self.counter < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE
        
    def combine_with(self, other: 'AdvantageTracker') -> 'AdvantageTracker':
        # to combine the active sources we get the list of keys and retrieve and combine the values from both with empty return if they do not hsare source
        keys = set(self.active_sources.keys()).union(set(other.active_sources.keys()))
        active_sources = {key: self.active_sources.get(key, []) + other.active_sources.get(key, []) for key in keys}
        return AdvantageTracker(active_sources=active_sources)

    def add(self,advantage_status: AdvantageStatus, source: str = "nosource"):
        
        self.active_sources = update_or_concat_to_dict(self.active_sources, (source, advantage_status))
 
        return self.status
    
    def add_multiple(self, advantage_statuses: List[Tuple[AdvantageStatus,str]]):
        for adv_status, source in advantage_statuses:
            self.add(adv_status, source)

class CriticalTracker(BaseModel):
    critical_statuses :Dict[str,List[CriticalStatus]] = Field(default_factory=dict)

    def add(self, critical_status: CriticalStatus, source: str = "nosource"):
        self.critical_statuses = update_or_concat_to_dict(self.critical_statuses, (source, critical_status))
    
    def add_multiple(self, critical_statuses: List[Tuple[CriticalStatus,str]]):
        for crit_status, source in critical_statuses:
            self.add(crit_status, source)

    def combine_with(self, other: 'CriticalTracker'):
        keys = set(self.critical_statuses.keys()).union(set(other.critical_statuses.keys()))
        critical_statuses = {key: self.critical_statuses.get(key, []) + other.critical_statuses.get(key, []) for key in keys}
        return CriticalTracker(critical_statuses=critical_statuses)
    
    @computed_field
    def status(self) -> CriticalStatus:
        #the rule is if any of the statuse is NOCRIT then the final status is NOCRIT
        # else if any of the status is AUTOCRIT then the final status is AUTOCRIT
        # else the final status is NONE
        if CriticalStatus.NOCRIT in self.critical_statuses.values():
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in self.critical_statuses.values():
            return CriticalStatus.AUTOCRIT
        elif CriticalStatus.NONE in self.critical_statuses.values() or len(self.critical_statuses.keys()) == 0:
            return CriticalStatus.NONE
        else:
            return CriticalStatus.NONE
        
class AutoHitTracker(BaseModel):
    auto_hit_statuses :Dict[str,List[AutoHitStatus]] = Field(default_factory=dict)

    def add(self, auto_hit_status: AutoHitStatus, source: str = "nosource"):
        if source in self.auto_hit_statuses:
            self.auto_hit_statuses[source].append(auto_hit_status)
        else:
            self.auto_hit_statuses[source] = [auto_hit_status]
        return self.status
    
    def add_multiple(self, auto_hit_statuses: List[Tuple[AutoHitStatus,str]]):
        for auto_hit_status, source in auto_hit_statuses:
            self.add(auto_hit_status, source)

    def combine_with(self, other: 'AutoHitTracker'):
        keys = set(self.auto_hit_statuses.keys()).union(set(other.auto_hit_statuses.keys()))
        auto_hit_statuses = {key: self.auto_hit_statuses.get(key, []) + other.auto_hit_statuses.get(key, []) for key in keys}
        return AutoHitTracker(auto_hit_statuses=auto_hit_statuses)
    
    @computed_field
    def status(self) -> AutoHitStatus:
        #the rule is if any of the statuse is AUTOMISS then the final status is AUTOMISS
        # else if any of the status is AUTOHIT then the final status is AUTOHIT
        # else the final status is NONE
        if AutoHitStatus.AUTOMISS in self.auto_hit_statuses.values():
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in self.auto_hit_statuses.values():
            return AutoHitStatus.AUTOHIT
        elif AutoHitStatus.NONE in self.auto_hit_statuses.values() or len(self.auto_hit_statuses.keys()) == 0:
            return AutoHitStatus.NONE
        else:
            return AutoHitStatus.NONE

BonusConverter = Callable[[int], int]


class BonusTracker(BaseModel):
    bonuses: Dict[str,int] = Field(default_factory=dict)

    def add(self, value: int, source: str = "nosource"):
        self.bonuses = update_or_sum_to_dict(self.bonuses, (source, value))
        return self.total_bonus
    
    def add_multiple(self, bonuses: List[Tuple[int,str]]):
        for bonus, source in bonuses:
            self.add(bonus, source)
            
    def combine_with(self, other: 'BonusTracker', bonus_converter: Optional[BonusConverter] = None) -> 'BonusTracker':
        """ combine with another bonus tracker by summing up the bonuses it can apply a bonus_converter to the incoming bonuses"""
        if bonus_converter:
            converted_bonuses = {key: bonus_converter(value) for key, value in other.bonuses.items()}
        else:
            converted_bonuses = other.bonuses
        keys = set(self.bonuses.keys()).union(set(converted_bonuses.keys()))
        bonuses = {key: self.bonuses.get(key, 0) + converted_bonuses.get(key, 0) for key in keys}
        return BonusTracker(bonuses=bonuses)

    @computed_field
    def total_bonus(self) -> int:
        return sum(self.bonuses.values()) if len(self.bonuses.keys())>0 else None