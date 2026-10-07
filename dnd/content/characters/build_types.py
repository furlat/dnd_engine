"""Passive saved character inputs, independent of native composition."""

from dataclasses import dataclass

from dnd.types.appearance import AppearanceConfig, BodyCategory, HeadCategory
from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.types.abilities import AbilityName
from dnd.types.character_progression import (
    AppliedClassLevel, Background, FeatureToggleSelection, OriginChoiceSelection,
    PreparedSpellSelection, Species, SpeciesVariant,
)

CHARACTER_BODY_ID = "creature.player.humanoid_body"


@dataclass(frozen=True, slots=True)
class CharacterAppearance:
    """Plain mechanical appearance values copied from accepted evidence."""

    visual_scale: float = 1.0
    visual_scale_x: float = 1.0
    body_category: BodyCategory = "NakedBody"
    skin_tint: int = 0xDDAA88
    head_category: HeadCategory | None = None
    hair_tint: int = 0
    has_beard: bool = False
    beard_tint: int = 0
    portrait_key: str | None = None

    def config(self) -> AppearanceConfig:
        """Validate and project these values onto the existing owner config."""
        return AppearanceConfig(
            visual_scale=self.visual_scale,
            visual_scale_x=self.visual_scale_x,
            body_category=self.body_category,
            skin_tint=self.skin_tint,
            head_category=self.head_category,
            hair_tint=self.hair_tint,
            has_beard=self.has_beard,
            beard_tint=self.beard_tint,
            portrait_key=self.portrait_key,
        )


@dataclass(frozen=True, slots=True)
class CharacterBuild:
    """Complete saveable authored input for one direct character."""

    name: str
    base_ability_scores: tuple[tuple[AbilityName, int], ...]
    flexible_ability_bonuses: tuple[tuple[AbilityName, int], ...]
    species: Species
    background: Background
    class_levels: tuple[AppliedClassLevel, ...]
    item_loadout: tuple[ItemLoadoutEntry, ...]
    appearance: CharacterAppearance
    species_variant: SpeciesVariant | None = None
    origin_choices: tuple[OriginChoiceSelection, ...] = ()
    prepared_spells: tuple[PreparedSpellSelection, ...] = ()
    feature_toggles: tuple[FeatureToggleSelection, ...] = ()
    character_body_id: str = CHARACTER_BODY_ID
    description: str = "Direct player character"
    faction: str | None = None
    position: tuple[int, int] = (0, 0)
    weight: int = 150


