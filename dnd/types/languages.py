"""Dependency-neutral identifiers for the SRD language vocabulary.

Runtime storage accepts validated namespaced identifiers so trusted content
packs may add languages without changing the engine. Built-in SRD content
uses this enum instead of repeating string literals.
"""

from enum import Enum


class SrdLanguageId(str, Enum):
    """Stable identifiers for the standard and exotic SRD 5.1 languages."""

    COMMON = "language.common"
    DWARVISH = "language.dwarvish"
    ELVISH = "language.elvish"
    GIANT = "language.giant"
    GNOMISH = "language.gnomish"
    GOBLIN = "language.goblin"
    HALFLING = "language.halfling"
    ORC = "language.orc"
    ABYSSAL = "language.abyssal"
    CELESTIAL = "language.celestial"
    DRACONIC = "language.draconic"
    DEEP_SPEECH = "language.deep_speech"
    INFERNAL = "language.infernal"
    PRIMORDIAL = "language.primordial"
    SYLVAN = "language.sylvan"
    UNDERCOMMON = "language.undercommon"


__all__ = ["SrdLanguageId"]
