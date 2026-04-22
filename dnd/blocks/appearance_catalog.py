"""Documented backend subset of the Studio appearance taxonomy."""

from typing import Dict, Literal, Tuple

from pydantic import BaseModel


class AppearanceOption(BaseModel):
    key: str
    slot: Literal["body", "head", "beard"]
    description: str
    tags: Tuple[str, ...] = ()


BODY_OPTIONS: Dict[str, AppearanceOption] = {
    "NakedBody": AppearanceOption(
        key="NakedBody",
        slot="body",
        description="Default living humanoid body from the Studio taxonomy.",
        tags=("body", "humanoid", "skin"),
    ),
    "NakedBody2": AppearanceOption(
        key="NakedBody2",
        slot="body",
        description="Skeleton/bone body from the Studio taxonomy.",
        tags=("body", "undead", "skeleton", "bone"),
    ),
    "NakedBody3": AppearanceOption(
        key="NakedBody3",
        slot="body",
        description="Spirit/ethereal body from the Studio taxonomy.",
        tags=("body", "spirit", "ethereal"),
    ),
}


HEAD_OPTIONS: Dict[str, AppearanceOption] = {
    "Head1": AppearanceOption(
        key="Head1",
        slot="head",
        description="Hair-bearing head category from the Studio taxonomy.",
        tags=("head", "hair"),
    ),
    "Head9": AppearanceOption(
        key="Head9",
        slot="head",
        description="Hair-bearing head category used by fighter/barbarian presets.",
        tags=("head", "hair"),
    ),
    "Head10": AppearanceOption(
        key="Head10",
        slot="head",
        description="Hair-bearing head category from the Studio taxonomy.",
        tags=("head", "hair"),
    ),
    "Head16": AppearanceOption(
        key="Head16",
        slot="head",
        description="Hair-bearing head category from the Studio taxonomy.",
        tags=("head", "hair"),
    ),
    "Head17": AppearanceOption(
        key="Head17",
        slot="head",
        description="Hair-bearing head category from the Studio taxonomy.",
        tags=("head", "hair"),
    ),
    "Head22": AppearanceOption(
        key="Head22",
        slot="head",
        description="Hair-bearing head category from the Studio taxonomy.",
        tags=("head", "hair"),
    ),
}


BEARD_OPTION = AppearanceOption(
    key="Head2",
    slot="beard",
    description="Beard overlay category from the Studio taxonomy.",
    tags=("head", "beard", "facial-hair"),
)
