"""Authored summon choices; all body rules remain in canonical recipes."""

from dataclasses import dataclass
from types import MappingProxyType

from dnd.core.content.recipes import ContentRecipe
from dnd.monsters.beasts import BEAST_RECIPES_BY_ID
from dnd.monsters.fiends import FIEND_RECIPES_BY_ID
from dnd.monsters.demon_variants import CORROSIVE_DEMON_RECIPE, DREAD_DEMON_RECIPE
from dnd.monsters.srd_roster import SRD_CREATURE_DECLARATIONS_BY_ID
from dnd.types.summoning import (
    SummonFamily, SummonManifestation, SummonRules, SummonSelection, SummonSustain,
)


@dataclass(frozen=True, slots=True)
class SummonForm:
    form_id: str
    display_name: str
    family: SummonFamily
    minimum_slot: int
    recipe: ContentRecipe
    manifestation: SummonManifestation


@dataclass(frozen=True, slots=True)
class SummonSpellSpecification:
    family: SummonFamily
    minimum_slot: int
    rules: SummonRules
    placement_range_feet: int = 60


SPELL_SPECIFICATIONS = MappingProxyType({
    SummonFamily.ANIMALS: SummonSpellSpecification(SummonFamily.ANIMALS, 3,
        SummonRules(duration_rounds=600, sustain=SummonSustain.EXISTENCE)),
    SummonFamily.FEY: SummonSpellSpecification(SummonFamily.FEY, 6,
        SummonRules(duration_rounds=600, sustain=SummonSustain.CONTROL)),
    SummonFamily.FIEND: SummonSpellSpecification(SummonFamily.FIEND, 3,
        SummonRules(duration_rounds=600, sustain=SummonSustain.EXISTENCE)),
})

_BEAST_UNLOCKS = (
    ("wolf", "Wolf", 3), ("hound", "Hound", 3), ("boar", "Boar", 3),
    ("stag", "Stag", 3), ("jaguar", "Jaguar", 3), ("bison", "Bison", 3),
    ("ostrich", "Ostrich", 3), ("brown_bear", "Brown Bear", 4),
    ("lion", "Lion", 4), ("tiger", "Tiger", 4), ("polar_bear", "Polar Bear", 5),
    ("rhinoceros", "Rhinoceros", 5), ("blue_raptor", "Blue Raptor", 5),
    ("stegosaurus", "Stegosaurus", 6), ("elephant", "Elephant", 6),
    ("triceratops", "Triceratops", 7), ("mammoth", "Mammoth", 8),
    ("raptor", "Raptor", 5),
)
_BEAST_RECIPES = {**BEAST_RECIPES_BY_ID, "wolf": ContentRecipe.create(
    ref=SRD_CREATURE_DECLARATIONS_BY_ID["wolf"].ref, parameters={})}
_FIEND_UNLOCKS = (
    ("dretch", "Dretch", 3), ("claw_mote_devil", "Claw Mote Devil", 3),
    ("corrosive_demon", "Corrosive Demon", 4), ("dread_demon", "Dread Demon", 4),
    ("huntsman_wing_devil", "Huntsman Wing Devil", 5),
    ("fellwing_devil", "Fellwing Devil", 6),
)
_FIEND_RECIPES = {**FIEND_RECIPES_BY_ID,
    "dretch": ContentRecipe.create(ref=SRD_CREATURE_DECLARATIONS_BY_ID["dretch"].ref, parameters={}),
    "corrosive_demon": CORROSIVE_DEMON_RECIPE, "dread_demon": DREAD_DEMON_RECIPE}

SUMMON_FORMS = tuple(
    SummonForm(key, name, family, max(minimum, floor), _BEAST_RECIPES[key], manifestation)
    for family, floor, manifestation in (
        (SummonFamily.ANIMALS, 3, SummonManifestation.NATURAL),
        (SummonFamily.FEY, 6, SummonManifestation.FEY_SPIRIT),
    )
    for key, name, minimum in _BEAST_UNLOCKS
) + tuple(
    SummonForm(key, name, SummonFamily.FIEND, minimum, _FIEND_RECIPES[key], SummonManifestation.FIEND)
    for key, name, minimum in _FIEND_UNLOCKS
)
_FORMS_BY_KEY = MappingProxyType({(form.family, form.form_id): form for form in SUMMON_FORMS})


def available_forms(family: SummonFamily, cast_at_level: int) -> tuple[SummonForm, ...]:
    """Return authored cumulative choices without materializing any creature."""
    if not 1 <= cast_at_level <= 9:
        return ()
    return tuple(form for form in SUMMON_FORMS
                 if form.family is family and form.minimum_slot <= cast_at_level)


def selected_form(selection: SummonSelection) -> SummonForm:
    """Reject an unknown family/form or a slot below its authored unlock."""
    form = _FORMS_BY_KEY.get((selection.family, selection.form_id))
    if form is None or selection.cast_at_level < form.minimum_slot:
        raise ValueError("Summon form is unavailable for this family and spell slot")
    form.recipe.verify_integrity()
    return form
