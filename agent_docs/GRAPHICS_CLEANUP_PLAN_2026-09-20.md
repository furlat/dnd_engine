# Graphics cleanup and presentation coverage plan

Date: 2026-09-20. Branch: `codex/recovery-design`.
Status: independently reviewed proposal; runtime implementation has not started
in this planning turn.

This follows the [graphics review](GRAPHICS_PORTABILITY_REVIEW_2026-09-20.md)
and the user's subsequent corrections. It replaces the review's preliminary
next-work list as the practical cleanup sequence. The original gameplay
objective in `RECOVERY_PLAN.md` remains in force.

## Outcome

Keep the working encounter, recorded-event playback and approved rendered results, while
making every active presentation choice have an identifiable owner. Ordinary
content additions should change authored records and media bindings. Shared
code should implement finite gameplay-presentation capabilities rather than
accumulate per-spell repair paths.

A later NeuroClient adapter should reuse those records and their explicit
semantics. The old TS schema is allowed to evolve. Unchanged acceptance by its
old validator is not an implementation goal and not a measure of design quality.

**The approved baseline is observable output, not the stored JSON.** Current
results depend on the data, selected media revision, importer/bake outputs,
loader defaults/overrides and runtime transforms together. Canonicalizing raw
values without accounting for those later operations can regress the approved
appearance. Numerical values and their representation may change to preserve
the effective result. Distinguish user-approved clips, current captures and
known defects; do not call every current value or picture approved.

Alongside this cleanup, expose an inventory that answers:

- Can this event payload be retained and projected to the player?
- Who presents its permitted result: itself, a causal parent, or ordinary state?
- Does the registered action/spell/condition/rig have the necessary binding?
- Is an omission intentional, unsupported, or simply not exercised yet?
- Which saved clip exercised it, and what did that run actually report?

The inventory must use initialization and existing registries/bindings. **No
SHA, filesystem crawling, source-content audits or per-frame verification.**

## Scope decisions already made by the user

1. Keep pure Python/Pygame execution now. TS/Godot/Bun are not game dependencies.
   Future TS reuse concerns data and execution meaning, not a mandatory full
   client port during this cleanup.
2. Tuned numerical offsets, pivots, contact frames and scales are legitimate
   authoring. Preserve approved appearance and timing; values may need conversion
   when their consumer semantics change. Do not demand a comprehensive keypoint
   or skeletal system.
3. Existing measured hand/frame points may be retained where useful; putting
   them under a clear owner does not mean collecting more for every animation.
4. Potion/source VFX omissions are accepted. Do not restore them as cleanup.
   This does not remove approved casting auras or target effects already in use.
5. Empty optional movement media and disabled extra recovery tracks are not a
   backlog item. Walking, jumping, landing and opportunity reactions already
   work. Their actual causal/timing behavior must survive the cleanup.
6. Native outcomes, visibility, conditions, handler interception and lineage
   rules stay native. Graphics cleanup must not revise them or push rendering
   hints into mechanics. Coverage does not disclose hidden events to players.

## What exists today

The useful pieces are present, but they do not form one coverage view:

| Existing owner | What it provides | What it does not establish |
| --- | --- | --- |
| `dnd/core/events.py:EventType` | 70 native event categories in the current checkout | Seventy distinct animations, or a list of concrete payload classes |
| `game/event_record.py:EVENT_MODELS` | 52 explicitly retainable concrete event models | Support for every native concrete class or visual treatment |
| `game/player_facts.py:PlayerFact` | 19 permitted fact variants plus separate initialization/world/observation records | A required standalone clip for every causal node |
| `game/animation_data.py:load_animation_data` | Selected spell, action, condition, rig and media maps | That all fields of every loaded row are executed |
| Content catalog/composition | Registered behavior identities | A matching presentation for each identity |
| `game/choreography.py:BoundChoreography.gaps` | Failures or unsupported tracks encountered during actual binding | A complete inventory of content never exercised |
| `devtools/animation_review/catalog.json` | 190 authored review scenarios, with real saved-event replay | Exhaustive event/content coverage or human approval of each visual |
| Review `trace.json` / run manifest | Bound nodes, timelines, outcomes and gap details for a particular run | That a passing run has no omissions; pass/checks and gaps are currently separate |

Metadata-only inspection finds **115 registered spell catalog entries**, with
**14 matching selected spell drafts**, plus the separate Ice Knife burst child
recipe. The other **101 have no selected cast draft**. Their damage, conditions
or other child results may still be represented by shared presentation; do not
translate this into “101 spells produce no visible result.”

The [event and content coverage inventory](PRESENTATION_EVENT_COVERAGE_2026-09-20.md)
records the current source-backed classification. It is a planning snapshot,
not a second registry that runtime must load or keep synchronized manually.

The existing gap list is not exhaustive: `bind_body_action` can return no cue
for a generic action with no selected recipe without adding a gap. Custom roots
such as Counterspell or Dragonborn breath also need their retention/projection
and selected action family distinguished from the supported child outcomes.
The inventory records these boundaries without making all of them cleanup
implementation tasks. A zero-gap run alone cannot establish complete coverage.

## Ownership after cleanup

Keep these responsibilities separate without constructing another framework:

| Owner | Owns | Must not own |
| --- | --- | --- |
| Native engine / subjective projection | Outcomes, complete causal relationships, permitted contacts and world state | Pixel offsets, frames, palettes or presentation-only timing |
| Canonical authored recipes | Body clip/rate, effect/contact anchors, chosen media, approved offsets/scales, palette treatment, attack variants | Another spell's generated mutable state |
| Rig and media registration | Sheet geometry, rows, clip mapping, support origin, existing body/hand attachment data and asset pivots | Gameplay hit detection or a separate spell executor |
| Offline import/bake tools | Copy/export images, convert packaging metadata, produce precolored media from declared inputs | Change contact timing, copy behavior from list positions, overwrite authored recipe decisions |
| Shared binding/sampling functions | Read facts and recipes; compose the lineage; sample time and stable world contacts | Re-run the encounter, infer hidden outcomes or branch on individual spell names |
| Pygame adapter | Load requested media, transform/project/composite it and draw UI | Decide game state or mutate canonical authoring |
| Coverage view | Combine initialized support declarations, selected bindings and observed run results | Gate gameplay through source audits or become a duplicate rules/dispatch engine |

Existing frozen records and functions are a suitable base. No animation-manager
class hierarchy, generic property interpreter, new expression language or
generalized plugin system is needed.

## Before edits — establish the effective visual baseline

Use the existing saved player inputs and gallery machinery for a bounded set
covering the owners being changed. Retain the pre-change code/data/media through
an ordinary Git checkpoint and keep the corresponding run artifacts accessible.
Record which outputs the user actually approved and any known issue still open.

Inspect actual composed frames and existing trace timing at release, contact,
reaction, landing and settled state as appropriate. Include current palette
baking, frame-page selection, attachment compensation, rotation, clipping,
scaling and depth composition. Saved gallery video is the visual reference;
replaying the same input with the current tree identifies whether that tree
still matches it. A different capture is not automatically a newly approved one.

Concrete downstream behavior to include in that baseline: socket/root/canvas
precedence in `animation.py:350`, the travel-versus-impact FPS rule at `:664`,
precolored `sourceSheet` versus runtime hue treatment in `animation_draw.py:174`,
percentile/gamma/noise palette mapping in `spell_palette.py:59`, and rotated
pivots, integer image scaling and blending in `animation_draw.py:450`.
These are observations of the current renderer, not a claim that each algorithm
must become a JSON field or is itself defective.

For a cleanup, compare before/after results from the same saved inputs and
camera/timeline sample points. Numeric endpoint/frame checks support that
comparison but cannot replace the final composed image. Reuse side-by-side
frames/videos; no SHA, asset scan or new automated pixel-diff platform. Do not
quietly combine a visual redesign with an ownership refactor. Known visual
defects remain explicit rather than being blessed as acceptance targets.

## Work unit 1 — make effective authoring authoritative

This is the first runtime/tooling cleanup because scattered recipe ownership is
the clearest demonstrated problem.

### Changes

- Use current `spell-studio-drafts.json` records in their existing local bundles
  as the starting authoring files. First account for effective defaults,
  inherited settings, media revisions and runtime post-processing. Make their
  resolved decisions authoritative while preserving rendered output; do not
  assume their raw values are what the user approved. Keep the unchanged
  imported baseline as reference; do not add another layer of override files.
- Keep one selected owner per content identity, including explicit child-effect
  records such as Ice Knife's burst. Original reference copies are not competing
  active authors.
- `bindings.json` currently mixes authored `effectDrafts` with generated media
  bindings. Preserve that authored section when updating generated fields, or
  move the same typed section into the canonical authored document if needed
  for clear file ownership. Do not create another recipe representation.
- Remove recipe construction/rewriting from `devtools/import_spell_recovery.py`
  and `devtools/import_ice_spells.py`. They may still emit asset/storage/resource
  metadata derived from delivered media.
- Remove Fireball's `drafts[1]` socket dependency and ice spells' dependence on
  the current generated Guiding Bolt recipe. Preserve their effective behavior
  through explicit authoring. Introduce named shared authoring only for a real repeated
  choice; an explicit record is preferable to a new inheritance system.
- Change `devtools/bake_spell_palettes.py` to consume the recipe's declared
  palette/material and output media bindings. It must stop setting hit timing,
  duration, gamma and other recipe behavior as part of an image bake.
- Include `devtools/import_spell_color_revision.py` in the ownership change:
  select the approved media revision explicitly so a routine import cannot
  silently restore older pixels. This is a packaging-input decision, not a new
  build orchestrator.
- Preserve the current distinction between actor art and isolated casting
  layers. Recoloring a casting asset must not recolor the character itself.
- Document which files a content author edits and which tools own generated
  packaging. Remove obsolete instructions that tell authors to modify outputs
  that a later import silently replaces.

### Acceptance

The same saved cases preserve the approved composed appearance, clips, frames,
contact times, equipment, palettes and geometry, including the current effects
of post-processing. Merely matching JSON is insufficient. Reimporting one media package does not edit
any canonical recipe or change another spell's behavior. No full art generation
or encounter recapture is needed. Compare values and selected observable replay
results directly; no hash-based proof or asset-folder audit.

## Work unit 2 — one understandable placement calculation

Do this after authoring ownership is stable, so corrections cannot be overwritten
by an importer.

### Changes

- Write down the existing units and transformation order: native world support
  and elevation -> actor attachment -> projected contact -> registered image
  pivot -> camera scale/rotation. Include where the trajectory lives and how
  physical depth is derived.
- Keep tuned numerical actor/media authoring. Preserve the current Ray/Ice
  correction in the initial baseline; do not assert the user approved its raw
  offset or every resulting view. Review intentional contact choices versus
  duplicate compensation in the context of the whole calculation. Convert
  values when necessary to preserve the selected rendered baseline.
- Resolve legacy canvas-center versus newer directional-pivot behavior in
  `game/animation.py` and `game/animation_draw.py`. Preserve older art registration
  through a bounded conversion/adaptation rather than retuning every spell.
- Make actor/clip-specific source measurements explicit instead of accidentally
  inheriting them through a spell. Fixed and modular rigs may use different
  authored registrations; neither needs a generalized bone hierarchy.
- Keep a stable contact meaning for target-side effects across supported rigs.
  Deliberate effect offsets remain allowed. Ground bursts retain a ground
  attachment and do not inherit body offsets.
- Explain depth-only controls, such as the current target-local approach value,
  as presentation placement if retained. Do not label them physical travel.
- Retain current shared wall/door/height composition. Change it only if the
  attachment cleanup demonstrates a specific inconsistency; avoid a simultaneous
  replacement with a new 3D renderer.

### Acceptance

Use a bounded set of existing original and new deliveries on flat ground and
different heights, noncanonical directions, all four cameras, and modular plus
packaged targets. Endpoints, approved appearance and contact timing remain
coherent. A camera turn or compatible asset swap does not require adding another
spell-specific conditional. Ordinary visual review remains necessary; passing
numeric checks alone is not acceptance of anatomy/alignment.

## Work unit 3 — make the presentation data contract explicit

### Changes

- Retain original useful Studio names and structures. Record the finite justified
  additions: media pages/layers, phase scale/timing controls, target-local
  delivery, body attachments, optional travel, palette treatment, stable weapon
  identity matching, and child-effect bindings.
- For each addition, state the actual consumer and observable meaning. Remove
  only a demonstrated duplicate or unjustified active mechanism, not a feature
  solely because the old TS validator rejects it.
- Mark the extended version/contract accurately. Keep the original baseline
  separately identifiable. Do not use permissive unknown-field acceptance as
  evidence of interoperability.
- Export ordinary data values independent of Python `Path`, dataclass identity,
  enums or `pygame.Surface`. The saved player-event boundary remains separate
  from authored content and from runtime-bound timeline objects.
- Include the resolved equipment visual ledger in the future TS handoff; it
  currently comes from passive Python item declarations. Do not make a browser
  import Python or native entity registries.
- Document code-owned behavior that accompanies the data: child joins, independent
  historical playback, prelaunch jump reactions, one-cycle jump body timing,
  interrupted sub-tile positions, area occlusion and procedural floor materials.
  These are shared semantics to port, not hundreds of new JSON rules.

### Acceptance

A short contract/example set explains how the same registered content would
be consumed in TS. Original and extended representative records can be decoded
without hidden cross-spell inheritance. Actual TS implementation is subsequent
authorized work; it does not block finishing the current Python cleanup.

## Work unit 4 — initialize a lean support inventory

The inventory is a view over existing owners, not a new engine event registry.
Native `EventQueue` remains the live event-instance registry. `EVENT_MODELS`
remains the recording contract; neither is repurposed to schedule animations.

### Construction

1. At presentation initialization, use the already available event categories,
   retained-model map, public fact types, selected content identities and loaded
   `AnimationData`/world bindings. Do not instantiate a game to discover them.
2. Existing presentation owners contribute small passive capability declarations
   describing their supported fact families/features and how their output is
   represented. Co-locate these with the actual owners. They describe shared
   support; they do not duplicate the full choreography dispatcher or recipes.
3. Join those declarations with the actual loaded recipe maps. This exposes a
   missing spell/action recipe, an unsupported selected track, a missing rig
   mapping, or an intentional state-only presentation. Use normal IDs and
   dictionary lookups; storage hashes have no role.
4. Keep explicit scope/selection. A registry-wide developer view may list content
   absent from the current encounter; ordinary playback need not import or
   initialize every unused catalog to construct its local coverage view.
5. Emit an ordinary JSON/list result when requested by the developer view or
   review tool. No disk scan, image decode or source checkout is needed to
   enumerate declared support. Actual media availability remains an observation
   from its existing loader, not a new initialization audit.

### Information per row

Keep separate questions separate; avoid a misleading single green/red flag:

| Column | Example values / meaning |
| --- | --- |
| Identity and family | Native category/concrete recording model, public fact kind, or content ID; do not conflate these inventories |
| Presentation owner | Cast, attack, movement, condition, equipment, world state, initialization, technical lineage |
| Expected representation | Own timeline; represented through parent contact; state update; technical structure/log; accepted omission; not classified |
| Selected binding | Actual recipe/rig/material identity, or missing |
| Declared support | Implemented for selected features; partial with reason; unsupported; not assessed |
| Observed evidence | Saved case and perspective; bound successfully; actual gap; not exercised; separate human visual judgment |

Examples:

- A damage child represented at its attack's contact is covered by that parent,
  not “missing its own animation.”
- A saving throw/check may contribute outcome/log/causality without a dedicated
  visual. Preserve the actual event/subjectivity rules; do not invent an effect.
- Potion body/effect playback can be covered while its source strip is an
  accepted omission.
- `spell.haste` currently has no selected cast draft even though movement under
  Haste and the condition's consequences have examples. Those are different rows.
- A scene-hidden or undisclosed actor is not an unsupported renderer. Lack of a
  permitted fact is not evidence of a failed projection or reason to leak one.
- A listed recipe with unsupported condition equipment modifiers is partial,
  even though the condition itself reduces correctly.

### What initialization can honestly promise

Initialization can enumerate declarations and resolve in-memory bindings.
It cannot establish that every event combination renders correctly. Conditional
branches, missing media actually requested, observer visibility and real causal
composition are assessed when binding/replaying an actual lineage.

Use existing binding results and `BoundChoreography.gaps` for that evidence.
Add structured reason/owner identities where needed, instead of parsing prose
messages or building another logger. Collect once at lineage binding/replay,
not by traversing events or assets every rendered frame.

Unknown/unassessed stays explicit; it must not become “no visual needed” by
default. Conversely, every old optional field does not become an obligatory
feature. Accepted omissions belong beside the relevant capability decision.
Do not generate placeholder recipes or generic effects simply to turn missing
bindings into green rows. Coverage reports what the implementation can do.

### Acceptance

- The initialized view lists the currently selected families/bindings and can
  enumerate the already-loaded registered content without running combat.
- Adding a registered spell without a presentation exposes its missing binding
  without a handwritten new row in a coverage Markdown file.
- A child-owned damage sequence, state-only update and accepted potion omission
  do not appear as unexplained rendering failures.
- A genuine missing selected recipe/feature appears with its owner and reason.
- No startup PNG checks, hashing, source audits, repeated startup/per-frame
  serialization or per-frame coverage work are introduced. Serializing the
  requested report once is ordinary output.

## Work unit 5 — connect coverage to the existing review gallery

- Extend the existing review manifest/trace with the support rows actually
  exercised. Reuse existing case IDs, perspectives, root/event IDs and gap data.
- Add a coverage table/filter to the existing gallery: missing binding,
  unsupported selected feature, accepted omission, and not exercised.
- Link an exercised row to its clip and trace. Keep the existing four-camera
  output and both subjective perspectives where the scenario has them.
- Keep checks passed, missing presentation and human visual approval distinct.
  A run can pass its replay checks yet still have an explicitly listed omission.
- The initialized catalog lists unexercised content; the run reports what it
  actually saw. Do not claim a global content test merely because one cast passed.
- Render existing saved sequences after the relevant changes. Add a native
  scenario only when an actual selected requirement has no suitable recording.
  Do not regenerate all mechanics every time authoring changes.

This is a small extension of the current tool, not another dashboard service,
test framework or video-diff platform. Pixel regression tests remain outside
this unit as the user previously requested.

## Work unit 6 — close the selected gaps and finish cleanup

Use the support view to prioritize actual missing observable behavior, rather
than all dormant fields. Condition-driven weapon appearance and the authored
appearance layer are known examples; implement through existing composition
owners if selected, never a branch per condition name. Missing spell bindings
should be grouped by shared delivery needs before authoring content in batches.

Do not promise that all 115 spell entries become fully presented in this
cleanup. The output is a trustworthy list and a scalable place to complete them.
Showing a status is not a substitute for completing an authorized feature.

Remove confirmed superseded active paths and misleading documentation after
their replacements have passed their scoped checks. Preserve the original
source/oracle as reference. Consolidate the active instructions around one
ownership table, one current plan and the registry-backed support view. Avoid
mass file moves, repository-wide stylistic rewrites or a new repository skill.

## Execution and verification order

1. This turn: complete the source inventory and have this plan independently
   reviewed. No runtime changes are part of the planning result.
2. Establish the effective visual baseline, then make canonical authoring and
   importer/bake ownership clean first.
3. Unify placement semantics and document the explicit portable contract.
4. Add the initialization inventory and connect existing binding/run evidence.
5. Use its actual findings to select shared capability completion, then remove
   the superseded paths/docs affected by this work.

Each implementation unit must produce a concrete diff, relevant existing tests,
and selected saved-input clips when appearance/timing changes. Unit boundaries
are validation points rather than automatic requests to stop for permission.
New decisions outside this plan still need human guidance. Follow
`HOW_TO_TEST.md`: verify externally visible behavior, avoid tests that merely
freeze private helper structure, and do not invent speculative mechanics cases.

The mandatory retained behaviors include independent latest/history, complete
subjective lineages, gear-at-time, body/target contact timing, height/camera
placement, prelaunch jump OA, interrupted body positions, persistent native
residue/trap state and player disclosure. Protect these through existing
representative cases; do not rebuild the engine or reopen visibility rules.

## Independent design review

- **Anti-slop reviewer:** authoring ownership, unnecessary abstractions, stable
  numerical placement, justified schema changes and bounded coverage cost.
- **Anti-OOP/ECS reviewer:** native/public event coverage, lineage ownership,
  state-versus-animation distinctions and passive registration boundaries.

Both reviewers approved this sequence, including the user's effective-rendered-
output correction:

- [Anti-slop review](GRAPHICS_CLEANUP_ANTISLOP_REVIEW_2026-09-20.md): approved the
  bounded ownership/coverage approach. Its requested color-revision ownership
  and on-demand-report serialization clarifications are incorporated. It also
  identifies downstream image/timing behavior that must be in the baseline.
- [ECS review and exhaustive inventory](PRESENTATION_EVENT_COVERAGE_2026-09-20.md#ecs--anti-oop-review-of-the-cleanup-plan):
  approved the native/public/visual boundaries, passive declarations, retained
  causal behavior and composed-output acceptance criterion.

The 70-category inventory was checked against the existing enum: every category
appears exactly once. The 115/14/101 spell binding counts were independently
recounted. These are metadata/list checks, not gameplay tests or proof of visual
correctness. No runtime code, media or existing saved inputs changed in this
planning turn.
