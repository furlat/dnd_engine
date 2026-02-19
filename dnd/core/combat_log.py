"""
Combat log data models for automatic event-based combat log generation.

Events generate their own combat log entries at COMPLETION phase,
eliminating post-hoc extraction and coupling between display layer and engine internals.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

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
    MULTI_ENTITY_ACTION = "multi_entity_action"  # Fireball, Magic Missile, etc.
    SPELL_SAVE = "spell_save"  # Save-based spell effect on single target
    SPELL_DAMAGE = "spell_damage"  # Auto-hit spell damage (Magic Missile dart)
    ENTITY_SPOTTED = "entity_spotted"  # Observer spots a hiding entity


class CombatLogVerbosity(str, Enum):
    """Verbosity levels for combat log display."""
    COMPACT = "compact"    # One-line summary only
    VERBOSE = "verbose"    # Summary + key details
    DETAILED = "detailed"  # Full breakdown with all modifiers


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


class SpellSaveLogData(BaseModel):
    """Structured data for save-based spell effects (single target)."""
    caster_name: str
    caster_uuid: str
    target_name: str
    target_uuid: str
    spell_name: str
    spell_level: int = 0

    # Save info
    save_ability: str  # "dexterity", "wisdom", etc.
    save_dc: int
    save_roll: DiceRollDisplay
    save_bonus_breakdown: List[ModifierBreakdown] = Field(default_factory=list)
    save_success: bool

    # Damage info
    damage_rolls: List[DamageRollDisplay] = Field(default_factory=list)
    base_damage: int = 0  # Before save halving
    final_damage: int = 0  # After save halving
    damage_type: str = ""

    # Target state after
    target_hp_after: Optional[int] = None


class SkillCheckLogData(BaseModel):
    """Structured skill check data."""
    entity_name: str
    entity_uuid: str
    skill: str  # "perception", "stealth", etc.
    dc: Optional[int] = None  # May not have a DC
    roll: DiceRollDisplay
    bonus_breakdown: List[ModifierBreakdown] = Field(default_factory=list)
    success: Optional[bool] = None  # Only set if there's a DC


class EntitySpottedLogData(BaseModel):
    """Structured data for when an observer spots a hiding entity."""
    observer_name: str
    observer_uuid: str
    target_name: str
    target_uuid: str
    target_position: Tuple[int, int]
    passive_perception: int
    stealth_dc: int


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


class MultiEntityLogData(BaseModel):
    """Structured data for multi-target actions (AoE spells, Magic Missile, etc.)."""
    action_name: str
    caster_name: str

    # Targeting info
    total_targets: int = 0
    target_names: List[str] = Field(default_factory=list)

    # Damage aggregation
    total_damage: int = 0
    per_target_damage: List[int] = Field(default_factory=list)

    # Save info (for save-based spells)
    saves_succeeded: int = 0
    saves_failed: int = 0

    # Per-target logs for detailed/programmatic access
    per_target_logs: List[Optional[Dict[str, Any]]] = Field(default_factory=list)

    # AoE-specific (optional)
    aoe_shape: Optional[str] = None  # "Sphere", "Cone", "Line", "Cube"
    aoe_center: Optional[Tuple[int, int]] = None



class CombatLogEntry(BaseModel):
    """
    A single combat log entry that can be generated by any event.

    Contains human-readable text at three verbosity levels and structured data
    for programmatic access.

    Text fields support markdown-style formatting for Rich rendering:
    - **text** -> bold
    - *text* -> italic
    - {color:text} -> colored text (e.g., {cyan:Hero}, {red:MISS})
    """
    entry_type: CombatLogEntryType

    # Actor info
    source_name: str
    source_uuid: str
    target_name: Optional[str] = None
    target_uuid: Optional[str] = None

    # Three verbosity levels - contain markdown for rich formatting
    compact: str = Field(
        description="One-line summary with markdown (e.g., '{cyan:Hero} hits {yellow:Skeleton}')"
    )
    verbose: str = Field(
        description="Summary + key details with markdown"
    )
    detailed: str = Field(
        description="Full breakdown with all modifiers"
    )

    # Structured data - type depends on entry_type
    # Using Dict for flexibility, cast to specific types as needed
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific structured data (AttackLogData, MovementLogData, etc.)"
    )

    # Success indicator (for attacks, saves, checks)
    success: Optional[bool] = None

    # Hierarchical sub-entries (for parent events that have children)
    # Supports recursive nesting (sub-entries can have sub-entries)
    sub_entries: List["CombatLogEntry"] = Field(
        default_factory=list,
        description="Combat log entries from child events, in order"
    )

    # Temporal visibility: which entity UUIDs could perceive this event
    # at the time it happened (stamped at COMPLETION phase).
    # Empty set = legacy entry (show to everyone).
    perceiver_uuids: Set[str] = Field(
        default_factory=set,
        description="Entity UUIDs that could perceive this event when it happened"
    )

    def get_text(self, verbosity: CombatLogVerbosity) -> str:
        """Get formatted text at specified verbosity level."""
        if verbosity == CombatLogVerbosity.COMPACT:
            return self.compact
        elif verbosity == CombatLogVerbosity.VERBOSE:
            return self.verbose
        else:  # DETAILED
            return self.detailed

    def get_text_with_children(
        self,
        verbosity: str = "compact",
        indent_str: str = "  ",
        depth: int = 0
    ) -> str:
        """Get formatted text including sub-entries with indentation.

        Recursively processes sub_entries with increasing indentation.

        Args:
            verbosity: One of "compact", "verbose", or "detailed"
            indent_str: String to use for each level of indentation
            depth: Current indentation depth (starts at 0)

        Returns:
            Formatted text with all sub-entries properly indented
        """
        text_field = getattr(self, verbosity, self.compact)
        prefix = indent_str * depth
        lines = [prefix + text_field]

        for sub_entry in self.sub_entries:
            # Recursive call handles nested sub-entries
            lines.append(sub_entry.get_text_with_children(verbosity, indent_str, depth + 1))

        return "\n".join(lines)

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


# =============================================================================
# Markdown Formatting Helpers for Verbosity Levels
# =============================================================================

def md_color(text: str, color: str) -> str:
    """Wrap text in color markdown: {color:text}"""
    return f"{{{color}:{text}}}"


def md_bold(text: str) -> str:
    """Wrap text in bold markdown: **text**"""
    return f"**{text}**"


def md_outcome(outcome: str) -> str:
    """Format outcome with appropriate color.

    Returns markdown like {green:HIT} or {red:MISS}.
    """
    outcome_lower = outcome.lower()
    if outcome_lower == "crit":
        return md_color("CRIT!", "bold yellow")
    elif outcome_lower == "hit":
        return md_color("HIT", "green")
    elif outcome_lower in ("miss", "crit_miss", "crit miss"):
        return md_color("MISS", "red")
    return outcome.upper()


def md_d20_roll(
    roll: DiceRollDisplay,
    include_advantage: bool = True
) -> str:
    """Format d20 roll with markdown.

    Returns: "d20({cyan:15})" or "ADV d20({cyan:15,8}→{green:15})"
    """
    if include_advantage and roll.advantage_status == "advantage" and roll.all_d20_rolls and len(roll.all_d20_rolls) >= 2:
        return f"ADV d20({roll.all_d20_rolls[0]},{roll.all_d20_rolls[1]}→{md_color(str(roll.d20_used), 'green')})"
    elif include_advantage and roll.advantage_status == "disadvantage" and roll.all_d20_rolls and len(roll.all_d20_rolls) >= 2:
        return f"DIS d20({roll.all_d20_rolls[0]},{roll.all_d20_rolls[1]}→{md_color(str(roll.d20_used), 'red')})"
    else:
        d20_val = roll.d20_used if roll.d20_used is not None else (roll.results[0] if roll.results else "?")
        return f"d20({md_color(str(d20_val), 'cyan')})"


def md_breakdown(breakdown: List[ModifierBreakdown]) -> str:
    """Format modifier breakdown: [Prof +2, DEX +2]"""
    if not breakdown:
        return ""
    parts = []
    for m in breakdown:
        if m.value == 0:
            continue
        sign = "+" if m.value >= 0 else ""
        parts.append(f"{m.name} {sign}{m.value}")
    return f"[{', '.join(parts)}]" if parts else ""


def format_attack_compact(
    source_name: str,
    target_name: str,
    outcome: str,
    total_damage: int
) -> str:
    """Format compact attack line.

    Example: "{cyan:Hero} {green:hits} {yellow:Skeleton} for {red:7} damage"
    """
    outcome_lower = outcome.lower()
    if outcome_lower == "crit":
        verb = md_color("CRITS", "bold yellow")
        damage_str = md_color(str(total_damage), "bold red")
        return f"{md_color(source_name, 'cyan')} {verb} {md_color(target_name, 'yellow')} for {damage_str} damage!"
    elif outcome_lower == "hit":
        verb = md_color("hits", "green")
        damage_str = md_color(str(total_damage), "red")
        return f"{md_color(source_name, 'cyan')} {verb} {md_color(target_name, 'yellow')} for {damage_str} damage"
    else:
        verb = md_color("misses", "dim")
        return f"{md_color(source_name, 'cyan')} {verb} {md_color(target_name, 'yellow')}"


def format_attack_verbose(
    source_name: str,
    target_name: str,
    weapon_name: str,
    attack_roll: DiceRollDisplay,
    target_ac: int,
    outcome: str,
    damage_rolls: List[DamageRollDisplay],
    total_damage: int,
    is_opportunity_attack: bool = False
) -> str:
    """Format verbose attack output.

    Example:
    {cyan:Hero} → {yellow:Skeleton} (Shortsword)
      Attack: d20({cyan:15}) +4 = 19 vs AC 13 → {green:HIT}
      Damage: 1d6({red:5}) +2 = {bold red:7} slashing
    """
    lines = []

    # Header line
    header = f"{md_color(source_name, 'cyan')} → {md_color(target_name, 'yellow')} ({weapon_name})"
    if attack_roll.advantage_status == "advantage":
        header += f" {md_color('ADV', 'green')}"
    elif attack_roll.advantage_status == "disadvantage":
        header += f" {md_color('DIS', 'red')}"
    lines.append(header)

    # Attack line
    attack_label = "Attack (OA)" if is_opportunity_attack else "Attack"
    d20_str = md_d20_roll(attack_roll, include_advantage=False)  # We show ADV/DIS in header
    bonus_str = f"+{attack_roll.bonus}" if attack_roll.bonus >= 0 else str(attack_roll.bonus)
    outcome_md = md_outcome(outcome)
    lines.append(f"  {attack_label}: {d20_str} {bonus_str} = {attack_roll.total} vs AC {target_ac} → {outcome_md}")

    # Damage line (only on hit)
    outcome_lower = outcome.lower()
    if outcome_lower in ("hit", "crit") and damage_rolls and total_damage > 0:
        dr = damage_rolls[0]
        dice_results = ",".join(str(d) for d in dr.dice_results) if dr.dice_results else "?"
        bonus_str = f" +{dr.bonus}" if dr.bonus > 0 else (f" {dr.bonus}" if dr.bonus < 0 else "")
        damage_md = md_color(str(total_damage), "bold red")
        lines.append(f"  Damage: {dr.dice_str}({md_color(dice_results, 'red')}){bonus_str} = {damage_md} {dr.damage_type}")

    return "\n".join(lines)


def format_attack_detailed(
    source_name: str,
    target_name: str,
    weapon_name: str,
    attack_roll: DiceRollDisplay,
    attack_breakdown: List[ModifierBreakdown],
    target_ac: int,
    ac_breakdown: List[ModifierBreakdown],
    outcome: str,
    damage_rolls: List[DamageRollDisplay],
    total_damage: int,
    is_opportunity_attack: bool = False
) -> str:
    """Format detailed attack output with full breakdowns.

    Example:
    {cyan:Hero} → {yellow:Skeleton} (Shortsword)
      Attack: d20({cyan:15}) +4 [Prof +2, DEX +2] = 19 vs AC 13 [Armor +13] → {green:HIT}
      Damage: 1d6({red:5}) +2 [DEX +2] = {bold red:7} slashing
    """
    lines = []

    # Header line
    header = f"{md_color(source_name, 'cyan')} → {md_color(target_name, 'yellow')} ({weapon_name})"
    if attack_roll.advantage_status == "advantage":
        header += f" {md_color('ADV', 'green')}"
    elif attack_roll.advantage_status == "disadvantage":
        header += f" {md_color('DIS', 'red')}"
    lines.append(header)

    # Attack line with breakdowns
    attack_label = "Attack (OA)" if is_opportunity_attack else "Attack"
    d20_str = md_d20_roll(attack_roll, include_advantage=False)
    bonus_str = f"+{attack_roll.bonus}" if attack_roll.bonus >= 0 else str(attack_roll.bonus)
    atk_breakdown = md_breakdown(attack_breakdown)
    ac_bd = md_breakdown(ac_breakdown)
    outcome_md = md_outcome(outcome)

    atk_line = f"  {attack_label}: {d20_str} {bonus_str}"
    if atk_breakdown:
        atk_line += f" {atk_breakdown}"
    atk_line += f" = {attack_roll.total} vs AC {target_ac}"
    if ac_bd:
        atk_line += f" {ac_bd}"
    atk_line += f" → {outcome_md}"
    lines.append(atk_line)

    # Damage line with breakdown (only on hit)
    outcome_lower = outcome.lower()
    if outcome_lower in ("hit", "crit") and damage_rolls and total_damage > 0:
        dr = damage_rolls[0]
        dice_results = ",".join(str(d) for d in dr.dice_results) if dr.dice_results else "?"
        bonus_str = f" +{dr.bonus}" if dr.bonus > 0 else (f" {dr.bonus}" if dr.bonus < 0 else "")
        dmg_breakdown = md_breakdown(dr.bonus_breakdown)
        damage_md = md_color(str(total_damage), "bold red")

        dmg_line = f"  Damage: {dr.dice_str}({md_color(dice_results, 'red')}){bonus_str}"
        if dmg_breakdown:
            dmg_line += f" {dmg_breakdown}"
        dmg_line += f" = {damage_md} {dr.damage_type}"
        lines.append(dmg_line)

    return "\n".join(lines)
