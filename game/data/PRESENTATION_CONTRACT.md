# Presentation authoring contract

The active local spell bundles use `schema: "dnd.spellStudioDrafts"`, `version: 1`.
They extend NeuroStudio's records; they are not claimed to be interchangeable
with its original v6 validator or executor. The unchanged imported reference in
`neuroclient/spell-studio-drafts.materialized.json` retains
`neuroclient.spellStudioDrafts`, version 6. Both decode through `StudioDraftFile`.

This is a data/execution contract for the current Python client and a future TS
adapter. It is not another event protocol or a requirement to port the client now.

## Ownership and packaging

| File / owner | Meaning |
| --- | --- |
| Each selected bundle's `spell-studio-drafts.json` | Explicit spell behavior in `spells`; child effects in `effectDrafts`, keyed by native effect identity |
| `projectile-assets.json` | Media dimensions, source phase ranges/rates, facing order, fixed registration and palette preview |
| `bindings.json` | Resource URLs to local files, spell ContentRefs and projectile storage; no authored child recipes |
| `neuroclient/attack-profiles.json` and source action recipes | Shared attack variants, with weapon overrides and damage-type defaults |
| `rigs/*.json` and root `neuroclient/bindings.json` | Rig identity, body registration, clips, slot categories and appearance bindings |
| `world_bindings.json` | Object transition/media bindings driven by permitted world state |
| `../../content_data/ledgers/neuroclient_authored_item_visuals.json` | Existing resolved equipment layer ledger, including sprite keys, tints, base bindings and variants |

Original reference records can be overridden by one selected local owner. Two
local bundles cannot own the same spell. A child effect retains the owning
spell's ContentRef; `spell.ice_knife.burst` is a child identity, not another paid
or independently catalogued spell. Importers copy media and update packaging;
they do not reconstruct behavior from another spell or overwrite selected drafts.

The original reference import/materializer remains an explicit source-conversion
tool. Ordinary content tuning belongs in selected local records. Re-running
source conversion is not required for gameplay or for editing local recipes.

Casting layers declare `sourceSheet` plus optional `palette` bake inputs. The
baker reads the original isolated category/clip sheet and writes the declared
output PNG. It does not alter flash timing, source selection or recipes. Runtime
uses the precolored sheet without applying the old hue transform again. Target
hit-flash palettes are separate: Chill uses a dark/noisy target treatment but a
full casting ramp. Neither operation changes the actor's equipment identity.

All these artifacts are ordinary JSON values. Resources are URL strings and
relative paths, not Python objects. A TS client resolves them through its asset
loader and reads the existing equipment ledger; it does not import Python item
registries. `AnimationData`, compiled timelines, `Path` values and Pygame surfaces
are runtime products, not portable authoring. Saved subjective events remain a
separate input stream.

## Additions to the original Studio vocabulary

| Field | Current consumer and observable meaning |
| --- | --- |
| `cast.enabled` | Cast compiler: a child delivery can run without repeating the caster gesture |
| `cast.holdReleaseForVolley` | Cast sampler: keep the release pose while the volley is released |
| Actor-layer `sourceSheet` / `palette` | Drawing / offline baker: selected isolated colored sheet and explicit bake treatment |
| `projectile.sourceSockets` | Attachment calculation: measured release/preparation coordinates in the actor source cell, overriding legacy source-anchor offsets |
| `targetAnchor.basis: "body"` | Attachment calculation: use the target rig's body point; ground deliveries remain on their ground support |
| Phase `startFrame`, `durationMs`, `overlapRelease` | Phase compiler: authored preparation start/duration and permitted overlap with release |
| Phase `scale` | Registration and drawing: local phase scale overrides projectile scale |
| Phase `timeMap` | Phase sampler: elapsed milliseconds to source-frame progression; does not alter native causality |
| Travel `overlapContactMs` | Sampler: continue/fade the arrived travel media after contact; damage is not delayed |
| `targetLocal` | Compiler/depth projection: effect at target with independent contact-after-release delay and optional temporary approach depth |
| Asset `anchorsByFacing` | Registration: measured normalized pivot per authored direction, rotated with the art |
| Optional asset travel phase | Impact-only assets need not invent unused travel frames |
| `projectileStorage` phases/layers/pages | Media loader: ordered alpha/additive layers, gain and page frame ranges; no game rules |
| `damage.hitFlash.palette` | Actor-media preparation: exact colors, gamma and optional noise/untinted shading, preserving silhouette |
| `area.surfaceReveal` | Playback: time already-recorded floor updates outward from the recorded contact; never generate native affected cells |
| `effectDrafts` | Child binding: select a typed recipe for an existing nested effect without a second caster action |
| Attack profile variants | Attack selection: explicit weapon identity overrides, damage-type fallback and authored critical variant |

Examples are the actual selected records: Fireball for phase scale/area reveal,
Eldritch Blast for measured sockets and volley preparation, Ice Knife plus its
child for body/ground separation, and Chill Touch for target-local time mapping.
Do not create a second normalized recipe language for these examples.

## Coordinates and clocks

1. The native actor or ground contact supplies grid position and support height.
   Temporary body lift is added independently; camera rotation projects the same
   recorded contacts and does not change their clock.
2. Actor sockets/body points use source-cell pixels. Subtract half cell width
   horizontally and cell height minus rig origin vertically, then apply actor
   visual scale (including horizontal scale for x). Ordinary authored anchor
   offsets retain their reference-pixel semantics.
3. Legacy sprite recipes retain Studio's canvas-center compensation, including
   its interaction with actor scale. Measured directional pivots instead attach
   directly at the socket. These are two asset registration conventions, not two
   spell-specific placement systems.
4. Convert the registered point into viewport pixels, apply image scale and its
   rotated pivot, then round for rasterization. Width/height rounding and sprite
   rotation stay in the Pygame adapter. Tuning an asset pivot is legitimate;
   changing every spell to compensate for a consumer inconsistency is not.
5. Compile duration from the retained reference-space trajectory and height
   metric. Never recompute travel duration from camera-projected screen distance.
   Existing travel FPS follows `projectile.fps`; preparation/impact use their
   phase FPS override when present. This precedence is retained behavior.

`targetLocal.approachOffsetTiles` is a temporary sorting/contact-depth choice for
an already local effect. It does not mean the native actor moved or the effect
travelled that distance. Area/wall masking continues to use shared geometry and
permitted native affected areas, independent of sprite padding.

## Execution that accompanies the data

A TS adapter must reproduce complete-lineage joins, independently advancing
latest state and historical playback, gear at presentation time, reaction
interruption, preserved sub-tile positions, prelaunch jump reactions and one
body cycle per jump airtime. These are finite shared algorithms, not JSON rules
per spell. Area occlusion and procedural floor residue also require their shared
algorithms; copying JSON alone does not port them.

The existing condition support report distinguishes supported body appearance
from populated unsupported equipment/appearance tracks. Accepted potion/source
strip omissions and empty optional movement/recovery media are not new work.
Unknown fields must not be silently accepted as evidence of interoperability.

Preserve approved composed results when changing representation. Numeric values
may change under a deliberate conversion; matching old JSON alone is insufficient.
Current captures and known defects are not automatically approved references.
