# Graphics cleanup: independent anti-slop review

2026-09-20. Documentation only. This review proposes the smallest ownership
cleanup supported by the current code, and constraints on the proposed
initialization/registry coverage inventory. The separate ECS review owns the
native-event and player-fact inventory. This is not an implementation approval
for unrelated mechanics or omitted VFX.

## Working objective

Keep approved rendered results and shared executors, remove accidental authoring owners,
and describe the finite contract another renderer must implement. The original
TypeScript format is useful source material, not a restriction against justified
extensions. Stable numeric tuning is legitimate authoring. The task is not to
measure new keypoints for every animation or to force every current record
through an unchanged old TypeScript validator.

**User correction: the approved baseline is the effective rendered result,
not the current JSON values.** That result includes selected media, inherited
defaults, importer/bake passes, runtime compensation and final compositing.
The current records are migration inputs, not values the user has endorsed as
the correct representation. Values may need to change when their interpretation
is cleaned up, precisely to preserve the approved appearance and timing.

Current jumps work, including single-cycle timing, height and prelaunch
reactions. Inactive movement-media/recovery fields are not a request to add
movement extras. Potion drinking and contact timing work; omitted potion/source
VFX strips are accepted. They must not reappear as mandatory cleanup work.

## Findings that justify actual edits

1. **Recipe regeneration currently reauthors behavior.**
   `devtools/import_spell_recovery.py:82` clones an old spell then chooses colors,
   timing and contact attachments. Its Fireball socket assignment at line 139
   depends on `drafts[1]`. `devtools/import_ice_spells.py:31` copies the current
   generated Guiding Bolt recipe. Reimporting media can therefore restore old
   choices or inherit another spell's changes.
2. **Palette baking rewrites more than pixels.**
   `devtools/bake_spell_palettes.py:90` picks different treatment behavior for
   Chill Touch, and later writes flash frame/duration, `sourceSheet` bindings,
   parent recipes and child-effect recipes. Reproducing the final content
   currently depends on the order of importer, color revision and palette bake.
3. **Attachment precedence is implicit.**
   `game/animation.py:350` applies legacy anchors then replaces them with source
   sockets; `:558` chooses a basis from geometry enablement; `:578` changes the
   canvas-offset path when the asset has directional anchors. These decisions
   should have one documented interpretation and owner. This is not evidence
   that every retained lift/offset is wrong.
4. **Coverage is distributed, but the data already has registries.**
   `game/animation_data.py:235` loads maps of spells/effects, attack/body-action/
   condition recipes, rigs, resources and media. `game/choreography.py:183`
   already collects event-linked gaps. `game/body_action.py:85` and `:108`, and
   `game/condition_animation.py:88`, already identify specific unimplemented
   tracks. A second discovery or hashing system is unnecessary.

## Recommended authoring ownership

The narrowest migration is to account for the current effective behavior and
then make the existing local record files its editable authoring source, rather
than regenerating behavior from imperative per-spell branches. Do not promote
their current numbers as authoritative before accounting for the transforms
that currently interpret them. Keep the imported baseline separate for reference.
There is no need for another general override language, recipe builder or
parallel authoring tree.

| Choice | Owner after cleanup | Concrete migration |
| --- | --- | --- |
| Cast clip, contact frame, rates, spell scale, overlap, time map, palette treatment, deliberate offsets | Existing local `game/data/{codexfx,spell_recovery,ice_spells}/spell-studio-drafts.json` records | Encode the approved effective behavior, changing values if ownership/units change; stop importers and palette bake reauthoring it |
| Nested Ice Knife burst behavior | Existing authored `effectDrafts` dictionary | Preserve it as authored input; media import must not replace the dictionary or recreate it from a parent spell with later patches |
| Weapon-specific variants and fallback selection | `game/data/neuroclient/attack-profiles.json` | Keep the existing authored table and stable weapon IDs; align the future TS selector with that meaning |
| Shared body interaction and action aliases | `object-interaction-recipe.json`, `action-recipe-bindings.json` | Keep current shared records; do not add one executor per door/lever/torch |
| Rig dimensions, origin, semantic clips and body attachment | Existing `BodyRig`/rig JSON | Keep per-rig mapping; clarify attachment units in the existing owner |
| Hand registration for a particular rig/clip | Existing measured socket data, given an explicit rig/clip owner or reference | Reuse present release points and the Eldritch preparation samples; no mandatory new tracking campaign |
| Per-facing projectile pivot, frame dimensions/counts, page layout, blending | Asset metadata and storage bindings translated from the export manifest | Media importer may update these fields and copy selected files |
| Precolored hand pixels | Palette baker output named by authored `sourceSheet` | Baker reads chosen source layer and treatment; it does not choose cast timing or flash behavior |
| Projection, pivot rotation, phase sampling, composition | Existing shared Python functions, with later TS equivalents | Keep algorithms in code; JSON carries the values and selections that are actually authored |

`bindings.json` currently mixes authored `effectDrafts` with generated resource
and storage metadata. The minimal implementation may preserve the authored
subsection and update only explicitly converter-owned fields. If a whole-file
generator would still overwrite it, move that same typed dictionary into the
authoritative authored file as part of that edit. Do not introduce a third
recipe representation to solve a file-ownership problem.

`sourceSockets` need not immediately become an elaborate socket graph. A named
existing rig/clip attachment with its present fixed coordinates is enough.
If two sheets actually need different registration, identify the specific
sheet/clip they describe; do not force coincident values merely to deduplicate
them. The recently reviewed upper-body contact is the result to preserve.
`liftY=-12` is its current encoding; keep or translate that value according to
the clarified attachment calculation, rather than treating the number itself
as the approved result.

## Practical file-level sequence

### A. Stabilize authoring before changing placement

1. Establish a bounded before-baseline from the same saved inputs and current
   effective code/data/media pipeline. Label references separately as
   user-approved clips, current captures without approval, and known defects.
   Current local drafts, child-effect records and attack variants are inputs to
   this baseline, not authoritative numbers to freeze. Then document each
   authored owner's intended meaning in the existing bundle README. Ordinary
   version control is sufficient; no source hash ledger is needed.
2. Change `import_spell_recovery.py` and `import_ice_spells.py` to package media
   and translate asset/storage metadata. Remove their role as owners of cast,
   damage-flash, target, overlap and palette decisions. An initial recipe can
   still be manually authored from a known example; reimport must not repeat
   that authoring operation over an accepted recipe.
3. Change `bake_spell_palettes.py` to consume the authored material settings and
   output the requested pixels/resource bindings. Preserve the approved final
   palette appearance, including relevant filtering/recoloring behavior. Avoid
   its current fallback of authoring a missing damage recipe
   during a pixel bake. The relevant recipe already exists in current data.
4. `import_spell_color_revision.py:28` also updates `palettePreview` metadata;
   make the approved media revision the selected asset input so a routine
   import does not restore pre-revision pixels. No new build orchestrator is
   necessary: document explicit input and output ownership in these few tools.

This first stage should preserve approved rendered output. Compare selected
actual composited frames and contact/phase timing before and after using the
same saved inputs, camera, appearance and elapsed times. Metadata comparisons
are supporting evidence, not the visual acceptance criterion. Confirm that
reimporting/baking does not reset deliberate authored behavior. Known defects
remain explicitly excluded from equivalence; current unreviewed captures are
observations, not retrospective user approval. No hashes, filesystem inventory,
full gallery regeneration or new pixel-regression framework is required.

Concrete effective behavior that this baseline must include:

- `animation.py:350`, `:558`, `:578`: socket overrides, legacy root/canvas
  compensation and directional-pivot registration. Identical raw offsets do
  not necessarily imply identical final contact after those paths change.
- `animation.py:664`: travel uses the main projectile FPS, while preparation/
  impact allow a phase override. At `:907`, actual arrival also depends on the
  computed distance, minimum duration, height and target-local override. Raw
  phase fields alone do not establish the played frame or contact time.
- `animation_draw.py:174`: a precolored `sourceSheet` bypasses the ordinary
  source-hue recolor; the non-precolored Magic3 path additionally remaps bright
  pixels to its secondary color at line 179. Preserve the composed hand effect,
  not merely its serialized tint.
- `spell_palette.py:59`: visible-pixel luminance percentiles, gamma and optional
  noise shape the actual hit treatment. A palette list alone is not its result.
- `projectile_media.py:87`: additive media bakes source alpha into RGB;
  `animation_draw.py:470` rotates the pivot displacement, then rounds scaling
  and applies rotation/fade before compositing. The raw PNG is not the final
  displayed image.

These are specific inputs to the before/after comparison, not a proposal to
move every rendering equation or numeric constant into JSON.

### B. Clarify the small runtime contract

5. In `game/animation_types.py` and bundle documentation, distinguish rig
   attachment, asset pivot, world support and recipe offset. Choose one
   precedence rule. Make the required edits in `animation.py` and
   `animation_draw.py`, preserving the approved visual result. Do not retune
   every spell simply because an old number was manually chosen.
6. Keep the actual finite extensions: directional pivots, rig/body/source
   attachments, per-phase scale/time mapping/overlap, target-local delivery,
   cast suppression/volley hold, palettes/precolored sheets, child-effect
   binding, surface reveal, stable weapon matching and paged/layered storage.
   These describe current accepted behavior. Consolidate names/ownership only
   when that removes a concrete ambiguity; do not invent a universal timeline
   language or require an unchanged old TS schema.
7. State the extended contract explicitly. Future NeuroClient support means
   adding equivalent consumers to its existing resolver, selector and drawing
   code. No current task requires starting that old client or replacing its
   whole animation architecture. Original TypeScript checks are a useful
   baseline diagnostic, not the sole acceptance criterion for justified new
   behavior.

For placement evidence, reuse a small selection of existing saved packets with
different rigs/camera directions and both original and new assets. Verify
contact and registration at their actual sampled times. Do not turn this into
a demand for all possible rigs, directions, heights and spells before progress.

### C. Add the coverage view to initialization

8. Use the same `load_animation_data` initialization and existing loaded
   dictionaries to resolve stable recipe, effect, rig and media identifiers.
   Add only the finite capability declarations required to describe what the
   existing consumers implement. Return the derived coverage record for a
   devtool/report; do not rebuild it in the frame loop.
9. Keep replay's event-linked gaps as observed evidence. Display those alongside
   the declared/bound support; do not replace the current binder logic with a
   generic dispatcher simply to produce a report.
10. Use the finished report to select real remaining gameplay presentation
    work. Accepted omissions stay accepted. Loaded records without used
    features are not an instruction to implement every dormant Studio option.

## Registry-backed coverage: approve with these bounds

**Lean and appropriate:** stable identifiers, the already-loaded recipe maps,
explicit finite consumer capabilities, ordinary dictionary joins and existing
replay gap output. Check unresolved references and incompatible selected
features once during registration. The current loader already rejects duplicate
identities and missing source-recipe bindings (`animation_data.py:270`, `:295`,
`:333`, `:365`); reuse that boundary.

Broken mandatory identity joins can remain initialization errors. Unsupported
visual features and accepted omissions should be reported with their proper
status, not converted into a new rule that prevents the game from starting.

**Avoid overstating what initialization proves.** A registered `SpellFact`
family does not make every spell renderable. The selected recipe, rig and used
tracks matter. Conversely, absence of a new actor animation is not automatically
a gap: state-only facts, lineage containers, invisible participants and effects
owned by an ancestor can be intentional. For example:

- `body_action.py:49` can return no cue when a behavior has no applicable
  actor-only recipe; `:57` deliberately excludes projectile/area drafts.
- `condition_animation.py:60` skips internal conditions intentionally, while
  `:88` reports populated strip/equipment/rig-layer features as unsupported.
- `choreography.py:250` gates action presentation by permitted visibility and
  `:281` joins child applications to an existing owner.
- `combat.py:198` explicitly gives equipment changes with identical visible
  layers no separate gesture.

A compact report needs separate meanings for:

- **Declared support/binding:** what the registered consumer and selected
  authored record are capable of handling;
- **Intentional no-visual or omitted feature:** an explicit accepted choice,
  including the potion/source strips already accepted by the user;
- **Missing/unsupported selected content:** a concrete missing identity,
  feature or required binding;
- **Observed replay evidence:** whether an existing saved sequence exercised
  it, and any actual binder/media gap observed there.

These can be fields or small enums in one passive record; they do not call for
a reporting subsystem. Keep the native-event/player-fact mapping as code-owned
data tied to actual registered projection/reduction owners. Do not infer support
by matching names or file text. Do not rewrite event projection or causal
composition to make the inventory easier.

**No SHA or source audit.** Do not compute or store hashes of code, PNGs,
recipes, event packets or directories for coverage or initialization. Do not
require Git state, timestamps, source archives, image decode or a native game
rerun. Existing imported historical identity fields need no new hashing
machinery; new graphics lookup/coverage should use stable registered IDs.
Structural versions describe interpretation, not file authentication.

**Do not pretend metadata proves disk/media availability.** Initialization can
join an asset ID to a registered storage binding without opening images. Actual
media decoding stays demand-driven and existing replay gaps report failures.
Label that result “bound,” not “all frames visually proven.” This prevents the
coverage request from rebuilding the slow asset-validation track the user
explicitly rejected.

## Review status

Reviewed `GRAPHICS_CLEANUP_PLAN_2026-09-20.md` after the independent review.
The plan is approved for its bounded authoring cleanup and lean coverage design,
subject to the subsequent effective-rendered-result baseline correction above.
It preserves accepted omissions, stable tuning, native causality and the
working jump system; it does not require a new dispatcher, universal format,
asset audit or full TypeScript implementation.

An independent metadata-only probe of `SPELL_CATALOG_COMPOSITION_ROWS` and the
selected draft files confirms **115 registered spell IDs, 14 matching draft
bindings and 101 without a selected cast draft**, plus the separate
`spell.ice_knife.burst` child key. The plan correctly avoids equating a missing
cast recipe with absence of shared visible damage/condition/child outcomes.

Two small corrections were requested before finalization:

- Include approved color-revision input selection in work unit 1. Otherwise
  reimporting the original media can restore pre-revision Fireball/Eldritch
  colors even after the recipe files become canonical. The current bundle
  README explicitly documents that ordering requirement.
- Limit the prohibition on extra serialization to repeated initialization or
  frame-loop work; the requested on-demand JSON coverage report is legitimate.

No runtime implementation was performed for this review.
