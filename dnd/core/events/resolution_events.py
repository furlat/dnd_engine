"""Roll, damage, healing, hit-point, and life-resolution event facts."""

from enum import Enum
from typing import Any, Dict, List, Optional, Self, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.base_object import BaseObject
from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    DamageTakenLogData,
    HealLogData,
    RollModificationLogData,
    RollModificationLogFact,
    TemporaryHitPointsLogData,
    md_color,
)
from dnd.core.damage import DamageResolution
from dnd.core.dice import Dice, DiceRoll
from dnd.core.events.events_registry import Event, EventType
from dnd.core.values import ModifiableValue
from dnd.types import abilities as ability_types
from dnd.types.damage import DamageType
from dnd.types.equipment import WeaponSlot
from dnd.types.rolls import AttackOutcome, DieSize, RollType

class RangeType(str, Enum):
    REACH = "Reach"
    RANGE = "Range"
    SELF = "Self"

class Range(BaseModel):
    type: RangeType = Field(
        description="The type of range (Reach, Range, or Self)"
    )
    normal: int = Field(
        default=0,
        description="Normal range in feet (0 for Self range)"
    )
    long: Optional[int] = Field(
        default=None,
        description="Long range in feet, only applicable for ranged weapons"
    )

    def __str__(self):
        if self.type == RangeType.SELF:
            return "Self"
        elif self.type == RangeType.REACH:
            return f"{self.normal} ft."
        elif self.type == RangeType.RANGE:
            return f"{self.normal}/{self.long} ft." if self.long else f"{self.normal} ft."

class Damage(BaseObject):
    """Damage dice specification plus damage type."""

    name: str = Field(default="Damage", description="Human-readable damage label.")
    damage_dice: DieSize = Field(
        description="Number of sides on each damage die."
    )
    dice_numbers: int = Field(
        description="Number of damage dice to roll."
    )
    damage_bonus: Optional[ModifiableValue] = Field(
        default=None,
        description="Modifiable flat bonus added to damage rolls."
    )
    damage_type: DamageType = Field(
        description="Damage type applied to this damage packet."
    )

    def get_dice(self, attack_outcome: AttackOutcome, crit_extra_dice: int = 0) -> Dice:
        """Build a `Dice` object for this damage packet.

        Args:
            attack_outcome: Attack outcome used for critical-damage handling.
            crit_extra_dice: Extra critical dice to add beyond the base rule.

        Returns:
            Dice configured for a damage roll.
        """
        assert self.damage_bonus is not None, "Damage requires damage_bonus to be set"
        return Dice(count=self.dice_numbers, value=self.damage_dice, bonus=self.damage_bonus, roll_type=RollType.DAMAGE, attack_outcome=attack_outcome, crit_extra_dice=crit_extra_dice)

class Healing(BaseObject):
    """Healing specification — analogous to Damage but for healing rolls."""
    name: str = Field(default="Healing", description="Name of the healing")
    healing_dice: DieSize = Field(
        description="Number of sides on the healing dice (e.g., 8 for d8)"
    )
    dice_numbers: int = Field(
        description="Number of dice to roll for healing (e.g., 2 for 2d8)"
    )
    healing_bonus: Optional[ModifiableValue] = Field(
        default=None,
        description="Bonus to healing rolls (typically spellcasting ability modifier)"
    )

    def get_dice(self) -> Dice:
        """Build a `Dice` object for this healing packet."""
        assert self.healing_bonus is not None, "Healing requires healing_bonus to be set"
        return Dice(
            count=self.dice_numbers,
            value=self.healing_dice,
            bonus=self.healing_bonus,
            roll_type=RollType.HEAL
        )

class RollModificationOperation(str, Enum):
    """Closed operation applied to an effective dice result."""

    REPLACE = "replace"
    APPEND = "append"

class RollModification(BaseModel):
    """Typed audit fact for one handler-owned dice-result change.

    Replacement facts carry the effective total that was replaced. Append
    facts identify the newly appended damage-packet index and have no previous
    total.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: RollModificationOperation = Field(
        description="Whether the handler replaced a roll or appended a damage packet.",
    )
    handler_name: str = Field(
        min_length=1,
        description="Human-readable handler that owned the change.",
    )
    packet_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Damage-packet index; absent for single-roll replacements.",
    )
    previous_total: Optional[int] = Field(
        default=None,
        description="Effective total replaced by this change; absent for append operations.",
    )
    final_total: int = Field(
        description="Effective total after replacement or the appended packet total.",
    )
    reason: str = Field(
        min_length=1,
        description="Rules-facing reason for the change.",
    )

    @model_validator(mode="after")
    def validate_operation_shape(self) -> "RollModification":
        """Reject ambiguous replacement and append audit facts."""
        if (
            self.operation is RollModificationOperation.REPLACE
            and self.previous_total is None
        ):
            raise ValueError("roll replacement requires previous_total")
        if self.operation is RollModificationOperation.APPEND:
            if self.packet_index is None:
                raise ValueError("roll append requires packet_index")
            if self.previous_total is not None:
                raise ValueError("roll append cannot carry previous_total")
        return self

class DiceRollResultEvent(Event):
    """Abstract base for post-roll, pre-application dice interception.

    Result processors such as Lucky, Great Weapon Fighting, or healing dice
    maximizers modify these events after dice have been rolled but before the
    consuming action applies the result. Concrete result events own distinct
    dispatch categories; the base itself is never published.
    """

    roll_type: RollType = Field(
        ...,
        description="Roll category used by handlers to decide eligibility.",
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary handler context carried with the roll result.",
    )
    roll_modifications: List[RollModification] = Field(
        default_factory=list,
        description="Typed ordered audit facts describing handler-owned roll changes.",
    )

    def _combat_log_packet_details(
        self,
        modification: RollModification,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Return optional damage-packet display facts for one modification."""
        return None, None

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Project actual result changes into one causal combat-log child."""
        if not self.roll_modifications:
            return None

        facts: List[RollModificationLogFact] = []
        detail_lines: List[str] = []
        for modification in self.roll_modifications:
            damage_type, dice_expression = self._combat_log_packet_details(
                modification,
            )
            fact = RollModificationLogFact(
                operation=modification.operation.value,
                handler_name=modification.handler_name,
                packet_index=modification.packet_index,
                previous_total=modification.previous_total,
                final_total=modification.final_total,
                reason=modification.reason,
                packet_damage_type=damage_type,
                packet_dice=dice_expression,
            )
            facts.append(fact)
            if modification.operation is RollModificationOperation.REPLACE:
                locus = (
                    f"damage packet {modification.packet_index}"
                    if modification.packet_index is not None
                    else f"{self.roll_type.value.lower()} roll"
                )
                detail_lines.append(
                    f"{modification.handler_name}: {locus} "
                    f"{modification.previous_total} → {modification.final_total} "
                    f"({modification.reason})"
                )
            else:
                packet_description = "damage packet"
                if dice_expression and damage_type:
                    packet_description = f"{dice_expression} {damage_type} damage"
                detail_lines.append(
                    f"{modification.handler_name}: added {packet_description} "
                    f"for {modification.final_total} "
                    f"({modification.reason})"
                )

        handler_names = list(dict.fromkeys(
            modification.handler_name
            for modification in self.roll_modifications
        ))
        source_name = self.source_entity_name or "Roll"
        compact = (
            f"{md_color(source_name, 'cyan')}'s roll changed: "
            f"{', '.join(handler_names)}"
        )
        verbose = f"{compact}\n  " + "\n  ".join(detail_lines)
        return CombatLogEntry(
            entry_type=CombatLogEntryType.ROLL_MODIFICATION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=self.target_entity_name,
            target_uuid=(
                str(self.target_entity_uuid)
                if self.target_entity_uuid is not None
                else None
            ),
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            data=RollModificationLogData(
                roll_type=self.roll_type.value.lower(),
                modifications=facts,
            ).model_dump(mode="json"),
        )

class D20RollResultEvent(DiceRollResultEvent):
    """Generic d20 result event when no attack/save/check subtype applies."""

    event_type: EventType = Field(
        default=EventType.D20_ROLL_RESULT,
        description="Base event category for d20 result interception.",
    )
    original_roll: DiceRoll = Field(..., description="Immutable d20 roll kept for audit.")
    final_roll: Optional[DiceRoll] = Field(
        default=None,
        description="Replacement d20 roll after handlers modify the result.",
    )
    dc: Optional[int] = Field(default=None, description="Difficulty class or armor class, if known.")
    bonus: Optional[ModifiableValue] = Field(default=None, description="Modifiers used for the d20 roll.")
    result: Optional[bool] = Field(default=None, description="Success flag set after the outcome is evaluated.")

    @model_validator(mode="after")
    def validate_roll_categories(self) -> "D20RollResultEvent":
        """Keep original and replacement rolls in this event's d20 category."""
        if self.original_roll.roll_type is not self.roll_type:
            raise ValueError("d20 original_roll must match event roll_type")
        if (
            self.final_roll is not None
            and self.final_roll.roll_type is not self.roll_type
        ):
            raise ValueError("d20 final_roll must match event roll_type")
        return self

    def replace_roll(
        self,
        new_roll: DiceRoll,
        handler_name: str,
        reason: str,
    ) -> Self:
        """Return a new event value with the effective d20 roll replaced.

        Args:
            new_roll: Replacement roll result.
            handler_name: Name of the handler making the replacement.
            reason: Human-readable reason for the replacement.

        Returns:
            Modified event value for the queue to store as handler evidence.
        """
        if new_roll.roll_type is not self.roll_type:
            raise ValueError("d20 replacement roll must match event roll_type")
        old_total = self.get_effective_roll().total
        modification = RollModification(
            operation=RollModificationOperation.REPLACE,
            handler_name=handler_name,
            previous_total=old_total,
            final_total=new_roll.total,
            reason=reason,
        )
        return self.with_updates(
            final_roll=new_roll,
            roll_modifications=[*self.roll_modifications, modification],
        )

    def get_effective_roll(self) -> DiceRoll:
        """Return final_roll if modified, otherwise original roll."""
        return (
            self.final_roll
            if self.final_roll is not None
            else self.original_roll
        )

class AttackD20RollResultEvent(D20RollResultEvent):
    """D20 result event for attack rolls."""

    event_type: EventType = Field(
        default=EventType.ATTACK_D20_ROLL_RESULT,
        description="Event category for attack d20 result interception.",
    )
    roll_type: RollType = Field(default=RollType.ATTACK, description="Roll category for attack d20 results.")
    weapon_slot: Optional[WeaponSlot] = Field(default=None, description="Weapon slot used for the attack.")

class SavingThrowD20RollResultEvent(D20RollResultEvent):
    """D20 result event for saving throws."""

    event_type: EventType = Field(
        default=EventType.SAVE_D20_ROLL_RESULT,
        description="Event category for saving throw d20 result interception.",
    )
    roll_type: RollType = Field(default=RollType.SAVE, description="Roll category for saving throw d20 results.")
    ability_name: Optional[ability_types.AbilityName] = Field(
        default=None,
        description="Ability used for the saving throw; absent for ability-neutral death saves.",
    )

class AbilityCheckD20RollResultEvent(D20RollResultEvent):
    """D20 result event for a generic ability check."""

    event_type: EventType = Field(
        default=EventType.CHECK_D20_ROLL_RESULT,
        description="Event category for ability-check d20 result interception.",
    )
    roll_type: RollType = Field(default=RollType.CHECK, description="Roll category for ability-check d20 results.")
    ability_name: ability_types.AbilityName = Field(description="Ability used for the raw check.")

class SkillCheckD20RollResultEvent(D20RollResultEvent):
    """D20 result event for skill checks."""

    event_type: EventType = Field(
        default=EventType.CHECK_D20_ROLL_RESULT,
        description="Event category for skill check d20 result interception.",
    )
    roll_type: RollType = Field(default=RollType.CHECK, description="Roll category for skill check d20 results.")
    skill_name: Optional[ability_types.SkillName] = Field(
        default=None,
        description="Skill used for the check; absent for a generic ability check.",
    )

class DamageRollPacket(BaseModel):
    """One typed damage definition and its original/effective roll result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    damage: Damage = Field(
        description="Damage definition that produced this packet.",
    )
    original_roll: DiceRoll = Field(
        description="Immutable damage roll captured before result handlers.",
    )
    final_roll: DiceRoll = Field(
        description="Effective damage roll consumed after result handlers.",
    )

    @model_validator(mode="after")
    def validate_roll_types(self) -> "DamageRollPacket":
        """Require both packet rolls to remain damage-category results."""
        if self.original_roll.roll_type is not RollType.DAMAGE:
            raise ValueError("damage packet original_roll must be a damage roll")
        if self.final_roll.roll_type is not RollType.DAMAGE:
            raise ValueError("damage packet final_roll must be a damage roll")
        return self

class DamageRollResultEvent(DiceRollResultEvent):
    """Damage-roll result event fired before damage is applied.

    Handlers replace a packet's effective roll while its original roll remains
    available for audit. They may also append complete packets for effects such
    as Divine Smite or monster bonus damage.
    """

    name: str = Field(default="Damage Roll Result", description="Human-readable damage-roll result label.")
    event_type: EventType = Field(
        default=EventType.DAMAGE_ROLL_RESULT,
        description="Event category for damage-roll result interception.",
    )
    roll_type: RollType = Field(default=RollType.DAMAGE, description="Roll category for damage results.")
    weapon_slot: WeaponSlot = Field(description="Weapon slot used for the attack.")
    attack_outcome: AttackOutcome = Field(description="Attack outcome associated with this damage roll.")
    damage_packets: List[DamageRollPacket] = Field(
        min_length=1,
        description=(
            "Ordered damage definitions with their original and effective "
            "rolls; one record is the indivisible rules packet."
        ),
    )

    @model_validator(mode="after")
    def validate_roll_category(self) -> "DamageRollResultEvent":
        """Require the event discriminator to remain damage-category."""
        if self.roll_type is not RollType.DAMAGE:
            raise ValueError("damage result event roll_type must be damage")
        return self

    def _combat_log_packet_details(
        self,
        modification: RollModification,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Project the affected damage packet's type and dice expression."""
        packet_index = modification.packet_index
        if packet_index is None or packet_index >= len(self.damage_packets):
            return None, None
        damage = self.damage_packets[packet_index].damage
        return (
            damage.damage_type.value.lower(),
            f"{damage.dice_numbers}d{damage.damage_dice}",
        )

    def replace_roll(
        self,
        packet_index: int,
        new_roll: DiceRoll,
        handler_name: str,
        reason: str,
    ) -> Self:
        """Return a new event value with one effective damage roll replaced.

        Args:
            packet_index: Index of the damage packet to replace.
            new_roll: Replacement damage roll.
            handler_name: Name of the handler making the replacement.
            reason: Human-readable reason for the replacement.

        Returns:
            Modified event value for the queue to store as handler evidence.
        """
        old_packet = self.damage_packets[packet_index]
        damage_packets = list(self.damage_packets)
        damage_packets[packet_index] = DamageRollPacket(
            damage=old_packet.damage,
            original_roll=old_packet.original_roll,
            final_roll=new_roll,
        )
        modification = RollModification(
            operation=RollModificationOperation.REPLACE,
            handler_name=handler_name,
            packet_index=packet_index,
            previous_total=old_packet.final_roll.total,
            final_total=new_roll.total,
            reason=reason,
        )
        return self.with_updates(
            damage_packets=damage_packets,
            roll_modifications=[*self.roll_modifications, modification],
        )

    def append_damage_roll(
        self,
        damage: Damage,
        roll: DiceRoll,
        handler_name: str,
        reason: str,
    ) -> Self:
        """Return a new event value with one typed damage packet appended."""
        packet_index = len(self.damage_packets)
        modification = RollModification(
            operation=RollModificationOperation.APPEND,
            handler_name=handler_name,
            packet_index=packet_index,
            final_total=roll.total,
            reason=reason,
        )
        return self.with_updates(
            damage_packets=[
                *self.damage_packets,
                DamageRollPacket(
                    damage=damage,
                    original_roll=roll,
                    final_roll=roll,
                ),
            ],
            roll_modifications=[*self.roll_modifications, modification],
        )

class HealRollResultEvent(DiceRollResultEvent):
    """Healing-roll result event fired before healing is applied.

    Mirrors the damage-roll result pattern for effects that maximize or replace
    healing dice.
    """

    name: str = Field(default="Heal Roll Result", description="Human-readable healing-roll result label.")
    event_type: EventType = Field(
        default=EventType.HEAL_ROLL_RESULT,
        description="Event category for healing-roll result interception.",
    )
    roll_type: RollType = Field(default=RollType.HEAL, description="Roll category for healing results.")
    spell_name: str = Field(default="", description="Name of the healing spell or effect.")
    original_roll: DiceRoll = Field(description="Original immutable healing roll.")
    final_roll: DiceRoll = Field(description="Healing roll to apply after handler modifications.")

    @model_validator(mode="after")
    def validate_roll_categories(self) -> "HealRollResultEvent":
        """Require healing events to contain only healing-category rolls."""
        if self.roll_type is not RollType.HEAL:
            raise ValueError("heal result event roll_type must be heal")
        if self.original_roll.roll_type is not RollType.HEAL:
            raise ValueError("heal original_roll must be a healing roll")
        if self.final_roll.roll_type is not RollType.HEAL:
            raise ValueError("heal final_roll must be a healing roll")
        return self

    def replace_roll(
        self,
        new_roll: DiceRoll,
        handler_name: str,
        reason: str,
    ) -> Self:
        """Return a new event value with the effective healing roll replaced.

        Args:
            new_roll: Replacement healing roll.
            handler_name: Name of the handler making the replacement.
            reason: Human-readable reason for the replacement.

        Returns:
            Modified event value for the queue to store as handler evidence.
        """
        if new_roll.roll_type is not RollType.HEAL:
            raise ValueError("heal replacement roll must be a healing roll")
        modification = RollModification(
            operation=RollModificationOperation.REPLACE,
            handler_name=handler_name,
            previous_total=self.final_roll.total,
            final_total=new_roll.total,
            reason=reason,
        )
        return self.with_updates(
            final_roll=new_roll,
            roll_modifications=[*self.roll_modifications, modification],
        )

class TakeDamageEvent(Event):
    """Damage-application event for tracking, reduction, and cancellation.

    Handlers use this event to reduce, replace, cancel, or react to incoming
    damage. `final_damage` overrides `total_damage` when present.
    """

    name: str = Field(default="Take Damage", description="Human-readable damage-application label.")
    event_type: EventType = Field(
        default=EventType.TAKE_DAMAGE,
        description="Event category for damage application.",
    )
    total_damage: int = Field(description="Total damage before any modifications")
    damage_rolls: List[DiceRoll] = Field(default_factory=list, description="Individual damage rolls")
    damages: List['Damage'] = Field(default_factory=list, description="Damage specifications (types)")
    effect_id: Optional[str] = Field(
        default=None,
        description="Stable identity of the effect causing this damage application.",
    )
    final_damage: Optional[int] = Field(
        default=None,
        description="Modified damage after handlers. If None, use total_damage."
    )
    normal_hit_point_damage_cap: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Maximum normal hit points this packet may remove after defenses and temporary hit points. "
            "Multiple survival effects compose by retaining the lowest cap."
        ),
    )
    resulting_hp: Optional[int] = Field(
        default=None,
        description="Entity HP after damage applied (set at EFFECT phase)"
    )
    resolution: Optional[DamageResolution] = Field(
        default=None,
        description="Factual defense and hit-point allocation attached at completion.",
    )

    def get_effective_damage(self) -> int:
        """Get the damage amount to apply (final_damage if set, else total_damage)."""
        return self.final_damage if self.final_damage is not None else self.total_damage

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for taking damage.

        Used for damage from zones, terrain, environmental effects, etc.
        Attack damage is logged by the attack event itself.
        """
        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "terrain"

        damage = self.get_effective_damage()

        damage_type_str = "damage"
        if self.damages:
            damage_type_str = str(self.damages[0].damage_type.value).lower()

        if self.canceled:
            reason = self.status_message or "blocked"
            compact_text = f"{md_color(target_name, 'yellow')} takes {md_color('0', 'green')} {damage_type_str} ({reason})"
            return CombatLogEntry(
                entry_type=CombatLogEntryType.DAMAGE_TAKEN,
                source_name=source_name,
                source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
                target_name=target_name,
                target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
                compact=compact_text,
                verbose=compact_text,
                detailed=compact_text,
                data=DamageTakenLogData(
                    target_name=target_name,
                    damage=0,
                    damage_type=damage_type_str,
                    source_name=source_name,
                    effect_id=self.effect_id,
                    blocked=True,
                    blocked_reason=reason,
                ).model_dump(exclude_none=True),
                success=False
            )

        compact_text = f"{md_color(target_name, 'yellow')} takes {md_color(str(damage), 'red')} {damage_type_str}"

        verbose_text = f"{md_color(target_name, 'yellow')} takes {md_color(str(damage), 'red')} {damage_type_str}"
        if source_name and source_name != "terrain":
            verbose_text += f" from {md_color(source_name, 'cyan')}"

        detailed_text = verbose_text
        if self.damage_rolls:
            roll_strs = []
            for roll in self.damage_rolls:
                if roll.results:
                    roll_strs.append(f"{roll.results}")
            if roll_strs:
                detailed_text += f"\n  Rolls: {', '.join(roll_strs)}"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.DAMAGE_TAKEN,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=DamageTakenLogData(
                target_name=target_name,
                damage=damage,
                damage_type=damage_type_str,
                source_name=source_name,
                effect_id=self.effect_id,
            ).model_dump(exclude_none=True),
            success=True
        )

class DamageAppliedEvent(Event):
    """Factual post-mitigation boundary for positive damage.

    `TakeDamageEvent` represents the interruptible incoming packet. This event
    is emitted only after defenses and temporary hit points have been applied,
    and only when a positive amount of damage was actually absorbed or lost.
    Consequences of taking damage subscribe to this event rather than the
    mutable incoming packet.
    """

    name: str = Field(default="Damage Applied", description="Human-readable applied-damage label.")
    event_type: EventType = Field(
        default=EventType.DAMAGE_APPLIED,
        description="Event category for a positive post-mitigation damage result.",
    )
    applied_damage: int = Field(
        gt=0,
        description="Positive damage remaining after defenses, including temporary hit points lost.",
    )
    normal_hit_point_damage: int = Field(
        ge=0,
        description="Damage applied beyond temporary hit points to the normal hit-point pool.",
    )
    temporary_hit_point_damage: int = Field(
        ge=0,
        description="Temporary hit points consumed by the damage application.",
    )
    resulting_normal_hp: int = Field(
        description="Target normal hit points immediately after damage application.",
    )
    resulting_temporary_hp: int = Field(
        ge=0,
        description="Target temporary hit points immediately after damage application.",
    )
    damage_type: DamageType = Field(description="Primary damage type used by the incoming packet.")
    damages: List['Damage'] = Field(
        default_factory=list,
        description="Typed damage components carried by the incoming packet.",
    )
    effect_id: Optional[str] = Field(
        default=None,
        description="Stable identity of the effect that caused the applied damage.",
    )
    resolution: Optional[DamageResolution] = Field(
        default=None,
        description="Complete resolution of the parent incoming damage packet.",
    )

class HealEvent(Event):
    """Healing-application event for HP restoration and blocking."""

    name: str = Field(default="Heal", description="Human-readable healing event label.")
    event_type: EventType = Field(default=EventType.HEAL, description="Event category for healing application.")
    total_healing: int = Field(default=0, description="Requested healing amount before HP caps.")
    actual_healing: int = Field(default=0, description="HP actually restored after caps and blockers.")
    source_description: str = Field(default="", description="Human-readable description of the healing source.")
    was_blocked: bool = Field(default=False, description="Whether healing was blocked by an effect.")
    spell_level: int = Field(default=0, description="Spell level used, or 0 for non-spell healing.")

    resulting_hp: Optional[int] = Field(
        default=None,
        description="Entity HP after healing applied (set at EFFECT phase)"
    )
    resulting_normal_hp: Optional[int] = Field(
        default=None,
        description="Entity normal hit points immediately after healing.",
    )
    resulting_temporary_hp: Optional[int] = Field(
        default=None,
        ge=0,
        description="Entity temporary hit points immediately after healing.",
    )

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for healing application."""
        target_name = self.target_entity_name or "Unknown"

        if self.was_blocked:
            text = f"{md_color(target_name, 'cyan')} healing blocked!"
            return CombatLogEntry(
                entry_type=CombatLogEntryType.HEAL,
                source_name=target_name,
                source_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
                compact=text,
                verbose=text,
                detailed=text,
                data=HealLogData(
                    entity_name=target_name,
                    entity_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
                    amount=0,
                    source_description=self.source_description
                ).model_dump(),
                success=False
            )

        amount = self.actual_healing
        compact = f"{md_color(target_name, 'cyan')} heals for {md_color(str(amount), 'green')} HP"
        verbose = compact
        if self.source_description:
            verbose = f"{compact} ({self.source_description})"
        detailed = verbose

        return CombatLogEntry(
            entry_type=CombatLogEntryType.HEAL,
            source_name=target_name,
            source_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=HealLogData(
                entity_name=target_name,
                entity_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
                amount=amount,
                source_description=self.source_description
            ).model_dump(),
            success=True
        )

class TemporaryHitPointsEvent(Event):
    """Interruptible grant of a non-stacking temporary-hit-point pool."""

    name: str = Field(default="Temporary Hit Points", description="Human-readable event label.")
    event_type: EventType = Field(
        default=EventType.TEMPORARY_HIT_POINTS,
        description="Event category for temporary-hit-point grants.",
    )
    requested_amount: int = Field(
        ge=0,
        description="Temporary hit points offered before the non-stacking rule.",
    )
    previous_amount: int = Field(
        default=0,
        ge=0,
        description="Temporary hit points immediately before the grant.",
    )
    resulting_amount: int = Field(
        default=0,
        ge=0,
        description="Temporary hit points immediately after the grant.",
    )
    source_description: str = Field(
        default="",
        description="Rules-facing description of the granting effect.",
    )

    def generate_combat_log(self) -> CombatLogEntry:
        """Describe whether the grant replaced the current temporary HP."""
        target_name = self.target_entity_name or "Unknown"
        if self.resulting_amount > self.previous_amount:
            compact = (
                f"{md_color(target_name, 'cyan')} gains "
                f"{md_color(str(self.resulting_amount), 'green')} temporary HP"
            )
        else:
            compact = (
                f"{md_color(target_name, 'cyan')} retains "
                f"{md_color(str(self.resulting_amount), 'green')} temporary HP"
            )
        verbose = (
            f"{compact} ({self.source_description})"
            if self.source_description
            else compact
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.TEMPORARY_HIT_POINTS,
            source_name=self.source_entity_name or "",
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=(
                str(self.target_entity_uuid)
                if self.target_entity_uuid is not None
                else ""
            ),
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            data=TemporaryHitPointsLogData(
                entity_name=target_name,
                entity_uuid=(
                    str(self.target_entity_uuid)
                    if self.target_entity_uuid is not None
                    else ""
                ),
                requested_amount=self.requested_amount,
                previous_amount=self.previous_amount,
                resulting_amount=self.resulting_amount,
                source_description=self.source_description,
            ).model_dump(),
            success=self.resulting_amount > self.previous_amount,
        )
