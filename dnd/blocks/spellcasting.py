"""Spell-specific modifier block for the D&D spell system."""

from typing import Dict, Optional, List, Tuple, Literal, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from dnd.core.base_block import BaseBlock
from dnd.core.content.durable_characters import RitualPreparationPolicy
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier, DamageType
from dnd.core.events import AbilityName, Damage
from dnd.core.progression import (
    CasterProgression,
    SpellcastingClassContribution,
    maximum_spell_rank_for_contribution,
)


class SpellcastingConfig(BaseModel):
    """Configuration for the SpellcastingBlock.

    Attributes:
        spellcasting_ability: Ability used for spellcasting.
        spell_attack_modifiers: Additional modifiers to spell attack rolls.
        spell_damage_modifiers: Additional modifiers to spell damage.
        spell_dc_modifiers: Additional modifiers to spell save DC.
        spell_crit_threshold_modifiers: Modifiers to spell critical hit threshold.
        spell_crit_extra_dice_modifiers: Modifiers to extra dice on spell crits.
    """

    spellcasting_ability: AbilityName = Field(
        default="charisma",
        description="The ability used for spellcasting"
    )
    spell_attack_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="(name, value) pairs for spell attack bonus modifiers"
    )
    spell_damage_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="(name, value) pairs for spell damage modifiers"
    )
    spell_dc_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="(name, value) pairs for spell save DC modifiers"
    )
    spell_crit_threshold_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="(name, value) pairs for spell-specific crit threshold modifiers"
    )
    spell_crit_extra_dice_modifiers: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="(name, value) pairs for spell-specific crit extra dice modifiers"
    )
    extra_spell_damage_dices: List[Literal[4, 6, 8, 10, 12, 20]] = Field(
        default_factory=list,
        description="Dice sides for extra spell damage (e.g., [6] for 1d6)"
    )
    extra_spell_damage_dices_numbers: List[int] = Field(
        default_factory=list,
        description="Number of dice for extra spell damage (e.g., [1] for 1d6)"
    )
    extra_spell_damage_bonus_modifiers: List[List[Tuple[str, int]]] = Field(
        default_factory=list,
        description="Per-damage bonus modifiers (list of (name, value) lists)"
    )
    extra_spell_damage_types: List[str] = Field(
        default_factory=list,
        description="DamageType names as strings (e.g., ['fire', 'radiant'])"
    )


class SpellcastingSource(BaseModel):
    """One exact class-owned source for spellcasting ability."""

    model_config = ConfigDict(frozen=True)

    source_id: UUID = Field(description="Owning progression grant UUID.")
    ability: AbilityName = Field(description="Ability used by this source.")
    provider_ref: ContentRef = Field(
        description="Exact authored class definition providing this source.",
    )
    caster_progression: CasterProgression = Field(
        description="Shared-slot progression owned by this provider.",
    )
    provider_level: int = Field(
        ge=1,
        le=20,
        description="Current level in the providing class.",
    )
    maximum_spell_rank: int = Field(
        ge=0,
        le=9,
        description="Highest spell rank this source can learn or prepare.",
    )
    ritual_policy: RitualPreparationPolicy = Field(
        description="Exact ritual entitlement policy of this source.",
    )

    @model_validator(mode="after")
    def _validate_provider(self) -> Self:
        if self.provider_ref.definition_kind != ContentDefinitionKind.CLASS:
            raise ValueError(
                "spellcasting source provider_ref must identify a class",
            )
        if self.caster_progression == CasterProgression.NON_CASTER:
            raise ValueError("non-caster cannot own a spellcasting source")
        expected_rank = maximum_spell_rank_for_contribution(
            SpellcastingClassContribution(
                class_level=self.provider_level,
                progression=self.caster_progression,
                spellcasting_feature_class_level=1,
            ),
        )
        if self.maximum_spell_rank != expected_rank:
            raise ValueError(
                "spellcasting source maximum_spell_rank disagrees with its "
                f"progression and provider level: expected {expected_rank}",
            )
        return self


class LearnedReactionSpellOwnership(BaseModel):
    """Shared runtime handler owned by one or more exact casting sources."""

    spell_ref: ContentRef = Field(
        description="Exact learned spell definition owning the handler.",
    )
    handler_uuid: UUID = Field(
        description="Single live reaction handler installed for this spell.",
    )
    source_ids: set[UUID] = Field(
        default_factory=set,
        description="Exact spellcasting sources that currently know the spell.",
    )

    @model_validator(mode="after")
    def _validate_spell_ownership(self) -> Self:
        if self.spell_ref.definition_kind != ContentDefinitionKind.SPELL:
            raise ValueError("learned reaction ownership requires a spell ref")
        if not self.source_ids:
            raise ValueError(
                "learned reaction ownership requires at least one source",
            )
        return self


class SpellDamageAffinityContribution(BaseModel):
    """One source-owned ability bonus for a matching spell damage type."""

    model_config = ConfigDict(frozen=True)

    source_id: UUID = Field(description="Exact structural grant identity.")
    damage_type: DamageType = Field(description="Eligible spell damage type.")
    ability_name: AbilityName = Field(
        description="Ability modifier added to one damage roll per cast.",
    )


class SpellcastingBlock(BaseBlock):
    """Spell-specific modifiers that are always present on an entity.

    This block stores spellcasting ability, spell attack/damage/DC modifiers,
    spell-specific critical modifiers, and extra spell damage payloads. Spell
    slots live on `ActionEconomy`, known spells live in registered actions, and
    proficiency/generic attack modifiers live on their own entity blocks.
    """

    name: str = Field(default="Spellcasting", description="Display name for this spellcasting block.")
    spellcasting_ability: AbilityName = Field(
        default="charisma",
        description="The ability used for spellcasting (charisma, intelligence, wisdom)"
    )
    sources: Dict[UUID, SpellcastingSource] = Field(
        default_factory=dict,
        description="Spellcasting abilities keyed by exact progression source.",
    )
    learned_reaction_spell_handlers: Dict[
        str,
        LearnedReactionSpellOwnership,
    ] = Field(
        default_factory=dict,
        description=(
            "One exact reaction handler per learned spell with source-owned "
            "lifetime."
        ),
    )
    spell_damage_affinity_contributions: Dict[
        UUID,
        SpellDamageAffinityContribution,
    ] = Field(
        default_factory=dict,
        description=(
            "Source-owned once-per-cast spell damage bonuses keyed by grant."
        ),
    )
    _consumed_spell_damage_affinity_executions: dict[UUID, set[UUID]] = (
        PrivateAttr(default_factory=dict)
    )
    spell_attack_bonus: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=UUID('00000000-0000-0000-0000-000000000000'),
            base_value=0,
            value_name="Spell Attack Bonus"
        ),
        description="Spell-specific attack bonus (e.g., Wand of the War Mage)"
    )
    spell_damage_bonus: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=UUID('00000000-0000-0000-0000-000000000000'),
            base_value=0,
            value_name="Spell Damage Bonus"
        ),
        description="Spell-specific damage bonus (e.g., Elemental Affinity)"
    )
    spell_dc_bonus: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=UUID('00000000-0000-0000-0000-000000000000'),
            base_value=0,
            value_name="Spell DC Bonus"
        ),
        description="Spell-specific DC bonus beyond 8+prof+ability"
    )
    spell_crit_threshold: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=UUID('00000000-0000-0000-0000-000000000000'),
            base_value=0,
            value_name="Spell Crit Threshold"
        ),
        description="Spell-specific crit threshold modifier (stacks with Equipment.crit_threshold)"
    )
    spell_crit_extra_dice: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=UUID('00000000-0000-0000-0000-000000000000'),
            base_value=0,
            value_name="Spell Crit Extra Dice"
        ),
        description="Spell-specific extra dice on critical hits (stacks with Equipment.crit_extra_dice)"
    )

    extra_spell_damage_dices: List[Literal[4, 6, 8, 10, 12, 20]] = Field(
        default_factory=list,
        description="Dice sides for extra spell damage"
    )
    extra_spell_damage_dices_numbers: List[int] = Field(
        default_factory=list,
        description="Number of dice for each extra spell damage"
    )
    extra_spell_damage_bonus: List[ModifiableValue] = Field(
        default_factory=list,
        description="Bonus modifiers for each extra spell damage"
    )
    extra_spell_damage_type: List[DamageType] = Field(
        default_factory=list,
        description="Damage type for each extra spell damage"
    )

    @model_validator(mode="after")
    def check_extra_damage_consistency(self) -> Self:
        """Ensure all extra spell damage payload lists have matching length."""
        targets = [
            self.extra_spell_damage_dices,
            self.extra_spell_damage_dices_numbers,
            self.extra_spell_damage_bonus,
            self.extra_spell_damage_type
        ]
        first_len = len(targets[0])
        for target in targets[1:]:
            if len(target) != first_len:
                raise ValueError("Extra spell damage lists must all have same length")
        return self

    def add_source(
        self,
        source_id: UUID,
        ability: AbilityName,
        *,
        provider_ref: ContentRef,
        caster_progression: CasterProgression,
        provider_level: int,
        maximum_spell_rank: int,
        ritual_policy: RitualPreparationPolicy,
    ) -> None:
        """Add one source without changing the legacy default ability."""
        incoming = SpellcastingSource(
            source_id=source_id,
            ability=ability,
            provider_ref=provider_ref,
            caster_progression=caster_progression,
            provider_level=provider_level,
            maximum_spell_rank=maximum_spell_rank,
            ritual_policy=ritual_policy,
        )
        existing = self.sources.get(source_id)
        if existing is not None and existing != incoming:
            raise ValueError(
                f"spellcasting source {source_id} already has different "
                "provider facts"
            )
        self.sources[source_id] = incoming

    def remove_source(self, source_id: UUID) -> bool:
        """Remove exactly one spellcasting source."""
        return self.sources.pop(source_id, None) is not None

    def resolve_spellcasting_ability(
        self,
        source_id: Optional[UUID] = None,
    ) -> AbilityName:
        """Resolve an explicit source or retain the legacy default seam."""
        if source_id is None:
            return self.spellcasting_ability
        source = self.sources.get(source_id)
        if source is None:
            raise KeyError(f"spellcasting source {source_id} is not registered")
        return source.ability

    def add_learned_reaction_spell_source(
        self,
        *,
        spell_ref: ContentRef,
        source_id: UUID,
        handler_uuid: UUID,
    ) -> UUID:
        """Own one shared reaction handler from an exact casting source."""
        if source_id not in self.sources:
            raise KeyError(
                f"spellcasting source {source_id} is not registered",
            )
        key = spell_ref.identity_key
        existing = self.learned_reaction_spell_handlers.get(key)
        if existing is None:
            self.learned_reaction_spell_handlers[key] = (
                LearnedReactionSpellOwnership(
                    spell_ref=spell_ref,
                    handler_uuid=handler_uuid,
                    source_ids={source_id},
                )
            )
            return handler_uuid
        if existing.spell_ref != spell_ref:
            raise ValueError(
                "learned reaction spell identity key has conflicting ref",
            )
        if existing.handler_uuid != handler_uuid:
            raise ValueError(
                "learned reaction spell already owns a different handler",
            )
        existing.source_ids.add(source_id)
        return existing.handler_uuid

    def learned_reaction_spell_handler_uuid(
        self,
        spell_ref: ContentRef,
    ) -> UUID | None:
        """Return the live handler for one exact learned reaction spell."""
        ownership = self.learned_reaction_spell_handlers.get(
            spell_ref.identity_key,
        )
        if ownership is None:
            return None
        if ownership.spell_ref != spell_ref:
            raise ValueError(
                "learned reaction spell identity key has conflicting ref",
            )
        return ownership.handler_uuid

    def add_spell_damage_affinity_contribution(
        self,
        source_id: UUID,
        *,
        damage_type: DamageType,
        ability_name: AbilityName,
    ) -> None:
        """Install one exact matching-type, once-per-cast contribution."""

        incoming = SpellDamageAffinityContribution(
            source_id=source_id,
            damage_type=damage_type,
            ability_name=ability_name,
        )
        existing = self.spell_damage_affinity_contributions.get(source_id)
        if existing is not None and existing != incoming:
            raise ValueError(
                f"spell damage affinity {source_id} already differs",
            )
        self.spell_damage_affinity_contributions[source_id] = incoming
        self._consumed_spell_damage_affinity_executions.setdefault(
            source_id,
            set(),
        )

    def remove_spell_damage_affinity_contribution(
        self,
        source_id: UUID,
    ) -> bool:
        """Remove one exact contribution and its ephemeral usage history."""

        removed = self.spell_damage_affinity_contributions.pop(
            source_id,
            None,
        )
        self._consumed_spell_damage_affinity_executions.pop(source_id, None)
        return removed is not None

    def claim_spell_damage_affinity_ability(
        self,
        *,
        spell_lineage_uuid: UUID,
        damage_type: DamageType,
    ) -> AbilityName | None:
        """Claim the strongest applicable contribution once for this cast.

        Same-named affinity grants do not stack.  Stable source ordering makes
        duplicate-provider behavior deterministic while exact source removal
        remains possible.
        """

        for source_id in sorted(
            self.spell_damage_affinity_contributions,
            key=str,
        ):
            contribution = self.spell_damage_affinity_contributions[source_id]
            if contribution.damage_type is not damage_type:
                continue
            consumed = self._consumed_spell_damage_affinity_executions.setdefault(
                source_id,
                set(),
            )
            if spell_lineage_uuid in consumed:
                continue
            consumed.add(spell_lineage_uuid)
            return contribution.ability_name
        return None

    def release_spell_damage_affinity_execution(
        self,
        spell_lineage_uuid: UUID,
    ) -> None:
        """Forget the ephemeral once-per-cast claims after execution ends."""

        for consumed in self._consumed_spell_damage_affinity_executions.values():
            consumed.discard(spell_lineage_uuid)

    def learned_reaction_spell_source_ids(
        self,
        spell_ref: ContentRef,
    ) -> tuple[UUID, ...]:
        """Return exact owning casting sources in deterministic order."""
        ownership = self.learned_reaction_spell_handlers.get(
            spell_ref.identity_key,
        )
        if ownership is None:
            return ()
        if ownership.spell_ref != spell_ref:
            raise ValueError(
                "learned reaction spell identity key has conflicting ref",
            )
        return tuple(sorted(ownership.source_ids, key=str))

    def remove_learned_reaction_spell_source(
        self,
        *,
        spell_ref: ContentRef,
        source_id: UUID,
        handler_uuid: UUID,
    ) -> bool:
        """Remove one owner and report whether the handler must be removed."""
        key = spell_ref.identity_key
        ownership = self.learned_reaction_spell_handlers.get(key)
        if ownership is None:
            raise KeyError(
                f"learned reaction spell {key} is not registered",
            )
        if (
            ownership.spell_ref != spell_ref
            or ownership.handler_uuid != handler_uuid
        ):
            raise ValueError(
                "learned reaction spell removal handle is inconsistent",
            )
        if source_id not in ownership.source_ids:
            raise KeyError(
                f"source {source_id} does not own learned reaction spell {key}",
            )
        ownership.source_ids.remove(source_id)
        if ownership.source_ids:
            return False
        del self.learned_reaction_spell_handlers[key]
        return True

    def get_extra_spell_damage(self) -> List[Damage]:
        """Return extra damage payloads that apply to spell damage."""
        damages: List[Damage] = []
        for i in range(len(self.extra_spell_damage_dices)):
            damages.append(Damage(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                damage_dice=self.extra_spell_damage_dices[i],
                dice_numbers=self.extra_spell_damage_dices_numbers[i],
                damage_bonus=self.extra_spell_damage_bonus[i],
                damage_type=self.extra_spell_damage_type[i]
            ))
        return damages

    @classmethod
    def create(
        cls,
        source_entity_uuid: UUID,
        config: Optional[SpellcastingConfig] = None,
        name: str = "Spellcasting",
        source_entity_name: Optional[str] = None,
        target_entity_uuid: Optional[UUID] = None,
        target_entity_name: Optional[str] = None,
    ) -> 'SpellcastingBlock':
        """Create a SpellcastingBlock from optional configuration.

        Args:
            source_entity_uuid: UUID of the entity this block belongs to.
            config: Configuration for the spellcasting block.
            name: Name of the block.
            source_entity_name: Name of the source entity.
            target_entity_uuid: UUID of the target entity, if any.
            target_entity_name: Name of the target entity, if any.

        Returns:
            A new spellcasting block instance.
        """
        if config is None:
            config = SpellcastingConfig()

        spell_attack_bonus = ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=0,
            value_name="Spell Attack Bonus"
        )
        for mod_name, mod_value in config.spell_attack_modifiers:
            spell_attack_bonus.self_static.add_value_modifier(
                NumericalModifier.create(
                    source_entity_uuid=source_entity_uuid,
                    name=mod_name,
                    value=mod_value
                )
            )

        spell_damage_bonus = ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=0,
            value_name="Spell Damage Bonus"
        )
        for mod_name, mod_value in config.spell_damage_modifiers:
            spell_damage_bonus.self_static.add_value_modifier(
                NumericalModifier.create(
                    source_entity_uuid=source_entity_uuid,
                    name=mod_name,
                    value=mod_value
                )
            )

        spell_dc_bonus = ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=0,
            value_name="Spell DC Bonus"
        )
        for mod_name, mod_value in config.spell_dc_modifiers:
            spell_dc_bonus.self_static.add_value_modifier(
                NumericalModifier.create(
                    source_entity_uuid=source_entity_uuid,
                    name=mod_name,
                    value=mod_value
                )
            )

        spell_crit_threshold = ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=0,
            value_name="Spell Crit Threshold"
        )
        for mod_name, mod_value in config.spell_crit_threshold_modifiers:
            spell_crit_threshold.self_static.add_value_modifier(
                NumericalModifier.create(
                    source_entity_uuid=source_entity_uuid,
                    name=mod_name,
                    value=mod_value
                )
            )

        spell_crit_extra_dice = ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=0,
            value_name="Spell Crit Extra Dice"
        )
        for mod_name, mod_value in config.spell_crit_extra_dice_modifiers:
            spell_crit_extra_dice.self_static.add_value_modifier(
                NumericalModifier.create(
                    source_entity_uuid=source_entity_uuid,
                    name=mod_name,
                    value=mod_value
                )
            )

        extra_spell_damage_bonus: List[ModifiableValue] = []
        for i, modifiers in enumerate(config.extra_spell_damage_bonus_modifiers):
            bonus = ModifiableValue.create(
                source_entity_uuid=source_entity_uuid,
                base_value=0,
                value_name=f"Extra Spell Damage Bonus {i}"
            )
            for mod_name, mod_value in modifiers:
                bonus.self_static.add_value_modifier(
                    NumericalModifier.create(
                        source_entity_uuid=source_entity_uuid,
                        name=mod_name,
                        value=mod_value
                    )
            )
            extra_spell_damage_bonus.append(bonus)

        extra_spell_damage_type = [DamageType(t) for t in config.extra_spell_damage_types]

        return cls(
            source_entity_uuid=source_entity_uuid,
            name=name,
            source_entity_name=source_entity_name,
            target_entity_uuid=target_entity_uuid,
            target_entity_name=target_entity_name,
            spellcasting_ability=config.spellcasting_ability,
            spell_attack_bonus=spell_attack_bonus,
            spell_damage_bonus=spell_damage_bonus,
            spell_dc_bonus=spell_dc_bonus,
            spell_crit_threshold=spell_crit_threshold,
            spell_crit_extra_dice=spell_crit_extra_dice,
            extra_spell_damage_dices=list(config.extra_spell_damage_dices),
            extra_spell_damage_dices_numbers=list(config.extra_spell_damage_dices_numbers),
            extra_spell_damage_bonus=extra_spell_damage_bonus,
            extra_spell_damage_type=extra_spell_damage_type,
        )
