"""Apply reviewed visual selections to existing Studio recipes, offline only.

The assignment file is an authoring input. Playback loads only the ordinary
Studio data written here; delivery, rules and definition identities stay intact.
"""

import argparse
import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from game.animation_data import load_animation_data
from game.animation_types import BodyRig, ElementColors, LayerColors, PaletteTreatment, StudioActorLayer, StudioSpellDraft


class LayerMaterialOverride(BaseModel):
    colors: LayerColors
    palette: PaletteTreatment


class MaterialSelection(BaseModel):
    identity: str
    source_file: str
    gamma: float
    noise_sheet: str
    layers: tuple[str, ...]
    layer_overrides: dict[str, LayerMaterialOverride] = Field(default_factory=dict)

    @model_validator(mode="after")
    def selected_overrides(self):
        if not self.layer_overrides.keys() <= set(self.layers):
            raise ValueError("material override must name a selected layer")
        if any(row.colors.source != "override" or row.colors.mode != "paletteSwap"
               for row in self.layer_overrides.values()):
            raise ValueError("intentional layer overrides require exact palette replacement")
        return self


class OrdinarySelection(MaterialSelection):
    mode: Literal["ordinary"]
    clip: str
    release_frame: int | None = None
    preparation_frame: int | None = None
    anchor_override_reason: str | None = None
    speed: float

    @model_validator(mode="after")
    def evidenced_anchors(self):
        if (self.release_frame is not None or self.preparation_frame is not None) and not self.anchor_override_reason:
            raise ValueError("explicit motion anchor needs its measured override reason")
        return self


class ChildSelection(MaterialSelection):
    mode: Literal["child_attack"]


Selection = Annotated[OrdinarySelection | ChildSelection, Field(discriminator="mode")]
SELECTIONS = TypeAdapter(tuple[Selection, ...])


def actor_layer(category: str, clip: str, slot: str, selection: MaterialSelection,
                colors: ElementColors) -> dict[str, Any]:
    override = selection.layer_overrides.get(category)
    return StudioActorLayer.model_validate({
        "id": f"cast-{slot}", "slot": slot, "enabled": True, "hidden": False,
        "category": category, "sourceSheet": f"/spritesheets/{category}/{clip}.png",
        "colors": (override.colors.model_dump(mode="json", exclude_none=True) if override else
                   {"source": "auto", "primary": colors.primary, "mode": "paletteSwap"}),
        "palette": (override.palette.model_dump(mode="json", exclude_none=True) if override else
                    {"colors": (colors.tertiary, colors.primary, colors.secondary),
                    "gamma": selection.gamma, "noiseSheet": selection.noise_sheet}),
    }).model_dump(mode="json", exclude_none=True)


def author_recipe(recipe: dict[str, Any], selection: Selection,
                  hand_paths: dict[str, Any], rig: BodyRig) -> None:
    colors = ElementColors.model_validate(recipe["elementColors"])
    if selection.mode == "child_attack":
        for pose in recipe["childAttack"]["poses"]:
            pose["layers"] = [actor_layer(category, pose["clip"], "weaponGlow", selection, colors)
                              for category in selection.layers]
        return
    paths = hand_paths[selection.clip]
    clip = rig.clips[selection.clip]
    missing = set(selection.layers) - clip.sheets.keys()
    if missing:
        raise ValueError(f"unregistered cast sheets: {selection.identity}/{selection.clip}/{sorted(missing)}")
    anchors = {row.name: row.frame for row in clip.anchors}
    release = selection.release_frame if selection.release_frame is not None else anchors["release"]
    prepare = selection.preparation_frame if selection.preparation_frame is not None else anchors["prepare"]
    if not 0 <= prepare <= release < clip.frames:
        raise ValueError(f"unreachable motion anchor: {selection.identity}")
    releases = {facing: points[release] for facing, points in paths.items()}
    if any(point is None for point in releases.values()):
        raise ValueError(f"unmeasured release: {selection.identity}/{selection.clip}/{release}")
    projectile = recipe.get("projectile")
    if (projectile is not None and projectile["prepare"]["enabled"]
            and any(point is None for points in paths.values() for point in points[prepare:release+1])):
        raise ValueError(f"unmeasured preparation: {selection.identity}/{selection.clip}")
    sockets = {"release": releases, "preparation": paths}
    cast = recipe["cast"]
    cast.update(actionClip=selection.clip, bodyPlaybackSpeed=selection.speed,
                releaseFrame=release, sourceSockets=sockets,
                weaponGlow=None, aura=None, effects=[], slash=None)
    effect_slots = iter(("effect", "effect2", "effect3"))
    for category in selection.layers:
        slot = "weaponGlow" if category.startswith("Magic") else (
            "aura" if category in ("Effect4", "Effect5") else next(effect_slots))
        layer = actor_layer(category, selection.clip, slot, selection, colors)
        if slot.startswith("effect"):
            cast["effects"].append(layer)
        else:
            if cast[slot] is not None:
                raise ValueError(f"duplicate selected slot: {selection.identity}/{slot}")
            cast[slot] = layer
    if projectile is not None:
        projectile["sourceSockets"] = sockets
        projectile["prepare"]["startFrame"] = prepare


def apply_selections(assignment_file: Path, repo: Path, *, write: bool,
                     backup: Path | None) -> tuple[str, ...]:
    document = json.loads(assignment_file.read_text())
    selections = SELECTIONS.validate_python(document["assignments"])
    data = load_animation_data()
    owners = {row.identity: row for row in selections}
    if len(owners) != len(selections) or set(owners) != {
            identity for identity, draft in data.drafts.items() if identity == draft.definitionRef.content_id}:
        raise ValueError("selections must cover every loaded canonical owner exactly once")
    hand_paths = json.loads((repo / "game/data/neuroclient/pose-sockets.json").read_text())["hand"]
    rig = data.rigs[data.root_rig]
    files: dict[Path, dict[str, Any]] = {}

    def document_at(relative: str) -> dict[str, Any]:
        path = (repo / relative).resolve()
        if not path.is_relative_to((repo / "game/data").resolve()):
            raise ValueError(f"recipe outside data root: {relative}")
        if path not in files:
            files[path] = json.loads(path.read_text())
        return files[path]

    for selection in selections:
        rows = document_at(selection.source_file)["spells"]
        matches = [row for row in rows if row["definitionRef"]["content_id"] == selection.identity]
        if len(matches) != 1:
            raise ValueError(f"canonical source owner is not unique: {selection.identity}")
        author_recipe(matches[0], selection, hand_paths, rig)
    derived = document["derived"]
    if {row["identity"] for row in derived} != set(data.drafts) - set(owners):
        raise ValueError("derived rows must cover the remaining loaded presentations")
    for row in derived:
        for relative, section in row["source_candidates"]:
            if section != "effectDrafts" or not row["cast_enabled"]:
                continue
            recipe = document_at(relative)[section][row["identity"]]
            # Own RGB/delivery survive; only gesture and accent policy inherit.
            author_recipe(recipe, owners[row["owner"]], hand_paths, rig)
    pending: dict[Path, str] = {}
    for path, document in files.items():
        for recipe in document.get("spells", ()):
            StudioSpellDraft.model_validate_json(json.dumps(recipe))
        for recipe in document.get("effectDrafts", {}).values():
            StudioSpellDraft.model_validate_json(json.dumps(recipe))
        content = json.dumps(document, indent=2) + "\n"
        if content != path.read_text():
            pending[path] = content
    for path, content in pending.items():
        if write:
            if backup is not None:
                receipt = backup / path.relative_to(repo)
                receipt.parent.mkdir(parents=True, exist_ok=True)
                if not receipt.exists():
                    receipt.write_bytes(path.read_bytes())
            path.write_text(content)
    return tuple(str(path.relative_to(repo)) for path in pending)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assignments", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    changed = apply_selections(args.assignments, Path.cwd(), write=args.apply, backup=args.backup)
    print(json.dumps({"applied": args.apply, "changed": changed}, indent=2))


if __name__ == "__main__":
    main()
