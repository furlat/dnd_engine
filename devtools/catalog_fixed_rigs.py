"""Prepare an offline fixed-character sheet catalog; never install or bind art.

Source labels propose basic aliases only. Attack semantics, pivots, FPS and
contact/release markers require explicit authoring before runtime registration.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile


ARCHIVES = {
    "orcs_goblins": "2D Orcs and Goblins - TopDown - V1.0.zip",
    "demons": "2D Demons - TopDown assetpack v1.1.zip",
    "undead": "2D HD Undead pack 1.zip",
    "enemy": "2D HD Enemy pack 1.zip",
    "hdz": "2D HD Zombie pack 1 V1.1.zip",
    "top": "2D Zombie pack 2 - Top down v1.1.zip",
    "barbarian": "2D HD Barbarian pack 1.zip",
    "character": "2D HD Character pack 1 V1.2.zip",
}
FACINGS = {"E", "NE", "N", "NW", "W", "SW", "S", "SE"}
BASIC_NAMES = {
    "Idle": ("idle", "idle1"),
    "Run": ("run",),
    "Walk": ("walk",),
    "TakeDamage": ("takedamage", "takedamage1"),
    "Die": ("die", "die1"),
    "Rolling": ("rolling", "roll1"),
    "CrouchIdle": ("crouchidle", "crouch"),
    "CrouchRun": ("crouchrun", "crouchwalk"),
    "RunBackwards": ("runbackwards",),
    "StrafeLeft": ("strafeleft",),
    "StrafeRight": ("straferight",),
    "Taunt": ("taunt",),
}
IDLE_NAME_EXCEPTIONS = {
    ("orcs_goblins", "Goblin 03"): "Idle 1 16bit",
    ("orcs_goblins", "Goblin 09"): "Idle 1 16bit",
    ("orcs_goblins", "Orc 05"): "Idle 1 16bit",
    ("demons", "Demon Spawn 6"): "Idle 12",
    ("demons", "Demon Spawn 7"): "Idle 16",
    ("demons", "Demon Spawn 10"): "Idle 16",
    ("demons", "Imp 7"): "Idle 1 16bit",
}


def source_action(member: str) -> str:
    return PurePosixPath(member).stem.removesuffix("_Shadowless")


def compact_name(name: str) -> str:
    return re.sub(r"[\s_-]", "", name).lower()


def layer_kind(member: str) -> str:
    parts = [part.lower() for part in PurePosixPath(member).parts[:-1]]
    if "shadows" in parts:
        return "shadow"
    if "effects" in parts:
        return "effect"
    if "combined" in parts or any(part.endswith("with shadow") for part in parts):
        return "combined"
    return "body"


def catalog(review: Path, archive_dir: Path) -> dict:
    source = json.loads(review.read_text(encoding="utf-8"))
    retained = [row for row in source["rows"]
                if row.get("image_only_review")
                and not row["image_only_review"]["excluded"]]
    rows = []
    for pack, archive_name in ARCHIVES.items():
        archive = archive_dir / archive_name
        with zipfile.ZipFile(archive) as package:
            members = [member for member in package.namelist() if member.endswith(".png")]
            for creature in (row for row in retained if row["pack"] == pack):
                variant = creature["source_variant"]
                sheets = []
                for member in members:
                    parts = PurePosixPath(member).parts
                    if variant not in parts[:-1] or parts[-2] in FACINGS:
                        continue
                    with package.open(member) as stream:
                        header = stream.read(26)
                    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
                        raise ValueError(f"Invalid PNG header: {member}")
                    width, height = struct.unpack(">II", header[16:24])
                    cell = height // 8 if height % 8 == 0 else None
                    frames = width // cell if cell and width % cell == 0 else None
                    sheets.append({
                        "archive_member": member,
                        "source_action": source_action(member),
                        "layer": layer_kind(member),
                        "width": width, "height": height,
                        "png_bit_depth": header[24], "png_color_type": header[25],
                        "candidate_square_cell": cell,
                        "candidate_frame_count": frames,
                        "layout_status": "eight square direction rows assumed; verify against source frames",
                        "bytes": package.getinfo(member).file_size,
                    })
                actions = sorted({sheet["source_action"] for sheet in sheets
                                  if sheet["layer"] in ("body", "combined")})
                aliases = {}
                for semantic, names in BASIC_NAMES.items():
                    matches = [action for action in actions if compact_name(action) in names]
                    if semantic == "Idle" and (pack, variant) in IDLE_NAME_EXCEPTIONS:
                        authored_name = IDLE_NAME_EXCEPTIONS[pack, variant]
                        if authored_name not in actions:
                            raise ValueError(f"Authored idle name absent: {pack}/{variant}")
                        matches = [authored_name]
                    aliases[semantic] = {
                        "source_candidates": matches,
                        "status": "review_candidate" if matches else "unavailable",
                    }
                authored = creature["authoring_card"]
                rows.append({
                    "pack": pack, "source_variant": variant,
                    "candidate_rig_id": f"fixed.{pack}.{compact_name(variant)}",
                    "authoring_identity": authored["identity"],
                    "archive": str(archive.resolve()),
                    "observed_equipment": creature["image_only_review"]["observed_weapon_forms"],
                    "observed_animation_notes": creature["image_only_review"]["animation_notes"],
                    "sheets": sheets,
                    "basic_alias_candidates": aliases,
                    "available_source_actions": actions,
                    "attack_cast_special_candidates": [action for action in actions
                        if re.search(r"attack|shot|cast|special|pummel|block", action, re.I)],
                    "authored_runtime_fields": {
                        "creature_content_refs": [], "facing_rows": None,
                        "fps": None, "origin_y_from_ground": None,
                        "body_anchor": None, "rest_pose_anchors": None,
                        "visual_scale": None, "pose_sockets": None,
                        "action_contact_release_markers": None,
                    },
                    "runtime_ready": False,
                    "holds": [
                        "Select stable native content or observed appearance identity.",
                        "Verify direction rows, meaningful frames and blank/partial exports.",
                        "Author FPS, support pivot, torso/rest anchors and uniform scale.",
                        "Choose independent shadow/body/effect treatment.",
                        "Author attack/cast semantics and contact/release markers.",
                        "Declare unsupported baked-gear and condition states.",
                    ],
                })
    expected = {(row["pack"], row["source_variant"]) for row in retained}
    actual = {(row["pack"], row["source_variant"]) for row in rows}
    if actual != expected or len(actual) != len(rows):
        raise ValueError("Catalog differs from retained review identities")
    if any(not row["sheets"] for row in rows):
        raise ValueError("Retained character has no sheet members")
    return {
        "schema": "fixed-character-integration-preparation", "version": 1,
        "scope": "Retained non-animal image-review characters; offline candidates only.",
        "summary": {
            "characters": len(rows), "by_pack": dict(Counter(row["pack"] for row in rows)),
            "sheet_members": sum(len(row["sheets"]) for row in rows),
            "runtime_ready": 0,
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = catalog(args.review, args.archive_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
