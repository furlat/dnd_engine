"""
Combat log data models for automatic event-based combat log generation.

Events generate their own combat log entries at COMPLETION phase,
eliminating post-hoc extraction and coupling between display layer and engine internals.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class CombatLogEntryType(str, Enum):
    """Types of combat log entries."""
    ATTACK = "attack"
    MOVEMENT = "movement"
    ACTION = "action"  # Dash, Dodge, Disengage
    SAVING_THROW = "saving_throw"
    SKILL_CHECK = "skill_check"
    CONDITION_APPLIED = "condition_applied"
    CONDITION_REMOVED = "condition_removed"
    DAMAGE_TAKEN = "damage_taken"
    HEAL = "heal"
    DEATH = "death"
    TURN_START = "turn_start"
    TURN_END = "turn_end"


class ModifierBreakdown(BaseModel):
    """A single modifier contributing to a roll or value."""
    name: str = Field(description="Human-readable modifier name (e.g., 'Prof', 'DEX')")
    value: int = Field(description="The modifier value (+2, -1, etc.)")
    source: str = Field(default="self", description="Where the modifier comes from")


class DiceRollDisplay(BaseModel):
    """Display information for a dice roll."""
    dice_str: str = Field(description="Dice notation (e.g., '1d6', 'd20')")
    results: List[int] = Field(default_factory=list, description="Individual die results")
    bonus: int = Field(default=0, description="Total bonus applied to roll")
    total: int = Field(description="Final total of roll")

    # For advantage/disadvantage on d20 rolls
    all_d20_rolls: Optional[List[int]] = Field(
        default=None,
        description="All d20 rolls when advantage/disadvantage applies"
    )
    d20_used: Optional[int] = Field(
        default=None,
        description="Which d20 result was used (for adv/dis)"
    )
    advantage_status: Optional[str] = Field(
        default=None,
        description="'advantage', 'disadvantage', or None"
    )


class DamageRollDisplay(BaseModel):
    """Display information for a damage roll."""
    dice_str: str = Field(description="Dice notation (e.g., '1d6', '2d8')")
    dice_results: List[int] = Field(default_factory=list, description="Individual die results")
    bonus: int = Field(default=0, description="Damage bonus")
    total: int = Field(description="Total damage")
    damage_type: str = Field(description="Type of damage (slashing, fire, etc.)")
    bonus_breakdown: List[ModifierBreakdown] = Field(
        default_factory=list,
        description="Breakdown of damage bonus modifiers"
    )


class AttackLogData(BaseModel):
    """Structured attack data for programmatic access."""
    attacker_name: str
    attacker_uuid: str
    target_name: str
    target_uuid: str
    weapon_name: str
    weapon_slot: Optional[str] = None

    # Attack roll details
    attack_roll: DiceRollDisplay
    attack_breakdown: List[ModifierBreakdown] = Field(default_factory=list)

    # Target AC
    target_ac: int
    ac_breakdown: List[ModifierBreakdown] = Field(default_factory=list)

    # Outcome
    outcome: str  # "hit", "miss", "crit", "crit_miss"
    is_hit: bool
    is_crit: bool

    # Damage (only on hit)
    damage_rolls: List[DamageRollDisplay] = Field(default_factory=list)
    total_damage: int = 0

    # Target HP after attack
    target_hp: Optional[int] = None

    # Flags
    is_opportunity_attack: bool = False
    is_long_range: bool = False
    is_threatened: bool = False


class MovementLogData(BaseModel):
    """Structured movement data for programmatic access."""
    entity_name: str
    entity_uuid: str
    start_position: Tuple[int, int]
    end_position: Tuple[int, int]
    path: List[Tuple[int, int]] = Field(default_factory=list)
    distance_feet: int = 0
    movement_cost: int = 0


class SavingThrowLogData(BaseModel):
    """Structured saving throw data."""
    entity_name: str
    entity_uuid: str
    ability: str  # "strength", "dexterity", etc.
    dc: int
    roll: DiceRollDisplay
    bonus_breakdown: List[ModifierBreakdown] = Field(default_factory=list)
    success: bool
    source_name: Optional[str] = None  # What caused the save


class SkillCheckLogData(BaseModel):
    """Structured skill check data."""
    entity_name: str
    entity_uuid: str
    skill: str  # "perception", "stealth", etc.
    dc: Optional[int] = None  # May not have a DC
    roll: DiceRollDisplay
    bonus_breakdown: List[ModifierBreakdown] = Field(default_factory=list)
    success: Optional[bool] = None  # Only set if there's a DC


class SelfActionLogData(BaseModel):
    """Structured data for self-targeting actions."""
    entity_name: str
    entity_uuid: str
    action_name: str
    effect_description: str


class TurnLogData(BaseModel):
    """Structured data for turn start/end events."""
    entity_name: str
    entity_uuid: str
    round_number: int
    turn_index: int


class CombatLogEntry(BaseModel):
    """
    A single combat log entry that can be generated by any event.

    Contains both human-readable text and structured data for
    different display modes (verbose, compact, programmatic).
    """
    entry_type: CombatLogEntryType

    # Actor info
    source_name: str
    source_uuid: str
    target_name: Optional[str] = None
    target_uuid: Optional[str] = None

    # Display strings
    summary: str = Field(description="One-line summary (e.g., 'Hero hits Skeleton for 7 damage')")
    detail_lines: List[str] = Field(
        default_factory=list,
        description="Detailed breakdown lines for verbose display"
    )

    # Structured data - type depends on entry_type
    # Using Dict for flexibility, cast to specific types as needed
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific structured data (AttackLogData, MovementLogData, etc.)"
    )

    # Success indicator (for attacks, saves, checks)
    success: Optional[bool] = None

    @property
    def verbose_text(self) -> str:
        """Full verbose output with details."""
        if not self.detail_lines:
            return self.summary
        return self.summary + "\n  " + "\n  ".join(self.detail_lines)

    @property
    def compact_text(self) -> str:
        """Compact single-line output."""
        return self.summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump()


# =============================================================================
# Helper Functions for Building Log Entries
# =============================================================================

def format_attack_roll_line(
    roll: DiceRollDisplay,
    attack_breakdown: List[ModifierBreakdown],
    target_ac: int,
    ac_breakdown: List[ModifierBreakdown],
    outcome: str
) -> str:
    """
    Format the attack roll line:
    d20(15) +4 [Prof +2, DEX +2] = 19 vs AC 13 [Armor +13] → HIT
    """
    # Build d20 roll string
    if roll.advantage_status == "advantage" and roll.all_d20_rolls and len(roll.all_d20_rolls) >= 2:
        d20_str = f"ADV d20({roll.all_d20_rolls[0]},{roll.all_d20_rolls[1]}→{roll.d20_used})"
    elif roll.advantage_status == "disadvantage" and roll.all_d20_rolls and len(roll.all_d20_rolls) >= 2:
        d20_str = f"DIS d20({roll.all_d20_rolls[0]},{roll.all_d20_rolls[1]}→{roll.d20_used})"
    else:
        d20_val = roll.d20_used if roll.d20_used is not None else (roll.results[0] if roll.results else "?")
        d20_str = f"d20({d20_val})"

    # Build bonus string
    bonus_str = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)

    # Build attack breakdown
    if attack_breakdown:
        atk_breakdown_str = " [" + ", ".join(
            f"{m.name} {'+' if m.value >= 0 else ''}{m.value}" for m in attack_breakdown
        ) + "]"
    else:
        atk_breakdown_str = ""

    # Build AC breakdown
    if ac_breakdown:
        ac_breakdown_str = " [" + ", ".join(
            f"{m.name} {'+' if m.value >= 0 else ''}{m.value}" for m in ac_breakdown
        ) + "]"
    else:
        ac_breakdown_str = ""

    # Outcome string
    outcome_map = {
        "hit": "HIT",
        "miss": "MISS",
        "crit": "CRIT",
        "crit_miss": "CRIT MISS"
    }
    outcome_str = outcome_map.get(outcome.lower(), outcome.upper())

    return f"{d20_str} {bonus_str}{atk_breakdown_str} = {roll.total} vs AC {target_ac}{ac_breakdown_str} → {outcome_str}"


def format_damage_line(damage_rolls: List[DamageRollDisplay]) -> str:
    """
    Format the damage line:
    1d6(5) +2 [DEX +2] = 7 slashing
    """
    if not damage_rolls:
        return ""

    parts = []
    for dr in damage_rolls:
        dice_str = dr.dice_str
        dice_results = ",".join(str(r) for r in dr.dice_results) if dr.dice_results else "?"

        bonus_str = ""
        if dr.bonus != 0:
            bonus_str = f" +{dr.bonus}" if dr.bonus > 0 else f" {dr.bonus}"

        breakdown_str = ""
        if dr.bonus_breakdown:
            breakdown_str = " [" + ", ".join(
                f"{m.name} {'+' if m.value >= 0 else ''}{m.value}" for m in dr.bonus_breakdown
            ) + "]"

        parts.append(f"{dice_str}({dice_results}){bonus_str}{breakdown_str} = {dr.total} {dr.damage_type}")

    return ", ".join(parts)


def format_d20_roll_line(
    roll: DiceRollDisplay,
    bonus_breakdown: List[ModifierBreakdown],
    dc: int,
    success: bool,
    label: str = ""
) -> str:
    """
    Format a generic d20 roll line:
    d20(8) +2 [DEX +2] = 10 vs DC 14 → FAIL
    """
    # Build d20 roll string
    if roll.advantage_status == "advantage" and roll.all_d20_rolls and len(roll.all_d20_rolls) >= 2:
        d20_str = f"ADV d20({roll.all_d20_rolls[0]},{roll.all_d20_rolls[1]}→{roll.d20_used})"
    elif roll.advantage_status == "disadvantage" and roll.all_d20_rolls and len(roll.all_d20_rolls) >= 2:
        d20_str = f"DIS d20({roll.all_d20_rolls[0]},{roll.all_d20_rolls[1]}→{roll.d20_used})"
    else:
        d20_val = roll.d20_used if roll.d20_used is not None else (roll.results[0] if roll.results else "?")
        d20_str = f"d20({d20_val})"

    # Build bonus string
    bonus_str = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)

    # Build breakdown
    if bonus_breakdown:
        breakdown_str = " [" + ", ".join(
            f"{m.name} {'+' if m.value >= 0 else ''}{m.value}" for m in bonus_breakdown
        ) + "]"
    else:
        breakdown_str = ""

    result_str = "SUCCESS" if success else "FAIL"

    prefix = f"{label}: " if label else ""
    return f"{prefix}{d20_str} {bonus_str}{breakdown_str} = {roll.total} vs DC {dc} → {result_str}"
