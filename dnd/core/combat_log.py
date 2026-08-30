"""Combat-log data models and display helpers.

Events generate their own combat-log entries at completion, which keeps
display payloads near the event data that produced them.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from pydantic import BaseModel, Field, field_serializer


def position_evidence_key(position: Tuple[int, int]) -> str:
    """Return the canonical internal key for one event-time grid position."""
    return f"{position[0]},{position[1]}"


class CombatLogEntryType(str, Enum):
    """Combat-log entry categories emitted by engine events."""

    ATTACK = "attack"
    MOVEMENT = "movement"
    ACTION = "action"
    SAVING_THROW = "saving_throw"
    SKILL_CHECK = "skill_check"
    CONDITION_APPLIED = "condition_applied"
    CONDITION_REMOVED = "condition_removed"
    DAMAGE_TAKEN = "damage_taken"
    HEAL = "heal"
    DEATH = "death"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    MULTI_ENTITY_ACTION = "multi_entity_action"
    SPELL_SAVE = "spell_save"
    SPELL_DAMAGE = "spell_damage"
    SPELL_INTERRUPTION = "spell_interruption"
    ENTITY_SPOTTED = "entity_spotted"
    HAZARD_DETECTED = "hazard_detected"
    ROLL_MODIFICATION = "roll_modification"
    SPATIAL_EFFECT = "spatial_effect"


class CombatLogVerbosity(str, Enum):
    """Verbosity levels for combat-log display text."""

    COMPACT = "compact"
    VERBOSE = "verbose"
    DETAILED = "detailed"


class ModifierBreakdown(BaseModel):
    """A single modifier contributing to a roll or value.

    Attributes:
        name: Human-readable modifier name.
        value: Numerical modifier value.
        source: Description of where the modifier originated.
    """

    name: str = Field(description="Human-readable modifier name (e.g., 'Prof', 'DEX')")
    value: int = Field(description="The modifier value (+2, -1, etc.)")
    source: str = Field(default="self", description="Where the modifier comes from")


class DiceRollDisplay(BaseModel):
    """Display information for a dice roll.

    Attributes:
        dice_str: Dice notation for the roll.
        results: Individual die results.
        bonus: Total numerical bonus applied to the roll.
        total: Final roll total.
        all_d20_rolls: All d20 values rolled for advantage or disadvantage.
        d20_used: D20 value used for the final result.
        advantage_status: Advantage state captured for the roll.
    """

    dice_str: str = Field(description="Dice notation (e.g., '1d6', 'd20')")
    results: List[int] = Field(default_factory=list, description="Individual die results")
    bonus: int = Field(default=0, description="Total bonus applied to roll")
    total: int = Field(description="Final total of roll")
    all_d20_rolls: Optional[List[int]] = Field(
        default=None,
        description="All d20 rolls when advantage or disadvantage applies.",
    )
    d20_used: Optional[int] = Field(
        default=None,
        description="D20 result used for the final roll total.",
    )
    advantage_status: Optional[str] = Field(
        default=None,
        description="Advantage state: advantage, disadvantage, or None.",
    )


class DamageRollDisplay(BaseModel):
    """Display information for a damage roll.

    Attributes:
        dice_str: Dice notation for the damage roll.
        dice_results: Individual damage die results.
        bonus: Total damage bonus.
        total: Final damage total.
        damage_type: Damage type label.
        bonus_breakdown: Modifier breakdown for the damage bonus.
    """

    dice_str: str = Field(description="Dice notation (e.g., '1d6', '2d8')")
    dice_results: List[int] = Field(default_factory=list, description="Individual die results")
    bonus: int = Field(default=0, description="Damage bonus")
    total: int = Field(description="Total damage")
    damage_type: str = Field(description="Type of damage (slashing, fire, etc.)")
    bonus_breakdown: List[ModifierBreakdown] = Field(
        default_factory=list,
        description="Breakdown of damage bonus modifiers",
    )


class RollModificationLogFact(BaseModel):
    """Combat-log projection of one rules-owned roll-result change.

    This is intentionally a projection rather than the engine event model:
    combat-log contracts are dependency-neutral and must not import upward
    from the event system.
    """

    operation: Literal["replace", "append"] = Field(
        description="Whether an effective roll changed or a damage packet was added.",
    )
    handler_name: str = Field(
        min_length=1,
        description="Rules handler responsible for the change.",
    )
    packet_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Affected damage-packet index, when applicable.",
    )
    previous_total: Optional[int] = Field(
        default=None,
        description="Effective total before a replacement.",
    )
    final_total: int = Field(
        description="Effective replacement total or appended packet total.",
    )
    reason: str = Field(
        min_length=1,
        description="Rules-facing explanation of the modification.",
    )
    packet_damage_type: Optional[str] = Field(
        default=None,
        description="Damage type for an affected damage packet.",
    )
    packet_dice: Optional[str] = Field(
        default=None,
        description="Dice expression for an affected damage packet.",
    )


class RollModificationLogData(BaseModel):
    """Structured ordered changes made to one effective roll result."""

    roll_type: str = Field(
        min_length=1,
        description="Mechanical roll category whose result changed.",
    )
    modifications: List[RollModificationLogFact] = Field(
        min_length=1,
        description="Ordered changes applied by result interceptors.",
    )


class AttackLogData(BaseModel):
    """Structured attack data for programmatic access.

    Attributes:
        attacker_name: Display name of the attacking entity.
        attacker_uuid: UUID string of the attacking entity.
        target_name: Display name of the attacked entity.
        target_uuid: UUID string of the attacked entity.
        weapon_name: Display name of the weapon used.
        weapon_slot: Equipment slot used for the attack, if known.
        attack_roll: Attack roll display data.
        attack_breakdown: Modifiers contributing to the attack roll.
        target_ac: Armor Class used as the attack DC.
        ac_breakdown: Modifiers contributing to the target Armor Class.
        outcome: Attack outcome label.
        is_hit: Whether the attack hit.
        is_crit: Whether the attack was a critical hit.
        damage_rolls: Damage rolls produced by the hit.
        total_damage: Total damage dealt by the attack.
        target_hp: Target HP after damage resolution, if known.
        advantage_breakdown: Advantage and disadvantage sources.
        is_opportunity_attack: Whether the attack was an opportunity attack.
        is_long_range: Whether the attack used long-range penalties.
        is_threatened: Whether the attacker was threatened while attacking.
    """

    attacker_name: str = Field(description="Display name of the attacking entity.")
    attacker_uuid: str = Field(description="UUID string of the attacking entity.")
    target_name: str = Field(description="Display name of the attacked entity.")
    target_uuid: str = Field(description="UUID string of the attacked entity.")
    weapon_name: str = Field(description="Display name of the weapon used.")
    weapon_slot: Optional[str] = Field(default=None, description="Equipment slot used for the attack, if known.")
    attack_roll: DiceRollDisplay = Field(description="Attack roll display data.")
    attack_breakdown: List[ModifierBreakdown] = Field(
        default_factory=list,
        description="Modifiers contributing to the attack roll.",
    )
    target_ac: int = Field(description="Armor Class used as the attack DC.")
    ac_breakdown: List[ModifierBreakdown] = Field(
        default_factory=list,
        description="Modifiers contributing to the target Armor Class.",
    )
    outcome: str = Field(description="Attack outcome label: hit, miss, crit, or crit_miss.")
    is_hit: bool = Field(description="Whether the attack hit.")
    is_crit: bool = Field(description="Whether the attack was a critical hit.")
    damage_rolls: List[DamageRollDisplay] = Field(default_factory=list, description="Damage rolls produced by the hit.")
    total_damage: int = Field(default=0, description="Total damage dealt by the attack.")
    target_hp: Optional[int] = Field(default=None, description="Target HP after damage resolution, if known.")
    advantage_breakdown: List[ModifierBreakdown] = Field(
        default_factory=list,
        description="Advantage and disadvantage sources.",
    )
    is_opportunity_attack: bool = Field(default=False, description="Whether the attack was an opportunity attack.")
    is_long_range: bool = Field(default=False, description="Whether the attack used long-range penalties.")
    is_threatened: bool = Field(default=False, description="Whether the attacker was threatened while attacking.")


class MovementLogData(BaseModel):
    """Structured movement data for programmatic access.

    Attributes:
        entity_name: Display name of the moving entity.
        entity_uuid: UUID string of the moving entity.
        start_position: Starting grid position.
        end_position: Ending grid position.
        path: Path cells traversed by the movement.
        distance_feet: Movement distance in feet.
        movement_cost: Action-economy movement cost in feet.
        requested_end_position: Destination requested before partial termination.
        termination_reason: Machine-readable reason movement ended.
        controller_revalidation: Whether a committed step required a new decision.
        controller_revalidation_reason: Subjective change requiring that decision.
    """

    entity_name: str = Field(description="Display name of the moving entity.")
    entity_uuid: str = Field(description="UUID string of the moving entity.")
    start_position: Tuple[int, int] = Field(description="Starting grid position.")
    end_position: Tuple[int, int] = Field(description="Ending grid position.")
    path: List[Tuple[int, int]] = Field(default_factory=list, description="Path cells traversed by the movement.")
    distance_feet: int = Field(default=0, description="Movement distance in feet.")
    movement_cost: int = Field(default=0, description="Action-economy movement cost in feet.")
    requested_end_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Originally requested destination before partial termination.",
    )
    termination_reason: str = Field(
        default="completed",
        description="Machine-readable reason the traversed movement ended.",
    )
    controller_revalidation: bool = Field(
        default=False,
        description="Whether a committed step required a fresh controller decision.",
    )
    controller_revalidation_reason: Optional[str] = Field(
        default=None,
        description="Typed subjective change that required controller revalidation.",
    )


class SavingThrowLogData(BaseModel):
    """Structured saving throw data.

    Attributes:
        entity_name: Display name of the saving entity.
        entity_uuid: UUID string of the saving entity.
        ability: Ability used for the saving throw.
        dc: Difficulty Class for the save.
        roll: Saving throw roll display data.
        bonus_breakdown: Modifiers contributing to the save.
        advantage_breakdown: Advantage and disadvantage sources.
        success: Whether the save succeeded.
        source_name: Display name of the effect that requested the save.
    """

    entity_name: str = Field(description="Display name of the saving entity.")
    entity_uuid: str = Field(description="UUID string of the saving entity.")
    ability: str = Field(description="Ability used for the saving throw.")
    dc: int = Field(description="Difficulty Class for the save.")
    roll: DiceRollDisplay = Field(description="Saving throw roll display data.")
    bonus_breakdown: List[ModifierBreakdown] = Field(default_factory=list, description="Modifiers contributing to the save.")
    advantage_breakdown: List[ModifierBreakdown] = Field(
        default_factory=list,
        description="Advantage and disadvantage sources.",
    )
    success: bool = Field(description="Whether the save succeeded.")
    source_name: Optional[str] = Field(default=None, description="Display name of the effect that requested the save.")


class SpellSaveLogData(BaseModel):
    """Structured data for a single save-based spell target.

    Attributes:
        caster_name: Display name of the spellcaster.
        caster_uuid: UUID string of the spellcaster.
        target_name: Display name of the spell target.
        target_uuid: UUID string of the spell target.
        spell_name: Display name of the spell.
        spell_level: Slot level or spell level used for display.
        save_ability: Ability used for the saving throw.
        save_dc: Difficulty Class for the spell save.
        save_roll: Saving throw roll display data.
        save_bonus_breakdown: Modifiers contributing to the save.
        save_advantage_breakdown: Advantage and disadvantage sources.
        save_success: Whether the target succeeded on the save.
        damage_rolls: Damage rolls before save adjustment.
        base_damage: Damage before save-based reduction.
        final_damage: Damage after save-based reduction.
        damage_type: Damage type label.
        target_hp_after: Target HP after spell resolution, if known.
    """

    caster_name: str = Field(description="Display name of the spellcaster.")
    caster_uuid: str = Field(description="UUID string of the spellcaster.")
    target_name: str = Field(description="Display name of the spell target.")
    target_uuid: str = Field(description="UUID string of the spell target.")
    spell_name: str = Field(description="Display name of the spell.")
    spell_level: int = Field(default=0, description="Slot level or spell level used for display.")
    save_ability: str = Field(description="Ability used for the saving throw.")
    save_dc: int = Field(description="Difficulty Class for the spell save.")
    save_roll: DiceRollDisplay = Field(description="Saving throw roll display data.")
    save_bonus_breakdown: List[ModifierBreakdown] = Field(default_factory=list, description="Modifiers contributing to the save.")
    save_advantage_breakdown: List[ModifierBreakdown] = Field(
        default_factory=list,
        description="Advantage and disadvantage sources.",
    )
    save_success: bool = Field(description="Whether the target succeeded on the save.")
    damage_rolls: List[DamageRollDisplay] = Field(default_factory=list, description="Damage rolls before save adjustment.")
    base_damage: int = Field(default=0, description="Damage before save-based reduction.")
    final_damage: int = Field(default=0, description="Damage after save-based reduction.")
    damage_type: str = Field(default="", description="Damage type label.")
    target_hp_after: Optional[int] = Field(default=None, description="Target HP after spell resolution, if known.")


class SpellInterruptionLogData(BaseModel):
    """Structured result of one Counterspell reaction."""

    outcome_code: str = Field(description="Stable reaction outcome identity.")
    counterspeller_name: str = Field(description="Display name of the reacting caster.")
    counterspeller_uuid: str = Field(description="UUID of the reacting caster.")
    original_caster_name: str = Field(description="Display name of the interrupted caster.")
    original_caster_uuid: str = Field(description="UUID of the interrupted caster.")
    spell_name: str = Field(description="Display name of the incoming spell.")
    incoming_spell_level: int = Field(ge=0, description="Level of the incoming cast.")
    counterspell_slot_level: int = Field(ge=3, description="Slot level spent on Counterspell.")
    automatic: bool = Field(description="Whether slot level made the result automatic.")
    check_total: Optional[int] = Field(default=None, description="Spellcasting check total when rolled.")
    check_dc: Optional[int] = Field(default=None, description="Spellcasting check DC when rolled.")
    succeeded: bool = Field(description="Whether the reaction interrupted the incoming spell.")


class SkillCheckLogData(BaseModel):
    """Structured skill check data.

    Attributes:
        entity_name: Display name of the checking entity.
        entity_uuid: UUID string of the checking entity.
        skill: Skill used for the check.
        dc: Difficulty Class, when the check has one.
        roll: Skill check roll display data.
        bonus_breakdown: Modifiers contributing to the check.
        advantage_breakdown: Advantage and disadvantage sources.
        success: Whether the check succeeded, when a DC exists.
    """

    entity_name: str = Field(description="Display name of the checking entity.")
    entity_uuid: str = Field(description="UUID string of the checking entity.")
    skill: str = Field(description="Skill used for the check.")
    dc: Optional[int] = Field(default=None, description="Difficulty Class, when the check has one.")
    roll: DiceRollDisplay = Field(description="Skill check roll display data.")
    bonus_breakdown: List[ModifierBreakdown] = Field(default_factory=list, description="Modifiers contributing to the check.")
    advantage_breakdown: List[ModifierBreakdown] = Field(
        default_factory=list,
        description="Advantage and disadvantage sources.",
    )
    success: Optional[bool] = Field(default=None, description="Whether the check succeeded, when a DC exists.")


class EntitySpottedLogData(BaseModel):
    """Structured data for when an observer spots a hiding entity.

    Attributes:
        observer_name: Display name of the observer.
        observer_uuid: UUID string of the observer.
        target_name: Display name of the spotted entity.
        target_uuid: UUID string of the spotted entity.
        target_position: Grid position where the entity was spotted.
        passive_perception: Passive Perception score that detected the entity.
        stealth_dc: Stealth DC that was beaten.
    """

    observer_name: str = Field(description="Display name of the observer.")
    observer_uuid: str = Field(description="UUID string of the observer.")
    target_name: str = Field(description="Display name of the spotted entity.")
    target_uuid: str = Field(description="UUID string of the spotted entity.")
    target_position: Tuple[int, int] = Field(description="Grid position where the entity was spotted.")
    passive_perception: int = Field(description="Passive Perception score that detected the entity.")
    stealth_dc: int = Field(description="Stealth DC that was beaten.")


class HazardDetectedLogData(BaseModel):
    """Structured data for when an observer detects a hidden hazard.

    Attributes:
        observer_name: Display name of the observer.
        observer_uuid: UUID string of the observer.
        hazard_name: Display name of the detected hazard.
        position: Grid position of the hazard.
        passive_perception: Passive Perception score that detected the hazard.
        stealth_dc: Stealth DC that was beaten.
    """

    observer_name: str = Field(description="Display name of the observer.")
    observer_uuid: str = Field(description="UUID string of the observer.")
    hazard_name: str = Field(description="Display name of the detected hazard.")
    position: Tuple[int, int] = Field(description="Grid position of the hazard.")
    passive_perception: int = Field(description="Passive Perception score that detected the hazard.")
    stealth_dc: int = Field(description="Stealth DC that was beaten.")


class DamageTakenLogData(BaseModel):
    """Structured data for blocked and successful damage events.

    Attributes:
        target_name: Display name of the damaged entity.
        damage: Damage applied, or zero when the effect was blocked.
        damage_type: Damage type label.
        source_name: Display name of the damage source.
        effect_id: Stable identity of the effect that caused the damage.
        blocked: Whether the damage effect was blocked.
        blocked_reason: Human-readable reason the damage was blocked.
    """

    target_name: str = Field(description="Display name of the damaged entity.")
    damage: int = Field(description="Damage applied, or zero when the effect was blocked.")
    damage_type: str = Field(description="Damage type label.")
    source_name: str = Field(description="Display name of the damage source.")
    effect_id: Optional[str] = Field(
        default=None,
        description="Stable identity of the effect that caused the damage.",
    )
    blocked: Optional[bool] = Field(
        default=None,
        description="Whether the damage effect was blocked.",
    )
    blocked_reason: Optional[str] = Field(
        default=None,
        description="Human-readable reason the damage was blocked.",
    )


class HealLogData(BaseModel):
    """Structured data for healing events.

    Attributes:
        entity_name: Display name of the healed entity.
        entity_uuid: UUID string of the healed entity.
        amount: Healing amount.
        source_description: Description of the healing source.
    """

    entity_name: str = Field(description="Display name of the healed entity.")
    entity_uuid: str = Field(description="UUID string of the healed entity.")
    amount: int = Field(description="Healing amount.")
    source_description: str = Field(description="Description of the healing source.")


class ActionLogData(BaseModel):
    """Structured data for actions without a more specific log model.

    Attributes:
        entity_name: Display name of the acting entity.
        entity_uuid: UUID string of the acting entity.
        action_name: Display name of the action.
        effect_description: Description of the action effect.
        target_name: Display name of the target, when the action has one.
        target_uuid: UUID string of the target, when the action has one.
    """

    entity_name: str = Field(description="Display name of the acting entity.")
    entity_uuid: str = Field(description="UUID string of the acting entity.")
    action_name: str = Field(description="Display name of the action.")
    effect_description: str = Field(description="Description of the action effect.")
    target_name: Optional[str] = Field(default=None, description="Display name of the target, if any.")
    target_uuid: Optional[str] = Field(default=None, description="UUID string of the target, if any.")


class TurnLogData(BaseModel):
    """Structured data for turn start and end events.

    Attributes:
        entity_name: Display name of the turn entity.
        entity_uuid: UUID string of the turn entity.
        round_number: Encounter round number.
        turn_index: Encounter initiative index.
    """

    entity_name: str = Field(description="Display name of the turn entity.")
    entity_uuid: str = Field(description="UUID string of the turn entity.")
    round_number: int = Field(description="Encounter round number.")
    turn_index: int = Field(description="Encounter initiative index.")


class MultiEntityLogData(BaseModel):
    """Structured data for multi-target actions.

    Attributes:
        action_name: Display name of the action.
        caster_name: Display name of the action source.
        total_targets: Number of targets affected.
        target_names: Display names of affected targets.
        total_damage: Total damage across all targets.
        per_target_damage: Damage totals per target.
        saves_succeeded: Count of successful target saves.
        saves_failed: Count of failed target saves.
        per_target_logs: Structured per-target log payloads.
        aoe_shape: Area-of-effect shape label, if applicable.
        aoe_center: Area-of-effect origin or center, if applicable.
    """

    action_name: str = Field(description="Display name of the action.")
    caster_name: str = Field(description="Display name of the action source.")
    total_targets: int = Field(default=0, description="Number of targets affected.")
    target_names: List[str] = Field(default_factory=list, description="Display names of affected targets.")
    total_damage: int = Field(default=0, description="Total damage across all targets.")
    per_target_damage: List[int] = Field(default_factory=list, description="Damage totals per target.")
    saves_succeeded: int = Field(default=0, description="Count of successful target saves.")
    saves_failed: int = Field(default=0, description="Count of failed target saves.")
    per_target_logs: List[Optional[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Structured per-target log payloads.",
    )
    aoe_shape: Optional[str] = Field(default=None, description="Area-of-effect shape label, if applicable.")
    aoe_center: Optional[Tuple[int, int]] = Field(default=None, description="Area-of-effect origin or center, if applicable.")


class CombatLogEntry(BaseModel):
    """A single combat-log entry generated by an event.

    Contains human-readable text at three verbosity levels and structured data
    for programmatic access. Text fields support Rich-style markdown such as
    bold spans and `{color:text}` color tags.

    Attributes:
        entry_type: Category of combat-log entry.
        source_name: Display name of the acting entity or source.
        source_uuid: UUID string of the acting entity or source.
        target_name: Display name of the target, if any.
        target_uuid: UUID string of the target, if any.
        compact: One-line markdown summary.
        verbose: Summary plus key details.
        detailed: Full breakdown text.
        data: Type-specific structured payload.
        success: Success indicator for attacks, saves, and checks.
        sub_entries: Nested combat-log entries from child events.
        perceiver_uuids: Entity UUID strings that could perceive the event.
        revealed_entity_uuids: Entity UUID strings revealed during the event chain.
        identified_entity_observer_uuids: Internal event-time identity grants,
            keyed by participant UUID.
        located_entity_observer_uuids: Internal event-time exact-location grants,
            keyed by participant UUID.
        located_position_observer_uuids: Internal event-time coordinate grants,
            keyed by canonical ``x,y`` position.
    """

    entry_type: CombatLogEntryType = Field(description="Category of combat-log entry.")
    source_name: str = Field(description="Display name of the acting entity or source.")
    source_uuid: str = Field(description="UUID string of the acting entity or source.")
    target_name: Optional[str] = Field(default=None, description="Display name of the target, if any.")
    target_uuid: Optional[str] = Field(default=None, description="UUID string of the target, if any.")
    compact: str = Field(
        description="One-line summary with markdown (e.g., '{cyan:Hero} hits {yellow:Skeleton}')",
    )
    verbose: str = Field(
        description="Summary plus key details with markdown.",
    )
    detailed: str = Field(
        description="Full breakdown with all modifiers.",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific structured data (AttackLogData, MovementLogData, etc.).",
    )
    success: Optional[bool] = Field(default=None, description="Success indicator for attacks, saves, and checks.")
    sub_entries: List["CombatLogEntry"] = Field(
        default_factory=list,
        description="Combat-log entries from child events, in order.",
    )
    perceiver_uuids: Set[str] = Field(
        default_factory=set,
        description="Entity UUIDs that could perceive this event when it happened.",
        json_schema_extra={"uniqueItems": True},
    )
    revealed_entity_uuids: Set[str] = Field(
        default_factory=set,
        description="Entity UUIDs revealed during this event chain.",
        json_schema_extra={"uniqueItems": True},
    )
    identified_entity_observer_uuids: Dict[str, Set[str]] = Field(
        default_factory=dict,
        exclude=True,
        description=(
            "Internal mapping from participant UUIDs to observer UUIDs that "
            "identified them when the event occurred."
        ),
    )
    located_entity_observer_uuids: Dict[str, Set[str]] = Field(
        default_factory=dict,
        exclude=True,
        description=(
            "Internal mapping from participant UUIDs to observer UUIDs that "
            "located them exactly when this event occurred."
        ),
    )
    located_position_observer_uuids: Dict[str, Set[str]] = Field(
        default_factory=dict,
        exclude=True,
        description=(
            "Internal mapping from exact grid coordinates to observer UUIDs "
            "that saw that coordinate at the relevant event phase."
        ),
    )

    @field_serializer(
        "perceiver_uuids",
        "revealed_entity_uuids",
        when_used="json",
    )
    def serialize_uuid_set(self, value: Set[str]) -> List[str]:
        """Emit unordered UUID knowledge as a canonical JSON array."""
        return sorted(value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode='json')


def md_color(text: str, color: str) -> str:
    """Wrap text in color markdown: {color:text}"""
    return f"{{{color}:{text}}}"


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

    header = f"{md_color(source_name, 'cyan')} → {md_color(target_name, 'yellow')} ({weapon_name})"
    if attack_roll.advantage_status == "advantage":
        header += f" {md_color('ADV', 'green')}"
    elif attack_roll.advantage_status == "disadvantage":
        header += f" {md_color('DIS', 'red')}"
    lines.append(header)

    attack_label = "Attack (OA)" if is_opportunity_attack else "Attack"
    d20_str = md_d20_roll(attack_roll)
    bonus_str = f"+{attack_roll.bonus}" if attack_roll.bonus >= 0 else str(attack_roll.bonus)
    outcome_md = md_outcome(outcome)
    lines.append(f"  {attack_label}: {d20_str} {bonus_str} = {attack_roll.total} vs AC {target_ac} → {outcome_md}")

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

    header = f"{md_color(source_name, 'cyan')} → {md_color(target_name, 'yellow')} ({weapon_name})"
    if attack_roll.advantage_status == "advantage":
        header += f" {md_color('ADV', 'green')}"
    elif attack_roll.advantage_status == "disadvantage":
        header += f" {md_color('DIS', 'red')}"
    lines.append(header)

    attack_label = "Attack (OA)" if is_opportunity_attack else "Attack"
    d20_str = md_d20_roll(attack_roll)
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
