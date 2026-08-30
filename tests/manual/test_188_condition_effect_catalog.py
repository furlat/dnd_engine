"""Exact static condition-effect catalog and producer-coverage gates."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import dnd.classes.fighter as fighter
import dnd.conditions as conditions
import dnd.monsters.traits as monster_traits
import dnd.spells.abjuration as abjuration
import dnd.spells.conjuration as conjuration
import dnd.spells.enchantment as enchantment
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.condition_effect_population import (
    INDIRECT_CONDITION_EFFECT_SPELL_TYPES,
    NO_CONDITION_EFFECT_SPELL_TYPES,
    builtin_condition_effect_source_types,
)
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.effects import (
    ConditionEffectCoverage,
    ConditionEffectOperation,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.registration import (
    ContentDeclaration,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.spells.catalog_content import (
    SPELL_CATALOG_METADATA_BY_CLASS,
    SPELL_CONTENT_IDENTITY_SPECS,
)
from server.content_catalog import build_public_content_catalog


@pytest.fixture(scope="module")
def loaded_content():
    """Return one frozen built-in content system for this contract suite."""
    return bootstrap_content_system(pack_roots=())


def _applied_refs(
    declaration: ContentDeclaration,
) -> tuple[ContentRef, ...]:
    profile = declaration.condition_effect_profile
    assert profile is not None
    applied_refs: list[ContentRef] = []
    for effect in profile.effects:
        if effect.operation is not ConditionEffectOperation.APPLY:
            continue
        condition_ref = effect.condition_ref
        assert condition_ref is not None
        applied_refs.append(condition_ref)
    return tuple(applied_refs)


def test_catalog_condition_effect_coverage_is_closed_and_exact(
    loaded_content,
) -> None:
    """Every public row owns one explicit effect disposition and exact refs."""
    catalog = build_public_content_catalog(loaded_content)
    assert catalog.schema_version == 6
    entries_by_ref = {
        entry.ref.identity_key: entry
        for entry in catalog.entries
    }

    for entry in catalog.entries:
        profile = entry.condition_effect_profile
        apply_dependencies = {
            dependency.target_ref.identity_key
            for dependency in entry.dependencies
            if dependency.relation
            is ContentDependencyRelation.APPLIES_CONDITION
        }
        if entry.condition_effect_coverage is ConditionEffectCoverage.PROFILED:
            assert profile is not None
        else:
            assert profile is None
            assert not apply_dependencies

        if (
            entry.condition_effect_coverage
            is ConditionEffectCoverage.LIFECYCLE_ONLY
        ):
            assert entry.runtime_behavior_kind is RuntimeBehaviorKind.CONDITION
            assert entry.condition_lifecycle is not None

        if profile is None:
            continue
        profile_payload = profile.model_dump(mode="json")
        assert "semantic_key" not in repr(profile_payload)
        assert "condition_name" not in repr(profile_payload)
        assert {
            effect.condition_ref.identity_key
            for effect in profile.effects
            if (
                effect.operation is ConditionEffectOperation.APPLY
                and effect.condition_ref is not None
            )
        } == apply_dependencies
        for effect in profile.effects:
            assert effect.source_ref == entry.ref
            if effect.condition_ref is not None:
                target = entries_by_ref[effect.condition_ref.identity_key]
                assert target.ref == effect.condition_ref
                assert (
                    target.runtime_behavior_kind
                    is RuntimeBehaviorKind.CONDITION
                )
            if effect.selector is not None:
                assert tuple(sorted(
                    effect.selector.resolved_condition_refs,
                    key=lambda ref: ref.identity_key,
                )) == effect.selector.resolved_condition_refs
                for condition_ref in effect.selector.resolved_condition_refs:
                    target = entries_by_ref[condition_ref.identity_key]
                    assert target.condition_lifecycle is not None
                    assert set(
                        effect.selector.required_tags,
                    ).issubset(target.condition_lifecycle.tags)
                    assert set(
                        effect.selector.required_removal_triggers,
                    ).issubset(target.condition_lifecycle.removal_triggers)
        for branch in profile.branches:
            applied = {
                effect.condition_ref.identity_key
                for effect in branch.effects
                if (
                    effect.operation is ConditionEffectOperation.APPLY
                    and effect.condition_ref is not None
                )
            }
            explicitly_removed = {
                effect.condition_ref.identity_key
                for effect in branch.effects
                if (
                    effect.operation
                    in {
                        ConditionEffectOperation.REMOVE,
                        ConditionEffectOperation.CLEANSE,
                    }
                    and effect.condition_ref is not None
                )
            }
            assert not (applied & explicitly_removed)


def test_every_public_condition_exposes_typed_lifecycle(
    loaded_content,
) -> None:
    """Refresh policy and break/removal facts live on condition definitions."""
    public_conditions = tuple(
        declaration
        for declaration in loaded_content.registry.declarations.values()
        if (
            declaration.descriptor.visibility is ContentVisibility.PUBLIC
            and declaration.runtime_behavior_kind
            is RuntimeBehaviorKind.CONDITION
        )
    )
    assert public_conditions
    assert all(
        declaration.condition_lifecycle is not None
        for declaration in public_conditions
    )
    assert all(
        declaration.condition_effect_coverage
        in {
            ConditionEffectCoverage.PROFILED,
            ConditionEffectCoverage.INTERNAL_ONLY,
            ConditionEffectCoverage.LIFECYCLE_ONLY,
        }
        for declaration in public_conditions
    )


def test_spell_condition_disposition_inventory_is_exhaustive(
    loaded_content,
) -> None:
    """All installed spells are profiled, condition-free, or exact-indirect."""
    all_spell_types = {
        spec.spell_type
        for spec in SPELL_CONTENT_IDENTITY_SPECS
    }
    profiled_spell_types = {
        spell_type
        for spell_type in all_spell_types
        if (
            get_content_declaration(spell_type).condition_effect_coverage
            is ConditionEffectCoverage.PROFILED
        )
    }
    assert len(all_spell_types) == 109
    assert (
        profiled_spell_types
        | set(NO_CONDITION_EFFECT_SPELL_TYPES)
        | set(INDIRECT_CONDITION_EFFECT_SPELL_TYPES)
    ) == all_spell_types
    assert not (
        profiled_spell_types
        & set(NO_CONDITION_EFFECT_SPELL_TYPES)
    )
    assert not (
        profiled_spell_types
        & set(INDIRECT_CONDITION_EFFECT_SPELL_TYPES)
    )
    for spell_type in NO_CONDITION_EFFECT_SPELL_TYPES:
        assert (
            get_content_declaration(spell_type).condition_effect_coverage
            is ConditionEffectCoverage.NONE
        )
    for spell_type in INDIRECT_CONDITION_EFFECT_SPELL_TYPES:
        assert (
            get_content_declaration(spell_type).condition_effect_coverage
            is ConditionEffectCoverage.INDIRECT
        )

    concentrating_ref = get_content_declaration(conditions.Concentrating).ref
    concentration_spells = {
        spell_type
        for spell_type, metadata in SPELL_CATALOG_METADATA_BY_CLASS.items()
        if metadata.concentration
    }
    assert len(concentration_spells) == 46
    assert all(
        concentrating_ref in _applied_refs(
            get_content_declaration(spell_type),
        )
        for spell_type in concentration_spells
    )


def test_profiles_preserve_direct_source_ownership_and_order() -> None:
    """Wrapper and zone children belong to their direct runtime producer."""
    hold_spell = get_content_declaration(enchantment.HoldPerson)
    hold_wrapper = get_content_declaration(enchantment.HoldPersonEffect)
    assert _applied_refs(hold_spell)[:1] == (
        hold_wrapper.ref,
    )
    assert get_content_declaration(conditions.Paralyzed).ref not in (
        _applied_refs(hold_spell)
    )
    assert _applied_refs(hold_wrapper) == (
        get_content_declaration(conditions.Paralyzed).ref,
    )

    web_spell = get_content_declaration(conjuration.Web)
    web_zone = get_content_declaration(conjuration.WebZone)
    web_wrapper = get_content_declaration(conjuration.WebRestrained)
    restrained_ref = get_content_declaration(conditions.Restrained).ref
    assert _applied_refs(web_spell)[:2] == (
        web_zone.ref,
        web_wrapper.ref,
    )
    assert restrained_ref not in _applied_refs(web_spell)
    assert _applied_refs(web_zone) == (web_wrapper.ref,)
    assert _applied_refs(web_wrapper) == (restrained_ref,)

    protection = get_content_declaration(abjuration.ProtectionFromPoison)
    protection_profile = protection.condition_effect_profile
    assert protection_profile is not None
    effects = protection_profile.effects
    assert effects[0].operation is ConditionEffectOperation.CLEANSE
    assert effects[0].condition_ref == get_content_declaration(
        conditions.Poisoned,
    ).ref
    assert effects[1].operation is ConditionEffectOperation.APPLY
    assert effects[1].condition_ref == get_content_declaration(
        abjuration.ProtectionFromPoisonEffect,
    ).ref

    wolf = get_content_declaration(
        monster_traits.WolfBiteProneRiderFeature,
    )
    wolf_profile = wolf.condition_effect_profile
    assert wolf_profile is not None
    gate_kinds = tuple(
        gate.kind
        for gate in wolf_profile.branches[0].gates
    )
    assert gate_kinds == ("attack_outcome", "saving_throw")


_AUDITED_NON_DECLARATION_MUTATION_OWNERS = frozenset({
    "dnd.actions:SpellAction",
    "dnd.classes.barbarian:<module>",
    "dnd.classes.fighter:<module>",
    "dnd.classes.rage:<module>",
    "dnd.extensions.aegis_spark:<module>",
    "tests.manual.reactive_fixture_support:<module>",
    "tests.manual.reactive_fixture_support:PrepareIntercept",
    "dnd.monsters.circus_fighter:<module>",
    "dnd.monsters.traits:<module>",
    "dnd.monsters.traits:BonusDamageFeature",
    "dnd.monsters.traits:HitSaveRiderFeature",
    "dnd.spells.abjuration:<module>",
    "dnd.spells.abjuration:AntimagicSuppression",
    "dnd.spells.conjuration:<module>",
    "dnd.spells.conjuration:GuardianOfFaithObject",
    "dnd.spells.divination:<module>",
    "dnd.spells.enchantment:CommandNextTurnEffect",
})


def test_condition_mutation_callsite_inventory_has_no_unclassified_owner(
    loaded_content,
) -> None:
    """A new gameplay mutator must own a profile or explicit disposition."""
    del loaded_content
    audited_roots = (
        Path("dnd/actions.py"),
        Path("dnd/classes"),
        Path("dnd/extensions"),
        Path("dnd/items"),
        Path("dnd/monsters"),
        Path("dnd/spells"),
        Path("dnd/tile_conditions.py"),
    )
    paths: list[Path] = []
    for root in audited_roots:
        paths.extend(root.rglob("*.py") if root.is_dir() else (root,))

    mutation_owners: set[str] = set()
    for path in sorted(set(paths)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        class_stack: list[str] = []

        class MutationVisitor(ast.NodeVisitor):
            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                class_stack.append(node.name)
                self.generic_visit(node)
                class_stack.pop()

            def visit_Call(self, node: ast.Call) -> None:
                function = node.func
                if (
                    isinstance(function, ast.Attribute)
                    and function.attr
                    in {
                        "add_condition",
                        "remove_condition",
                        "remove_condition_by_uuid",
                    }
                ):
                    module = ".".join(path.with_suffix("").parts)
                    owner = ".".join(class_stack) or "<module>"
                    mutation_owners.add(f"{module}:{owner}")
                self.generic_visit(node)

        MutationVisitor().visit(tree)

    declared_owners = {
        f"{source_type.__module__}:{source_type.__qualname__}"
        for source_type in builtin_condition_effect_source_types()
        if get_content_declaration(source_type).condition_effect_coverage
        in {
            ConditionEffectCoverage.PROFILED,
            ConditionEffectCoverage.INTERNAL_ONLY,
            ConditionEffectCoverage.LIFECYCLE_ONLY,
        }
    }
    assert (
        mutation_owners - declared_owners
    ) == _AUDITED_NON_DECLARATION_MUTATION_OWNERS
    assert fighter.ActionSurge in builtin_condition_effect_source_types()
    assert (
        get_content_declaration(fighter.ActionSurge)
        .condition_effect_coverage
        is ConditionEffectCoverage.INTERNAL_ONLY
    )
