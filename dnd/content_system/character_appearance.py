"""Exact durable appearance resolution for the installed player body.

Character revisions persist stable semantic option/value tokens.  This module
owns the one adapter from those cold tokens to the current engine Appearance
block.  Class progression never chooses appearance, and renderers never infer
it from a class, display name, or premade identifier.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, cast

from dnd.blocks.appearance import (
    Appearance,
    AppearanceConfig,
    BodyCategory,
    HeadCategory,
)
from dnd.core.content.durable_characters import (
    CharacterAppearanceOptionSelection,
    CharacterAppearanceSelection,
)
from dnd.core.content.identities import ContentRef


CharacterAppearanceControlKind = Literal["choice", "color"]
CharacterAppearanceRuntimeValue = (
    BodyCategory | HeadCategory | int | float | bool
)
CharacterAppearanceTintSourceOptionId = Literal["appearance.hair_tint"]


@dataclass(frozen=True, slots=True)
class CharacterAppearanceValueSpec:
    """One selectable semantic value and its exact runtime projection."""

    value_id: str
    display_name: str
    runtime_value: CharacterAppearanceRuntimeValue | None
    tint_rgb: int | None = None
    tint_source_option_id: CharacterAppearanceTintSourceOptionId | None = None


@dataclass(frozen=True, slots=True)
class CharacterAppearanceOptionSpec:
    """One closed appearance option shared by validation and the catalog."""

    option_id: str
    display_name: str
    control_kind: CharacterAppearanceControlKind
    default_value_id: str
    values: tuple[CharacterAppearanceValueSpec, ...]

    def __post_init__(self) -> None:
        value_ids = tuple(value.value_id for value in self.values)
        if not value_ids or len(set(value_ids)) != len(value_ids):
            raise ValueError(
                f"{self.option_id} requires unique appearance values",
            )
        if self.default_value_id not in value_ids:
            raise ValueError(
                f"{self.option_id} default must identify one value",
            )
        for value in self.values:
            has_literal_tint = value.tint_rgb is not None
            has_tint_source = value.tint_source_option_id is not None
            if self.control_kind == "color":
                if has_literal_tint == has_tint_source:
                    raise ValueError(
                        f"{self.option_id} color values require exactly one "
                        "literal tint or tint source",
                    )
                if has_literal_tint and value.runtime_value != value.tint_rgb:
                    raise ValueError(
                        f"{value.value_id} runtime tint must match tint_rgb",
                    )
                if has_tint_source and value.runtime_value is not None:
                    raise ValueError(
                        f"{value.value_id} sourced tint has no literal runtime "
                        "value",
                    )
            elif has_literal_tint or has_tint_source:
                raise ValueError(
                    f"{self.option_id} non-color values cannot carry tint facts",
                )


@dataclass(frozen=True, slots=True)
class CharacterAppearanceConstraintSpec:
    """One exact cross-option compatibility rule for creator clients."""

    when_option_id: str
    when_value_id: str
    required_option_id: str
    allowed_value_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CharacterAppearanceMigration:
    """One explicit retired-selection projection onto the current vocabulary."""

    selection: CharacterAppearanceSelection
    added_options: tuple[CharacterAppearanceOptionSelection, ...] = ()


def _tint(
    value_id: str,
    display_name: str,
    tint_rgb: int,
) -> CharacterAppearanceValueSpec:
    """Return one exact literal creator tint."""

    return CharacterAppearanceValueSpec(
        value_id=value_id,
        display_name=display_name,
        runtime_value=tint_rgb,
        tint_rgb=tint_rgb,
    )


_HAIR_TINT_VALUE_SPECS = (
    _tint("appearance.color.none", "Untinted", 0x000000),
    _tint("appearance.color.raven", "Raven", 0x17151A),
    _tint("appearance.color.charcoal", "Charcoal", 0x302A30),
    _tint("appearance.color.dark_brown", "Dark Brown", 0x3A241B),
    _tint("appearance.color.chestnut", "Chestnut", 0x5A3026),
    _tint("appearance.color.walnut", "Walnut", 0x6B432D),
    _tint("appearance.color.auburn", "Auburn", 0x993F00),
    _tint("appearance.color.copper", "Copper", 0xB65C36),
    _tint("appearance.color.ginger", "Ginger", 0xD2763A),
    _tint("appearance.color.mahogany", "Mahogany", 0x6F2C2C),
    _tint("appearance.color.burgundy", "Burgundy", 0x6A2942),
    _tint("appearance.color.ash_brown", "Ash Brown", 0x75675F),
    _tint("appearance.color.golden_brown", "Golden Brown", 0x9A6A35),
    _tint("appearance.color.honey", "Honey", 0xC58B3C),
    _tint("appearance.color.blonde", "Blonde", 0xD9B86C),
    _tint("appearance.color.sand", "Sand", 0xD0BFA1),
    _tint("appearance.color.light_tan", "Light Tan", 0xE6BC98),
    _tint("appearance.color.warm_tan", "Warm Tan", 0xD4AA78),
    _tint("appearance.color.platinum", "Platinum", 0xE7DFD0),
    _tint("appearance.color.silver", "Silver", 0xB8BCC4),
)

_SKIN_TINT_VALUE_SPECS = (
    _tint("appearance.color.none", "Untinted", 0x000000),
    _tint("appearance.color.auburn", "Auburn", 0x993F00),
    _tint("appearance.color.sand", "Sand", 0xD0BFA1),
    _tint("appearance.color.light_tan", "Light Tan", 0xE6BC98),
    _tint("appearance.color.warm_tan", "Warm Tan", 0xD4AA78),
    _tint("appearance.color.porcelain", "Porcelain", 0xF2D2C0),
    _tint("appearance.color.fair", "Fair", 0xE8B89E),
    _tint("appearance.color.golden", "Golden", 0xC98A58),
    _tint("appearance.color.bronze", "Bronze", 0xA96F47),
    _tint("appearance.color.copper", "Copper", 0xB46C4C),
    _tint("appearance.color.olive", "Olive", 0xA38458),
    _tint("appearance.color.caramel", "Caramel", 0x9C6041),
    _tint("appearance.color.umber", "Umber", 0x744634),
    _tint("appearance.color.deep_brown", "Deep Brown", 0x56352B),
    _tint("appearance.color.ebony", "Ebony", 0x2F2224),
    _tint("appearance.color.ashen", "Ashen", 0xA59AA0),
    _tint("appearance.color.crimson", "Crimson", 0xA83F46),
    _tint("appearance.color.ocean_blue", "Ocean Blue", 0x4D648D),
    _tint("appearance.color.verdant", "Verdant", 0x5C7D52),
    _tint("appearance.color.violet", "Violet", 0x70507F),
)

_BEARD_TINT_VALUE_SPECS = (
    CharacterAppearanceValueSpec(
        value_id="appearance.beard_tint.follow_hair",
        display_name="Match Hair",
        runtime_value=None,
        tint_source_option_id="appearance.hair_tint",
    ),
    *_HAIR_TINT_VALUE_SPECS,
)

PLAYER_CHARACTER_APPEARANCE_OPTIONS = (
    CharacterAppearanceOptionSpec(
        option_id="appearance.beard",
        display_name="Beard",
        control_kind="choice",
        default_value_id="appearance.beard.absent",
        values=(
            CharacterAppearanceValueSpec(
                value_id="appearance.beard.absent",
                display_name="No Beard",
                runtime_value=False,
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.beard.present",
                display_name="Beard",
                runtime_value=True,
            ),
        ),
    ),
    CharacterAppearanceOptionSpec(
        option_id="appearance.beard_tint",
        display_name="Beard Color",
        control_kind="color",
        default_value_id="appearance.beard_tint.follow_hair",
        values=_BEARD_TINT_VALUE_SPECS,
    ),
    CharacterAppearanceOptionSpec(
        option_id="appearance.body",
        display_name="Body",
        control_kind="choice",
        default_value_id="appearance.body.humanoid",
        values=(
            CharacterAppearanceValueSpec(
                value_id="appearance.body.humanoid",
                display_name="Humanoid",
                runtime_value="NakedBody",
            ),
        ),
    ),
    CharacterAppearanceOptionSpec(
        option_id="appearance.build",
        display_name="Build",
        control_kind="choice",
        default_value_id="appearance.build.average",
        values=(
            CharacterAppearanceValueSpec(
                value_id="appearance.build.slender",
                display_name="Slender",
                runtime_value=0.9,
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.build.average",
                display_name="Average",
                runtime_value=1.0,
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.build.broad",
                display_name="Broad",
                runtime_value=1.1,
            ),
        ),
    ),
    CharacterAppearanceOptionSpec(
        option_id="appearance.hair_tint",
        display_name="Hair Color",
        control_kind="color",
        default_value_id="appearance.color.auburn",
        values=_HAIR_TINT_VALUE_SPECS,
    ),
    CharacterAppearanceOptionSpec(
        option_id="appearance.head",
        display_name="Hair",
        control_kind="choice",
        default_value_id="appearance.head.hair_09",
        values=(
            CharacterAppearanceValueSpec(
                value_id="appearance.head.hair_01",
                display_name="Hair 01",
                runtime_value="Head1",
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.head.hair_09",
                display_name="Hair 09",
                runtime_value="Head9",
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.head.hair_10",
                display_name="Hair 10",
                runtime_value="Head10",
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.head.hair_16",
                display_name="Hair 16",
                runtime_value="Head16",
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.head.hair_17",
                display_name="Hair 17",
                runtime_value="Head17",
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.head.hair_22",
                display_name="Hair 22",
                runtime_value="Head22",
            ),
        ),
    ),
    CharacterAppearanceOptionSpec(
        option_id="appearance.skin_tint",
        display_name="Skin Color",
        control_kind="color",
        default_value_id="appearance.color.light_tan",
        values=_SKIN_TINT_VALUE_SPECS,
    ),
    CharacterAppearanceOptionSpec(
        option_id="appearance.stature",
        display_name="Stature",
        control_kind="choice",
        default_value_id="appearance.stature.average",
        values=(
            CharacterAppearanceValueSpec(
                value_id="appearance.stature.short",
                display_name="Short",
                runtime_value=0.9,
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.stature.average",
                display_name="Average",
                runtime_value=1.0,
            ),
            CharacterAppearanceValueSpec(
                value_id="appearance.stature.tall",
                display_name="Tall",
                runtime_value=1.1,
            ),
        ),
    ),
)

PLAYER_CHARACTER_APPEARANCE_CONSTRAINTS: tuple[
    CharacterAppearanceConstraintSpec,
    ...,
] = ()

_REQUIRED_OPTION_IDS = tuple(
    option.option_id for option in PLAYER_CHARACTER_APPEARANCE_OPTIONS
)
_RETIRED_V1_OPTION_IDS = tuple(
    option_id
    for option_id in _REQUIRED_OPTION_IDS
    if option_id not in {"appearance.build", "appearance.stature"}
)
_OPTION_VALUES: Mapping[
    str,
    Mapping[str, CharacterAppearanceValueSpec],
] = MappingProxyType({
    option.option_id: MappingProxyType({
        value.value_id: value for value in option.values
    })
    for option in PLAYER_CHARACTER_APPEARANCE_OPTIONS
})


def default_player_character_appearance() -> CharacterAppearanceSelection:
    """Return the canonical valid starting selection for a custom builder."""

    return CharacterAppearanceSelection(
        options=tuple(
            CharacterAppearanceOptionSelection(
                option_id=option.option_id,
                value_id=option.default_value_id,
            )
            for option in PLAYER_CHARACTER_APPEARANCE_OPTIONS
        ),
    )


def migrate_player_character_appearance(
    selection: CharacterAppearanceSelection,
) -> CharacterAppearanceMigration:
    """Explicitly upgrade the one released six-option appearance vocabulary.

    Unknown or partially matching shapes are returned unchanged so ordinary
    strict validation reports them.  This migration is called only by the
    durable-character rebase service; runtime appearance resolution never
    supplies missing values.
    """

    option_ids = tuple(row.option_id for row in selection.options)
    if option_ids == _REQUIRED_OPTION_IDS:
        return CharacterAppearanceMigration(selection=selection)
    if option_ids != _RETIRED_V1_OPTION_IDS:
        return CharacterAppearanceMigration(selection=selection)
    existing = {
        row.option_id: row
        for row in selection.options
    }
    defaults = {
        row.option_id: row
        for row in default_player_character_appearance().options
    }
    added_options = (
        defaults["appearance.build"],
        defaults["appearance.stature"],
    )
    return CharacterAppearanceMigration(
        selection=CharacterAppearanceSelection(
            options=tuple(
                existing.get(option_id, defaults[option_id])
                for option_id in _REQUIRED_OPTION_IDS
            ),
        ),
        added_options=added_options,
    )


def _selection(
    *,
    skin_tint: str,
    hair_tint: str,
    head: str,
    build: str,
    stature: str,
    has_beard: bool,
    beard_tint: str,
) -> CharacterAppearanceSelection:
    """Build one exact built-in selection in canonical option order."""
    return CharacterAppearanceSelection(
        options=(
            CharacterAppearanceOptionSelection(
                option_id="appearance.beard",
                value_id=(
                    "appearance.beard.present"
                    if has_beard
                    else "appearance.beard.absent"
                ),
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.beard_tint",
                value_id=beard_tint,
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.body",
                value_id="appearance.body.humanoid",
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.build",
                value_id=build,
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.hair_tint",
                value_id=hair_tint,
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.head",
                value_id=head,
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.skin_tint",
                value_id=skin_tint,
            ),
            CharacterAppearanceOptionSelection(
                option_id="appearance.stature",
                value_id=stature,
            ),
        ),
    )


BARBARIAN_HUMAN_APPEARANCE = _selection(
    skin_tint="appearance.color.warm_tan",
    hair_tint="appearance.color.sand",
    head="appearance.head.hair_17",
    build="appearance.build.broad",
    stature="appearance.stature.tall",
    has_beard=False,
    beard_tint="appearance.color.none",
)
FIGHTER_HUMAN_APPEARANCE = _selection(
    skin_tint="appearance.color.light_tan",
    hair_tint="appearance.color.auburn",
    head="appearance.head.hair_10",
    build="appearance.build.average",
    stature="appearance.stature.average",
    has_beard=True,
    beard_tint="appearance.color.auburn",
)
SORCERER_HUMAN_APPEARANCE = _selection(
    skin_tint="appearance.color.light_tan",
    hair_tint="appearance.color.auburn",
    head="appearance.head.hair_22",
    build="appearance.build.slender",
    stature="appearance.stature.short",
    has_beard=False,
    beard_tint="appearance.color.none",
)


def resolve_player_character_appearance(
    *,
    body_ref: ContentRef,
    species_ref: ContentRef,
    selection: CharacterAppearanceSelection,
) -> AppearanceConfig:
    """Validate and resolve one exact semantic appearance selection.

    Body and species identities are deliberately accepted as context rather
    than switched on here.  Installed origin definitions will own any future
    body/species option constraints; the cold persisted value tokens remain
    independent of Python factory identities.
    """
    _ = body_ref, species_ref

    values = {
        row.option_id: row.value_id
        for row in selection.options
    }
    option_ids = tuple(values)
    if option_ids != _REQUIRED_OPTION_IDS:
        raise ValueError(
            "human player appearance requires exact ordered options "
            f"{_REQUIRED_OPTION_IDS}; got {option_ids}",
        )
    try:
        body_category = cast(
            BodyCategory,
            _OPTION_VALUES["appearance.body"][
                values["appearance.body"]
            ].runtime_value,
        )
        head_category = cast(
            HeadCategory,
            _OPTION_VALUES["appearance.head"][
                values["appearance.head"]
            ].runtime_value,
        )
        skin_tint = cast(
            int,
            _OPTION_VALUES["appearance.skin_tint"][
                values["appearance.skin_tint"]
            ].runtime_value,
        )
        hair_tint = cast(
            int,
            _OPTION_VALUES["appearance.hair_tint"][
                values["appearance.hair_tint"]
            ].runtime_value,
        )
        has_beard = cast(
            bool,
            _OPTION_VALUES["appearance.beard"][
                values["appearance.beard"]
            ].runtime_value,
        )
        beard_tint_spec = _OPTION_VALUES["appearance.beard_tint"][
            values["appearance.beard_tint"]
        ]
        beard_tint = (
            hair_tint
            if beard_tint_spec.tint_source_option_id
            == "appearance.hair_tint"
            else cast(int, beard_tint_spec.runtime_value)
        )
        visual_scale = cast(
            float,
            _OPTION_VALUES["appearance.stature"][
                values["appearance.stature"]
            ].runtime_value,
        )
        visual_scale_x = cast(
            float,
            _OPTION_VALUES["appearance.build"][
                values["appearance.build"]
            ].runtime_value,
        )
    except KeyError as exc:
        raise ValueError(
            f"unknown human player appearance value {exc.args[0]!r}",
        ) from exc
    if not has_beard:
        beard_tint = 0

    return AppearanceConfig(
        visual_scale=visual_scale,
        visual_scale_x=visual_scale_x,
        body_category=body_category,
        skin_tint=skin_tint,
        head_category=head_category,
        hair_tint=hair_tint,
        has_beard=has_beard,
        beard_tint=beard_tint,
    )


def apply_player_character_appearance(
    appearance: Appearance,
    *,
    body_ref: ContentRef,
    species_ref: ContentRef,
    selection: CharacterAppearanceSelection,
) -> None:
    """Commit one validated durable selection to the owned Appearance block."""
    config = resolve_player_character_appearance(
        body_ref=body_ref,
        species_ref=species_ref,
        selection=selection,
    )
    appearance.apply_config(config)


__all__ = [
    "BARBARIAN_HUMAN_APPEARANCE",
    "CharacterAppearanceConstraintSpec",
    "CharacterAppearanceControlKind",
    "CharacterAppearanceMigration",
    "CharacterAppearanceOptionSpec",
    "CharacterAppearanceValueSpec",
    "FIGHTER_HUMAN_APPEARANCE",
    "PLAYER_CHARACTER_APPEARANCE_CONSTRAINTS",
    "PLAYER_CHARACTER_APPEARANCE_OPTIONS",
    "SORCERER_HUMAN_APPEARANCE",
    "apply_player_character_appearance",
    "default_player_character_appearance",
    "migrate_player_character_appearance",
    "resolve_player_character_appearance",
]
