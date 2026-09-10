"""Purchased body selections retain original pixels and cover mapped clips."""

import hashlib
import json

import pygame
import pytest

from game.animation_data import DATA_ROOT, load_animation_data


@pytest.mark.parametrize("filename,identity,rig_id,attack,source,cell", (
    ("demonbeast01", "content.srd_5_1_cc:creature:creature.dretch@1",
     "smallscale.demonbeast01", "Attack6", "Attack 1", 128),
    ("skeletonarcher05", "content.neurodragon:creature:creature.skeleton_archer@1",
     "smallscale.skeletonarcher05", "Attack3", "QuickShot", 128),
    ("greywolf", "content.srd_5_1_cc:creature:creature.wolf@1",
     "smallscale.greywolf", "Attack6", "Attack1", 64),
))
def test_fixed_creature_identity_maps_native_attack_and_preserves_all_direction_frames(
    filename: str, identity: str, rig_id: str, attack: str, source: str, cell: int,
) -> None:
    binding = DATA_ROOT.parent / f"rigs/{filename}.json"
    data = load_animation_data(rig_files=(binding,))
    document = json.loads(binding.read_text())
    assert data.creature_rigs[identity] == rig_id
    rig = data.rigs[rig_id]
    assert (rig.cell_width, rig.cell_height) == (cell, cell)
    assert rig.clips[attack].source_clip == source
    assert {"Idle", "Run", "TakeDamage", "Die", attack} <= rig.clips.keys()
    # There are no independent gear layers inside a baked body. Only the
    # Demon package supplies separate shadow media; the others are shadowless.
    assert rig.slot_order == (("shadow", "body") if filename == "demonbeast01" else ("body",))
    for url, record in document["provenance"]["files"].items():
        payload = data.resources[url].read_bytes()
        assert (len(payload), hashlib.sha256(payload).hexdigest()) == (record["bytes"], record["sha256"])
    # A dimensionally valid atlas may still have truncated/empty final columns.
    # Check every actual body cell, including the death hold and all 8 facings.
    category, = rig.slot_categories["body"]
    checked: set[str] = set()
    for clip in rig.clips.values():
        url = clip.sheets[category]
        if url in checked:
            continue
        checked.add(url)
        sheet = pygame.image.load(data.resources[url])
        assert sheet.get_size() == (cell * clip.frames, cell * 8)
        for row in range(8):
            for frame in range(clip.frames):
                sprite = sheet.subsurface((frame * cell, row * cell, cell, cell))
                assert pygame.mask.from_surface(sprite, threshold=8).count() > 0, (filename, url, row, frame)
