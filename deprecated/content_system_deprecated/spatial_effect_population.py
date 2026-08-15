"""Closed spell-to-spatial-effect dependency inventory for built-in content."""

from __future__ import annotations

from collections.abc import Callable

import dnd.spells.abjuration as abjuration
import dnd.spells.conjuration as conjuration
import dnd.spells.evocation as evocation
import dnd.spells.illusion as illusion
import dnd.spells.transmutation as transmutation
import dnd.classes.sorcerer as sorcerer
import dnd.monsters.traits as monster_traits
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.registration import (
    ContentDeclaration,
    get_content_declaration,
    replace_content_declaration_at_cold_startup,
)
from dnd.spatial_effect_content import (
    ANTIMAGIC_FIELD_DECLARATION,
    CLOUDKILL_CLOUD_DECLARATION,
    CONTINUAL_FLAME_FIELD_DECLARATION,
    DARKNESS_FIELD_DECLARATION,
    DAYLIGHT_FIELD_DECLARATION,
    DRACONIC_PRESENCE_FIELD_DECLARATION,
    ENTANGLE_FIELD_DECLARATION,
    EVARDS_BLACK_TENTACLES_FIELD_DECLARATION,
    FOG_CLOUD_DECLARATION,
    GLOBE_OF_INVULNERABILITY_FIELD_DECLARATION,
    GREASE_SURFACE_DECLARATION,
    GUARDIAN_OF_FAITH_FIELD_DECLARATION,
    GUST_OF_WIND_FIELD_DECLARATION,
    ICE_STORM_SURFACE_DECLARATION,
    INSECT_PLAGUE_FIELD_DECLARATION,
    INCENDIARY_CLOUD_DECLARATION,
    LEADERSHIP_FIELD_DECLARATION,
    SILENCE_FIELD_DECLARATION,
    SLEET_STORM_FIELD_DECLARATION,
    SPIRIT_GUARDIANS_FIELD_DECLARATION,
    SPIKE_GROWTH_SURFACE_DECLARATION,
    STINKING_CLOUD_DECLARATION,
    WEB_SURFACE_DECLARATION,
)


_Definition = type[object] | Callable[..., object]

_SPATIAL_EFFECT_BY_SPELL: dict[_Definition, ContentDeclaration] = {
    conjuration.Grease: GREASE_SURFACE_DECLARATION,
    conjuration.Entangle: ENTANGLE_FIELD_DECLARATION,
    conjuration.EvardsBlackTentacles: (
        EVARDS_BLACK_TENTACLES_FIELD_DECLARATION
    ),
    conjuration.GuardianOfFaith: GUARDIAN_OF_FAITH_FIELD_DECLARATION,
    conjuration.Cloudkill: CLOUDKILL_CLOUD_DECLARATION,
    conjuration.FogCloud: FOG_CLOUD_DECLARATION,
    conjuration.IncendiaryCloud: INCENDIARY_CLOUD_DECLARATION,
    conjuration.StinkingCloud: STINKING_CLOUD_DECLARATION,
    conjuration.Web: WEB_SURFACE_DECLARATION,
    transmutation.SpikeGrowth: SPIKE_GROWTH_SURFACE_DECLARATION,
    evocation.IceStorm: ICE_STORM_SURFACE_DECLARATION,
    conjuration.SpiritGuardians: SPIRIT_GUARDIANS_FIELD_DECLARATION,
    conjuration.Darkness: DARKNESS_FIELD_DECLARATION,
    conjuration.Daylight: DAYLIGHT_FIELD_DECLARATION,
    conjuration.InsectPlague: INSECT_PLAGUE_FIELD_DECLARATION,
    conjuration.SleetStorm: SLEET_STORM_FIELD_DECLARATION,
    illusion.Silence: SILENCE_FIELD_DECLARATION,
    evocation.GustOfWind: GUST_OF_WIND_FIELD_DECLARATION,
    abjuration.GlobeOfInvulnerability: (
        GLOBE_OF_INVULNERABILITY_FIELD_DECLARATION
    ),
    abjuration.AntimagicField: ANTIMAGIC_FIELD_DECLARATION,
    evocation.ContinualFlame: CONTINUAL_FLAME_FIELD_DECLARATION,
    sorcerer.DraconicPresence: DRACONIC_PRESENCE_FIELD_DECLARATION,
    monster_traits.LeadershipAction: LEADERSHIP_FIELD_DECLARATION,
}


def populate_builtin_spatial_effect_dependencies(
    declarations: tuple[ContentDeclaration, ...],
) -> tuple[ContentDeclaration, ...]:
    """Attach each exact created phenomenon to its authored source spell."""
    source_by_key = {
        get_content_declaration(spell_type).ref.identity_key: (
            spell_type,
            effect_declaration,
        )
        for spell_type, effect_declaration in _SPATIAL_EFFECT_BY_SPELL.items()
    }
    replacements: dict[str, ContentDeclaration] = {}
    for declaration in declarations:
        source = source_by_key.get(declaration.ref.identity_key)
        if source is None:
            updated = declaration
        else:
            spell_type, effect_declaration = source
            retained = tuple(
                dependency
                for dependency in declaration.dependencies
                if dependency.relation
                is not ContentDependencyRelation.CREATES_SPATIAL_EFFECT
            )
            dependency = ContentDependency(
                relation=ContentDependencyRelation.CREATES_SPATIAL_EFFECT,
                target_ref=effect_declaration.ref,
                phase=ContentDependencyPhase.RUNTIME_REFERENCE,
                notes=(
                    "Exact independent spatial owner created by this spell; "
                    "concentration, when present, is an external lifetime link."
                ),
            )
            copied = declaration.model_copy(
                update={"dependencies": (*retained, dependency)},
            )
            updated = ContentDeclaration.model_validate(dict(copied.__dict__))
            replace_content_declaration_at_cold_startup(spell_type, updated)
        replacements[updated.ref.identity_key] = updated
    if len(replacements) != len(declarations):
        raise ValueError("Built-in spatial-effect inventory contains duplicate refs")
    return tuple(
        replacements[declaration.ref.identity_key]
        for declaration in declarations
    )


__all__ = ["populate_builtin_spatial_effect_dependencies"]
