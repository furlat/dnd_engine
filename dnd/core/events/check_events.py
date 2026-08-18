"""Ability checks, skill checks, and saving-throw event facts."""

from typing import List, Optional, Union

from pydantic import Field

from dnd.core.combat_log import (
    AbilityCheckLogData,
    CombatLogEntry,
    CombatLogEntryType,
    DiceRollDisplay,
    ModifierBreakdown,
    SavingThrowLogData,
    SkillCheckLogData,
    md_breakdown,
    md_color,
    md_d20_roll,
)
from dnd.types.saving_throws import SavingThrowContext
from dnd.core.dice import Dice, DiceRoll
from dnd.core.events.events_registry import Event, EventType
from dnd.core.values import ModifiableValue
from dnd.types import abilities as ability_types

class D20Event(Event):
    """Legacy event payload for a resolved d20 check."""

    name: str = Field(default="D20", description="Human-readable d20 event label.")
    dc: Optional[Union[int, ModifiableValue]] = Field(
        default=None,
        description="Difficulty class for the roll, either fixed or modifiable.",
    )
    bonus: Optional[Union[int, ModifiableValue]] = Field(
        default=0,
        description="Roll bonus, either fixed or represented by a modifiable value.",
    )
    dice: Optional[Dice] = Field(default=None, description="Dice object used to create the roll.")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="Resolved dice roll.")
    result: Optional[bool] = Field(default=None, description="Whether the roll met or exceeded its DC.")

    def get_dc(self) -> Optional[int]:
        """Return the current numeric difficulty class."""
        if self.dc is None:
            return None
        if isinstance(self.dc, ModifiableValue):
            return self.dc.normalized_score
        return self.dc

class SavingThrowEvent(D20Event):
    """Legacy event payload for a resolved saving throw."""

    name: str = Field(default="Saving Throw", description="Human-readable saving throw label.")
    ability_name: ability_types.AbilityName = Field(description="Ability used for the saving throw.")
    saving_throw_context: Optional[SavingThrowContext] = Field(
        default=None,
        description=(
            "Exact authored cause, effect identity, magical fact, and closed "
            "rule semantics for this saving throw."
        ),
    )
    condition_context: Optional[str] = Field(
        default=None,
        description="Optional condition name this save is made against, such as Poisoned.",
    )
    event_type: EventType = Field(
        default=EventType.SAVING_THROW,
        description="Event category for saving throw events.",
    )

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this saving throw event.

        Uses self.* fields only - no external lookups. Entity names must be
        populated when the event is created.
        """
        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "Unknown"

        dc = self.get_dc() or 0

        roll = DiceRollDisplay(
            dice_str="d20",
            results=[],
            bonus=0,
            total=0
        )

        if self.dice_roll:
            results = self.dice_roll.results
            if isinstance(results, list):
                roll.results = list(results)
                roll.all_d20_rolls = list(results)
                roll.d20_used = results[0] if results else 0

                adv_status = self.dice_roll.advantage_status
                if adv_status:
                    adv_value = adv_status.value.lower()
                    roll.advantage_status = adv_value
                    if len(results) >= 2:
                        if adv_value == "advantage":
                            roll.d20_used = max(results)
                        elif adv_value == "disadvantage":
                            roll.d20_used = min(results)
            elif isinstance(results, int):
                roll.results = [results]
                roll.d20_used = results

            roll.bonus = self.dice_roll.bonus
            roll.total = self.dice_roll.total

        bonus_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_breakdown():
                bonus_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        advantage_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_full_advantage_breakdown():
                adv_val = mod.get('value', 'inactive')
                if adv_val == 'advantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
                    ))
                elif adv_val == 'disadvantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
                    ))

        success = self.result if self.result is not None else (roll.total >= dc if dc > 0 else None)

        ability_display = self.ability_name.upper()[:3]

        success_str = md_color("succeeds", "green") if success else md_color("fails", "red")

        compact_text = f"{md_color(target_name, 'cyan')} {success_str} {md_color(ability_display, 'yellow')} save (DC {dc})"

        d20_str = md_d20_roll(roll)
        bonus_str = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)
        verbose_text = f"{md_color(target_name, 'cyan')} {md_color(ability_display, 'yellow')} save vs DC {dc}"
        verbose_text += f"\n  Save: {d20_str} {bonus_str} = {roll.total} → {success_str}"

        detailed_text = f"{md_color(target_name, 'cyan')} {md_color(ability_display, 'yellow')} save vs DC {dc}"
        breakdown_str = md_breakdown(bonus_breakdown)
        detailed_text += f"\n  Save: {d20_str} {bonus_str}"
        if breakdown_str:
            detailed_text += f" {breakdown_str}"
        detailed_text += f" = {roll.total} → {success_str}"

        data = SavingThrowLogData(
            entity_name=target_name,
            entity_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else str(self.source_entity_uuid),
            ability=self.ability_name,
            dc=dc,
            roll=roll,
            bonus_breakdown=bonus_breakdown,
            advantage_breakdown=advantage_breakdown,
            success=success or False,
            source_name=source_name if source_name != target_name else None
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.SAVING_THROW,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data.model_dump(),
            success=success
        )

class SkillCheckEvent(D20Event):
    """Typed request and resolved outcome for one skill check."""

    name: str = Field(default="Skill Check", description="Human-readable skill check label.")
    skill_name: ability_types.SkillName = Field(description="Skill used for the check.")
    event_type: EventType = Field(
        default=EventType.SKILL_CHECK,
        description="Event category for skill check events.",
    )

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this skill check event.

        Uses self.* fields only - no external lookups. Entity names must be
        populated when the event is created.
        """
        source_name = self.source_entity_name or "Unknown"

        dc = self.get_dc()

        roll = DiceRollDisplay(
            dice_str="d20",
            results=[],
            bonus=0,
            total=0
        )

        if self.dice_roll:
            results = self.dice_roll.results
            if isinstance(results, list):
                roll.results = list(results)
                roll.all_d20_rolls = list(results)
                roll.d20_used = results[0] if results else 0

                adv_status = self.dice_roll.advantage_status
                if adv_status:
                    adv_value = adv_status.value.lower()
                    roll.advantage_status = adv_value
                    if len(results) >= 2:
                        if adv_value == "advantage":
                            roll.d20_used = max(results)
                        elif adv_value == "disadvantage":
                            roll.d20_used = min(results)
            elif isinstance(results, int):
                roll.results = [results]
                roll.d20_used = results

            roll.bonus = self.dice_roll.bonus
            roll.total = self.dice_roll.total

        bonus_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_breakdown():
                bonus_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        advantage_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_full_advantage_breakdown():
                adv_val = mod.get('value', 'inactive')
                if adv_val == 'advantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
                    ))
                elif adv_val == 'disadvantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
                    ))

        success = self.result if self.result is not None else (roll.total >= dc if dc is not None and dc > 0 else None)

        skill_display = self.skill_name.replace('_', ' ').title()

        d20_str = md_d20_roll(roll)
        bonus_str = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)
        breakdown_str = md_breakdown(bonus_breakdown)

        if dc is not None:
            success_str = md_color("succeeds", "green") if success else md_color("fails", "red")

            compact_text = f"{md_color(source_name, 'cyan')} {success_str} {md_color(skill_display, 'yellow')} check (DC {dc})"

            verbose_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check vs DC {dc}"
            verbose_text += f"\n  {skill_display}: {d20_str} {bonus_str} = {roll.total} → {success_str}"

            detailed_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check vs DC {dc}"
            detailed_text += f"\n  {skill_display}: {d20_str} {bonus_str}"
            if breakdown_str:
                detailed_text += f" {breakdown_str}"
            detailed_text += f" = {roll.total} → {success_str}"
        else:
            compact_text = f"{md_color(source_name, 'cyan')} rolls {md_color(skill_display, 'yellow')}: {md_color(str(roll.total), 'cyan')}"
            verbose_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check"
            verbose_text += f"\n  {skill_display}: {d20_str} {bonus_str} = {roll.total}"
            detailed_text = verbose_text
            if breakdown_str:
                detailed_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check"
                detailed_text += f"\n  {skill_display}: {d20_str} {bonus_str} {breakdown_str} = {roll.total}"

        data = SkillCheckLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            skill=self.skill_name,
            dc=dc,
            roll=roll,
            bonus_breakdown=bonus_breakdown,
            advantage_breakdown=advantage_breakdown,
            success=success
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.SKILL_CHECK,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data.model_dump(),
            success=success
        )

class AbilityCheckEvent(D20Event):
    """Typed request and resolved outcome for one raw ability check."""

    name: str = Field(default="Ability Check", description="Human-readable ability check label.")
    ability_name: ability_types.AbilityName = Field(description="Ability used for the raw check.")
    event_type: EventType = Field(
        default=EventType.ABILITY_CHECK,
        description="Event category for raw ability-check events.",
    )

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate one exact raw ability-check combat-log entry."""
        source_name = self.source_entity_name or "Unknown"
        dc = self.get_dc()
        roll = DiceRollDisplay(dice_str="d20", results=[], bonus=0, total=0)
        if self.dice_roll:
            results = self.dice_roll.results
            if isinstance(results, list):
                roll.results = list(results)
                roll.all_d20_rolls = list(results)
                roll.d20_used = results[0] if results else 0
                advantage = self.dice_roll.advantage_status
                if advantage:
                    advantage_value = advantage.value.lower()
                    roll.advantage_status = advantage_value
                    if len(results) >= 2:
                        roll.d20_used = (
                            max(results)
                            if advantage_value == "advantage"
                            else min(results)
                            if advantage_value == "disadvantage"
                            else roll.d20_used
                        )
            elif isinstance(results, int):
                roll.results = [results]
                roll.d20_used = results
            roll.bonus = self.dice_roll.bonus
            roll.total = self.dice_roll.total

        bonus_breakdown: List[ModifierBreakdown] = []
        advantage_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            bonus_breakdown = [
                ModifierBreakdown(
                    name=modifier.get("name", "Unknown"),
                    value=modifier.get("value", 0),
                    source=modifier.get("source", "self"),
                )
                for modifier in self.bonus.get_breakdown()
            ]
            for modifier in self.bonus.get_full_advantage_breakdown():
                value = modifier.get("value", "inactive")
                if value in {"advantage", "disadvantage"}:
                    advantage_breakdown.append(
                        ModifierBreakdown(
                            name=modifier.get("name", "Unknown"),
                            value=1 if value == "advantage" else -1,
                            source=modifier.get("source", "self"),
                        ),
                    )

        success = (
            self.result
            if self.result is not None
            else roll.total >= dc
            if dc is not None
            else None
        )
        ability_display = self.ability_name.title()
        d20_display = md_d20_roll(roll)
        bonus_display = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)
        breakdown_display = md_breakdown(bonus_breakdown)
        if dc is None:
            compact = (
                f"{md_color(source_name, 'cyan')} rolls "
                f"{md_color(ability_display, 'yellow')}: "
                f"{md_color(str(roll.total), 'cyan')}"
            )
            verbose = (
                f"{md_color(source_name, 'cyan')} "
                f"{md_color(ability_display, 'yellow')} check"
                f"\n  {ability_display}: {d20_display} {bonus_display} = {roll.total}"
            )
            detailed = verbose
            if breakdown_display:
                detailed = (
                    f"{md_color(source_name, 'cyan')} "
                    f"{md_color(ability_display, 'yellow')} check"
                    f"\n  {ability_display}: {d20_display} {bonus_display} "
                    f"{breakdown_display} = {roll.total}"
                )
        else:
            success_display = (
                md_color("succeeds", "green")
                if success
                else md_color("fails", "red")
            )
            compact = (
                f"{md_color(source_name, 'cyan')} {success_display} "
                f"{md_color(ability_display, 'yellow')} check (DC {dc})"
            )
            verbose = (
                f"{md_color(source_name, 'cyan')} "
                f"{md_color(ability_display, 'yellow')} check vs DC {dc}"
                f"\n  {ability_display}: {d20_display} {bonus_display} = "
                f"{roll.total} → {success_display}"
            )
            detailed = (
                f"{md_color(source_name, 'cyan')} "
                f"{md_color(ability_display, 'yellow')} check vs DC {dc}"
                f"\n  {ability_display}: {d20_display} {bonus_display}"
            )
            if breakdown_display:
                detailed += f" {breakdown_display}"
            detailed += f" = {roll.total} → {success_display}"

        data = AbilityCheckLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            ability=self.ability_name,
            dc=dc,
            roll=roll,
            bonus_breakdown=bonus_breakdown,
            advantage_breakdown=advantage_breakdown,
            success=success,
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.ABILITY_CHECK,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=data.model_dump(),
            success=success,
        )
