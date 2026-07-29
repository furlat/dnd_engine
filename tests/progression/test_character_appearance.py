"""Exact durable character appearance resolution and projection."""

from __future__ import annotations

from uuid import uuid4

import pytest

from dnd.blocks.appearance import Appearance
from dnd.content_system.character_appearance import (
    PLAYER_CHARACTER_APPEARANCE_OPTIONS,
    default_player_character_appearance,
    migrate_player_character_appearance,
    resolve_player_character_appearance,
)
from dnd.core.content.durable_characters import (
    CharacterAppearanceOptionSelection,
    CharacterAppearanceSelection,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from server.world_projection import project_appearance


_BODY_REF = ContentRef(
    pack_id="test.appearance",
    definition_kind=ContentDefinitionKind.CREATURE,
    content_id="creature.player_body",
    content_version=1,
    definition_contract_hash="a" * 64,
)
_SPECIES_REF = ContentRef(
    pack_id="test.appearance",
    definition_kind=ContentDefinitionKind.SPECIES,
    content_id="species.human",
    content_version=1,
    definition_contract_hash="b" * 64,
)


def _selection(
    replacements: dict[str, str] | None = None,
) -> CharacterAppearanceSelection:
    replacements = replacements or {}
    return CharacterAppearanceSelection(
        options=tuple(
            CharacterAppearanceOptionSelection(
                option_id=row.option_id,
                value_id=replacements.get(row.option_id, row.value_id),
            )
            for row in default_player_character_appearance().options
        ),
    )


def _resolve(
    selection: CharacterAppearanceSelection,
):
    return resolve_player_character_appearance(
        body_ref=_BODY_REF,
        species_ref=_SPECIES_REF,
        selection=selection,
    )


def test_default_selection_persists_every_required_appearance_dimension() -> None:
    assert tuple(
        (row.option_id, row.value_id)
        for row in default_player_character_appearance().options
    ) == (
        ("appearance.beard", "appearance.beard.absent"),
        (
            "appearance.beard_tint",
            "appearance.beard_tint.follow_hair",
        ),
        ("appearance.body", "appearance.body.humanoid"),
        ("appearance.build", "appearance.build.average"),
        ("appearance.hair_tint", "appearance.color.auburn"),
        ("appearance.head", "appearance.head.hair_09"),
        ("appearance.skin_tint", "appearance.color.light_tan"),
        ("appearance.stature", "appearance.stature.average"),
    )


def test_creator_exposes_curated_hair_skin_and_beard_palettes() -> None:
    options = {
        option.option_id: option
        for option in PLAYER_CHARACTER_APPEARANCE_OPTIONS
    }
    hair_values = options["appearance.hair_tint"].values
    skin_values = options["appearance.skin_tint"].values
    beard_values = options["appearance.beard_tint"].values

    assert len(hair_values) == 20
    assert len(skin_values) == 20
    assert len(beard_values) == 21
    assert tuple(
        value.value_id for value in beard_values[1:]
    ) == tuple(value.value_id for value in hair_values)
    assert beard_values[0].value_id == "appearance.beard_tint.follow_hair"
    assert beard_values[0].tint_rgb is None
    assert (
        beard_values[0].tint_source_option_id
        == "appearance.hair_tint"
    )
    for value in (*hair_values, *skin_values, *beard_values[1:]):
        assert value.tint_rgb is not None
        assert value.tint_source_option_id is None


def test_beard_tint_follows_hair_unless_explicitly_overridden() -> None:
    following = _selection({
        "appearance.beard": "appearance.beard.present",
        "appearance.beard_tint": "appearance.beard_tint.follow_hair",
        "appearance.hair_tint": "appearance.color.copper",
    })
    explicit = _selection({
        "appearance.beard": "appearance.beard.present",
        "appearance.beard_tint": "appearance.color.silver",
        "appearance.hair_tint": "appearance.color.copper",
    })

    assert _resolve(following).hair_tint == 0xB65C36
    assert _resolve(following).beard_tint == 0xB65C36
    assert _resolve(explicit).hair_tint == 0xB65C36
    assert _resolve(explicit).beard_tint == 0xB8BCC4


def test_absent_beard_projects_zero_tint_without_destroying_follow_semantics() -> None:
    selection = _selection({
        "appearance.beard": "appearance.beard.absent",
        "appearance.beard_tint": "appearance.beard_tint.follow_hair",
        "appearance.hair_tint": "appearance.color.copper",
    })

    assert next(
        row.value_id
        for row in selection.options
        if row.option_id == "appearance.beard_tint"
    ) == "appearance.beard_tint.follow_hair"
    assert not _resolve(selection).has_beard
    assert _resolve(selection).beard_tint == 0


@pytest.mark.parametrize(
    ("value_id", "head_category"),
    (
        ("appearance.head.hair_01", "Head1"),
        ("appearance.head.hair_09", "Head9"),
        ("appearance.head.hair_10", "Head10"),
        ("appearance.head.hair_16", "Head16"),
        ("appearance.head.hair_17", "Head17"),
        ("appearance.head.hair_22", "Head22"),
    ),
)
def test_every_supported_hair_rig_has_one_exact_durable_token(
    value_id: str,
    head_category: str,
) -> None:
    resolved = _resolve(_selection({"appearance.head": value_id}))
    assert resolved.head_category == head_category


@pytest.mark.parametrize(
    ("value_id", "visual_scale_x"),
    (
        ("appearance.build.slender", 0.9),
        ("appearance.build.average", 1.0),
        ("appearance.build.broad", 1.1),
    ),
)
def test_build_choice_resolves_only_to_horizontal_presentation_scale(
    value_id: str,
    visual_scale_x: float,
) -> None:
    resolved = _resolve(_selection({"appearance.build": value_id}))
    assert resolved.visual_scale_x == visual_scale_x
    assert resolved.visual_scale == 1.0


@pytest.mark.parametrize(
    ("value_id", "visual_scale"),
    (
        ("appearance.stature.short", 0.9),
        ("appearance.stature.average", 1.0),
        ("appearance.stature.tall", 1.1),
    ),
)
def test_stature_choice_resolves_only_to_uniform_presentation_scale(
    value_id: str,
    visual_scale: float,
) -> None:
    resolved = _resolve(_selection({"appearance.stature": value_id}))
    assert resolved.visual_scale == visual_scale
    assert resolved.visual_scale_x == 1.0


def test_retired_six_option_selection_fails_closed_without_default_inference() -> None:
    current = default_player_character_appearance()
    retired = CharacterAppearanceSelection(
        options=tuple(
            row
            for row in current.options
            if row.option_id not in {"appearance.build", "appearance.stature"}
        ),
    )

    with pytest.raises(ValueError, match="exact ordered options"):
        _resolve(retired)

    migration = migrate_player_character_appearance(retired)
    assert tuple(
        (row.option_id, row.value_id)
        for row in migration.added_options
    ) == (
        ("appearance.build", "appearance.build.average"),
        ("appearance.stature", "appearance.stature.average"),
    )
    assert _resolve(migration.selection).visual_scale == 1.0
    assert _resolve(migration.selection).visual_scale_x == 1.0


def test_partially_missing_new_dimensions_fail_closed() -> None:
    partial = CharacterAppearanceSelection(
        options=tuple(
            row
            for row in default_player_character_appearance().options
            if row.option_id != "appearance.build"
        ),
    )

    with pytest.raises(ValueError, match="exact ordered options"):
        _resolve(partial)


def test_unknown_appearance_value_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown human player appearance value"):
        _resolve(_selection({"appearance.build": "appearance.build.massive"}))


def test_horizontal_scale_projects_through_the_canonical_appearance_dto() -> None:
    appearance = Appearance.create(
        source_entity_uuid=uuid4(),
        config=_resolve(_selection({"appearance.build": "appearance.build.broad"})),
    )

    projected = project_appearance(appearance)

    assert projected.visual_scale == 1.0
    assert projected.visual_scale_x == 1.1
