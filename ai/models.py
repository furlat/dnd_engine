"""Agent-facing tactical data models and scoring estimates.

The AI layer reads these Pydantic models instead of live engine objects. A
`GameInterface` implementation translates engine state into the models here,
and decision code chooses legal action rows from that snapshot.
"""

from typing import Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field


class TacticalEntity(BaseModel):
    """Visible actor snapshot used by tactical decisions."""

    uuid: str = Field(description="Stable entity UUID serialized as text.")
    name: str = Field(description="Display name for the visible entity.")
    position: Tuple[int, int] = Field(description="Current grid position.")
    hp: int = Field(description="Current hit points.")
    max_hp: int = Field(description="Maximum hit points.")
    ac: int = Field(description="Current Armor Class.")
    conditions: List[str] = Field(
        default_factory=list,
        description="Active condition names visible to the agent.",
    )
    distance_feet: Optional[int] = Field(
        default=None,
        description="Distance from the controlled actor in feet, when known.",
    )
    is_dead: bool = Field(
        default=False,
        description="Whether the entity currently has no hit points.",
    )
    faction: Optional[str] = Field(
        default=None,
        description="Faction identifier used for ally and enemy grouping.",
    )

    @property
    def hp_fraction(self) -> float:
        """Return current hit points as a fraction of maximum hit points."""
        return self.hp / self.max_hp if self.max_hp > 0 else 0.0


class DiceSpec(BaseModel):
    """Damage dice descriptor used by tactical scoring estimates."""

    count: int = Field(description="Number of dice rolled.")
    sides: int = Field(description="Number of sides on each die.")
    bonus: int = Field(
        default=0,
        description="Static damage bonus added after rolling the dice.",
    )
    damage_type: str = Field(
        default="",
        description="Damage type label, such as slashing, fire, or force.",
    )

    @property
    def average(self) -> float:
        """Return the average damage represented by this dice descriptor."""
        return self.count * (self.sides + 1) / 2 + self.bonus


class AttackData(BaseModel):
    """Attack-roll math exposed to tactical scoring."""

    attack_bonus: int = Field(
        default=0,
        description="Attack bonus added to the d20 roll.",
    )
    advantage: str = Field(
        default="none",
        description="Advantage state: advantage, disadvantage, or none.",
    )
    crit_threshold: int = Field(
        default=20,
        description="Natural d20 result that starts the critical range.",
    )
    crit_extra_dice: int = Field(
        default=0,
        description="Additional weapon dice added to critical hits.",
    )
    damage_dice: List[DiceSpec] = Field(
        default_factory=list,
        description="Damage dice applied when the attack hits.",
    )
    auto_hit: str = Field(
        default="none",
        description="Automatic hit state: autohit, automiss, or none.",
    )


class SpellData(BaseModel):
    """Spell math exposed to tactical scoring."""

    spell_level: int = Field(
        default=0,
        description="Base spell level.",
    )
    cast_at_level: int = Field(
        default=0,
        description="Slot level used for this cast.",
    )
    spell_dc: int = Field(
        default=0,
        description="Saving throw DC used by save-based spells.",
    )
    save_ability: str = Field(
        default="",
        description="Ability name used by the target saving throw.",
    )
    half_on_save: bool = Field(
        default=True,
        description="Whether a successful save still takes half damage.",
    )
    is_attack_roll: bool = Field(
        default=False,
        description="Whether the spell resolves with a spell attack roll.",
    )
    spell_attack_bonus: int = Field(
        default=0,
        description="Attack bonus used by spell attack rolls.",
    )
    damage_dice: List[DiceSpec] = Field(
        default_factory=list,
        description="Damage dice applied by the spell.",
    )
    concentration: bool = Field(
        default=False,
        description="Whether the spell requires concentration.",
    )
    school: str = Field(
        default="",
        description="Spell school label.",
    )


class TargetOption(BaseModel):
    """One selectable target row for an action option."""

    index: int = Field(description="Stable target index accepted by execution.")
    target_uuid: Optional[str] = Field(
        default=None,
        description="Target entity UUID for entity-targeting actions.",
    )
    target_name: Optional[str] = Field(
        default=None,
        description="Target entity display name.",
    )
    position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Target grid position for position-targeting actions.",
    )
    distance: Optional[int] = Field(
        default=None,
        description="Distance from the actor to this target in feet.",
    )
    path_cost: Optional[int] = Field(
        default=None,
        description="Movement cost to reach this target position.",
    )
    is_path_hazardous: bool = Field(
        default=False,
        description="Whether the path crosses hazardous terrain.",
    )
    safe_path_cost: Optional[int] = Field(
        default=None,
        description="Alternative safe path cost when one is available.",
    )
    aoe_affected_count: Optional[int] = Field(
        default=None,
        description="Number of entities affected by an area target.",
    )
    aoe_affected_uuids: Optional[List[str]] = Field(
        default=None,
        description="Entity UUIDs affected by an area target.",
    )
    aoe_affected_names: Optional[List[str]] = Field(
        default=None,
        description="Entity names affected by an area target.",
    )
    target_ac: Optional[int] = Field(
        default=None,
        description="Target Armor Class when known.",
    )
    target_save_bonus: Optional[int] = Field(
        default=None,
        description="Target saving throw bonus when known.",
    )


class ActionOption(BaseModel):
    """One legal or visible action row from engine discovery."""

    template_name: str = Field(
        description="Registered action template name used for execution.",
    )
    display_name: str = Field(description="Player-facing action label.")
    category: str = Field(
        description="Action category, such as attack, spell, ability, or movement.",
    )
    target_type: str = Field(
        description="Engine target type required by the action.",
    )
    cost_type: str = Field(
        description="Action economy or resource type spent by the action.",
    )
    cost_amount: int = Field(
        default=1,
        description="Amount of the cost type spent by the action.",
    )
    can_afford: bool = Field(
        default=True,
        description="Whether the actor can currently pay the action cost.",
    )
    targets: List[TargetOption] = Field(
        default_factory=list,
        description="Selectable target rows for this action.",
    )
    weapon_name: Optional[str] = Field(
        default=None,
        description="Weapon display name for weapon attacks.",
    )
    weapon_slot: Optional[str] = Field(
        default=None,
        description="Weapon slot used by a weapon attack.",
    )
    num_projectiles: Optional[int] = Field(
        default=None,
        description="Number of projectiles created by this action.",
    )
    allow_same_target: Optional[bool] = Field(
        default=None,
        description="Whether multiple projectiles may select the same target.",
    )
    is_item_use: bool = Field(
        default=False,
        description="Whether the action is provided by an item.",
    )
    source_item_uuid: Optional[str] = Field(
        default=None,
        description="Item UUID that provides this action, when applicable.",
    )
    attack_data: Optional[AttackData] = Field(
        default=None,
        description="Attack-roll math for tactical scoring.",
    )
    spell_data: Optional[SpellData] = Field(
        default=None,
        description="Spell math for tactical scoring.",
    )


class ActionEconomy(BaseModel):
    """Remaining turn economy in a tactical snapshot."""

    actions: int = Field(
        default=0,
        description="Remaining actions.",
    )
    bonus_actions: int = Field(
        default=0,
        description="Remaining bonus actions.",
    )
    reactions: int = Field(
        default=0,
        description="Remaining reactions.",
    )
    movement: int = Field(
        default=0,
        description="Remaining movement in feet.",
    )

    @property
    def has_action(self) -> bool:
        """Return whether at least one action remains."""
        return self.actions > 0

    @property
    def has_bonus(self) -> bool:
        """Return whether at least one bonus action remains."""
        return self.bonus_actions > 0

    @property
    def has_movement(self) -> bool:
        """Return whether any movement remains."""
        return self.movement > 0

    @property
    def is_empty(self) -> bool:
        """Return whether no action or movement budget remains."""
        return self.actions <= 0 and self.bonus_actions <= 0 and self.movement <= 0


class ActionResult(BaseModel):
    """Result of executing one selected tactical action."""

    success: bool = Field(description="Whether the action resolved successfully.")
    message: str = Field(
        default="",
        description="Failure or summary message for the execution result.",
    )
    entity_hp: Optional[int] = Field(
        default=None,
        description="Acting entity hit points after execution.",
    )
    target_hp: Optional[int] = Field(
        default=None,
        description="Primary target hit points after execution.",
    )
    deaths: List[str] = Field(
        default_factory=list,
        description="Entity names reduced to zero hit points by the action.",
    )
    encounter_ended: bool = Field(
        default=False,
        description="Whether the encounter ended after the action.",
    )
    triggered_reactions: List[str] = Field(
        default_factory=list,
        description="Reaction or child-event names triggered by the action.",
    )
    combat_log: List[str] = Field(
        default_factory=list,
        description="Combat-log summaries associated with the action.",
    )


class TacticalState(BaseModel):
    """Complete subjective tactical view for one controlled actor."""

    me: TacticalEntity = Field(description="Controlled actor snapshot.")
    action_economy: ActionEconomy = Field(
        description="Remaining turn budgets for the controlled actor.",
    )
    is_threatened: bool = Field(
        default=False,
        description="Whether a visible enemy is within melee reach.",
    )
    is_concentrating: bool = Field(
        default=False,
        description="Whether the controlled actor is concentrating.",
    )
    enemies: List[TacticalEntity] = Field(
        default_factory=list,
        description="Visible enemies ordered by distance.",
    )
    allies: List[TacticalEntity] = Field(
        default_factory=list,
        description="Visible allies ordered by distance.",
    )
    attacks: List[ActionOption] = Field(
        default_factory=list,
        description="Available attack action rows.",
    )
    spells: List[ActionOption] = Field(
        default_factory=list,
        description="Available spell action rows.",
    )
    movements: List[ActionOption] = Field(
        default_factory=list,
        description="Available movement action rows.",
    )
    self_actions: List[ActionOption] = Field(
        default_factory=list,
        description="Available self-targeting action rows.",
    )
    object_actions: List[ActionOption] = Field(
        default_factory=list,
        description="Available object-targeting action rows.",
    )
    spell_slots: Dict[int, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Current and maximum spell slots keyed by spell level.",
    )
    resources: Dict[str, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Current and maximum named resources keyed by resource name.",
    )
    hazardous_positions: Set[Tuple[int, int]] = Field(
        default_factory=set,
        description="Known hazardous map positions.",
    )
    round_number: int = Field(
        default=1,
        description="Encounter round number for the snapshot.",
    )

    def nearest_enemy(self) -> Optional[TacticalEntity]:
        """Return the nearest visible enemy, if any."""
        return self.enemies[0] if self.enemies else None

    def weakest_enemy(self) -> Optional[TacticalEntity]:
        """Return the lowest-HP visible enemy that is still alive."""
        alive = [enemy for enemy in self.enemies if not enemy.is_dead]
        return min(alive, key=lambda enemy: enemy.hp) if alive else None

    def enemies_in_range(self, feet: int) -> List[TacticalEntity]:
        """Return visible enemies within a distance threshold.

        Args:
            feet: Maximum distance in feet.

        Returns:
            Enemies with known distance less than or equal to the threshold.
        """
        return [
            enemy for enemy in self.enemies
            if enemy.distance_feet is not None and enemy.distance_feet <= feet
        ]

    def has_affordable_attack(self) -> bool:
        """Return whether at least one affordable attack has a target."""
        return any(action.can_afford and action.targets for action in self.attacks)

    def has_affordable_spell(self) -> bool:
        """Return whether at least one affordable spell has a target."""
        return any(action.can_afford and action.targets for action in self.spells)

    def find_attack_targeting(
        self,
        uuid: str,
    ) -> Optional[Tuple[ActionOption, TargetOption]]:
        """Find the first affordable attack that can target an entity.

        Args:
            uuid: Target entity UUID string.

        Returns:
            Matching action and target row, or `None`.
        """
        for action in self.attacks:
            if not action.can_afford:
                continue
            for target in action.targets:
                if target.target_uuid == uuid:
                    return (action, target)
        return None

    def find_move_adjacent_to(
        self,
        uuid: str,
    ) -> Optional[Tuple[ActionOption, TargetOption]]:
        """Find a move row that gets adjacent to a target entity.

        Args:
            uuid: Target entity UUID string.

        Returns:
            Best movement action and target row, or `None`.
        """
        target_entity = next(
            (entity for entity in self.enemies + self.allies if entity.uuid == uuid),
            None,
        )
        if not target_entity:
            return None

        best: Optional[Tuple[ActionOption, TargetOption, int]] = None
        for action in self.movements:
            if not action.can_afford:
                continue
            for target in action.targets:
                if target.position is None:
                    continue
                dx = abs(target.position[0] - target_entity.position[0])
                dy = abs(target.position[1] - target_entity.position[1])
                distance = max(dx, dy)
                if best is None or distance < best[2]:
                    best = (action, target, distance)
        return (best[0], best[1]) if best else None

    def find_move_toward(
        self,
        uuid: str,
    ) -> Optional[Tuple[ActionOption, TargetOption]]:
        """Find a move row that reduces distance to a target entity.

        Args:
            uuid: Target entity UUID string.

        Returns:
            Best movement action and target row, or `None`.
        """
        target_entity = next(
            (entity for entity in self.enemies + self.allies if entity.uuid == uuid),
            None,
        )
        if not target_entity:
            return None

        my_distance = (
            abs(self.me.position[0] - target_entity.position[0])
            + abs(self.me.position[1] - target_entity.position[1])
        )
        best: Optional[Tuple[ActionOption, TargetOption, int]] = None
        for action in self.movements:
            if not action.can_afford:
                continue
            for target in action.targets:
                if target.position is None:
                    continue
                distance = (
                    abs(target.position[0] - target_entity.position[0])
                    + abs(target.position[1] - target_entity.position[1])
                )
                if distance < my_distance and (best is None or distance < best[2]):
                    best = (action, target, distance)
        return (best[0], best[1]) if best else None

    def find_move_away_from(
        self,
        position: Tuple[int, int],
    ) -> Optional[Tuple[ActionOption, TargetOption]]:
        """Find a move row that maximizes distance from a position.

        Args:
            position: Grid position to move away from.

        Returns:
            Best movement action and target row, or `None`.
        """
        best: Optional[Tuple[ActionOption, TargetOption, int]] = None
        for action in self.movements:
            if not action.can_afford:
                continue
            for target in action.targets:
                if target.position is None:
                    continue
                distance = (
                    abs(target.position[0] - position[0])
                    + abs(target.position[1] - position[1])
                )
                if best is None or distance > best[2]:
                    best = (action, target, distance)
        return (best[0], best[1]) if best else None

    def find_best_aoe(self) -> Optional[Tuple[ActionOption, TargetOption]]:
        """Find the area spell row that affects the most entities."""
        best: Optional[Tuple[ActionOption, TargetOption]] = None
        best_count = 0
        for spell in self.spells:
            if not spell.can_afford:
                continue
            for target in spell.targets:
                count = target.aoe_affected_count or 0
                if count > best_count:
                    best = (spell, target)
                    best_count = count
        return best

    def find_self_action(self, name: str) -> Optional[ActionOption]:
        """Find a self-action by case-insensitive partial name.

        Args:
            name: Text to match against the display name.

        Returns:
            Matching self-action row, or `None`.
        """
        name_lower = name.lower()
        for action in self.self_actions:
            if name_lower in action.display_name.lower():
                return action
        return None


def hit_chance(
    attack_bonus: int,
    target_ac: int,
    advantage: str = "none",
    auto_hit: str = "none",
) -> float:
    """Estimate attack hit chance from d20 math.

    Args:
        attack_bonus: Attack bonus added to the d20.
        target_ac: Target Armor Class.
        advantage: Advantage state: advantage, disadvantage, or none.
        auto_hit: Automatic hit state: autohit, automiss, or none.

    Returns:
        Probability between 0.0 and 1.0.
    """
    if auto_hit == "automiss":
        return 0.0
    if auto_hit == "autohit":
        return 1.0
    needed = target_ac - attack_bonus
    base = max(0.05, min(0.95, (21 - needed) / 20))
    if advantage == "advantage":
        return 1 - (1 - base) ** 2
    if advantage == "disadvantage":
        return base ** 2
    return base


def crit_chance(crit_threshold: int = 20, advantage: str = "none") -> float:
    """Estimate critical-hit chance from d20 math.

    Args:
        crit_threshold: Natural d20 result that starts the critical range.
        advantage: Advantage state: advantage, disadvantage, or none.

    Returns:
        Probability between 0.0 and 1.0.
    """
    crit_range = 21 - crit_threshold
    base = crit_range / 20
    if advantage == "advantage":
        return 1 - (1 - base) ** 2
    if advantage == "disadvantage":
        return base ** 2
    return base


def attack_ev(attack: AttackData, target_ac: int) -> float:
    """Estimate expected damage for one attack target.

    Args:
        attack: Tactical attack math.
        target_ac: Target Armor Class.

    Returns:
        Expected damage estimate for tactical ranking.
    """
    p_hit = hit_chance(
        attack.attack_bonus,
        target_ac,
        attack.advantage,
        attack.auto_hit,
    )
    p_crit = crit_chance(attack.crit_threshold, attack.advantage)
    p_normal_hit = p_hit - p_crit

    normal_damage = sum(die.average for die in attack.damage_dice)
    crit_dice_damage = sum(
        die.count * (die.sides + 1) / 2 for die in attack.damage_dice
    )
    crit_bonus_damage = sum(die.bonus for die in attack.damage_dice)
    max_die = max((die.sides for die in attack.damage_dice), default=0)
    extra_crit_average = (
        attack.crit_extra_dice * (max_die + 1) / 2 if max_die > 0 else 0
    )
    crit_damage = crit_dice_damage * 2 + crit_bonus_damage + extra_crit_average

    return p_normal_hit * normal_damage + p_crit * crit_damage


def spell_save_ev(spell: SpellData, target_save_bonus: int) -> float:
    """Estimate expected damage for one save-based spell target.

    Args:
        spell: Tactical spell math.
        target_save_bonus: Target saving throw bonus for the spell ability.

    Returns:
        Expected damage estimate for tactical ranking.
    """
    save_needed = spell.spell_dc - target_save_bonus
    p_fail = max(0.05, min(0.95, (save_needed - 1) / 20))
    full_damage = sum(die.average for die in spell.damage_dice)
    half_damage = full_damage / 2 if spell.half_on_save else 0
    return p_fail * full_damage + (1 - p_fail) * half_damage


def spell_attack_ev(spell: SpellData, target_ac: int) -> float:
    """Estimate expected damage for one spell attack target.

    Args:
        spell: Tactical spell math.
        target_ac: Target Armor Class.

    Returns:
        Expected damage estimate for tactical ranking.
    """
    p_hit = hit_chance(spell.spell_attack_bonus, target_ac, "none")
    return p_hit * sum(die.average for die in spell.damage_dice)


def action_ev(action: ActionOption, target: TargetOption) -> float:
    """Estimate expected damage for an action-target pair.

    This is an agent scoring heuristic. It does not replace engine resolution.

    Args:
        action: Tactical action row.
        target: Tactical target row.

    Returns:
        Expected damage estimate, or zero for non-damaging actions.
    """
    if action.attack_data and target.target_ac is not None:
        return attack_ev(action.attack_data, target.target_ac)
    if action.spell_data:
        if action.spell_data.is_attack_roll and target.target_ac is not None:
            return spell_attack_ev(action.spell_data, target.target_ac)
        if (
            not action.spell_data.is_attack_roll
            and target.target_save_bonus is not None
        ):
            return spell_save_ev(action.spell_data, target.target_save_bonus)
        if target.aoe_affected_count and target.aoe_affected_count > 0:
            single_target_damage = sum(
                die.average for die in action.spell_data.damage_dice
            )
            return single_target_damage * target.aoe_affected_count * 0.5
    return 0.0
