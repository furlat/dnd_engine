"""Four ordinary frozen builds consumed by the direct character path."""

from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from dnd.content.characters.builds import (
    CharacterAppearance,
    CharacterBuild,
    create_character,
)
from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.entity import Entity
from dnd.types.character_progression import (
    AppliedClassLevel,
    Background,
    CharacterClass,
    CharacterSubclass,
    ClassChoiceSelection,
    OriginChoiceSelection,
    Species,
)


BARBARIAN_PREMADE_ID = "hero.barbarian_l5_berserker_torch"
FIGHTER_PREMADE_ID = "hero.fighter_l5_shield_torch"
SORCERER_PREMADE_ID = "hero.sorcerer_l5_standard_torch"
SPELLBLADE_PREMADE_ID = "hero.fighter_2_sorcerer_3_spellblade"

_HUMAN_ORIGIN = (
    OriginChoiceSelection(
        "species.human.additional_language",
        ("language.draconic",),
    ),
)


def _fighter_levels(
    count: int,
    *,
    style: str,
) -> tuple[AppliedClassLevel, ...]:
    rows: list[AppliedClassLevel] = []
    for level in range(1, count + 1):
        choices: list[ClassChoiceSelection] = []
        if level == 1:
            choices.extend((
                ClassChoiceSelection(
                    "class.fighter.first_class.starting_equipment",
                    ("starting_equipment.fighter.sword_shield",),
                ),
                ClassChoiceSelection(
                    "class.fighter.proficiencies.skills",
                    ("athletics", "perception"),
                ),
                ClassChoiceSelection(
                    "class.fighter.level_1.fighting_style",
                    (style,),
                ),
            ))
        elif level == 3:
            choices.append(ClassChoiceSelection(
                "class.fighter.level_3.subclass",
                (CharacterSubclass.CHAMPION.value,),
            ))
        elif level == 4:
            choices.append(ClassChoiceSelection(
                "class.fighter.level_4.asi_or_feat",
                ("ability_score.strength.2",),
            ))
        rows.append(AppliedClassLevel(
            step_id=f"class.fighter.level_{level}",
            character_level=level,
            class_id=CharacterClass.FIGHTER,
            resulting_class_level=level,
            subclass_id=(CharacterSubclass.CHAMPION if level >= 3 else None),
            choices=tuple(choices),
        ))
    return tuple(rows)


def _barbarian_levels() -> tuple[AppliedClassLevel, ...]:
    rows: list[AppliedClassLevel] = []
    for level in range(1, 6):
        choices: list[ClassChoiceSelection] = []
        if level == 1:
            choices.extend((
                ClassChoiceSelection(
                    "class.barbarian.first_class.starting_equipment",
                    ("starting_equipment.barbarian.greataxe",),
                ),
                ClassChoiceSelection(
                    "class.barbarian.proficiencies.skills",
                    ("athletics", "perception"),
                ),
            ))
        elif level == 3:
            choices.append(ClassChoiceSelection(
                "class.barbarian.level_3.subclass",
                (CharacterSubclass.BERSERKER.value,),
            ))
        elif level == 4:
            choices.append(ClassChoiceSelection(
                "class.barbarian.level_4.asi_or_feat",
                ("ability_score.strength.2",),
            ))
        rows.append(AppliedClassLevel(
            step_id=f"class.barbarian.level_{level}",
            character_level=level,
            class_id=CharacterClass.BARBARIAN,
            resulting_class_level=level,
            subclass_id=(CharacterSubclass.BERSERKER if level >= 3 else None),
            choices=tuple(choices),
        ))
    return tuple(rows)


def _sorcerer_level(
    *,
    class_level: int,
    character_level: int,
    first_class: bool,
    cantrips: tuple[str, ...] = (),
    spells: tuple[str, ...] = (),
) -> AppliedClassLevel:
    choices: list[ClassChoiceSelection] = []
    if class_level == 1 and first_class:
        choices.extend((
            ClassChoiceSelection(
                "class.sorcerer.first_class.starting_equipment",
                ("starting_equipment.sorcerer.dagger",),
            ),
            ClassChoiceSelection(
                "class.sorcerer.proficiencies.skills",
                ("arcana", "deception"),
            ),
        ))
    if class_level == 1:
        choices.append(ClassChoiceSelection(
            "class.sorcerer.level_1.subclass",
            (CharacterSubclass.DRACONIC_BLOODLINE.value,),
        ))
    if cantrips:
        choices.append(ClassChoiceSelection(
            f"class.sorcerer.level_{class_level}.cantrips",
            cantrips,
        ))
    if spells:
        choices.append(ClassChoiceSelection(
            f"class.sorcerer.level_{class_level}.spell_known",
            spells,
        ))
    if class_level == 3:
        choices.append(ClassChoiceSelection(
            "class.sorcerer.level_3.metamagic",
            (
                "class_feature.sorcerer.metamagic.quickened_spell",
                "class_feature.sorcerer.metamagic.twinned_spell",
            ),
        ))
    if class_level == 4:
        choices.append(ClassChoiceSelection(
            "class.sorcerer.level_4.asi_or_feat",
            ("ability_score.charisma.2",),
        ))
    if class_level == 1:
        choices.append(ClassChoiceSelection(
            "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
            ("class_feature.sorcerer.draconic_ancestry.red",),
        ))
    return AppliedClassLevel(
        step_id=f"class.sorcerer.level_{class_level}",
        character_level=character_level,
        class_id=CharacterClass.SORCERER,
        resulting_class_level=class_level,
        subclass_id=CharacterSubclass.DRACONIC_BLOODLINE,
        choices=tuple(choices),
    )


def _sorcerer_levels(
    *,
    character_level_offset: int = 0,
    spellblade: bool = False,
) -> tuple[AppliedClassLevel, ...]:
    if spellblade:
        cantrips = (
            "spell.fire_bolt",
            "spell.light",
            "spell.ray_of_frost",
            "spell.shocking_grasp",
        )
        spells = (
            ("spell.magic_missile", "spell.shield"),
            ("spell.burning_hands",),
            ("spell.scorching_ray",),
        )
        count = 3
    else:
        cantrips = (
            "spell.acid_splash",
            "spell.chill_touch",
            "spell.fire_bolt",
            "spell.ray_of_frost",
        )
        spells = (
            ("spell.burning_hands", "spell.magic_missile"),
            ("spell.charm_person",),
            ("spell.scorching_ray",),
            ("spell.hold_person",),
            ("spell.fireball",),
        )
        count = 5
    return tuple(
        _sorcerer_level(
            class_level=level,
            character_level=character_level_offset + level,
            first_class=character_level_offset == 0,
            cantrips=(
                cantrips
                if level == 1
                else ("spell.light",)
                if level == 4
                else ()
            ),
            spells=spells[level - 1],
        )
        for level in range(1, count + 1)
    )


_COMMON_SUPPLEMENT = (
    ItemLoadoutEntry("consumable.potion_haste"),
    ItemLoadoutEntry("consumable.healing_potion", quantity=2),
)
_FIGHTER_SUPPLEMENT = (
    ItemLoadoutEntry("apparel.leather_boots.brown", equipment_slot=BodyPart.FEET),
    *_COMMON_SUPPLEMENT,
    ItemLoadoutEntry("apparel.cloth_shoes"),
    ItemLoadoutEntry("apparel.iron_helmet.steel", equipment_slot=BodyPart.HEAD),
    ItemLoadoutEntry("weapon.handaxe"),
    ItemLoadoutEntry("weapon.javelin"),
    ItemLoadoutEntry("weapon.dagger"),
    ItemLoadoutEntry("armor.leather"),
)
_BARBARIAN_SUPPLEMENT = (
    *_COMMON_SUPPLEMENT,
    ItemLoadoutEntry("weapon.handaxe"),
    ItemLoadoutEntry("weapon.javelin"),
    ItemLoadoutEntry("weapon.dagger"),
    ItemLoadoutEntry("weapon.longsword"),
    ItemLoadoutEntry("shield.shield"),
)
_SORCERER_SUPPLEMENT = (
    ItemLoadoutEntry("apparel.robes.red_mage", equipment_slot=BodyPart.BODY),
    ItemLoadoutEntry("apparel.cloth_shoes.red", equipment_slot=BodyPart.FEET),
    *_COMMON_SUPPLEMENT,
    ItemLoadoutEntry("apparel.robes.wizard"),
    ItemLoadoutEntry("apparel.cloth_shoes.blue"),
    ItemLoadoutEntry("apparel.wizard_hat.red", equipment_slot=BodyPart.HEAD),
    ItemLoadoutEntry("weapon.quarterstaff"),
)

_BARBARIAN_APPEARANCE = CharacterAppearance(
    visual_scale=1.1,
    visual_scale_x=1.1,
    skin_tint=0xD4AA78,
    head_category="Head17",
    hair_tint=0xD0BFA1,
)
_FIGHTER_APPEARANCE = CharacterAppearance(
    skin_tint=0xE6BC98,
    head_category="Head10",
    hair_tint=0x993F00,
    has_beard=True,
    beard_tint=0x993F00,
)
_SORCERER_APPEARANCE = CharacterAppearance(
    visual_scale=0.9,
    visual_scale_x=0.9,
    skin_tint=0xE6BC98,
    head_category="Head22",
    hair_tint=0x993F00,
)

_FIGHTER_PACKAGE = (
    ItemLoadoutEntry("armor.chain_mail", equipment_slot=BodyPart.BODY),
    ItemLoadoutEntry("weapon.longsword", equipment_slot=WeaponSlot.MELEE_MAIN),
    ItemLoadoutEntry("shield.shield", equipment_slot=WeaponSlot.MELEE_OFF),
)

PREMADE_CHARACTER_BUILDS: Mapping[str, CharacterBuild] = MappingProxyType({
    BARBARIAN_PREMADE_ID: CharacterBuild(
        name="Berserker",
        species=Species.HUMAN,
        background=Background.ADVENTURER,
        base_ability_scores=(
            ("strength", 15), ("dexterity", 13), ("constitution", 14),
            ("intelligence", 8), ("wisdom", 12), ("charisma", 10),
        ),
        flexible_ability_bonuses=(("strength", 2), ("constitution", 1)),
        origin_choices=_HUMAN_ORIGIN,
        class_levels=_barbarian_levels(),
        item_loadout=(
            ItemLoadoutEntry("weapon.greataxe", equipment_slot=WeaponSlot.MELEE_MAIN),
            *_BARBARIAN_SUPPLEMENT,
            ItemLoadoutEntry(
                "apparel.costume.pit_fighter_wrap",
                equipment_slot=BodyPart.BODY,
            ),
            ItemLoadoutEntry("apparel.leather_boots", equipment_slot=BodyPart.FEET),
            ItemLoadoutEntry("equipment.portable_torch"),
        ),
        appearance=_BARBARIAN_APPEARANCE,
    ),
    FIGHTER_PREMADE_ID: CharacterBuild(
        name="Shield Fighter",
        species=Species.HUMAN,
        background=Background.ADVENTURER,
        base_ability_scores=(
            ("strength", 15), ("dexterity", 14), ("constitution", 13),
            ("intelligence", 10), ("wisdom", 12), ("charisma", 8),
        ),
        flexible_ability_bonuses=(("strength", 2), ("constitution", 1)),
        origin_choices=_HUMAN_ORIGIN,
        class_levels=_fighter_levels(
            5,
            style="class_feature.fighter.fighting_style.dueling",
        ),
        item_loadout=(
            *_FIGHTER_PACKAGE,
            *_FIGHTER_SUPPLEMENT,
            ItemLoadoutEntry("weapon.longbow", equipment_slot=WeaponSlot.RANGED_MAIN),
            ItemLoadoutEntry("equipment.portable_torch"),
        ),
        appearance=_FIGHTER_APPEARANCE,
    ),
    SORCERER_PREMADE_ID: CharacterBuild(
        name="Draconic Sorcerer",
        species=Species.HUMAN,
        background=Background.ADVENTURER,
        base_ability_scores=(
            ("strength", 8), ("dexterity", 14), ("constitution", 13),
            ("intelligence", 10), ("wisdom", 12), ("charisma", 15),
        ),
        flexible_ability_bonuses=(("constitution", 1), ("charisma", 2)),
        origin_choices=_HUMAN_ORIGIN,
        class_levels=_sorcerer_levels(),
        item_loadout=(
            ItemLoadoutEntry("weapon.dagger", equipment_slot=WeaponSlot.MELEE_MAIN),
            *_SORCERER_SUPPLEMENT,
            ItemLoadoutEntry("equipment.portable_torch"),
        ),
        appearance=_SORCERER_APPEARANCE,
    ),
    SPELLBLADE_PREMADE_ID: CharacterBuild(
        name="Draconic Spellblade",
        species=Species.HUMAN,
        background=Background.ADVENTURER,
        base_ability_scores=(
            ("strength", 15), ("dexterity", 13), ("constitution", 13),
            ("intelligence", 8), ("wisdom", 9), ("charisma", 14),
        ),
        flexible_ability_bonuses=(("strength", 2), ("charisma", 1)),
        origin_choices=_HUMAN_ORIGIN,
        class_levels=(
            *_fighter_levels(
                2,
                style="class_feature.fighter.fighting_style.dueling",
            ),
            *_sorcerer_levels(character_level_offset=2, spellblade=True),
        ),
        item_loadout=(
            *_FIGHTER_PACKAGE,
            ItemLoadoutEntry(
                "apparel.leather_boots.brown",
                equipment_slot=BodyPart.FEET,
            ),
            *_COMMON_SUPPLEMENT,
            ItemLoadoutEntry("apparel.cloth_shoes"),
            ItemLoadoutEntry("apparel.iron_helmet.steel"),
            ItemLoadoutEntry("weapon.handaxe"),
            ItemLoadoutEntry("weapon.javelin"),
            ItemLoadoutEntry("weapon.dagger"),
            ItemLoadoutEntry("armor.leather"),
            ItemLoadoutEntry("apparel.spellblade_crown", equipment_slot=BodyPart.HEAD),
            ItemLoadoutEntry("equipment.portable_torch"),
        ),
        appearance=_FIGHTER_APPEARANCE,
    ),
})


def create_premade_character(
    premade_id: str,
    *,
    runtime_entity_uuid: UUID | None = None,
    faction: str | None = None,
    position: tuple[int, int] | None = None,
) -> Entity:
    """Look up one ordinary build and immediately use the public creator."""
    try:
        build = PREMADE_CHARACTER_BUILDS[premade_id]
    except KeyError as exc:
        raise KeyError(f"unknown direct premade {premade_id!r}") from exc
    return create_character(
        build,
        runtime_entity_uuid=runtime_entity_uuid,
        faction=faction,
        position=position,
    )


__all__ = [
    "BARBARIAN_PREMADE_ID",
    "FIGHTER_PREMADE_ID",
    "PREMADE_CHARACTER_BUILDS",
    "SORCERER_PREMADE_ID",
    "SPELLBLADE_PREMADE_ID",
    "create_premade_character",
]
