# Shared presentation semantics, declarative timing and text renderer

2026-10-05 — **PROVISIONAL; not ready for migration or implementation.**

The user's exhaustive-rendering correction takes precedence. The [schema readiness audit](audits/RENDERING_SCHEMA_READINESS_2026-10-05.md) identifies missing lifetime, sampling, evidence and dependency cases. Complete its concrete family mappings and verification before freezing this proposal. Earlier reviews approved architectural direction, not exhaustive schema fit.

This supersedes the discussion-only outline in [the renderer study](audits/RENDERER_ARCHITECTURE_AND_TYPESCRIPT_PORT_STUDY_2026-10-05.md). It preserves that study's source findings. Current authorization is study/design/plan; production changes await acceptance of this plan.

## 1. Objective and completion boundary

One observer-permitted action sequence plus one effective presentation catalog must be sufficient to produce:

- The existing Pygame presentation, preserving accepted artwork, timing and gameplay outcomes.
- A deterministic text narrative, including meaningful gesture/delivery/impact/condition transitions and optional mechanical detail.
- A portable presentation contract that a future TypeScript/PixiJS implementation can execute without recovering hidden Python decisions.

Python/TypeScript implement a finite collection of functional operators over passive typed data. Content selects operators and authors their parameters, relationships and descriptions. Entities do not become renderer objects or acquire executable methods.

Completion means all currently supported presentation families use the common timing/meaning contract, the text renderer handles all projected fact kinds deliberately, and graphics still passes existing acceptance checks. A single Ray of Frost demonstration does not finish this plan. Families may migrate in bounded commits, but the final acceptance covers the complete active catalog.

Included: authoring extensions and validation; shared binding/timing; descriptions; narrative rendering; pygame-ce narrative view with optional images and plain transcript export; live narrative observer integration into the existing encounter loop; current graphics adaptation; regression evidence and independent reviews.

Excluded: new spells/rules/art, replacing the native event queue, full TypeScript/Pixi implementation, networking protocol replacement, a new game-command UI, AI redesign, scenario redesign, new terminal emulator, natural-language command interpretation or LLM-generated runtime prose. The narrative view uses the existing encounter command path; a new action-selection UI is not required to validate this renderer.

## 2. Non-negotiable ownership

| Value | Authoritative owner |
|---|---|
| Hit, damage, save, movement commitment, application/removal, item transfer | Projected native facts |
| Who/what is identified, located or visible at a moment | Existing observer projection and event-time observations |
| Actual causal ancestry and resolution ownership | Existing lineage/version/ResolutionRef records |
| How a witnessed operation is presented | Authored presentation recipe and shared operators |
| Gesture/media meaning and descriptions | Authored description metadata |
| Presentation dependency/overlap/commit policy | Typed authored timing policy, instantiated against actual facts |
| Geometry/material evaluation | Shared functional implementations selected by typed data |
| Pixels, text layout, transcript bytes | Local output adapters |

We cannot author a different causal history. “Data-driven causal relationships” means preserving native causal edges as data and explicitly authoring presentation dependencies over them. A recipe may delay displayed damage until impact; it cannot create damage or turn an unknown source into a known caster.

No second gameplay event system, generic script interpreter, callback strings, reflective attribute paths, runtime subclass discovery, renderer-owned condition handlers or synthetic native events.

## 3. Current gaps and concrete changes

| Existing owner | Present behavior | Planned change |
|---|---|---|
| `choreography.py:300–1753` | Nested visitation plus many implicit timing joins | Keep fact binding; replace authored timing choices with typed policy evaluation and expose resolved milestones |
| `animation.py:1407` | Compiles gesture/delivery/application timing | Retain operators; expose their measured anchors/durations as inputs to shared scheduling |
| `choreography.py:1490–1625` | Formation/clearance dates propagate through causal ownership | Retain source matching; express commit dependencies in typed policy data |
| `choreography.py:2296` | Movement/interrupt/resume plus specialized profiles | Preserve movement semantics; expose leg/reaction markers and author overlap/hold policy |
| `FACT_PRESENTATION` at `choreography.py:1944` | Hand-maintained descriptive inventory | Replace inventory text with generated report of typed bindings and descriptions; do not make it a second dispatcher |
| `StudioSpellDraft`, `BodyClip`, media tracks | Detailed graphics without common semantic descriptions | Extend existing owners with references to semantic descriptions and timing policies |
| `condition_sampling.py:116` | Marker cycle literal 1800 ms | Put cycle duration/selection policy in existing condition presentation data; keep functional selection |
| `animation_draw.py` | Some legacy asset-name rules | Move crown/hair preservation and layer recoloring capabilities into existing rig/layer metadata |
| `body_action.py` | Three explicit strip-omission exceptions | Move accepted omission plus reason to recipe capability data; validate intentional omission |
| `animation_data.py` | Ordered bundle probing and resource-path policy | Emit a resolved, versioned presentation catalog from the same admitted inputs |
| `PlayerNode.combat_log` | Existing projected mechanical summaries/details | Reuse as optional fact-backed detail; do not parse prose to recover facts or print it twice |
| `DrawCommand` | Pygame surfaces/NumPy depths | Keep local; narrative never traverses pixel commands |

`recording_compat.py` remains the named legacy archive-upgrade boundary. Do not remove old archive support or move spell-specific compatibility into live rendering.

## 4. Proposed data model: extensions, not replacement recipes

All names below are proposed concrete names, not claims that the types already exist.

### 4.1 `PresentationDescription`

A record in `game/data/presentation/descriptions.json` supplies reusable meaning for an existing gesture, layer or operator:

- `id`: stable content key.
- `role`: closed enum `gesture | preparation | delivery | impact | manifestation | condition_marker | body_material | movement | transition | decorative`.
- `descriptionKey`: localized author-facing explanation, e.g. “kneels and strikes the ground”.
- `narration`: optional references for `start`, `contact`, `change`, `end` to constrained text templates.
- `detail`: `normal | detailed | inspect_only`.

Descriptions attach to existing `BodyClip`/casting selection, `StudioActorLayer`, media tracks, condition layers and spatial/construction phases. They do not create a second list of effects. A spell may override a phrase at its existing recipe owner; it must not copy a complete generic recipe merely to rename it.

Every admitted semantic layer resolves a role and description, including decorative ones. Shared descriptions may be inherited from the existing operator/clip/material owner; individual atlas parts, sparse pages and repeated particles are not separate prose records. Coverage checks the resolved description rather than requiring copied authoring on every instance. Decorative layers are inspectable but omitted from ordinary narrative. Floating feedback remains nonblocking as specified by `feedback.py`; presence in the layer list must not make it extend action completion. An Effect3 skeleton motif is described as a spectral image, never a summoned creature. A head icon is an indicator of a received condition, never a second condition application.

A rig-specific gesture description may override the modular gesture: a creature without arms must not “extend its hand” because the spell used that description on a human. Resolution: recipe override for an actually supported action context, then resolved rig clip description, then neutral action-family wording. No anatomical claims inferred from creature names.

### 4.2 `PresentationTimingPolicy`

Shared policies live in `game/data/presentation/timing.json`, referenced by existing cast/action/context/transition owners. Materialization resolves defaults and explicit overrides into the effective catalog. The runtime does not run a cascading search for policy values.

A policy contains a finite list of **milestone constraints**, not executable expressions:

```
MilestoneConstraint:
  target: typed local milestone
  inputs: non-empty list of typed milestone references
  combine: max
  offsetMs: finite number
```

References carry a closed owner selector, not arbitrary JSON paths:

- `self`: this bound action or transition.
- `application`: this explicit application/ResolutionRef.
- `parent_delivery`: actual bound delivering owner, if disclosed.
- `trigger`: actual reaction trigger.
- `causal_source`: exact observed-change/destruction source selected by native references.
- `owned_children`: a validated set of actual child tracks selected by family and ownership, not every descendant indiscriminately.

Milestones are finite: `start`, `prepare`, `release`, `contact`, `injury`, `hp_commit`, `condition_commit`, `formation_commit`, `clearance_commit`, `arrival`, `recovery_start`, `recovery_end`, `complete`. Family-specific measured markers already supported by body/media contexts are namespaced resource markers, not new mechanics.

Each milestone has exactly one writer: **operator-owned measured marker** or **policy-owned derived marker**. An operator-owned marker is immutable relative to its track origin; a policy cannot overwrite projectile contact independently of trajectory arrival. Policy constraints assign only derived markers or a track origin. Moving a track origin translates all its measured markers and sampled geometry/media together. A derived marker is exactly `max(expanded inputs) + offset`, subject to the causal safety checks below; multiple writers are rejected. Durations/time maps remain operator/authoring inputs, never silently stretched by an unrelated constraint. The existing explicit area-envelope fitting policy is a separately named operation.

`owned_children` expands to exact eligible bound milestone IDs in native source order then stable local track order. Selection is by declared family/ownership and blocking policy; decorative floating feedback is excluded. An empty collection contributes no maximum candidate. Every collection join must also have a required scalar baseline (for recovery, `self.recovery_end`), or a declared family-specific standalone marker. Thus no children means ordinary recovery, never time zero. Reject a policy whose expanded join has neither input nor baseline.

Causal safety is not editable content: HP, condition and world-state commits and factual narrative cannot precede their admitted outcome/contact anchor or any required disclosed source commit. A negative visual offset is allowed for anticipation only; it cannot move these commits earlier. Binding validates this after resolution. Anticipation contributes a required lead-in while placing the owning dependency region, before absolute dates are resolved. The region is the current presentation group including linked reactions; external already-placed causal anchors remain fixed. Lead-in is propagated through that placement equation, never applied as a post-resolution translation of a subtree. If it cannot coexist with a fixed external anchor under a supported relation, reject the policy. All tracks and state dates are resolved from the same resulting placement. A recipe that violates safety is rejected, not clamped into an unexplained different timeline.

Scalar selectors must resolve exactly one permitted milestone; zero matches follow the explicit missing-reference policy and multiple matches fail validation. `owned_children` is the only author-selectable collection selector. For an indivisible sensory/world update, the binder expands every exact retained observed-source reference into scalar `causal_source` inputs before policy validation. It includes all disclosed contributing causes, not one chosen source or all descendants. This expansion feeds the single commit equation and is mandatory, not an optional authored query. Distinguish unavailable/undisclosed evidence (no assertion and no invented track) from a missing authored marker on an otherwise admitted track (invalid catalog). An optional reference must declare `omit_input` or a specific permitted fallback marker; there is no implicit zero/default. A reference distinguishes `required` from an explicitly authored fallback marker. Missing undisclosed sources do not generate fake tracks. Family policies for standalone outcomes anchor to the admitted standalone entry; diagnostics record that choice. A malformed required reference in fully admitted content is an error, not zero milliseconds. Missing artwork must not suppress an admitted factual text result; missing optional prose must not block graphics or reduction.

Primitive operators produce base marker dates from clip frames, playback rates, travel distance and media time maps. Policy constraints arrange those markers and commits. A data-selected policy cannot alter source order, final state or outcome ownership.

Simultaneous effects reference one shared anchor; do not model equality using reciprocal edges. Dependencies must be acyclic after binding. Solve in stable topological order; equal-time state commits retain native version order. Offsets may place anticipation earlier relative to contact only through the lead-in placement rule above; there is no post-hoc group shift. No self-dependent contact/recovery rule. No iterative relaxation to hide cycles.

### 4.3 Keep phases and outcomes distinct

An authored “impact” image can occur on a blocked attack; damage still requires an actual DamageResult fact. A successful saving throw may still take damage, so “save success” cannot stand for “no damage”. A condition may fail while damage succeeds. Each description and visual response reads its own typed admitted outcome.

Existing finite selectors such as required save outcome, healing applied, condition applied and presence mode stay typed. Do not replace them with a general predicate language. New selectors require a real current use, a source field and tests.

### 4.4 `BoundPresentation` as an evolution of `BoundChoreography`

Do not create a parallel event archive. Evolve the existing bound result into a passive compiled presentation with:

- Existing root/before/after/gaps and family-specific bound tracks.
- Resolved milestone table and dependency provenance.
- References from tracks to description metadata.
- Small `PresentationMeaning` rows for meaningful observable occurrences.

`PresentationMeaning` holds `id`, source event/lineage IDs, optional ResolutionRef/application ID, semantic role, occurrence phase, resolved milestone ID, description/template reference and typed participant/outcome references. Each outcome reference identifies its exact projected node/event version as well as any ResolutionRef: one resolution may contain multiple saves, targets and results. Each participant/description also carries an evidence cut from existing source-version indexes. Resolve labels/images against that native evidence cut, separately from visual milliseconds; staging a later actor for binding cannot disclose its identity earlier. It references existing facts rather than copying HP, conditions and equipment into a new authoritative world.

Stable occurrence ID: group identity + source lineage + application identity when present + track local ID + phase + occurrence ordinal. Group identity is the primary native root lineage qualified by sequence generation and observer identity; linked reaction occurrences retain their own source lineage. Local track IDs are authored stable IDs; ordinal is assigned from canonical native source order then authored track order before filtering by output mode. Serialize this as a structured tuple with an unambiguous canonical encoding, not separator-concatenated names. No ID based on rounded time, target name or text. These rows are derived annotations on the existing bound result, not a separately persisted event stream. Repeated A/B/A targets must remain separate.

Every meaningful row must have evidence: permitted fact or admitted presentation track tied to a fact. There is no “free narrative event” authoring path.

Family-specific tracks remain appropriate: a portal and a volumetric cloud do not need identical payloads. Shared envelope/meaning fields support common traversal; raster-specific arrays remain inside graphical sampling/drawing.

## 5. Concrete scheduling examples

These examples describe the proposed schema and binding behavior; they are not production JSON yet.

### Forward projectile

```
body.release             <- measured resolved clip release
projectile.start         <- body.release
application.contact      <- projectile travel operator
application.hp_commit    <- max(application.contact, injury.commit_marker)
application.condition_commit <- application.contact + authored application offset
body.complete            <- max(body.recovery_end, owned finite response ends)
```

Narrative emits the visible gesture, witnessed release, and actual outcome at the same resolved markers. When source/gesture is undisclosed, it can still describe a witnessed arrival without naming the caster.

### Wall or obscurement

```
formation.start          <- cast.contact
formation_commit         <- formation.start + binding.formationCommitMs
sensory/world commit     <- max(own event marker, all exact observed-source commits)
removal.start            <- witnessed removal cause
clearance_commit         <- removal.start + binding.removalCommitMs
```

The narrative says the wall forms at its meaningful reveal and clears at clearance. It does not say movement is mechanically possible merely because an artwork fade began. Authoritative latest state remains independent.

### Reaction and movement

A movement leg gives a known pose and boundary markers. A disclosed reaction binds at the trigger marker, travel holds for its authored required interval, then the next permitted leg starts. Actual native step commitment and interruption outcomes remain facts. A hidden path is not reconstructed for either renderer.

### Area damage behind a breaking object

An AreaReachFact names prerequisite destruction lineages. Its presentation depends on those structures' clearance markers. Targets are actual received applications. A data-selected `fit_to_last_reach_plus_tail` envelope policy stretches existing media sampling through the final admitted reach; it does not create a new propagation simulation.

### Suppression, expiry and persistent effects

Condition/item/spatial lifetime owners remain separate. Suppression changes presentation availability without resetting the original application clock or fabricating a removal. Expiry comes from received state/edges. Text describes only an admitted transition, not every repeated sampled frame. Marker rotation does not become repeated condition narration.

## 6. Policy inventory to move out of implicit Python branches

For each row, binding remains a typed function; only the presentation choice/relationship becomes data.

| Policy | Authored owner | Existing implementation to migrate |
|---|---|---|
| Gesture release/recovery and hand marker | Existing rig/cast context | `animation.py`, `body_action.py` |
| Outcome feedback contact/injury/HP dates | Existing damage/healing/life contexts | `_bound_damage_timing`, `finish_conditions` |
| Reaction overlap/alignment | Existing interruption/reaction context | `join_reactions`, `presentation_group.py` consumer |
| Which children extend actor recovery | Shared family timing policy | `join_actor_subtrees` |
| Sequential versus contact-aligned child actions | Existing action timing policy | `visit` child dispatch |
| Area envelope follows delayed native reach | Area timing policy | Post-visit staged-area extension |
| Formation/removal/observed-state joins | Existing spatial/construction bindings | `formation_commits`, `spatial_causal_commits` |
| Flight/connector phase boundaries | Existing movement profile | `bind_motion`, `_bind_jump` |
| Portal emergence overlap | Existing portal/transfer context | Portal binding and body cue joins |
| Condition marker cycle/priority | Condition presentation settings | `select_condition_markers` |
| Multiple action-rate contributions | Existing movement/rate settings, explicit `max` policy | `animation_rates.py` |
| Native-rig gesture description | Existing rig clip metadata | New description binding beside current action resolution |

Outcome ownership resolution, camera transforms, curve evaluation, alpha equations and reducer ordering remain code algorithms. Putting those algorithms into a string expression evaluator would make the system less portable and less verifiable.

## 7. Procedural narrative design

### Input and output

Input: compiled presentation meanings/milestones + projected facts/state available at those milestones + resolved descriptions/templates. The text renderer must not import Pygame, load texture pixels or call the engine.

Output: ordered passive `NarrativeEntry` values:

- Stable occurrence ID and logical presentation date.
- Paragraph/group identity and optional cause reference.
- Plain structured spans with semantic styles.
- Optional detail payload from an already projected combat-log entry.
- Optional `ImageRef` with admitted resource identity, plain alt text and bounded display hint.

Images are supplementary. Disabling images must not change meanings, chronology or facts.

### Templates, not an LLM

Use a restricted token vocabulary: admitted actor/item/action labels, witnessed gesture/delivery description, actual outcome, damage/healing amount and type when permitted, condition label, permitted place description. Templates cannot execute expressions or access arbitrary object attributes. Normal grammar functions provide lists, counts and agreement.

Template variants are finite explicit cases: known/unknown source, target available/unavailable, hit/miss/blocked, result detail present/absent. They do not use a general-purpose templating interpreter. Start with one English catalog and Unicode-safe output; keep localization keys rather than embed prose into scheduling code. No random adjectives; replay must be stable.

### Modes

- **Narrative:** compact, grouped action/response prose; preserves meaningful chronology.
- **Detailed:** adds permitted mechanical numbers and existing log detail.
- **Inspect:** exposes gestures/layers, milestone dependencies and provenance; useful for authoring review rather than player prose.

A compact summary can aggregate only after the included outcomes have become available. Timed playback must not print an action's future outcome at its start. An instant completed replay can group already completed events. “Instant” is a display mode, not a different causal compiler.

### Disclosure and identity

Resolve labels at the occurrence's disclosed moment. Do not use the final actor table to name someone who was unidentified during the action. Preserve existing projection restrictions. If a fact or required label is absent, omit that claim or use neutral wording supported by the visible occurrence. Do not invent “you hear” because a visual source is missing; auditory wording requires auditory evidence.

Unidentified sources do not get identifying portraits. Remembered actors do not get fresh position descriptions. Geometry used only for graphics should not automatically appear as precise coordinates in prose.

### Combat log coexistence

`PlayerNode.combat_log` already contains projected text, structured detail and possible subentries. Narrative does not walk every nested subentry as an additional event, and does not parse compact/verbose strings to reconstruct mechanics. Use the existing log as expandable detail for the matched source occurrence. One native result must not be printed once from DamageResult and again from its log subtree. Expandable details are gated until every outcome they reveal reaches its permitted presentation marker; attach a complete aggregate log to the completion marker when per-result segmentation is unavailable. Apply the same evidence/date gate to Inspect mode, links, tooltips, alt text and images. No hidden future information is preloaded into an inspectable UI payload.

Do not rewrite `dnd/core/combat_log.py` in this change. If missing projected evidence prevents necessary narration, record a narrow projection-contract gap and add the smallest typed public field; do not query objective engine state.

### Replays and seeks

`entries_until(t)` is inclusive (`date <= t`) and a pure projection of the bound sequence. Forward streaming emits `(previous_t, t]` with the identical total ordering, using a before-zero initial cursor to include zero-date entries. Stable IDs and ordering are independent of mode, images, detail selection, rebinding and seek. Initial persistent conditions are described as initial scene state, not synthetic applications; a replay slice restores lifetime state without re-emitting historical application occurrences. Streaming output prints newly crossed stable IDs. Seeking backwards rebuilds the narrative view or begins a clearly marked replay segment; it must not mutate shared world state. Repeated frame sampling cannot duplicate text. Nested/overlapping roots retain stable ordering by marker date then native source order then local track order.

Optional text pacing may delay screen delivery for readability, but cannot reorder entries, publish future outcomes early or feed back into graphics/mechanics. Default follows common presentation time; instant transcript has no sleeps.

## 8. UI decision: pygame-ce for both views

User clarification: keep graphical and narrative interfaces in pygame-ce; no TypeScript/Pixi or terminal migration to deliver this work. Adopt this as the default, superseding the initial terminal investigation.

The repository pins `pygame-ce==2.5.8`. `pygame_gui` is not currently declared in `pyproject.toml`/`uv.lock`; remembering the package from earlier work does not establish that it is installed here.

**Proposed UI adapter: pygame_gui inside the existing pygame-ce application.** Its `UITextBox` supports formatted text, inline images and appended text. This makes it a reasonable fit for narrative paragraphs, colored names, condition icons and optional creature/item illustrations. Its supported markup is a limited UI format, not arbitrary browser HTML. See [official UITextBox documentation](https://pygame-gui.readthedocs.io/en/latest/pygame_gui.elements.html) and [text layout documentation](https://pygame-gui.readthedocs.io/en/latest/pygame_gui.core.text.html).

User requests latest stable pygame-ce. Checked PyPI release metadata on 2026-10-05: latest stable is **2.5.8**, already pinned by the repository; the documentation version heading is not proof of a published release. Recheck at implementation start; if a newer stable is available, update the exact pin and lockfile as an isolated dependency change after recording the old baseline, then validate it before migrating presentation policy. Do not select a development release by default. Source: [PyPI](https://pypi.org/project/pygame-ce/).

Before dependency adoption, verify a pinned compatible pygame_gui release against the selected stable pygame-ce: Unicode/font loading, resize, scroll, selection/copy, inline image layout, append performance and UI event consumption. Keep any pygame-ce upgrade explicit and separate from UI and schedule changes. If a widget limitation appears, first use normal image widgets beside paragraphs; do not create a custom rich-text engine. pygame-ce provides text rendering, and its current documentation recommends `pygame.font` for new code, including multiline/shaping support ([font guidance](https://pyga.me/docs/ref/freetype.html)). Font drawing alone does not supply all scrolling/layout behavior; use the UI adapter for those responsibilities.

### View behavior

- `Scene`, `Narrative`, and `Split` view modes share one encounter, one bound presentation and one playback cursor.
- Narrative mode hides the map rendering work; it does not stop the shared clock, reduction or action processing.
- Scrollable paragraphs, narrative/detailed/inspect choice, pause/resume, replay seek and export transcript.
- Autoscroll only while the reader is at the end; new output shows a count when reading earlier paragraphs.
- Optional images come from already admitted local content. No image-generation or new portraits scope. Missing images show alt text.
- Clicking a permitted actor/result reference may inspect already disclosed data; it does not query objective state or silently seek to future knowledge.
- Switching modes or resizing must not restart casts, recompute outcomes or duplicate narrative.
- UI input is consumed before world picking so scrolling/clicking prose cannot issue a game action.

`NarrativeEntry` remains plain data. Only the UI adapter converts spans to supported markup and resolves image resources to surfaces/files. The semantic compiler and transcript export have no display requirement. Thus pygame-ce can host both outputs without making the underlying text renderer depend on pixels.

Bound the displayed paragraph/image cache and provide history paging from retained narrative entries. Do not append an entire long campaign into a single reparsed text box or build a second unbounded copy of all rendered paragraphs. Benchmark a long transcript and resize before selecting chunk size; keep that as UI configuration, not gameplay/presentation semantics.

The text core still supports a simple UTF-8 transcript export for tests and sharing. A command such as `python -m game.text_replay PLAYER_SEQUENCE.json --mode narrative --output transcript.txt` is proposed, not available now. No terminal image adapter, xterm.js, Textual or WezTerm installation is part of this plan.

## 9. Module layout and dependency rules

Avoid relocating all `/game` files in one operation. Introduce only owners required by the new shared contract, while moving existing logic out of its previous owner in the same migration.

| Module | Responsibility | Allowed dependencies |
|---|---|---|
| Existing `player_facts.py` / `player_reduction.py` | Public facts and reduction | Existing passive engine types; no drawing or narrative |
| New `presentation_types.py` | Timing references, description references, meaning/entry passive values | Standard library + passive schema types only |
| Existing `animation_types.py` / `condition_types.py` | Extend current recipe owners | `presentation_types`; existing passive rig/media types |
| New `presentation_schedule.py` | Validate and resolve finite milestone dependencies | `presentation_types`, math/collections; no raster or engine execution |
| Existing `combat.py` / `choreography.py` | Bind actual facts to existing family operators and shared schedule | Facts, reduction, recipes, schedule; no narrative formatting |
| Existing `animation.py` and family binders | Durations, trajectories, body/media marker sampling | Passive values and geometry math |
| New `presentation_text.py` | Resolve meanings to structured narrative spans | Passive bound meanings, projected values, template catalog |
| New `text_replay.py` | Headless replay-to-transcript CLI | Text API, public sequence loading, catalog loading |
| New `narrative_view.py` | pygame_gui widgets, spans/images, bounded layout and scrolling | NarrativeEntry values, approved resource resolver, pygame-ce/pygame_gui |
| Existing `animation_draw.py`, media modules, `app.py` | Graphical sampling/composition | Shared bound output + raster libraries |
| Existing `export_schema.py` | Export new schema components with current contracts | Passive types only |

Do not put stateful renderer methods on PlayerActor or subclass spells for text. Exhaustive tagged unions plus ordinary functions are sufficient. Shared types never import consumers. New imports must remain a DAG; no late import workarounds.

### Headless dependency removal is real work

Today `combat.py` imports `AreaSolid` from a raster-related module, and imported metadata modules can bring loading concerns transitively. `device_art.py` and `portal_art.py` are already passive metadata/math modules without Pygame imports; keep them rather than splitting them solely because their names contain “art”. The text baseline must prove `presentation_text` and its required compiler path run with no Pygame initialization or pixel files. Move shared geometric records such as `AreaSolid` into a narrowly scoped passive `game/presentation_geometry.py` owner and import them from both consumers. Extract metadata from pixel loaders only where an actual dependency requires it.

Do not settle for setting SDL's dummy video driver: that still leaves a graphics dependency. Texture path existence/decoding validation belongs to graphical admission; semantic/catalog schema validation remains available to text. Metadata needed for timing, e.g. dimensions/FPS/anchors, must still be required and validated.

`AnimationData` currently includes paths and heterogeneous metadata. Compile meanings from an immutable metadata view built by the same loader; do not maintain an independently authored text catalog. The resolved export contains resource IDs and portable content-relative paths, not machine absolute paths or Python callables.

## 10. Authoring migration and complete coverage

Produce one generated coverage ledger with:

- Every effective spell/action identity and resolved rig context.
- Gesture description, active layers/roles and selected timing policy.
- Outcome selector source, semantic/narration coverage and intentional decorative omission.
- Referenced resources and legacy capability declarations.
- Every PlayerFact kind's handling: meaningful occurrence, state-only, causal-only or explicit unsupported diagnostic.

The union of actual public fact kinds, not the current informal `FACT_PRESENTATION` table, defines completeness. Source-only/canceled/partial observations count as supported cases. Unknown selector evidence is not false/miss/zero; it produces no asserted outcome. Do not claim coverage by catalog row count alone.

Migrate defaults offline into effective data. Preserve current selected gestures, palettes, sockets, scales, rates, accepted omissions and specific effect semantics. Do not re-author all spells for variety during architecture work. Existing `game/data/PRESENTATION_CONTRACT.md` has a stale paragraph saying formation milestones still need enabling; reconcile it with the accepted repair report rather than perpetuating contradictory status.

No normal runtime branch on a spell identity for timing/narrative. Exceptional artistic choices remain explicit values on the recipe that owns them. Shared operators may dispatch on finite media/motion/material kinds. Legacy recording upgrades stay separate.

## 11. Implementation sequence and deletion ledger

Each step ends with focused observable checks and independent anti-slop/ECS review; final delivery cannot stop after a demonstration step.

### Step 1 — lock source inventory and behavioral baseline

Files: existing audit inventories; add coverage exporter under `devtools/`; read existing HOW_TO_TEST guidance.

Capture effective catalog with selected creature rigs, current bound marker/state timings and representative four-camera frames from retained recordings. Record branch/content hashes and exact selection inputs. Do not rerun gameplay merely to change expected outcomes. Capture all fact families, then choose focused visual cases by shared operator.

Deliverable: baseline corpus + coverage ledger. Check latest stable pygame-ce against the current pin; if newer, make the separately traceable dependency update and compare image scaling/registration, alpha blending, font layout, input and recording output before proceeding. Record package/SDL versions; do not attribute dependency-induced differences to the scheduling refactor.

### Step 2 — passive contracts and authoring materialization

Files: `presentation_types.py`, current authored types, `authoring_conversion.py`, `animation_data.py`, existing export tool, new descriptions/timing/template data.

Add closed types and validators, materialize effective policy/description references, export them. Preserve original imported records through existing version conversion. Reject contradictory timing owners, missing mandatory descriptions and unsupported selectors at authoring load. Runtime has one materialized representation.

Delete/replace: no parallel default derivation scattered across text and graphics. Add a documented new local schema revision through the existing converter; keep legacy input admission only at that boundary.

### Step 3 — shared scheduling and current graphical compiler

Files: `presentation_schedule.py`, `animation.py`, `body_action.py`, `choreography.py`, movement/portal binders.

First expose current resolved milestones/descriptions with unchanged dates and run a minimal text consumer over them. This validates the shared seam before changing scheduling authority. Then move policy rows in section 6 in batches: cast/results; reactions/children; world formation/clearance; movement/portal; persistent transitions. Preserve family geometry algorithms. Return shared milestones/provenance and meanings while existing graphics samples the same resolved dates.

Delete/replace in each migrated family: old branch calculating the same authored date/overlap. Temporary old/new comparison is permitted only in tests/tools, never two production compilers behind a permanent flag. The existing native reducer is not replaced.

Acceptance: identical final public state; preserved observed dates and ordering; reviewed explicit differences only where a baseline bug is proven. No global “close enough” timing tolerance masking changed causality.

### Step 4 — descriptions and narrative for every supported family

Files: descriptions/templates data, `presentation_text.py`, shared binder meaning output, coverage exporter.

Fill current catalog descriptions by shared semantic roles and specific accepted overrides. Handle all fact kinds deliberately. Reuse projected mechanical details and deduplicate log ownership. Implement narrative/detailed/inspect modes and timed/instant sampling.

Delete/replace: hand-maintained descriptive `FACT_PRESENTATION` entries once generated inventory covers their use; no parallel text event traversal rebuilding ownership.

Acceptance: same sequence, different outputs; text and graphics share marker/identity provenance. Assert no incorrect body anatomy, invented hits, hidden identities or early outcome text.

### Step 5 — bounded composition metadata cleanup

Files: rig/layer capability data, `animation_draw.py`, `body_action.py`, condition settings.

Migrate Head5/Head8 hair policy, legacy recoloring capability names, accepted potion omissions and marker cycle settings into their existing metadata owners. Preserve output exactly. Leave named material algorithms in Python, inventory their parameters/equations for TS. Do not build a shader-graph language.

Delete/replace: active asset-name policy branches moved to metadata. Do not remove explicit support validation or archive upgrades.

### Step 6 — pygame-ce narrative view, images and transcript export

Files: `text_replay.py`, `narrative_view.py`, integration in `encounter_play.py` at already-bound presentation consumption, compatible pinned pygame_gui dependency/theme.

CLI consumes public replay. The existing encounter attaches narrative consumption after shared compilation; it must not issue a second action or privately project the world again. Implement Scene/Narrative/Split view switching and paragraph/image rendering. Plain export works without textures/display. Live mode emits crossed meanings once. Verify input routing, Unicode, copying, resizing, autoscroll and bounded long-history layout.

Deliverable: an actual pygame-ce narrative/split-view recording and plain transcript from existing gameplay, including optional images, matched to graphical occurrence IDs. A hand-authored story mockup does not constitute acceptance.

### Step 7 — complete review and removal checks

Run focused shared-contract tests, existing complete game suite and appropriate complete engine regression suite because client binding changes can expose broad integration failures. Follow the project's documented environment. Preserve/report failures; never weaken tests to declare success.

Review every migrated policy against deletion ledger, schema round trip, DAG, headless import, complete catalog coverage and disclosure tests. Independent anti-slop and anti-OOP/ECS reviews plus narrative/disclosure review. Close actionable findings before final implementation acceptance.

Final artifacts: source/data change trace, generated full coverage ledger, matched transcript/graphics examples linked by occurrence IDs, focused gallery of all changed operator families, test results, reviewer receipts and future TS operator specification. Existing large galleries remain archival evidence; no blanket rerender unless needed by changed shared paths.

## 12. Observable acceptance matrix

| Case | Required text/shared result | Graphic invariant |
|---|---|---|
| A/B/A missiles | Three distinct applications, no target-based collapse | Existing individual paths/contacts |
| Miss/block/save-half | Claims reflect independent actual outcomes | Correct existing response selection |
| Hidden caster, witnessed impact | No name/gesture/source portrait leak | No invented source body |
| Newly identified recipient within the same group | Earlier effect stays anonymous; later identification cannot alter earlier names/images/details | Preserved disclosure staging |
| Counterspell cancellation | Attempt/interruption; only completed child outcomes | Original cutoff/tail timing |
| Movement reaction | Narration follows step/interrupt/resume | Known pose held, no teleport to latest |
| Wall formation/removal | Text/state transition at owned marker | No early obscurement/clearance |
| Area through broken door | Later reach only after required clearance | Existing volume, no new tile mask |
| Prone to death | Death described without fictitious stand-up | Accepted prone/death transition |
| Item coating transfer | Same item/modifier identity before and after | Held/ground ownership preserved |
| Condition suppression/expiry | No duplicate application or expired reactivation | Current repaired behavior retained |
| Multiple head markers | One condition transition per actual edge | Other persistent VFX continue |
| Summon/portal | Disclosed arrival/departure only | Native rigs/materials/portal clipping retained |
| Repeated sampling/seek | Deterministic entries, no duplicate IDs | Absolute-time sampling preserved |
| No media pixels/display | Complete text output using metadata | Graphics reports asset admission separately |
| All active catalog entries | Valid typed roles/descriptions/policies | No silent generic fallback success |

Tests assert these boundaries, not exact private helper calls or an implementation-shaped hierarchy. Narrative prose snapshots may cover authored text, but semantic assertions must also check evidence IDs, chronology and permitted participants.

## 13. Risks, decisions and review gate

Chosen defaults for the proposed plan: deterministic English templates; narrative/detailed/inspect modes; pygame-ce Scene/Narrative/Split views with a pygame_gui adapter; optional existing images; plain transcript export; no browser or terminal UI migration; same bound presentation with typed meaning rows; existing specialized rendering operators retained; no gameplay expansion.

The largest technical risk is extracting timing without accidentally changing current causal precedence. The mitigation is family-by-family comparison and deletion of old production policy as each family migrates, then full-catalog validation. The largest semantic risk is describing future/hidden outcomes; event-time evidence and matched occurrence IDs are mandatory.

Image support is a presentation convenience and does not justify tying core text generation to pygame_gui, Pygame or an asset decoder. The output adapter deliberately uses pygame-ce; the meaning and text generation do not. A fluent transcript alone does not prove the architecture is data-driven: it must be generated from the same compiled dependencies consumed by graphics.

Independent final plan reviews: anti-OOP/ECS approved; causal/disclosure/narrative correctness approved; anti-slop approved subject to explicit all-observed-source expansion, which is now specified in section 4.2. Review corrections also established unique milestone writers, pre-placement anticipation, deterministic empty joins, source-version evidence cuts, gated detail surfaces, stable replay identities and inherited semantic descriptions. These approvals cover design, not an implemented renderer or visual acceptance. This document does not authorize implementation by itself.
