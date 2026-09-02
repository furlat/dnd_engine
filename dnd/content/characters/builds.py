"""One direct authored build and composition path for player characters."""

from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

from dnd.actions_functional import setup_standard_actions, update_weapon_templates
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.appearance import AppearanceConfig, BodyCategory, HeadCategory
from dnd.blocks.creature_proficiencies import CreatureProficienciesConfig
from dnd.blocks.health import HealthConfig
from dnd.content.characters.class_definitions import (
    resolve_barbarian_level,
    resolve_fighter_level,
    resolve_sorcerer_level,
)
from dnd.content.characters.origin_definitions import ResolvedOrigin, resolve_origin
from dnd.content.characters.origin_grants import apply_origin
from dnd.content.characters.progression import apply_initial_class_levels
from dnd.content.items.authored_item_builders import (
    DIRECT_ITEM_BUILDERS,
    build_authored_item,
)
from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.core.progression import point_buy_cost
from dnd.entity import Entity, EntityConfig
from dnd.items.torches import Torch
from dnd.types.abilities import AbilityName
from dnd.types.character_progression import (
    AppliedClassLevel,
    AppliedOriginState,
    Background,
    CharacterClass,
    FeatureToggleSelection,
    OriginChoiceSelection,
    PreparedSpellSelection,
    Species,
    SpeciesVariant,
)


CHARACTER_BODY_ID = "creature.player.humanoid_body"
SUPPORTED_FEATURE_TOGGLE_IDS = frozenset({
    "class_feature.fighter.fighting_style.great_weapon_fighting",
    "class_feature.fighter.fighting_style.protection",
    "class_feature.fighter.indomitable",
    "class_feature.barbarian.retaliation",
    "feat.lucky",
})


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


@dataclass(frozen=True, slots=True)
class ResolvedCharacterBuild:
    """Pure validated values consumed by the single composition function."""

    build: CharacterBuild
    origin: ResolvedOrigin
    known_spell_ids: tuple[str, ...]


def _multiclass_prerequisite(
    class_id: CharacterClass,
    abilities: dict[AbilityName, int],
) -> bool:
    if class_id is CharacterClass.BARBARIAN:
        return abilities["strength"] >= 13
    if class_id is CharacterClass.FIGHTER:
        return abilities["strength"] >= 13 or abilities["dexterity"] >= 13
    return abilities["charisma"] >= 13


def _known_spells(levels: tuple[AppliedClassLevel, ...]) -> tuple[str, ...]:
    known: list[str] = []
    for level in levels:
        if level.class_id is not CharacterClass.SORCERER:
            continue
        for choice in level.choices:
            if choice.choice_id.endswith((".cantrips", ".spell_known")):
                known.extend(choice.values)
            elif choice.choice_id.endswith(".spell_replacement"):
                old_spell, new_spell = choice.values
                known.remove(old_spell)
                known.append(new_spell)
    return tuple(known)


def resolve_character_build(build: CharacterBuild) -> ResolvedCharacterBuild:
    """Validate one complete build without creating any runtime owner."""
    if not build.name.strip():
        raise ValueError("character name cannot be empty")
    if build.character_body_id != CHARACTER_BODY_ID:
        raise ValueError("unsupported direct character body")
    if not build.class_levels:
        raise ValueError("a character build requires at least one class level")
    if len(build.class_levels) > 20:
        raise ValueError("total character level cannot exceed 20")

    point_buy_total = sum(
        point_buy_cost(score)
        for _ability, score in build.base_ability_scores
    )
    if point_buy_total != 27:
        raise ValueError(
            f"base ability scores must spend exactly 27 points, got {point_buy_total}",
        )

    state = AppliedOriginState(
        base_ability_scores=build.base_ability_scores,
        flexible_ability_bonuses=build.flexible_ability_bonuses,
        choices=build.origin_choices,
    )
    origin = resolve_origin(
        species=build.species,
        species_variant=build.species_variant,
        background=build.background,
        state=state,
    )
    abilities = dict(build.base_ability_scores)
    for ability, amount in build.flexible_ability_bonuses:
        abilities[ability] += amount

    applied: tuple[AppliedClassLevel, ...] = ()
    class_ids: set[CharacterClass] = set()
    owned_features: set[str] = set()
    for index, level in enumerate(build.class_levels):
        if class_ids and level.class_id not in class_ids:
            for class_id in (*tuple(class_ids), level.class_id):
                if not _multiclass_prerequisite(class_id, abilities):
                    raise ValueError(
                        f"multiclass prerequisite is not met for {class_id.value}",
                    )
        if level.class_id is CharacterClass.FIGHTER:
            resolved_level = resolve_fighter_level(
                level,
                applied,
                initial_first_class=index == 0,
            )
        elif level.class_id is CharacterClass.BARBARIAN:
            resolved_level = resolve_barbarian_level(
                level,
                applied,
                initial_first_class=index == 0,
            )
        else:
            resolved_level = resolve_sorcerer_level(
                level,
                applied,
                initial_first_class=index == 0,
            )
        for ability, amount in resolved_level.ability_increases:
            abilities[ability] += amount
            if abilities[ability] > 20:
                raise ValueError(f"ASI would raise {ability} above 20")
        owned_features.update(resolved_level.feature_ids)
        applied = (*applied, level)
        class_ids.add(level.class_id)

    source_ids = tuple(row.source_id for row in build.prepared_spells)
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("prepared spell sources must be unique")
    known_spell_ids = _known_spells(build.class_levels)
    known_spells = set(known_spell_ids)
    for row in build.prepared_spells:
        if row.source_id != "class.sorcerer.spellcasting":
            raise ValueError(f"unsupported prepared spell source {row.source_id!r}")
        unknown = set(row.spell_ids) - known_spells
        if unknown:
            raise ValueError(
                "prepared spells must already be known: "
                f"{', '.join(sorted(unknown))}",
            )

    toggle_ids = tuple(row.feature_id for row in build.feature_toggles)
    if len(set(toggle_ids)) != len(toggle_ids):
        raise ValueError("feature toggle IDs must be unique")
    unsupported = set(toggle_ids) - SUPPORTED_FEATURE_TOGGLE_IDS
    if unsupported:
        raise ValueError(
            f"unsupported feature toggle {min(unsupported)!r}",
        )
    for toggle in build.feature_toggles:
        if toggle.enabled and toggle.feature_id not in owned_features:
            raise ValueError(
                f"enabled feature toggle {toggle.feature_id!r} is not owned",
            )

    occupied_slots = tuple(
        row.equipment_slot
        for row in build.item_loadout
        if row.equipment_slot is not None
    )
    if len(set(occupied_slots)) != len(occupied_slots):
        raise ValueError("character loadout repeats an equipment slot")
    for row in build.item_loadout:
        if row.item_id not in DIRECT_ITEM_BUILDERS:
            raise ValueError(f"unknown direct character item {row.item_id!r}")

    build.appearance.config()
    return ResolvedCharacterBuild(
        build=build,
        origin=origin,
        known_spell_ids=known_spell_ids,
    )


def _ability_config(
    scores: tuple[tuple[AbilityName, int], ...],
) -> AbilityScoresConfig:
    values = dict(scores)
    return AbilityScoresConfig(
        strength=AbilityConfig(ability_score=values["strength"]),
        dexterity=AbilityConfig(ability_score=values["dexterity"]),
        constitution=AbilityConfig(ability_score=values["constitution"]),
        intelligence=AbilityConfig(ability_score=values["intelligence"]),
        wisdom=AbilityConfig(ability_score=values["wisdom"]),
        charisma=AbilityConfig(ability_score=values["charisma"]),
    )


def create_character(
    build: CharacterBuild,
    *,
    runtime_entity_uuid: UUID | None = None,
    faction: str | None = None,
    position: tuple[int, int] | None = None,
) -> Entity:
    """Compose one direct character and publish its sole birth fact."""
    resolved = resolve_character_build(build)
    entity_uuid = runtime_entity_uuid or uuid4()
    entity = Entity.create(
        entity_uuid,
        name=build.name,
        description=build.description,
        config=EntityConfig(
            ability_scores=_ability_config(build.base_ability_scores),
            health=HealthConfig(hit_dices=[]),
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_weapon_ids=(),
                base_armor_types=(),
                base_shields=False,
            ),
            proficiency_bonus=2,
            position=position if position is not None else build.position,
            faction=faction if faction is not None else build.faction,
            appearance=build.appearance.config(),
            weight=build.weight,
            uses_death_saves=True,
        ),
    )
    try:
        entity.set_character_body_identity(build.character_body_id)
        entity.prepared_spell_selections = build.prepared_spells
        entity.feature_toggle_selections = build.feature_toggles
        setup_standard_actions(entity)
        apply_origin(
            entity,
            resolved.origin,
            character_level=len(build.class_levels),
        )
        apply_initial_class_levels(entity, build.class_levels)

        placements = tuple(
            (
                build_authored_item(
                    row.item_id,
                    entity.uuid,
                    quantity=row.quantity,
                ),
                row.equipment_slot,
            )
            for row in build.item_loadout
        )
        entity.install_initial_items(placements)
        update_weapon_templates(entity)
        for row, (item, _slot) in zip(build.item_loadout, placements):
            if row.item_id == "equipment.portable_torch":
                cast(Torch, item).ignite(entity.uuid)
        entity.compose_entity()
        return entity
    except BaseException:
        if Entity.get(entity.uuid) is entity and not entity.creation_committed:
            entity.discard_uncommitted()
        raise


__all__ = [
    "CHARACTER_BODY_ID",
    "SUPPORTED_FEATURE_TOGGLE_IDS",
    "CharacterAppearance",
    "CharacterBuild",
    "ResolvedCharacterBuild",
    "create_character",
    "resolve_character_build",
]
