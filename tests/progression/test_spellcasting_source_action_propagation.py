"""Exact spellcasting-source propagation through spell action execution."""

from typing import cast
from uuid import UUID, uuid4

from dnd.actions.standard import (
    SpellAction,
    SpellEvent,
)
from dnd.actions.operations import register_spell
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.core.base_actions import (
    ActionOutcomeProfile,
)
from dnd.core.content.durable_characters import RitualPreparationPolicy
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.types.abilities import AbilityName
from dnd.core.events.events_registry import (
    EventPhase,
)
from dnd.types.damage import DamageType
from dnd.types.progression import CasterProgression
from dnd.entity import Entity, EntityConfig
from dnd.spells.evocation import FireBolt, MagicMissile, SacredFlame


class _SourceSaveSpell(SpellAction):
    """One save spell used to exercise the shared SpellAction DC seam."""

    name: str = "Source Save Spell"
    spell_level: int = 1

    def get_outcome_profile(self, actor: object) -> ActionOutcomeProfile | None:
        """Expose the shared save outcome profile through a concrete spell."""
        if not isinstance(actor, Entity):
            return None
        return self.saving_throw_damage_outcome_profile(
            actor,
            dice_count=1,
            die_size=8,
            damage_type=DamageType.RADIANT,
            save_ability="dexterity",
            half_damage_on_save=False,
        )


def _multiclass_caster() -> tuple[Entity, UUID, UUID]:
    caster = Entity.create(
        source_entity_uuid=uuid4(),
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                charisma=AbilityConfig(ability_score=8),
                wisdom=AbilityConfig(ability_score=18),
            ),
            proficiency_bonus=3,
        ),
    )
    charisma_source = uuid4()
    wisdom_source = uuid4()
    for source_id, ability, content_id in (
        (charisma_source, "charisma", "class.charisma"),
        (wisdom_source, "wisdom", "class.wisdom"),
    ):
        caster.spellcasting.add_source(
            source_id,
            cast(AbilityName, ability),
            provider_ref=ContentRef(
                pack_id="fixture.spell_source_propagation",
                definition_kind=ContentDefinitionKind.CLASS,
                content_id=content_id,
                content_version=1,
                definition_contract_hash="a" * 64,
            ),
            caster_progression=CasterProgression.FULL_CASTER,
            provider_level=5,
            maximum_spell_rank=3,
            ritual_policy=RitualPreparationPolicy.NONE,
        )
    return caster, charisma_source, wisdom_source


def test_same_registered_spell_uses_its_exact_casting_source() -> None:
    caster, charisma_source, wisdom_source = _multiclass_caster()

    register_spell(
        caster,
        FireBolt,
        caster_level=5,
        spellcasting_source_id=charisma_source,
    )
    register_spell(
        caster,
        FireBolt,
        caster_level=5,
        spellcasting_source_id=wisdom_source,
    )
    spells = [
        action
        for action in caster.registered_actions
        if isinstance(action, FireBolt)
    ]

    assert len(spells) == 2
    assert [spell.spellcasting_source_id for spell in spells] == [
        charisma_source,
        wisdom_source,
    ]
    profiles = [spell.get_outcome_profile(caster) for spell in spells]
    assert all(profile is not None for profile in profiles)
    assert [profile.attack_bonus for profile in profiles if profile is not None] == [
        2,
        7,
    ]


def test_same_save_spell_uses_distinct_source_owned_dcs() -> None:
    caster, charisma_source, wisdom_source = _multiclass_caster()

    register_spell(
        caster,
        _SourceSaveSpell,
        spellcasting_source_id=charisma_source,
    )
    register_spell(
        caster,
        _SourceSaveSpell,
        spellcasting_source_id=wisdom_source,
    )
    spells = [
        action
        for action in caster.registered_actions
        if isinstance(action, _SourceSaveSpell)
    ]

    profiles = [spell.get_outcome_profile(caster) for spell in spells]
    assert [profile.save_dc for profile in profiles if profile is not None] == [
        10,
        15,
    ]


def test_concrete_save_spell_execution_uses_exact_casting_source() -> None:
    caster, charisma_source, wisdom_source = _multiclass_caster()
    target = Entity.create(source_entity_uuid=uuid4())
    spells = [
        SacredFlame(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            spellcasting_source_id=source_id,
        )
        for source_id in (charisma_source, wisdom_source)
    ]

    completed = []
    for spell in spells:
        declaration = spell._create_declaration_event(use_register=False)
        assert declaration is not None
        execution = declaration.phase_to(EventPhase.EXECUTION)
        assert isinstance(execution, SpellEvent)
        result = spell._apply(execution)
        assert result is not None
        completed.append(result)

    assert [event.save_dc for event in completed] == [10, 15]


def test_spell_variants_and_executable_clones_preserve_exact_source() -> None:
    caster, _, wisdom_source = _multiclass_caster()
    template = MagicMissile(
        source_entity_uuid=caster.uuid,
        spellcasting_source_id=wisdom_source,
        template=True,
    )

    variant = template._create_variant(cast_at_level=3)
    executable = template.instantiate(target_entity_uuid=uuid4())
    assert isinstance(executable, SpellAction)

    assert variant.spellcasting_source_id == wisdom_source
    assert executable.spellcasting_source_id == wisdom_source


def test_legacy_spell_action_without_source_uses_default_ability() -> None:
    caster, _, _ = _multiclass_caster()
    spell = FireBolt(source_entity_uuid=caster.uuid, caster_level=5)

    profile = spell.get_outcome_profile(caster)

    assert profile is not None
    assert spell.spellcasting_source_id is None
    assert profile.attack_bonus == 2
