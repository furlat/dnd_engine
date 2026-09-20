# Graphics review: anchors, authoring and NeuroStudio portability

Read-only review, 2026-09-20. No runtime, media, tests or TypeScript files were
changed. This note covers the spell/attack authoring contract and attachment
semantics. The parallel reviews cover event reduction, actor state and scene
occlusion. It does not replace those reviews.

## Conclusion

The current implementation retains useful NeuroStudio structures and runs them
through shared Python executors. It is **not currently an interchangeable
NeuroStudio v6 data set**. The local dialect contains both explicit extensions
that original TypeScript rejects and extensions that pass its validator but
have no consumer. Minimal adaptation is still plausible, but it involves
implementing agreed semantics in TypeScript, not simply copying JSON and paths.

The measured sprite pivots and hand sockets are legitimate asset registration.
The more consequential design issue is that attachment, legacy canvas
registration and physical/depth position still have partly different meanings
in different paths. The recent `-12` torso correction is a bounded authored
adjustment; its successful visual review does not establish one anatomical
attachment contract for every spell or rig. Fire Bolt is not established as the
canonical anatomically correct reference.

## Sources and executable checks

Python workspace: `/mnt/c/users/tommaso/documents/dev/dnd_engine`.
TypeScript workspace: `/home/tommaso/Dev/NeuroClient/app`.
The TypeScript checkout is exactly
`d274f2d62ca9c1c5ed62a77841cacf6cc0347491`, the same revision used by the
original imported materializer/oracle. Relevant TypeScript paths were clean.
This is not a comparison against a different, newer client.

I ran the actual TypeScript functions directly from unchanged source using the
installed Bun 1.3.14 executable at
`app/node_modules/@oven/bun-linux-x64-baseline/bin/bun`, with a stdin script.
No build, client startup or generated source was involved. Entry points:

- `src/render/spellAuthoring/validation.ts:362`,
  `validatePersistedStudioDraft` for each draft;
- `src/render/spellAuthoring/validation.ts:238`,
  `validateProjectileAssetFileStrict` for each asset;
- `src/render/actionPresentationRecipes.ts:369`,
  `validateContentActionPresentationRecipeFile` with current local variants
  inserted into a clone of the original `action.attack` recipe.

All eight original materialized spell drafts pass. Among the nine currently
approved spell presentations, seven fail the original spell validator:

| Active presentation | Actual reported incompatibility |
| --- | --- |
| Acid Splash, Guiding Bolt | `projectile.sourceSockets`; `targetAnchor` is not a finite **tile-local** anchor because its basis is `body` |
| Eldritch Blast | Same, plus `prepare.overlapRelease` |
| Fireball | `sourceSockets`; `travel.scale` |
| Ray of Frost, Ice Knife | `sourceSockets`; `travel.overlapContactMs`; body target anchor |
| Chill Touch | `sourceSockets`; `targetLocal`; `travel.overlapContactMs`; `impact.timeMap`; body target anchor |
| Fire Bolt, Magic Missile | No draft-validation issues; this does **not** establish consumption of the palette extensions below |

These are checks of emitted data, not guesses from the type declarations.
The Rune Dart and three recovered point-projectile asset records validate.
Fireball's impact-only asset fails with
`$projectileAssets[0].phases.travel must be an object.` All five ice asset
records fail with
`$projectileAssets[0] has unexpected fields: anchorsByFacing.`

Isolated additions to a valid baseline draft also gave concrete evidence of
silent acceptance: `cast.enabled`, `cast.holdReleaseForVolley`, actor-layer
`sourceSheet`, `damage.hitFlash.palette`, and `area.surfaceReveal` each produce
**zero validation issues**. Their current TypeScript consumers do not implement
the new behavior. No visual equivalence is implied by an accepted JSON object.

## 1. The extension boundary is real and needs an honest contract

Python still declares `schema=neuroclient.spellStudioDrafts`, `version=6`
(`game/animation_types.py:369`). The original validator recognizes v6
(`spellAuthoring/validation.ts:203`), but rejects unknown projectile fields
at line 862, unknown phase fields at 1109 and non-tileCenter target bases at
1193. This makes the unchanged version label misleading as a compatibility
claim.

| Local extension | Python definition/use | Original TypeScript gap |
| --- | --- | --- |
| `sourceSockets`, target basis `body` | `animation_types.py:151`, `:208`; `animation.py:376`, `:385` | No matching schema or binding behavior; original anchors require `tileCenter` |
| Phase `overlapRelease`, `scale`, `timeMap`, `overlapContactMs` | `animation_types.py:125` | Original phase fields stop at `durationMs`; resolver only returns those original fields (`runtimeResolver.ts:292`) |
| `targetLocal` and contact/approach controls | `animation_types.py:138`; `animation.py:493` | No target-local delivery executor; original sprite lifecycle awaits prepare, then travel, then impact (`SpriteProjectileFx.ts:147`) |
| `anchorsByFacing` | `animation_types.py:434`; `animation_draw.py:470` | Asset allowed-fields list excludes it (`validation.ts:248`); sprite placement uses a scalar anchor (`SpriteProjectileFx.ts:463`) |
| Optional travel phase for impact-only assets | `animation_types.py`, `AuthoredProjectilePhases` | Original asset parser always parses `phases.travel` (`validation.ts:325`) |
| Paged/layered `projectileStorage` | `animation_types.py:442`; `projectile_media.py:96` | Separate local resource binding; original registry loads and slices one sheet (`AuthoredProjectileTextureRegistry.ts:28`, `:76`) |
| `effectDrafts` keyed by child effect identity | `animation_data.py:356`; ice importer `:106` | Separate local binding; copying the spell draft file alone omits the Ice Knife child presentation |

The table is an adaptation inventory, not an argument against these features.
For example, paged storage and per-facing measured pivots are reasonable media
requirements. TypeScript needs a deliberate equivalent loader/placement path;
changing URLs alone cannot provide it.

## 2. Accepted fields can still disappear or change selection

- **Cast and hand effects:** original `runtimeResolver.ts:67` returns explicit
  cast fields without `enabled` or `holdReleaseForVolley`. Its actor-layer
  resolver at line 179 returns category/tints without `sourceSheet`. Python's
  precolored hand sheets therefore do not follow automatically into the client.
- **Hit palettes:** the damage resolver initially clones the flash object, but
  `clips/TakeDamageClip.ts:26` builds a hit-flash intent containing a scalar
  `flashColor` and duration. There is no palette treatment consumer. This matters
  even for Fire Bolt and Magic Missile, whose draft validation succeeds.
- **Surface reveal:** the additional field passes area validation, but no
  original render source consumes `surfaceReveal`. Python choreography does
  consume it (`game/choreography.py:333`).
- **Weapon IDs:** Python adds `sourceItemIds`
  (`game/animation_types.py:834`). Original
  `actionPresentationRecipes.ts:1270` parses only `sourceItemRefs` and other
  original match fields, returning a new object at line 1329. The full current
  variant table therefore fails with
  `action recipe[0].variants[5].match duplicates another exact Attack profile.`
  Dropping the morningstar ID restriction makes it duplicate the generic
  piercing row. A separate one-variant probe succeeds but drops
  `sourceItemIds: ["weapon.dagger"]`, leaving a critical-piercing match with no
  dagger restriction. The full-table rejection and isolated silent loss are
  distinct verified results.

Stable weapon IDs do not need replacing with invented legacy content digests.
They need an explicit matching contract in both consumers. Likewise, keeping
the palette work does not require a new effects system; the existing actor
layer/flash consumers need the agreed extra material semantics.

## 3. Registration data and coordinate compensation are mixed

There are several different kinds of point, and they should not be judged as
one category of arbitrary offsets:

1. **Pixel registration:** ice exports supply a measured pixel point per facing.
   `devtools/import_ice_spells.py:87` normalizes those source measurements by
   canvas size. `game/animation_draw.py:470` rotates the pivot displacement with
   the sprite. This is valid art registration, not a guessed world position.
2. **Hand attachment:** `sourceSockets` records measured positions in the actor
   source sheet, including preparation frames. The source import reads the
   measured manifest (`import_spell_recovery.py:103`). Python attaches them
   using the rig's dimensions/origin (`animation.py:385`). This is useful, but
   the sockets live inside each spell recipe and are tied to that source clip/
   sheet. Their presence does not establish support for arbitrary caster rigs.
3. **Anatomical target:** the body path reads `rig.body_anchor`
   (`animation.py:376`). The root data is `(64,72)`
   (`game/data/neuroclient/bindings.json:450`). With a 128-pixel cell and 41-pixel
   ground registration, this sits 15 source pixels above the ground anchor.
   The recent Ray/Ice `liftY=-12` moves that contact upward by 12 source pixels
   before the actor/camera scaling. It is authored target placement, not a
   measured projectile pivot.
4. **Legacy canvas placement:** `_projected_endpoints` chooses rig-root versus
   tile-center behavior from `projectile.geometry.enabled`
   (`animation.py:558`), not from the source anchor's serialized `basis`.
   `projectile_center_offset` derives a canvas-center offset from asset anchor,
   scale and sprite offsets (`:528`). The legacy path feeds that registration
   into endpoints (`:563`); `project_projectile` bypasses this coupling for
   assets with directional anchors (`:578`). These are two actual semantics,
   not merely two spell values.
5. **Depth approximation:** Chill's `targetLocal.approachOffsetTiles=.12` until
   frame 240 is authored in `import_ice_spells.py:60`.
   `animation.py:494` changes the ground contact used for depth; it does not move
   the projected sprite point. This is a depth-placement convention with its
   own units/meaning. Calling it just another source-image anchor would hide
   what the field does.

When sockets exist they replace the previously computed source-anchor point
(`animation.py:385`), and disable the source axis inset (`:565`). The older
serialized fields remain present. This is a precedence rule that a port must
preserve or intentionally simplify; it is not represented by JSON field names
alone. Body targets also interpret `forwardPx` differently from the legacy
endpoint inset (`:383`, `:566`).

The current `-12` change is local, regenerable and does not alter ground-burst
placement: the importer copies the Ice Knife child first at line 107, then
changes incoming Ray/Ice targets at line 119. Those are sound bounds for that
correction. They do not prove Fire Bolt uses the same target contract: Fire
Bolt retains the legacy target/canvas path. A future shared torso decision
should be based on rig anatomy and visual evidence, not on matching an older
spell's compensated appearance.

## 4. Runtime is mostly generic; authoring ownership is less clear

The current spell executors do not need a different rendering branch for each
spell. Timing, rows, palettes and sockets are consumed as data. However, the
data is partly authored by imperative import scripts, not entirely by the
original Studio editor:

- `import_spell_recovery.py:82` clones existing spell recipes and patches
  per-spell choices. Fireball copies sockets from `drafts[1]` at line 139,
  coupling its hand attachment to the position of the Guiding Bolt recipe in
  an importer list.
- `import_ice_spells.py:31` clones the **current generated Guiding Bolt recipe**,
  then changes selected fields. Its inherited values therefore depend on
  another spell's generated result. The Chill timing map, depth convention and
  latest torso offsets are authored in that importer (`:59`, `:119`).
- `devtools/bake_spell_palettes.py` subsequently modifies emitted drafts and
  creates actor-layer resources. Its ordering relative to import/reimport is
  part of reproducing the final data.

Offline per-spell authoring is not itself an architectural defect. It is a
problem to call these importers neutral converters or to promise that editing
the original Studio file is sufficient to reproduce the current result.
Choose which small authored records own these decisions; converters should
read those records rather than silently acquiring the latest values of a
different spell. This does not require another DSL or editor.

## 5. Existing fields also have incomplete Python coverage

`StudioArea` accepts original `phases`, `geometry` and `sprite`
(`animation_types.py:314`). In the selected cast executor, area presence checks
for a ground destination (`animation.py:795`); choreography uses the new
`surfaceReveal`, while the original area phase fields are not sampled there.
The implemented shared ground effects use projectile impact timing/media.
Consequently, editing an accepted area's original phase duration is not
evidence it will change Python playback as it does in the original area
executor. This is a supported-subset/documentation issue; it does not by itself
prove a current Fireball rendering failure.

Conversely, several unsupported features fail explicitly in Python
(`animation.py:797`): unsupported generated primitives, alternate travel asset
semantics, palette swaps and weapon-selection modes. Explicit unsupported
behavior is preferable to silently claiming complete Studio coverage. Do not
remove these boundaries merely to make import checks pass.

## What is sound and worth retaining

- The original imported drafts and materializer are still available and their
  actual TypeScript validation passes. This provides a useful parity baseline.
- Shared absolute-time sampling and declarative phase bindings can be ported;
  the newly required behavior is finite and identifiable. It does not require
  rewriting spell mechanics or introducing per-spell renderer classes.
- Per-facing residual rotation, measured source sockets and art pivots solve
  real registration needs. A constant backed by source art is not automatically
  a patch to discard.
- Precolored hand overlays remain separate from the character's body, and
  temporary hit treatment does not replace the persistent actor appearance.
- Paged media are fetched by requested phase/frame/direction. The 640 MiB cache
  is a ceiling, not an eager allocation (`projectile_media.py:47`, `:65`, `:96`).
  This review found no reason to replace that with runtime asset audits.
- The recent target adjustment stays in recipe/importer data and leaves native
  gameplay and the ground burst unchanged. Its narrow success is useful
  evidence, just not proof of whole-contract portability.

## Minimum next decisions, before further authoring expansion

1. **Name the compatibility target accurately.** Preserve the original v6
   baseline; enumerate the finite extensions above as an explicit adaptation
   contract/version or sidecar. Implement only their required equivalents in
   the existing TS resolver/player when migration is authorized. Do not claim
   unmodified v6 interoperability meanwhile.
2. **Agree the point meanings once.** Distinguish gameplay/world support,
   rig/clip attachment and image pivot. State units, scaling and precedence.
   Decide whether the current body anchor means torso and where measured hand
   sockets are owned. Preserve verified legacy playback until an intentional
   migration covers it; do not replace all offsets with another guessed one.
3. **Give authored choices one source.** Use the existing JSON authoring
   records (with explicit extensions) or a small existing-format override file
   as the owner of per-spell choices. Remove dependence on another generated
   spell/list position when that change is planned. Importers can still copy
   pixels and translate source manifests; no generic authoring framework is
   needed.
4. **Check meaning at a small boundary.** Reuse the actual TS validator and
   sampled endpoint/contact/phase checks for representative original and
   extended records. Include one accepted-but-ignored palette/weapon case.
   These should be development checks of the portability claim, not hashes,
   broad startup verification, exhaustive video diffs or a new test platform.

No implementation of these decisions was performed during this audit. The
immediate result is a concrete compatibility inventory and a separation of
legitimate art data from unresolved coordinate/authoring ownership.
