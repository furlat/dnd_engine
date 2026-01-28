"""
Spellcasting block for D&D 5e spell system.

This module provides the minimal SpellcastingBlock that holds spell-specific modifiers.
Spell slots are tracked in ActionEconomy (not here) to avoid redundancy.
Known spells are tracked via Entity.registered_actions (not here) to use existing pattern.

Import Structure:
- This module imports ONLY from core modules (no Entity import)
- Entity imports this module and provides spell convenience methods
- SpellAction (in actions.py) imports Entity and uses Entity.spell_attack_bonus()
"""

from typing import Optional, List, Tuple, Literal, Self
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

from dnd.core.base_block import BaseBlock
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier, DamageType
from dnd.core.events import AbilityName, Damage


class SpellcastingConfig(BaseModel):
    """Configuration for the SpellcastingBlock.

    Attributes:
        spellcasting_ability: The ability used for spellcasting ("charisma", "intelligence", "wisdom")
        spell_attack_modifiers: Additional modifiers to spell attack rolls (e.g., Wand of the War Mage)
        spell_damage_modifiers: Additional modifiers to spell damage (e.g., Elemental Affinity)
        spell_dc_modifiers: Additional modifiers to spell save DC (e.g., magic items)
        spell_crit_threshold_modifiers: Modifiers to spell critical hit threshold (spell-specific, stacks with Equipment)
        spell_crit_extra_dice_modifiers: Modifiers to extra dice on spell crits (spell-specific, stacks with Equipment)
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
    # Extra spell damage (parallel to Equipment.extra_attack_damage_*)
    # Used for features like Elemental Affinity ("add CHA to fire spell damage")
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


class SpellcastingBlock(BaseBlock):
    """
    Spell-specific modifiers block. Always present on Entity (non-optional).

    NOT stored here (to avoid redundancy):
    - Spell slots: Live in ActionEconomy.spell_slot_X
    - Known spells: Live in Entity.registered_actions
    - Proficiency bonus: Live in Entity.proficiency_bonus
    - Generic attack modifiers (Blinded, Poisoned): Live in Equipment.attack_bonus

    Stored here:
    - Spellcasting ability (CHA/INT/WIS)
    - Spell-specific attack bonus (Wand of the War Mage adds to spell attacks only)
    - Spell-specific damage bonus (Elemental Affinity adds to certain spell damage)
    - Spell-specific DC bonus (magic items that increase spell save DC)
    - Spell-specific crit threshold (stacks with Equipment.crit_threshold)
    - Spell-specific crit extra dice (stacks with Equipment.crit_extra_dice)

    Entity.spell_attack_bonus() combines:
    - proficiency_bonus
    - ability modifier (from spellcasting_ability)
    - Equipment.attack_bonus (generic - Blinded, Poisoned apply here!)
    - SpellcastingBlock.spell_attack_bonus (spell-specific)

    Critical threshold stacking:
    - Equipment.crit_threshold affects ALL attacks (including spells)
    - spell_crit_threshold adds ONLY for spell attacks
    - Final spell crit = 20 - (Equipment.crit_threshold + spell_crit_threshold)
    """
    name: str = Field(default="Spellcasting")
    spellcasting_ability: AbilityName = Field(
        default="charisma",
        description="The ability used for spellcasting (charisma, intelligence, wisdom)"
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

    # Extra spell damage (parallel to Equipment.extra_attack_damage_*)
    # Used for features like "add 1d6 radiant to all spell damage"
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
        """Ensure all extra damage lists have same length (mirrors Equipment pattern)."""
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

    def get_extra_spell_damage(self) -> List[Damage]:
        """Get list of extra Damage objects for all spells (parallel to Equipment.get_extra_attack_damage)."""
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
        """Create a new SpellcastingBlock instance.

        Args:
            source_entity_uuid: UUID of the entity this block belongs to
            config: Configuration for the spellcasting block
            name: Name of the block
            source_entity_name: Name of the source entity
            target_entity_uuid: UUID of the target entity (if any)
            target_entity_name: Name of the target entity (if any)

        Returns:
            A new SpellcastingBlock instance
        """
        if config is None:
            config = SpellcastingConfig()

        # Create ModifiableValues with proper source_entity_uuid
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

        # Create extra spell damage ModifiableValues
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

        # Convert damage type strings to DamageType enum
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
            # Extra spell damage fields
            extra_spell_damage_dices=list(config.extra_spell_damage_dices),
            extra_spell_damage_dices_numbers=list(config.extra_spell_damage_dices_numbers),
            extra_spell_damage_bonus=extra_spell_damage_bonus,
            extra_spell_damage_type=extra_spell_damage_type,
        )
