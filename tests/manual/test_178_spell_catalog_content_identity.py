"""Exact content identity across spell, content, and presentation catalogs."""

from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import get_content_declaration
from tests.spell_test_exports import (
    ALL_SPELLS,
    SPELL_CONTENT_DECLARATIONS,
    SPELL_CONTENT_DECLARATIONS_BY_CLASS,
    SPELL_CONTENT_DECLARATIONS_BY_NAME,
    SPELL_CONTENT_IDENTITY_SPECS,
)


def test_all_public_spells_have_one_explicit_exact_content_identity() -> None:
    """The public spell catalog cannot infer content identity from a label."""
    assert tuple(ALL_SPELLS.items()) == tuple(
        (spec.display_name, spec.spell_type)
        for spec in SPELL_CONTENT_IDENTITY_SPECS
    )
    assert set(SPELL_CONTENT_DECLARATIONS_BY_NAME) == set(ALL_SPELLS)
    assert set(SPELL_CONTENT_DECLARATIONS_BY_CLASS) == set(ALL_SPELLS.values())

    refs = tuple(
        declaration.ref
        for declaration in SPELL_CONTENT_DECLARATIONS
    )
    assert len({ref.identity_key for ref in refs}) == len(refs)
    assert all(
        ref.definition_kind is ContentDefinitionKind.SPELL
        for ref in refs
    )

    for spec, declaration in zip(
        SPELL_CONTENT_IDENTITY_SPECS,
        SPELL_CONTENT_DECLARATIONS,
        strict=True,
    ):
        assert SPELL_CONTENT_DECLARATIONS_BY_NAME[spec.display_name] is declaration
        assert SPELL_CONTENT_DECLARATIONS_BY_CLASS[spec.spell_type] is declaration
        assert get_content_declaration(spec.spell_type).ref == declaration.ref
        assert declaration.ref.pack_id == spec.pack_id
        assert declaration.ref.content_id == spec.content_id
        assert declaration.descriptor.display_name == spec.display_name


def test_spell_icon_keys_use_exact_authored_manifest_identity() -> None:
    """Manifest keys are authored facts, never content-id normalization."""
    assert (
        SPELL_CONTENT_DECLARATIONS_BY_NAME[
            "Burning Hands"
        ].descriptor.presentation.icon_key
        == "spell.burning-hands"
    )
    assert (
        SPELL_CONTENT_DECLARATIONS_BY_NAME[
            "Lightning Bolt"
        ].descriptor.presentation.icon_key
        == "spell.lightning-bolt"
    )
