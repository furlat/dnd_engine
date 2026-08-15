from typing import Optional, List, Literal, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, computed_field, field_validator
from dnd.core.damage import DamageComponentResolution, DamageResolution
from dnd.types.life import LifeState
from dnd.core.values import ModifiableValue
from dnd.types.damage import DamageType
from dnd.core.modifiers import NumericalModifier, ResistanceModifier
from dnd.types.damage import ResistanceStatus
from dnd.types.rolls import HitDieSize

from random import randint
from functools import cached_property

from dnd.core.base_block import BaseBlock


class HitDiceConfig(BaseModel):
    """Configuration used to materialize a hit-dice block."""

    hit_dice_value: HitDieSize = Field(
        default=6,
        description="Die size used by each hit die, such as 8 for d8.",
    )
    hit_dice_value_modifiers: List[Tuple[str, int]] = Field(
        default=[],
        description="Static modifiers applied to the hit-dice die size.",
    )
    hit_dice_count: int = Field(default=1, description="Number of hit dice in this block.")
    hit_dice_count_modifiers: List[Tuple[str, int]] = Field(
        default=[],
        description="Static modifiers applied to the number of hit dice.",
    )
    mode: Literal["average", "maximums","roll"] = Field(
        default="average",
        description="Policy used to convert hit dice into maximum hit points.",
    )
    ignore_first_level: bool = Field(
        default=False,
        description="Whether first-level maximum-hit-die treatment is skipped.",
    )
    spent_hit_dice: int = Field(default=0, ge=0, description="Hit dice already spent for short-rest healing.")


class HitDiceHealingResult(BaseModel):
    """Result of spending one hit die for short-rest healing."""

    hit_dice_index: int = Field(description="Index of the hit-dice block spent.")
    die_value: int = Field(description="Die size rolled, such as 8 for d8.")
    roll: int = Field(description="Natural die result.")
    constitution_modifier: int = Field(description="Constitution modifier added to the roll.")
    total_healing: int = Field(description="Healing requested before HP cap and blockers.")
    actual_healing: int = Field(default=0, description="HP restored after cap and blockers.")

class HitDice(BaseBlock):
    """Hit-dice block used for maximum HP and short-rest healing.

    Attributes:
        name: Block name used in health block indexes.
        hit_dice_value: Modifiable die size, such as d8 or d10.
        hit_dice_count: Modifiable count of dice in this block.
        mode: Policy used to convert hit dice into maximum hit points.
        ignore_first_level: Whether first-level maximum-hit-die treatment is skipped.
        spent_hit_dice: Number of dice already spent on short-rest healing.
    """

    name: str = Field(default="HitDice", description="Block name used in health block indexes.")
    hit_dice_value: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=6, value_name="Hit Dice Value"),
        description="Modifiable die size used by each hit die.",
    )
    hit_dice_count: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=1, value_name="Hit Dice Count"),
        description="Modifiable number of hit dice in this block.",
    )
    mode: Literal["average", "maximums","roll"] = Field(
        default="average",
        description="Policy used to convert hit dice into maximum hit points.",
    )
    ignore_first_level: bool = Field(
        default=False,
        description="Whether first-level maximum-hit-die treatment is skipped.",
    )
    spent_hit_dice: int = Field(default=0, ge=0, description="Number of dice from this block spent on short-rest healing.")

    @computed_field
    @cached_property
    def hit_points(self) -> int:
        """
        Calculate the hit points based on the hit dice and mode.

        Returns:
            int: The calculated hit points.

        Raises:
            ValueError: If an invalid mode is specified.
        """
        first_level_hit_points = self.hit_dice_value.score if not self.ignore_first_level else 0
        remaining_dice_count = self.hit_dice_count.score - 1 if not self.ignore_first_level else self.hit_dice_count.score
        if self.mode == "average":
            return first_level_hit_points + remaining_dice_count * ((self.hit_dice_value.score // 2)+1)
        elif self.mode == "maximums":
            return first_level_hit_points + remaining_dice_count * self.hit_dice_value.score
        elif self.mode == "roll":
            return sum(randint(1, self.hit_dice_value.score) for _ in range(self.hit_dice_count.score))
        else:
            raise ValueError(f"Invalid mode: {self.mode}")

    @computed_field
    @property
    def available_hit_dice(self) -> int:
        """Return unspent hit dice in this block."""
        return max(0, self.hit_dice_count.normalized_score - self.spent_hit_dice)

    def spend(self, count: int = 1) -> None:
        """Spend hit dice from this block.

        Args:
            count: Number of hit dice to spend.

        Raises:
            ValueError: If count is invalid or exceeds available dice.
        """
        if count < 1:
            raise ValueError("count must be at least 1")
        if count > self.available_hit_dice:
            raise ValueError(f"Not enough hit dice available to spend {count}")
        self.spent_hit_dice += count

    def recover(self, count: int = 1) -> int:
        """Recover spent hit dice.

        Args:
            count: Maximum number of spent hit dice to recover.

        Returns:
            Number of hit dice actually recovered.

        Raises:
            ValueError: If count is invalid.
        """
        if count < 1:
            raise ValueError("count must be at least 1")
        recovered = min(count, self.spent_hit_dice)
        self.spent_hit_dice -= recovered
        return recovered

    def roll_spent_die(self) -> int:
        """Roll this block's hit die for short-rest healing."""
        return randint(1, self.hit_dice_value.normalized_score)

    @field_validator("hit_dice_value")
    def check_hit_dice_value(cls, v: ModifiableValue) -> ModifiableValue:
        """
        Validate that the hit dice value is one of the allowed values.

        Args:
            v (ModifiableValue): The hit dice value to validate.

        Returns:
            ModifiableValue: The validated hit dice value.

        Raises:
            ValueError: If the hit dice value is not one of the allowed values.
        """
        allowed_dice = [4,6,8,10,12]
        if v.score not in allowed_dice:
            raise ValueError(f"Hit dice value must be one of the following: {allowed_dice} instead of {v.score}")
        return v

    @field_validator("hit_dice_count")
    def check_hit_dice_count(cls, v: ModifiableValue) -> ModifiableValue:
        """
        Validate that the hit dice count is greater than 0.

        Args:
            v (ModifiableValue): The hit dice count to validate.

        Returns:
            ModifiableValue: The validated hit dice count.

        Raises:
            ValueError: If the hit dice count is less than 1.
        """
        if v.score < 1:
            raise ValueError(f"Hit dice count must be greater than 0 instead of {v.score}")
        return v

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "HitDice", source_entity_name: Optional[str] = None,
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None,
                config: Optional[HitDiceConfig] = None) -> 'HitDice':
        """Create a hit-dice block from optional configuration.

        Args:
            source_entity_uuid: Entity UUID that owns this hit-dice block.
            name: Block name used in health indexes.
            source_entity_name: Optional source entity display name.
            target_entity_uuid: Optional target entity UUID.
            target_entity_name: Optional target entity display name.
            config: Optional hit-dice configuration to materialize.

        Returns:
            HitDice block with modifiable die size and count values.
        """
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            modifiable_hit_dice_value = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=config.hit_dice_value, value_name="Hit Dice Value")
            for modifier in config.hit_dice_value_modifiers:
                modifiable_hit_dice_value.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            modifiable_hit_dice_count = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=config.hit_dice_count, value_name="Hit Dice Count")
            for modifier in config.hit_dice_count_modifiers:
                modifiable_hit_dice_count.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name,
                       hit_dice_value=modifiable_hit_dice_value, hit_dice_count=modifiable_hit_dice_count, mode=config.mode, ignore_first_level=config.ignore_first_level, spent_hit_dice=config.spent_hit_dice)
class HealthConfig(BaseModel):
    """Configuration used to materialize a health block."""

    life_state: LifeState = Field(
        default=LifeState.ALIVE,
        description="Initial authoritative life state.",
    )
    hit_dices: List[HitDiceConfig] = Field(default_factory=list, description="Hit-dice blocks used for HP and short rests.")
    max_hit_points_bonus: int = Field(default=0, description="Static bonus added to maximum hit points.")
    max_hit_points_bonus_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="Named static modifiers applied to the maximum-hit-point bonus.",
    )
    temporary_hit_points: int = Field(default=0, description="Initial temporary hit points.")
    temporary_hit_points_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="Named static modifiers applied to temporary hit points.",
    )
    damage_reduction: int = Field(default=0, description="Flat damage reduction applied after type multipliers.")
    damage_reduction_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="Named static modifiers applied to flat damage reduction.",
    )
    vulnerabilities: List[DamageType] = Field(default_factory=list, description="Damage types that double incoming damage.")
    resistances: List[DamageType] = Field(default_factory=list, description="Damage types that halve incoming damage.")
    immunities: List[DamageType] = Field(default_factory=list, description="Damage types that reduce incoming damage to zero.")


DamageApplicationPreview = DamageResolution


class Health(BaseBlock):
    """Entity health state and damage/healing primitives.

    Attributes:
        name: Block name used in entity composition indexes.
        hit_dices: Hit-dice blocks used for maximum HP and short rests.
        max_hit_points_bonus: Modifiable bonus added to maximum HP.
        temporary_hit_points: Modifiable temporary HP pool.
        damage_taken: Normal HP damage currently marked on the entity.
        damage_reduction: Flat reduction and type multiplier channel.
        healing_blocked: Whether healing effects currently restore no HP.
    """

    name: str = Field(default="Health", description="Block name used in entity composition indexes.")
    life_state: LifeState = Field(
        default=LifeState.ALIVE,
        description="Authoritative lifecycle state for the owning entity.",
    )
    hit_dices: List[HitDice] = Field(
        default_factory=lambda: [HitDice.create(source_entity_uuid=uuid4(),name="HitDice")],
        description="Hit-dice blocks used for maximum HP and short rests.",
    )
    max_hit_points_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Max Hit Points Bonus"), description="Max Hit Points Bonus, e.g. Aid spell")
    temporary_hit_points: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Temporary Hit Points"), description="Temporary Hit Points, e.g. False Life spell")
    damage_taken: int = Field(default=0,ge=0, description="The amount of damage taken")
    damage_reduction: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Damage Reduction"), description="Damage Reduction, e.g. Damage Resistance")
    healing_blocked: bool = Field(default=False, description="If True, entity cannot regain HP (e.g., Chill Touch)")

    def get_resistance(self,damage_type: DamageType) -> ResistanceStatus:
        return self.damage_reduction.resistance[damage_type]

    @computed_field
    @property
    def hit_dices_total_hit_points(self) -> int:
        """
        Calculate the total hit points from all hit dice.

        Returns:
            int: The sum of hit points from all hit dice.
        """
        return sum(hit_dice.hit_points for hit_dice in self.hit_dices)
    @computed_field
    @property
    def total_hit_dices_number(self) -> int:
        """
        Calculate the total number of hit dice.

        Returns:
            int: The sum of hit dice counts from all hit dice.
        """
        return sum(hit_dice.hit_dice_count.score for hit_dice in self.hit_dices)

    @computed_field
    @property
    def spent_hit_dices_number(self) -> int:
        """Return the total number of spent hit dice."""
        return sum(hit_dice.spent_hit_dice for hit_dice in self.hit_dices)

    @computed_field
    @property
    def available_hit_dices_number(self) -> int:
        """Return the total number of available hit dice."""
        return sum(hit_dice.available_hit_dice for hit_dice in self.hit_dices)

    def get_hit_dice(self, hit_dice_index: int = 0) -> HitDice:
        """Return a hit-dice block by index.

        Args:
            hit_dice_index: Index of the hit-dice block.

        Returns:
            Hit-dice block at the requested index.

        Raises:
            ValueError: If the index is out of range.
        """
        if hit_dice_index < 0 or hit_dice_index >= len(self.hit_dices):
            raise ValueError(f"Hit dice index {hit_dice_index} out of range")
        return self.hit_dices[hit_dice_index]

    def add_hit_dice(self, hit_dice: HitDice) -> None:
        """Attach one exact source-owned hit-dice block."""
        if hit_dice.source_entity_uuid != self.source_entity_uuid:
            raise ValueError("hit dice must belong to the health block owner")
        if any(existing.uuid == hit_dice.uuid for existing in self.hit_dices):
            raise ValueError(f"hit dice {hit_dice.uuid} is already attached")
        self.hit_dices.append(hit_dice)

    def remove_hit_dice_by_uuid(self, hit_dice_uuid: UUID) -> bool:
        """Detach and unregister exactly one hit-dice source."""
        for index, hit_dice in enumerate(self.hit_dices):
            if hit_dice.uuid != hit_dice_uuid:
                continue
            del self.hit_dices[index]
            type(hit_dice).unregister(hit_dice.uuid)
            return True
        return False

    def spend_hit_die(
        self,
        constitution_modifier: int,
        hit_dice_index: int = 0,
    ) -> HitDiceHealingResult:
        """Spend and roll one hit die for short-rest healing.

        Args:
            constitution_modifier: Constitution modifier added to the roll.
            hit_dice_index: Index of the hit-dice block to spend.

        Returns:
            Hit-dice healing roll result before HP caps and blockers.
        """
        hit_die = self.get_hit_dice(hit_dice_index)
        hit_die.spend()
        roll = hit_die.roll_spent_die()
        return HitDiceHealingResult(
            hit_dice_index=hit_dice_index,
            die_value=hit_die.hit_dice_value.normalized_score,
            roll=roll,
            constitution_modifier=constitution_modifier,
            total_healing=max(0, roll + constitution_modifier),
        )

    def recover_hit_dice(self, count: int) -> int:
        """Recover spent hit dice in block order.

        Args:
            count: Maximum number of spent hit dice to recover.

        Returns:
            Number of hit dice actually recovered.

        Raises:
            ValueError: If count is negative.
        """
        if count < 0:
            raise ValueError("count must be non-negative")
        remaining = count
        recovered = 0
        for hit_die in self.hit_dices:
            if remaining <= 0:
                break
            if hit_die.spent_hit_dice > 0:
                recovered_now = hit_die.recover(remaining)
                recovered += recovered_now
                remaining -= recovered_now
        return recovered

    def recover_long_rest_hit_dice(self) -> int:
        """Recover the SRD long-rest amount of spent hit dice."""
        total_hit_dice = self.total_hit_dices_number
        if total_hit_dice <= 0:
            return 0
        return self.recover_hit_dice(max(1, total_hit_dice // 2))

    def add_damage(self, damage: int) -> None:
        """
        Add damage to the entity's current damage taken.

        Args:
            damage (int): The amount of damage to add.
        """
        self.damage_taken += damage

    def damage_multiplier(self, damage_type: DamageType) -> float:
        """
        Calculate the damage multiplier based on vulnerabilities and resistances.

        Args:
            damage_type (damage_types): The type of damage being dealt.

        Returns:
            float: The damage multiplier (2.0 for vulnerabilities, 0.5 for resistances, 1.0 otherwise).
        """
        resistance = self.get_resistance(damage_type)
        if resistance == ResistanceStatus.IMMUNITY:
            return 0
        elif resistance == ResistanceStatus.RESISTANCE:
            return 0.5
        elif resistance == ResistanceStatus.VULNERABILITY:
            return 2
        else:
            return 1

    def _preview_damage_components(
        self,
        components: List[Tuple[int, DamageType]],
        *,
        declared_damage: int,
        normal_hit_point_damage_cap: Optional[int] = None,
        normal_hit_points_available: Optional[int] = None,
    ) -> DamageApplicationPreview:
        """Resolve typed components through affinities, defenses, and HP pools."""
        component_resolutions: list[DamageComponentResolution] = []
        for damage, damage_type in components:
            if damage < 0:
                raise ValueError(f"Damage must be greater than 0 instead of {damage}")
            if not isinstance(damage_type, DamageType):
                raise ValueError(
                    "Damage must use a DamageType instead of "
                    f"{damage_type!r}"
                )
            resistance_status = self.get_resistance(damage_type)
            multiplier = self.damage_multiplier(damage_type)
            after_affinity_damage = max(0, int(damage * multiplier))
            component_resolutions.append(
                DamageComponentResolution(
                    damage_type=damage_type,
                    incoming_damage=damage,
                    resistance_status=resistance_status,
                    multiplier=multiplier,
                    after_affinity_damage=after_affinity_damage,
                    affinity_prevented_damage=(
                        max(0, damage - after_affinity_damage)
                        if resistance_status in (
                            ResistanceStatus.RESISTANCE,
                            ResistanceStatus.IMMUNITY,
                        )
                        else 0
                    ),
                    vulnerability_bonus_damage=(
                        max(0, after_affinity_damage - damage)
                        if resistance_status == ResistanceStatus.VULNERABILITY
                        else 0
                    ),
                )
            )

        incoming_damage = sum(component.incoming_damage for component in component_resolutions)
        after_affinity_damage = sum(
            component.after_affinity_damage for component in component_resolutions
        )
        flat_reduction_damage = min(
            after_affinity_damage,
            max(0, self.damage_reduction.score),
        )
        mitigated_damage = after_affinity_damage - flat_reduction_damage
        current_temporary_hit_points = self.temporary_hit_points.score
        if current_temporary_hit_points < 0:
            raise ValueError(f"Temporary Hit Points must be greater than 0 instead of {current_temporary_hit_points}")
        temporary_hit_point_damage = min(current_temporary_hit_points, mitigated_damage)
        uncapped_normal_damage = max(0, mitigated_damage - temporary_hit_point_damage)
        normal_hit_point_damage = uncapped_normal_damage
        if normal_hit_point_damage_cap is not None:
            normal_hit_point_damage = min(
                normal_hit_point_damage,
                max(0, normal_hit_point_damage_cap),
            )
        survival_cap_prevented_damage = uncapped_normal_damage - normal_hit_point_damage
        effective_normal_hit_point_damage = normal_hit_point_damage
        overkill_damage = 0
        if normal_hit_points_available is not None:
            effective_normal_hit_point_damage = min(
                max(0, normal_hit_points_available),
                normal_hit_point_damage,
            )
            overkill_damage = normal_hit_point_damage - effective_normal_hit_point_damage
        event_prevented_damage = max(0, declared_damage - incoming_damage)
        event_amplified_damage = max(0, incoming_damage - declared_damage)
        return DamageApplicationPreview(
            declared_damage=declared_damage,
            incoming_damage=incoming_damage,
            event_prevented_damage=event_prevented_damage,
            event_amplified_damage=event_amplified_damage,
            components=tuple(component_resolutions),
            after_affinity_damage=after_affinity_damage,
            affinity_prevented_damage=sum(
                component.affinity_prevented_damage
                for component in component_resolutions
            ),
            vulnerability_bonus_damage=sum(
                component.vulnerability_bonus_damage
                for component in component_resolutions
            ),
            flat_reduction_damage=flat_reduction_damage,
            mitigated_damage=mitigated_damage,
            temporary_hit_point_damage=temporary_hit_point_damage,
            normal_hit_point_damage=normal_hit_point_damage,
            survival_cap_prevented_damage=survival_cap_prevented_damage,
            effective_normal_hit_point_damage=effective_normal_hit_point_damage,
            overkill_damage=overkill_damage,
        )

    def apply_damage_preview(
        self,
        preview: DamageApplicationPreview,
        source_entity_uuid: UUID,
    ) -> int:
        """Apply a previously resolved preview against the current health state."""
        if preview.temporary_hit_point_damage > 0:
            self.remove_temporary_hit_points(preview.temporary_hit_point_damage, source_entity_uuid)
        if preview.normal_hit_point_damage > 0:
            self.add_damage(preview.normal_hit_point_damage)
        return preview.normal_hit_point_damage

    def preview_damage_components(
        self,
        components: List[Tuple[int, DamageType]],
        normal_hit_point_damage_cap: Optional[int] = None,
        *,
        declared_damage: Optional[int] = None,
        normal_hit_points_available: Optional[int] = None,
    ) -> DamageApplicationPreview:
        """Preview mixed typed damage without mutating health state."""
        incoming_damage = sum(max(0, damage) for damage, _ in components)
        return self._preview_damage_components(
            components,
            declared_damage=(incoming_damage if declared_damage is None else declared_damage),
            normal_hit_point_damage_cap=normal_hit_point_damage_cap,
            normal_hit_points_available=normal_hit_points_available,
        )

    def preview_damage(
        self,
        damage: int,
        damage_type: DamageType,
        normal_hit_point_damage_cap: Optional[int] = None,
        *,
        declared_damage: Optional[int] = None,
        normal_hit_points_available: Optional[int] = None,
    ) -> DamageApplicationPreview:
        """Preview one typed damage amount without mutating health state."""
        return self._preview_damage_components(
            [(damage, damage_type)],
            declared_damage=(damage if declared_damage is None else declared_damage),
            normal_hit_point_damage_cap=normal_hit_point_damage_cap,
            normal_hit_points_available=normal_hit_points_available,
        )

    def is_healing_blocked(self) -> bool:
        """Check if healing is blocked by a condition (e.g., Chill Touch).

        Returns:
            True if the entity cannot regain hit points.
        """
        return self.healing_blocked

    def heal(self, heal: int) -> None:
        """
        Heal the entity by removing damage. Cannot remove damage taken by the temporary hit points.

        Args:
            heal (int): The amount of healing to apply.
        """
        if self.is_healing_blocked():
            return

        if self.temporary_hit_points.score > 0:
            damage_taken_after_temporary_hp = self.damage_taken - self.temporary_hit_points.score
            damage_absorbed_by_temporary_hp = min(self.damage_taken,self.temporary_hit_points.score)
            if damage_taken_after_temporary_hp > 0:
                self.damage_taken = max(0, damage_taken_after_temporary_hp - heal) + damage_absorbed_by_temporary_hp
        else:
            self.damage_taken = max(0, self.damage_taken - heal)

    def clear_temporary_hit_points(self) -> int:
        """Remove all current temporary hit points.

        Returns:
            Temporary hit points removed.
        """
        removed = self.temporary_hit_points.normalized_score
        self.temporary_hit_points.remove_all_modifiers()
        return removed

    def on_long_rest(self) -> int:
        """Apply health recovery from a completed long rest.

        Returns:
            Normal hit point damage healed by the rest.
        """
        self.clear_temporary_hit_points()
        self.recover_long_rest_hit_dice()
        if self.is_healing_blocked():
            return 0
        healed = self.damage_taken
        self.damage_taken = 0
        return healed

    def _grant_temporary_hit_points(
        self,
        temporary_hit_points: int,
        source_entity_uuid: UUID,
    ) -> None:
        """Commit a validated non-stacking temporary-HP grant."""
        if (
            temporary_hit_points <= 0
            or temporary_hit_points <= self.temporary_hit_points.score
        ):
            return
        modifier = NumericalModifier(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            name=f"Temporary Hit Points from {source_entity_uuid}",
            value=temporary_hit_points,
        )
        self.temporary_hit_points.remove_all_modifiers()
        self.temporary_hit_points.self_static.add_value_modifier(modifier)

    def remove_temporary_hit_points(self, temporary_hit_points: int, source_entity_uuid: UUID) -> None:
        """
        Remove temporary hit points from the entity.

        Args:
            temporary_hit_points (int): The amount of temporary hit points to remove.
            source_entity_uuid (UUID): The UUID of the entity removing the temporary hit points.
        """
        modifier = NumericalModifier(source_entity_uuid=source_entity_uuid, target_entity_uuid=self.source_entity_uuid, name=f"Temporary Hit Points from {source_entity_uuid}", value=-temporary_hit_points)
        if modifier.value + self.temporary_hit_points.score <= 0:
            self.temporary_hit_points.remove_all_modifiers()
        else:

            self.temporary_hit_points.self_static.add_value_modifier(modifier)

    def get_max_hit_dices_points(self, constitution_modifier: int) -> int:
        """
        Calculate the maximum hit points based on hit dice and constitution modifier.

        Args:
            constitution_modifier (int): The constitution modifier of the entity.

        Returns:
            int: The maximum hit points.
        """
        return self.hit_dices_total_hit_points + constitution_modifier * self.total_hit_dices_number

    def get_total_hit_points(self, constitution_modifier: int) -> int:
        """
        Calculate the total current hit points, including temporary hit points.

        Args:
            constitution_modifier (int): The constitution modifier of the entity.

        Returns:
            int: The total current hit points.
        """
        return self.get_max_hit_dices_points(constitution_modifier) + self.max_hit_points_bonus.score + self.temporary_hit_points.score - self.damage_taken

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "Health", source_entity_name: Optional[str] = None,
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None,
                config: Optional[HealthConfig] = None) -> 'Health':
        """
        Create a new Health instance with the given parameters.
        """
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            hit_dices = [HitDice.create(source_entity_uuid=source_entity_uuid, config=hit_dice) for hit_dice in config.hit_dices]
            max_hit_points_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.max_hit_points_bonus, value_name="Max Hit Points Bonus")
            for modifier in config.max_hit_points_bonus_modifiers:
                max_hit_points_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            temporary_hit_points = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.temporary_hit_points, value_name="Temporary Hit Points")
            for modifier in config.temporary_hit_points_modifiers:
                temporary_hit_points.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            damage_reduction = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.damage_reduction, value_name="Damage Reduction")
            for modifier in config.damage_reduction_modifiers:
                damage_reduction.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            for vulnerability in config.vulnerabilities:
                damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid, value=ResistanceStatus.VULNERABILITY, damage_type=vulnerability, name=f"Vulnerability to {vulnerability}"))
            for resistance in config.resistances:
                damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid, value=ResistanceStatus.RESISTANCE, damage_type=resistance, name=f"Resistance to {resistance}"))
            for immunity in config.immunities:
                damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid, value=ResistanceStatus.IMMUNITY, damage_type=immunity, name=f"Immunity to {immunity}"))
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name,
                       hit_dices=hit_dices, max_hit_points_bonus=max_hit_points_bonus, temporary_hit_points=temporary_hit_points, damage_reduction=damage_reduction,
                       life_state=config.life_state)
