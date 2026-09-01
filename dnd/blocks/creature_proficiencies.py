"""Creature-owned training for weapons, armor, and shields."""

from collections.abc import Iterable
from uuid import UUID

from pydantic import BaseModel, Field

from dnd.core.base_block import BaseBlock
from dnd.core.content.identities import validate_namespaced_id
from dnd.core.equipment_types import ArmorType, WeaponProperty
from dnd.core.proficiency_types import ProficiencyMode, ProficiencySourceSet


_WEAPON_CATEGORIES = frozenset({
    WeaponProperty.SIMPLE,
    WeaponProperty.MARTIAL,
})
_ARMOR_CATEGORIES = frozenset({
    ArmorType.LIGHT,
    ArmorType.MEDIUM,
    ArmorType.HEAVY,
})


class CreatureProficienciesConfig(BaseModel):
    """Cold creature training installed before progression grants."""

    base_simple_weapons: bool = True
    base_martial_weapons: bool = True
    base_weapon_ids: tuple[str, ...] = ()
    base_armor_types: tuple[ArmorType, ...] = (
        ArmorType.LIGHT,
        ArmorType.MEDIUM,
        ArmorType.HEAVY,
    )
    base_shields: bool = True
    base_languages: tuple[str, ...] = ()
    base_tools: tuple[str, ...] = ()


class CreatureProficiencies(BaseBlock):
    """Source-owned creature training, independent from equipped gear."""

    name: str = "Creature Proficiencies"
    base_simple_weapons: bool = True
    base_martial_weapons: bool = True
    base_weapon_ids: frozenset[str] = Field(default_factory=frozenset)
    base_armor_types: frozenset[ArmorType] = Field(
        default_factory=lambda: frozenset(_ARMOR_CATEGORIES),
    )
    base_shields: bool = True
    weapon_sources: dict[WeaponProperty, ProficiencySourceSet] = Field(
        default_factory=lambda: {
            category: ProficiencySourceSet()
            for category in sorted(_WEAPON_CATEGORIES, key=lambda row: row.value)
        },
    )
    specific_weapon_sources: dict[str, ProficiencySourceSet] = Field(
        default_factory=dict,
    )
    armor_sources: dict[ArmorType, ProficiencySourceSet] = Field(
        default_factory=lambda: {
            category: ProficiencySourceSet()
            for category in sorted(_ARMOR_CATEGORIES, key=lambda row: row.value)
        },
    )
    shield_sources: ProficiencySourceSet = Field(
        default_factory=ProficiencySourceSet,
    )
    base_languages: frozenset[str] = Field(default_factory=frozenset)
    base_tools: frozenset[str] = Field(default_factory=frozenset)
    language_sources: dict[str, ProficiencySourceSet] = Field(
        default_factory=dict,
    )
    tool_sources: dict[str, ProficiencySourceSet] = Field(
        default_factory=dict,
    )

    @classmethod
    def create(
        cls,
        *,
        source_entity_uuid: UUID,
        config: CreatureProficienciesConfig | None = None,
    ) -> "CreatureProficiencies":
        """Create one creature-owned training block."""
        resolved = config or CreatureProficienciesConfig()
        unsupported = set(resolved.base_armor_types) - _ARMOR_CATEGORIES
        if unsupported:
            values = ", ".join(sorted(row.value for row in unsupported))
            raise ValueError(f"unsupported armor proficiency categories: {values}")
        base_weapon_ids = frozenset(
            validate_namespaced_id(item_id, "specific weapon item_id")
            for item_id in resolved.base_weapon_ids
        )
        return cls(
            source_entity_uuid=source_entity_uuid,
            base_simple_weapons=resolved.base_simple_weapons,
            base_martial_weapons=resolved.base_martial_weapons,
            base_weapon_ids=base_weapon_ids,
            base_armor_types=frozenset(resolved.base_armor_types),
            base_shields=resolved.base_shields,
            base_languages=frozenset(
                validate_namespaced_id(
                    language,
                    "base language",
                )
                for language in resolved.base_languages
            ),
            base_tools=frozenset(
                validate_namespaced_id(
                    tool,
                    "base tool",
                )
                for tool in resolved.base_tools
            ),
        )

    def add_weapon_source(
        self,
        source_id: UUID,
        category: WeaponProperty,
    ) -> None:
        """Grant one simple or martial weapon proficiency source."""
        if category not in _WEAPON_CATEGORIES:
            raise ValueError(
                f"{category.value} is not a weapon proficiency category",
            )
        self.weapon_sources[category].add(source_id, ProficiencyMode.FULL)

    def add_specific_weapon_source(
        self,
        source_id: UUID,
        weapon_id: str,
    ) -> None:
        """Grant proficiency with one exact authored weapon item."""
        weapon_key = validate_namespaced_id(
            weapon_id,
            "specific weapon item_id",
        )
        sources = self.specific_weapon_sources.setdefault(
            weapon_key,
            ProficiencySourceSet(),
        )
        sources.add(source_id, ProficiencyMode.FULL)

    def add_armor_source(
        self,
        source_id: UUID,
        category: ArmorType,
    ) -> None:
        """Grant one light, medium, or heavy armor proficiency source."""
        if category not in _ARMOR_CATEGORIES:
            raise ValueError(
                f"{category.value} is not an armor proficiency category",
            )
        self.armor_sources[category].add(source_id, ProficiencyMode.FULL)

    def add_shield_source(self, source_id: UUID) -> None:
        """Grant shield proficiency from one exact source."""
        self.shield_sources.add(source_id, ProficiencyMode.FULL)

    def add_language_source(
        self,
        source_id: UUID,
        language_id: str,
    ) -> None:
        """Grant knowledge of one exact language from one source."""
        language_key = validate_namespaced_id(language_id, "language_id")
        self.language_sources.setdefault(
            language_key,
            ProficiencySourceSet(),
        ).add(source_id, ProficiencyMode.FULL)

    def add_tool_source(
        self,
        source_id: UUID,
        tool_id: str,
    ) -> None:
        """Grant proficiency with one exact tool from one source."""
        tool_key = validate_namespaced_id(tool_id, "tool_id")
        self.tool_sources.setdefault(
            tool_key,
            ProficiencySourceSet(),
        ).add(source_id, ProficiencyMode.FULL)

    def remove_source(self, source_id: UUID) -> bool:
        """Remove one source from every creature-training category."""
        removed = self.shield_sources.remove(source_id)
        for sources in self.weapon_sources.values():
            removed = sources.remove(source_id) or removed
        empty_specific_keys: list[str] = []
        for weapon_key, sources in self.specific_weapon_sources.items():
            removed = sources.remove(source_id) or removed
            if not sources.sources:
                empty_specific_keys.append(weapon_key)
        for weapon_key in empty_specific_keys:
            del self.specific_weapon_sources[weapon_key]
        for sources in self.armor_sources.values():
            removed = sources.remove(source_id) or removed
        for source_sets in (self.language_sources, self.tool_sources):
            empty_keys: list[str] = []
            for identity, sources in source_sets.items():
                removed = sources.remove(source_id) or removed
                if not sources.sources:
                    empty_keys.append(identity)
            for identity in empty_keys:
                del source_sets[identity]
        return removed

    def is_weapon_proficient(
        self,
        properties: Iterable[WeaponProperty] | None,
        weapon_id: str | None = None,
    ) -> bool:
        """Return proficiency for an unarmed, simple, or martial attack."""
        if properties is None:
            return True
        if weapon_id is not None:
            weapon_key = validate_namespaced_id(
                weapon_id,
                "specific weapon item_id",
            )
            if weapon_key in self.base_weapon_ids:
                return True
            exact_sources = self.specific_weapon_sources.get(weapon_key)
            if exact_sources is not None and exact_sources.sources:
                return True
        property_set = frozenset(properties)
        category = (
            WeaponProperty.MARTIAL
            if WeaponProperty.MARTIAL in property_set
            else WeaponProperty.SIMPLE
        )
        if category == WeaponProperty.MARTIAL:
            return (
                self.base_martial_weapons
                or bool(self.weapon_sources[category].sources)
            )
        return (
            self.base_simple_weapons
            or bool(self.weapon_sources[category].sources)
        )

    def is_armor_proficient(self, armor_type: ArmorType) -> bool:
        """Return whether the creature is trained in one armor category."""
        if armor_type == ArmorType.CLOTH:
            return True
        sources = self.armor_sources.get(armor_type)
        if sources is None:
            return False
        return armor_type in self.base_armor_types or bool(sources.sources)

    def is_shield_proficient(self) -> bool:
        """Return whether any base or source-owned shield training exists."""
        return self.base_shields or bool(self.shield_sources.sources)

    def knows_language(self, language_id: str) -> bool:
        """Return whether a base or source-owned language is known."""
        language_key = validate_namespaced_id(language_id, "language_id")
        sources = self.language_sources.get(language_key)
        return (
            language_key in self.base_languages
            or (sources is not None and bool(sources.sources))
        )

    def is_tool_proficient(self, tool_id: str) -> bool:
        """Return whether a base or source-owned tool proficiency exists."""
        tool_key = validate_namespaced_id(tool_id, "tool_id")
        sources = self.tool_sources.get(tool_key)
        return (
            tool_key in self.base_tools
            or (sources is not None and bool(sources.sources))
        )


__all__ = [
    "CreatureProficiencies",
    "CreatureProficienciesConfig",
]
