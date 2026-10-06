# Summon and goblin portraits — production handoff, 6 October 2026

**41 new painted portraits, 123 native PNGs:** 18 beast identities shared by Animals and Fey, six fiends and 17 authored goblin variants. These extend the preceding pixelated portrait bank. Human visual acceptance and production installation remain pending.

## Delivery

- [Native-size review](http://127.0.0.1:8784/creature-portraits-2026-10-06/)
- [Runtime archive](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/creature-portraits-2026-10-06/creature-portraits-runtime.zip)
- [Authoring archive](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/creature-portraits-2026-10-06/creature-portraits-authoring.zip)
- [Exact manifest](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/creature-portraits-2026-10-06/manifest.json)
- [Archive receipt and hashes](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/creature-portraits-2026-10-06/DELIVERY_RECEIPT.json)
- [Previous portrait-only handoff](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/agent_docs/PLAYER_UI_PIXELATED_PORTRAITS_HANDOFF_2026-10-06.md)

Asset root: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/creature-portraits-2026-10-06`. Paths in `files` resolve relative to the extracted runtime root. Runtime contains the native portraits, manifest, profile/palette and this document. Keep the large paintings and review materials in the authoring archive; they do not need to ship in the game.

## Style and sizes

The new paintings use the preceding Sable and Fighter repaint masters as visual references, together with three facings from each creature's actual authored body. They use matte old-school painted faces, earthy colour planes and a quiet textured background. Goblins have individual faces and retain the source hood, cap, helmet and armour distinctions. Portraits have no baked border, text or action glyph.

| Role | Manifest field | Native pixels |
|---|---|---|
| Initiative | `files.initiative` | 36 × 48 |
| Party / active character | `files.hud` | 48 × 64 |
| Sheet / inspection | `files.sheet` | 96 × 128 |

One centred 3:4 crop is shared by all three roles. Each role is resized directly from the original painting with premultiplied alpha, then processed once through the existing D65 CIE76, 64-colour profile. Display at native pixels; use nearest-neighbour sampling for intentional integer enlargement. Choose the role-specific PNG instead of enlarging the initiative portrait into the inspection slot. UI borders and selection indicators remain separate overlays.

## Identity and integration

1. Resolve the creature using `contentId` and its authored `rigId`, then read the chosen role from `files`. `contentRef` preserves the source catalog or rig binding, including its pack/version. Do not select portraits by display name or generate a different portrait for every summon instance.
2. Animals and Fey use the same 18 canonical creature bodies and portraits. Summon manifestation VFX remains separate. The 42 current summon choices are covered by 24 unique portraits, with no duplicate Fey paintings.
3. `Raptor` keeps its backend name and the authored Tyrannosaurus body. `Dretch` follows the actual DemonBeast01 body. The Packtrail and Ashhide portraits show their goblin riders; their mounts are not separate portraits in this bank.
4. The 17 goblin records map to Goblin01–17. Preserve those bindings and do not replace the older encounter portraits by positional index. This delivery makes no inferred aliases for older `goblin_archer` / `goblin_caster` fallback identities.
5. Install the native files and exact mapping after review. Gameplay rules, sprites, rigs and the renderer were not changed by this delivery.

## Source and validation

Catalog scope is taken from production `dnd/summoning/forms.py`, `dnd/monsters/goblins.py` and the corresponding `game/data/rigs/*.json`. `authoring/roster.json` records source paths, body facings/crops and durable identities. Per-creature `authoring/prompts/*.json` records the built-in image-generation prompt, the two style references, the body reference and original generated file. Original source sprites and prior portraits are preserved.

`authoring/pixelate.py` reproduces the native bank using the existing CodexFX appearance pipeline and the included profile/palette. `authoring/package.py` verifies dimensions, content coverage, source/output SHA-256 values and ZIP contents. Visual review covers every family at native size and checks portraits against their source bodies; automated file checks do not imply human acceptance.

`review/catalog-check.json` records the exact 24-body / 17-goblin comparison against the current production catalog and confirms 41 distinct painting masters. `review/gallery-check.json` records 41 cards, 123 loaded native portraits, no missing images or JavaScript errors, correct role dimensions, family filtering and nearest-neighbour inspection. Family contact sheets and browser screenshots are included in the authoring pack.

All 41 expected identities have three native sizes. The gallery loads native PNGs and small sprite-reference boards by default; a large painting is loaded only when its source disclosure is opened. This keeps the review lightweight.

## Animals / Fey

| Portrait | Content ID | Rig | Asset directory |
|---|---|---|---|
| Wolf | `creature.wolf` | `smallscale.greywolf` | `portraits/wolf/` |
| Hound | `creature.hound` | `smallscale.shepherddog` | `portraits/hound/` |
| Boar | `creature.boar` | `smallscale.boar` | `portraits/boar/` |
| Stag | `creature.stag` | `smallscale.stag` | `portraits/stag/` |
| Jaguar | `creature.jaguar` | `smallscale.jaguar` | `portraits/jaguar/` |
| Bison | `creature.bison` | `smallscale.bison` | `portraits/bison/` |
| Ostrich | `creature.ostrich` | `smallscale.ostrich` | `portraits/ostrich/` |
| Brown Bear | `creature.brown_bear` | `smallscale.brownbear` | `portraits/brown_bear/` |
| Lion | `creature.lion` | `smallscale.lion` | `portraits/lion/` |
| Tiger | `creature.tiger` | `smallscale.tiger` | `portraits/tiger/` |
| Polar Bear | `creature.polar_bear` | `smallscale.polarbear` | `portraits/polar_bear/` |
| Rhinoceros | `creature.rhinoceros` | `smallscale.rhino` | `portraits/rhinoceros/` |
| Blue Raptor | `creature.blue_raptor` | `smallscale.blueraptor` | `portraits/blue_raptor/` |
| Stegosaurus | `creature.stegosaurus` | `smallscale.stegosaurus` | `portraits/stegosaurus/` |
| Elephant | `creature.elephant` | `smallscale.elephant` | `portraits/elephant/` |
| Triceratops | `creature.triceratops` | `smallscale.triceratops` | `portraits/triceratops/` |
| Mammoth | `creature.mammoth` | `smallscale.mammoth` | `portraits/mammoth/` |
| Raptor | `creature.raptor` | `smallscale.tyrannosaurus` | `portraits/raptor/` |

## Fiends

| Portrait | Content ID | Rig | Asset directory |
|---|---|---|---|
| Dretch | `creature.dretch` | `smallscale.demonbeast01` | `portraits/dretch/` |
| Claw Mote Devil | `creature.claw_mote_devil` | `smallscale.imp05` | `portraits/claw_mote_devil/` |
| Corrosive Demon | `creature.corrosive_demon` | `smallscale.demonbeast02` | `portraits/corrosive_demon/` |
| Dread Demon | `creature.dread_demon` | `smallscale.demonbeast03` | `portraits/dread_demon/` |
| Huntsman Wing Devil | `creature.huntsman_wing_devil` | `smallscale.demonbeast05` | `portraits/huntsman_wing_devil/` |
| Fellwing Devil | `creature.fellwing_devil` | `smallscale.demonbeast04` | `portraits/fellwing_devil/` |

## Goblins

| Portrait | Content ID | Rig | Asset directory |
|---|---|---|---|
| Ashhook | `creature.goblin` | `smallscale.goblin01` | `portraits/goblin/` |
| Wispbinder | `creature.goblin_wispbinder` | `smallscale.goblin02` | `portraits/goblin_wispbinder/` |
| Reedshot | `creature.goblin_reedshot` | `smallscale.goblin03` | `portraits/goblin_reedshot/` |
| Buckler Rat | `creature.goblin_buckler_rat` | `smallscale.goblin04` | `portraits/goblin_buckler_rat/` |
| Longpoint | `creature.goblin_longpoint` | `smallscale.goblin05` | `portraits/goblin_longpoint/` |
| Ironhide | `creature.goblin_ironhide` | `smallscale.goblin06` | `portraits/goblin_ironhide/` |
| Briarling | `creature.goblin_briarling` | `smallscale.goblin07` | `portraits/goblin_briarling/` |
| Redcap | `creature.goblin_redcap` | `smallscale.goblin08` | `portraits/goblin_redcap/` |
| Quicktail | `creature.goblin_quicktail` | `smallscale.goblin09` | `portraits/goblin_quicktail/` |
| Spearline | `creature.goblin_spearline` | `smallscale.goblin10` | `portraits/goblin_spearline/` |
| Packtrail | `creature.goblin_packtrail` | `smallscale.goblin11` | `portraits/goblin_packtrail/` |
| Ashhide | `creature.goblin_ashhide` | `smallscale.goblin12` | `portraits/goblin_ashhide/` |
| Thornrunner | `creature.goblin_thornrunner` | `smallscale.goblin13` | `portraits/goblin_thornrunner/` |
| Buckler Hex | `creature.goblin_buckler_hex` | `smallscale.goblin14` | `portraits/goblin_buckler_hex/` |
| Gloomplate | `creature.goblin_gloomplate` | `smallscale.goblin15` | `portraits/goblin_gloomplate/` |
| Mossbreaker | `creature.goblin_mossbreaker` | `smallscale.goblin16` | `portraits/goblin_mossbreaker/` |
| Gutterknife | `creature.goblin_gutterknife` | `smallscale.goblin17` | `portraits/goblin_gutterknife/` |
