# Full presentation repair and shared graphics/text plan

**Superseded scope, October 5:** the user canceled narrative rendering. Its
implementation has been removed; retain the original combat log and completed
shared graphics/timing/catalog work. Text-related requirements below are archival,
not outstanding tasks.

2026-10-05 — rewritten from full-pipeline source coverage. Planning deliverable, not production implementation. Independent review disposition is recorded at the end. This replaces the [previous proposal](audits/rendering-readiness-20261005/previous-provisional-plan.md); its architectural direction survives, but its spell-weighted denominator and premature schema freeze do not.

## 1. Goal and scope

One observer-permitted sequence and effective authored catalog must drive both graphics and procedural narrative. Keep pygame-ce for both adapters, with headless text export. Future TypeScript/Pixi portability is a design constraint, not a client rewrite in this task.

Coverage means **all current presentation**: actions, attacks, movement, reactions, combat results, conditions, items, summons, world objects, spatial-handler outputs, tiles, surfaces/deposits, observation changes, initial/idle state and composition. The [full coverage report](audits/FULL_PRESENTATION_COVERAGE_2026-10-05.md) and [branch readiness audit](audits/RENDERING_SCHEMA_READINESS_2026-10-05.md) are normative inputs. Recipe selection, source review, recorded execution, timing checks, disclosure checks and pixel review are different evidence levels.

No new gameplay rules, spells, surface chemistry, art, AI redesign, OOP entity behavior, networking rewrite or generic executable JSON language. Backend handlers remain owners of rules. Any missing semantic field must be justified by an actual presentation need and added at the permitted projection boundary, never recovered from live engine state by the renderer.

## 2. Work before schema freeze

The inventory now enumerates all AnimationData fields, top-level game modules, selected content, public/bound records and declared review cases. This is the starting denominator, not acceptance.

For each effective behavioral variant, complete a ledger row:

`input channel + variant → actual selected owner/operator → exact evidence/instance identity → measured clocks and dependencies → proposed passive representation → narrative disposition → case/perspective → verification status`.

Every row must have a concrete encoding using real received/bound values before broad migration. Map shared operators once, but separately verify content parameters and semantic assignments. Add rows for branches exposed during review; do not add escape-hatch fields or arbitrary callbacks.

Specific prerequisite cases include repeated A/B/A missiles; creature/object/off-hand attacks; hidden-source damage; declaration-time weapon changes; body-only actions; effective-handler attribution; movement holds with nested displacement; first and maintained Shield blocks; field motion with independent old/new sight; atomic residue updates; partial construction destruction; initial and reacquired effects; canceled parents with surviving children. The coverage report supplies the full family list.

A family with a missing fixture is recorded as an evidence task, not assumed correct. Use retained recordings where current; capture new cases only for actual missing distinctions. No production schema is frozen until the mappings cover current behavior and both reviewers accept those concrete mappings.

## 3. Data ownership and module boundaries

| Responsibility | Existing owner / bounded change |
|---|---|
| Public evidence | `player_facts.py`, projected versions, `player_projection.py`; keep existing identities, observations and permissions |
| State reduction | `player_reduction.py`; one reducer, reused by graphics and text |
| Native grouping | `presentation_group.py`; retain native roots/order; presentation association never becomes invented parentage |
| Authoring | Existing `animation_types.py`, condition/world types and data loaders; extend typed fields in their current families |
| Bound relations | Existing BoundChoreography, MotionTimeline and family cue records; add typed milestone/evidence annotations to their owners |
| Timing evaluation | Small pure `presentation_schedule.py` if shared equations justify extraction; family binders supply measured anchors, not duplicate tracks |
| Passive shared references | `presentation_types.py` for evidence/milestone/semantic records only; no registry, renderer objects or callbacks |
| Retained phases | Existing condition/item/concentration/spatial/construction/deposit lifetime maps; no universal second lifetime store |
| Sampling | Existing attack/body/motion/condition/world/material/geometry functions; preserve specialized mathematics |
| Narrative | `presentation_text.py`: finite template selection and formatting over shared semantic records; no state reduction or gameplay imports |
| Headless export | `text_replay.py`: public sequence decoding and shared binding; no Pygame initialization or raster loading |
| Pygame UI | `narrative_view.py`: layout/scrolling/images only; Scene/Narrative/Split share encounter and cursor |
| Graphics adapter | Existing draw/media/resource modules; surfaces, NumPy depth arrays and caches remain local |

Headless boundary repair: `combat.py` currently imports `AreaSolid` through `area_media.py`, pulling Pygame/NumPy into shared binding. Move that passive geometry record to an existing suitable passive geometry owner (or the shared passive types module if necessary), update both consumers, and remove the graphics import from combat. Verify imports in a fresh process that rejects Pygame imports; SDL dummy mode is not a headless dependency test.

Dependency direction: passive projected values and authored types → binding/scheduling and pure samplers → text/graphics adapters → application composition. No late imports, reflection-based dispatch, live ECS queries from presentation or duplicate spell/action registry. Review actual imports when implementing; a diagram is not proof of a DAG.

## 4. Proposed common contract, constrained by existing families

Use passive records with a finite tagged union of family payloads. Shared fields identify evidence, instance owner, application, selected recipe and milestones. Family fields retain geometry, attachment, material or lifecycle data. Do not force them into an untyped property bag.

**Evidence reference:** exact node/version and resolution/application where present; observation/world-update evidence for state-only input. Known names and details are taken at the permitted evidence cut, not the final snapshot. Content attribution is a distinct supported input. A binder returning no graphical cue does not remove factual meaning.

**Milestone reference:** exact bound owner plus named measured or derived anchor. A field has one producer. Measured source frames/sockets define release/contact/body availability; explicit dependencies can delay the whole relevant track, not independently move its contact and disconnect geometry. Mechanical commitment, body recovery, decorative end and persistent retirement are different anchors. State commits retain causal floors and same-time native version ordering. Anticipatory visual lead-in may shift the containing presentation start; it cannot move an HP/world commit before its permitted cause. Resolve dependencies in a stable topological order after cycle validation.

**Dependency expansion:** binder expands owned children, AreaReach prerequisite destruction lineages/previous reach, sensory observed changes and reaction trigger references into actual scalar references. Never relabel these as children. Empty/disclosed/unknown references are handled explicitly; missing required measured data is an authoring error or existing disclosed limitation, never a guessed cause. Cross-head references resolve against existing retained owners.

**Sampling clock:** elapsed local age, retained original age, frozen sample age and moving mask/release age remain separate where needed. Loops, complementary crossfade weights, trajectories and historical trails are sampled functions, not infinitely expanded scheduler nodes. Optional tails cannot delay unrelated action completion.

**Semantic occurrence:** witnessed attempt/release/contact/result/application/consumption/removal/return etc., with explicit template and permitted participants. Identity follows the retained native edge/application and phase, not just the enclosing group. Multiple encounters with the same edge deduplicate; repeated actual applications do not. State inspection is a separate record, not a fabricated occurrence.

**Description metadata:** authored motion/effect/layer meanings describe what the selected visual actually does. Templates consume resolved public values; no LLM-generated runtime text and no inference from emitted pixels. Pure technical operator names are not user-facing prose.

## 5. Family-specific contracts that the common fields must not erase

- Attacks select highest-precedence profile from declaration-time source/slot/item/rig/outcome. Keep target contact typed as creature/object; same native attack route, distinct response payload. Absent fixed-rig slots are explicit capability limitations.
- Body actions include aliases, effective-handler attribution and condition responses. Body end, child join, hidden-slot restoration and recovery are separate.
- Equipment can commit stance at a frame and membership/AC at completion. Unchanged appearance may have no gesture but still meaningful state.
- Movement uses received steps/mode/connector. Hidden intervals are dwell/observation boundaries, not interpolated secret paths. Reactions can own displacement; do not render that displacement twice. Preserve preflight/landing distinctions and native flight/window profiles.
- Damage requests and applied packets remain separate. Save success does not imply zero damage. Blocked healing, unknown attacker and zero result retain factual meaning. Prone-to-death preserves accepted pose handling.
- Maintained Shield contact does not replay initial casting. Initial application, suppression, expiration, consumption, lost sight and quiet reacquisition are distinct.
- Condition, item effect, concentration slot, spatial owner, construction section/parent and deposit-source identities retain their own clocks. Marker cycling is display policy only.
- World transition fields retain projectile/dust/collapse/membrane payloads. Repeated activation is not deduplicated merely because settled state is unchanged.
- Tile facets and connectors support state inspection even without VFX. Tile condition labels do not identify rules or causes. Atomic WorldUpdates remain atomic; reveal timing cannot split them into invented per-cell mechanics.
- Native deposits retain fragment geometry and source; never reconstruct undisclosed full pools. Remembered ground and currently visible airborne material have separate disclosure policy.
- Field geometry can move while permission remains independently sampled from old/new disclosures. No translated visibility mask. Partial retirement needs witnessed removal.
- Construction section break, whole-owner retirement and suppression differ. Portal endpoints have independent evidence; seeing one does not reveal the other.
- Specialist geometry/material operators remain functional code. Formation, clearance and contact parameters can be authored; reusable math stays code. Final XYZ/depth/support cuts and crossfade blending remain explicit adapter contracts.

## 6. Concrete repair lanes and implementation order

Each lane requires comparison evidence and independent review before carrying it into later work. These are implementation gates, not claims the work is done.

| Step | Change and old ownership removed | Verification / gate |
|---|---|---|
| A. Complete mappings | Extend study ledgers across all families, contexts, world/public fields and actual admissions. Resolve aliases such as reaction Counterspell. No production migration | Every current branch has concrete representation and evidence disposition; reviewers approve schema fit |
| B. Evidence instrumentation | Extend existing review trace output to include omitted bound families, exact source/application and state-commit provenance. Keep runtime facts unchanged | Repeated applications, child-only outcomes and boundary times inspectable; old traces explicitly versioned |
| C. Authoritative material selection | Fix attack/cast layer color-treatment mismatch in loader/materialization; one resolved swap/source treatment used by loading, cache identity and future export | Palette swap at actual pixels, multiple palettes, source-sheet paths, fixed/modular rigs; preserve accepted art except explicit correction |
| D. Shared timing annotations | Annotate existing bound owners; extract repeated scheduling policy only where equivalent. Remove corresponding duplicated binder equations, not family samplers | Before/at/after markers, no early HP/world visibility change, unchanged final state and accepted geometry |
| E. Actions/attacks/combat | Apply contract to profiles, actions, equipment, damage/heal/save/life, attribution and reaction outcomes | All nonspell matrix distinctions, including missing body and unknown source |
| F. Movement/reactions | Apply contract to visible legs, dwell, connectors, nested reactions, forced transfer, portals and absence | No duplicate movement, no hidden path, original native order, proper interrupted sampling |
| G. Persistent/world/tile | Connect existing lifetime milestones, state-description input and world commits; remove repeated lifetime inference from consumers | Suppression/expiry/reacquisition, atomic surface update, partial destruction, native deposits and mechanism activation |
| H. Spell catalog | Adapt all effective spell recipes and semantic assignments using established contracts, preserving specialized media operators | Full identity ledger and meaningful geometry/rig/permission combinations; no generic per-spell fallback |
| I. Text + Pygame narrative | Add finite templates and state inspection over same bound evidence; headless transcript plus Scene/Narrative/Split | Deterministic seek/forward output, no hidden information, text works without textures/display |
| J. Final consolidation | Remove superseded selection/timing paths, update authoring documentation/export schema, pin actual dependencies | Complete suite, import-DAG/type/schema checks, visual issue guide, independent final reviews |

Step A is a hard prerequisite to freezing the schema. B gathers evidence, not a license to mutate presentation. C–H proceed only after the concrete family mappings have been accepted; order can group shared dependencies, but no half-migrated lane is declared complete. Runtime implementation requires user acceptance of this rewritten plan.

## 7. Text adapter behavior

State descriptions answer what is currently known: observed terrain/condition labels, visible equipment, known HP/lifecycle, doors and fields. Occurrences answer what was witnessed: a disclosed attack, damage, entering a portal or a removed effect. Reacquiring someone with changed HP is not evidence to narrate the hidden attack.

Narrative includes event outcome independent of optional animation: resisted shove, blocked healing, unsuccessful reaction, or action without a known body. It may describe authored gesture/effect meaning only when that component is actually selected and permitted. No particle-by-particle prose.

Use the existing pygame-ce application. Current pin 2.5.8 was verified as stable during the preceding study; recheck official release metadata at implementation, upgrade only if newer stable and run relevant regressions. Do not bump to development docs' version. Evaluate pygame_gui UITextBox for formatted text and inline images at the adapter boundary; it must not become a core dependency for headless binding/text.

One shared presentation cursor drives graphics and narrative. Advancing yields occurrences in `(previous, current]`; seeking rebuilds visible transcript without duplicate side effects. Initial known state is displayed explicitly. Textual detail/images cannot expose information earlier than graphics' shared evidence cut. Event-time participant references remain stable after later changes.

## 8. Validation contract

Read HOW_TO_TEST.MD before implementing tests. Verify externally visible behavior, not incidental private function structure.

- Validate authored schedule references before playback: reject cycles, missing required references and multiple producers; define deterministic tie ordering from retained native order and explicit stable track identity. Optional unavailable evidence cannot become a guessed required reference.
- Export only portable values and logical resource IDs, never absolute local paths, surfaces, arrays or callbacks. Validate public/schema round trips and stable enum/union discriminators. Test numeric units and deterministic ordering; no TypeScript implementation is needed for this contract check.
- Saved public inputs drive both renderers. Preserve native order, exact resolution ownership, resulting state and permission differences.
- Compare transition boundaries immediately before/at/after dates, not only settled state or FPS samples.
- Four camera views test geometry; paired observer inputs test disclosure. Neither substitutes for the other.
- Include all non-fact input channels and state-only families. Every selected item has mapping status; `binding_selected` cannot mean visual approval.
- Reuse family verification where implementation and parameters warrant it; inspect every content semantic assignment. Required distinct combinations include body size/rig, camera/elevation, target kind, outcome, visibility, ownership and interruption.
- Historical unsupported art stays explicit. No new art or rule expansion disguised as coverage repair.
- Full relevant engine/game suites run at final implementation acceptance; report actual failures and causes, no blanket dismissal as unrelated. No test run is claimed for this planning-only pass.
- Anti-slop review checks no duplicate pipelines, registries, inferred fallback semantics or unnecessary mechanisms. Anti-OOP/ECS review checks data ownership, DAG imports, instance identity, observer safety and absence of client-side rule execution.

## 9. Review disposition

Initial independent source reviews required changes: [anti-slop](audits/rendering-readiness-20261005/antislop-full-review.md), [ECS](audits/rendering-readiness-20261005/ecs-full-review.md). This rewrite incorporates their nonspell, tile, world, attribution, material and lifetime requirements. Both independent second-pass reviews now **approve the rewritten work plan and source-coverage scope**. Their receipts are appended to those reports. Follow-up corrections incorporated explicit headless dependency extraction, portable export validation, schedule cycle/reference/producer checks, stable ordering and causal commit floors.

Even an approved implementation plan is not certification of current pixels or permission to skip Step A's concrete schema-fit gate. The purpose is to prevent a succession of migrations whose schema changes whenever the next real behavior is encountered.

## 10. Implementation resolution of timing validation

The concrete producer work established that the proposed common graph must be
**passive evidence of the existing binders**, not a second scheduler. Local
producer ordering, reference/value agreement, equations and clock offsets are
validated. Measured external anchors remain explicit rather than being guessed
or linked through an invented global node registry. Retained snapshots identify
their native admission because their local tables may restart on reacquisition.

This resolves the provisional global-topological wording in sections 4 and 8:
there is no separately executable global schedule and no claim of exhaustive
external-anchor graph validation. The existing family binders keep their causal
ordering and functional mathematics. Anti-slop and ECS source reviews support
this narrower, nonduplicating representation. Runtime acceptance is recorded in
[the implementation report](audits/SHARED_PRESENTATION_IMPLEMENTATION_2026-10-05.md),
separately from the original planning coverage.
