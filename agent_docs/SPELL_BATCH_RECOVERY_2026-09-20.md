# Recovered Godot spell batch — September 20

The user requested recovery of the spell work preceding the long Web iteration.
The original files are intact and the consolidated handoff has arrived.
This record distinguishes the selected sources from stale delivery snapshots
and from spells already integrated into this branch. No production spell or
geometry behavior changed during intake.

The intake status below is historical. The seven spells are now integrated; see
the [implementation result](SPELL_BATCH_RESULT_2026-09-20.md) for current behavior,
validation and the user's Web timing follow-up.

## Source and version selection

Source task: `01a0b6af-5fa9-7ec0-9915-0ecee0a6baec`, **Author Godot weapon projectiles and…**.
Its workspace is `/home/tommaso/.codex/worktrees/1aac/dnd_engine`.
The authoritative frozen package is
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/delivery-pending-spells-2026-09-20/`.
Read its [complete integration handoff](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/delivery-pending-spells-2026-09-20/HANDOFF.md)
and [selected-version index](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/delivery-pending-spells-2026-09-20/index.json).
Paths in the table below are relative to this package. Original editable Godot
sources and full native capture archives remain in the source workspace; the
package contains the runtime media and integration references.

The consolidated handoff and index supersede historical selection/status wording
in `docs/SPELL_BATCH_HANDOFF_2026-09-20.md` and copied preview documents. The existing
`delivery-latest-v1` snapshot contains superseded Burning Hands and Gust versions;
do not import that folder wholesale.

| Spell | Selected source | Authored contract / intake status |
| --- | --- | --- |
| Sacred Flame | `cantrips-review/review-sheets/manifest.json`, `sacred_flame` | Golden descending beam anchored to target ground, Special1 invocation, exact spell palette. 504 frames at 168 fps, 768px cells, pivot `[384,650.04]`; contact source frame 51. Latest handoff records positive visual feedback and permission to integrate. |
| Shocking Grasp | Same manifest, `shocking_grasp` | Adjacent caster; separate electrical front/back wrap and hand arcs. 252 frames at 144 fps, 384px cells. Native hit reaction and 150ms flash remain separate from lingering electricity. |
| Poison Spray | Same manifest, `poison_spray` | Single-target palm puff, not a gameplay cone. 360 frames at 144 fps, 512px cells. Per-facing contact timing in `poison-contact.json`; exact poison palette. |
| Burning Hands | `burning-hands-review/manifest.json`, `sheets/`, `REVIEW.md` | `actual-cone-v9`; reauthored varied flame components preserving the original donor shader and motion. 216 frames at 144 fps, eight directions, fixed 512px canvas/pivots. Latest handoff records “looking good”; older v6/v7 deliveries and replacement-sheet experiments are superseded. |
| Thunderwave | `aoe-crest-review/manifest.json`, its `thunderwave` entry and `sheets/thunderwave/` | Thick purple Blender crest, source native-v10, preview smooth-playback-v5. 144 source frames at 144 fps, four native direction banks. Delivered front/back cell slices need reconciliation with the user's later objection to using tile alpha cuts to manufacture an effect footprint. The frozen manifest removes the obsolete Burning Hands entry. |
| Gust of Wind | `gust-wave-review/whole-manifest.json`, `whole-sheets/`, `REVIEW.md` | Visually approved `authored-dense-v4`. 432 frames at 144 fps, eight directions. Whole effect packed into lossless horizontal bands with canvas offsets; old repeated-front `gust-review` and clipped `native-v1` pilot are superseded. This three-second cast/hold/release example is not an authored indefinite concentration loop. |
| Web | `web/manifest.json`, `palette.json` | Frozen `delivery-web-v9` equals preview `uneven-silk-v11`. Projectile 144 frames, deployment 288 at 144 fps; exact final deployment frame becomes the persistent ground. Separate condition-driven front/back body wraps. Stopping iteration is not a claim of seamless projectile-to-ground contact. |

The cantrip root `manifest.json` omits atlas paths; use the manifest inside
`review-sheets/`. Reference actor textures, measured sockets, palette files and
target-motion/contact metadata remain beside it. Reference sorcerer sprites are
not replacements for the game's actual modular actors.

An intake-only file check found all referenced pages: 624 cantrip pages,
112 Burning Hands pages, 216 Thunderwave pages and 54 Gust pages. No hash scan,
runtime validation or source import hook was introduced. The final package's
atlas-reference report lists 1,138 resolved references across all seven selections
and no missing pages. Its checksum inventory is not an engine/import requirement.

## Production status at handoff

- **Pending new-art integration:** the first six spells above. Their native spell
  classes already exist. Asset recovery does not imply production recipes,
  timing, wall occlusion or final in-game review are complete.
- **Sleep integrated:** `sleep-web-review/delivery-sleep-v1`, including mage and
  device casting, authored projectile/mist/palette, native HP-pool recipients,
  condition-owned lying pose/Zzz and actual damage wake. It is not concentration.
- **Web foundation integrated:** `delivery-web-v2` / `settling-web-v4`, native
  gameplay, finite spatial deployment, persistent ground field and device
  sustaining/tether. Later art and body-wrap integration were paused by the user.
  The final handoff now selects `delivery-web-v9` / `uneven-silk-v11` and ends art
  iteration. This newer media and its body wraps are received but not integrated;
  the handoff does not change this branch's existing v2 foundation.
- **Already integrated earlier:** Ray of Frost, Ice Knife and Chill Touch
  `ice-spells/production-v8`, plus the earlier spell palette corrections.
  Do not downgrade these while recovering the pending batch.

Cannons already have independent spell grants, damage flashes, destruction
animation and inert native wrecks. None of those mechanisms need replacement to
recover this art.

## Meaning of the art task's integration notes

The artist reports discrepancies in current cone/line cell selection and in
diagonal forced-movement distance reporting. Those are observations to reproduce
against this branch when integrating the affected capability, not established
new defects from this intake or authorization to change rules silently.

Preserve naturally authored effect silhouettes. Wall/body occlusion may hide
obscured pixels; gameplay cell masks must not sculpt an otherwise wrong spell
shape. Production events own targets, saves, damage, displacement and sustained
lifetime. Preview target-coordinate contact probes and staged push outcomes are
reference measurements, not executable game rules.

For Web, body wraps must follow actual observed restraint and clear on save,
escape or field removal. The delivered fixed 4×4 ground image does not itself
implement partial destruction. For Gust, the finite sample does not supply a
maintained concentration loop. These are explicit integration limits, not reasons
to invent renderer-owned gameplay or to restart the artist's work during intake.
