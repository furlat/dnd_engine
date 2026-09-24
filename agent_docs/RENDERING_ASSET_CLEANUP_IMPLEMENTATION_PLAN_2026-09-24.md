# Rendering and asset cleanup — implementation plan, 24 September 2026

Status: implementation plan approved after two independent review rounds, plus
asset/setup review and revalidation. Review records are linked at the end. This
document does not claim the proposed code or packages are built.

The rendering cleanup is the primary work. Forward private-art separation and
production packing are a parallel delivery track. Historical Git scrubbing is
secondary and outside the critical path; do not turn it into another prerequisite
for making the game work. New spells, art direction, multi-Z, new game rules and
the queued sensory-spell handoff are outside this unit.

## 1. Outcome and evidence

At completion, the current authored content has one documented ownership model:

```text
complete serialized subjective lineages
  -> retained player state and historical presentation
  -> existing authored recipes + rig/object/media data
  -> shared sampling and named drawing semantics
  -> registered geometry and composition
  -> Pygame pixels
```

The engine continues to own damage, targeting, movement, conditions, propagation,
destruction and sensory disclosure. Initial actors and world state arrive through
events too. Event intake can advance while historical playback retains its own
speed. The renderer consumes complete lineages and their recorded relationships;
there is no second gameplay implementation in its animation code.

Portable authoring consists of JSON values, stable content/resource identities,
units, timelines, attachments and state selectors. The future TS client reuses
those records and the specified shared algorithms. It does not import Python
objects or Pygame surfaces. This work does not implement that future client.

The plan follows these completed studies, rather than reopening their scope:

- [Rendering architecture review](RENDERING_ARCHITECTURE_REVIEW_2026-09-23.md),
  including R1–R12 and the classified test failures.
- [Complete asset inventory](PRODUCTION_ASSET_INVENTORY_2026-09-24.md), including
  every installed file, actual frame/state consumers, size and packing choices.
- Geometry, event and authoring specialist reports linked from those documents.
- Existing `game/data/PRESENTATION_CONTRACT.md` and `HOW_TO_TEST.MD`.

Baseline is `508f5f8d38cc2e6982b73c44ee7f911b794c042a`, on the current recovery
branch. Preserve current uncommitted work; do not reset the branch to establish
that reference. Baseline selected game results are 2,052 passed, 206 failed,
7 setup errors and 15 deselected. Whole-game typing is clean. The failures are
classified evidence, not an accepted permanent test baseline.

### Completion means

1. Fresh public recordings and the actual retained legacy fixtures replay with
   the existing passive/event-only contract.
2. Media ingestion cannot silently rewrite authored behavior or replace a
   selected current delivery with a historical converter's output.
3. Existing storage, composition, attachment and coordinate semantics are
   explicit and typed at their owning boundaries.
4. Gameplay-relevant drawing semantics no longer hide in diagnostic tuple slots.
5. Current supported finite tracks participate in the same completion rules;
   dormant unsupported combinations are identified honestly.
6. Approved visual behavior survives mechanical migrations. The independently
   reproduced wall-cap defect is corrected as a separately reviewed visual change.
7. Initialized coverage accounts for the newer object, portal, spatial and
   material families, with no runtime art-tree scan.
8. The private installation path works with preserved local art; forward Git
   tracking separates public code/authoring from private media. Remote publication
   is a separate completion item if credentials or storage are unavailable.
9. Selected production media can be packaged without changing resource meaning,
   source sample selection, timing or registration. Full originals remain archived.

## 2. Non-negotiable preservation contracts

| Boundary | Preserve | Do not replace it with |
| --- | --- | --- |
| Subjectivity | Existing disclosed facts, causal identity, hidden observations and independent face memory | Fresh native queries, guessed recipients or changed visibility policy |
| Timeline | Full causal lineages; linked reaction roots; independent clocks; recorded initialization | Per-event animations, a new scheduler, or accelerated playback to catch intake |
| Movement/body | Walk OA interruption, preflight jump reactions, one jump cycle, subcell stopped/dead pose, sleep fall/wake, equipment commit | New timing rules, tile-center snapping, or a generic recovery workaround |
| Spell placement | Approved Fire Bolt sockets and offsets, direction correction, carrier/impact distinction, target pose | Blanket zero offsets, spell-by-spell retuning, or new keypoint infrastructure |
| Environment | Event-driven same-object destruction, clearance markers, independent liquid release markers, current trap/portal semantics | Deleting the body at damage time or tying all children to one break frame |
| Media | Logical canvas, crop/pivot, source indices, camera/facing selection, material order and numeric coordinates | Full-canvas allocations, temporal thinning, unregistered resizing or filtering numeric data |
| Authoring | Original NeuroStudio reference reader/data plus explicit local extensions | Another recipe DSL, a universal object record, or one Python executor per spell |
| Performance | Lazy decoding, existing bounded source cache, explicit offline work | Startup hashes, directory walks, provenance checks, mandatory source validation or new cache layers without measurements |

Fixed numerical registration is valid authoring. The cleanup changes ownership
and interpretation, not the user's approved pictures merely because their values
look inelegant. Shared algorithms remain code; tunable art choices belong to the
existing material/rig/recipe records.

## 3. Execution units and dependencies

Each row is a reviewable change boundary, not a demand to stop and ask the user
after every checkpoint. Once its checks pass, continue to the next authorized
unit. A real change to gameplay/disclosure or an unavoidable visual compromise
requires an explicit decision; routine type names and mechanical migrations do
not. This document itself authorizes planning, not execution of its future steps.

| Unit | Deliverable | Prerequisite | Intended commit boundary |
| --- | --- | --- | --- |
| U0 | Preserve reference inputs, validation map and cheap capture metadata | Existing audit | Small tooling change only if needed |
| U1a | Current public JSON replay repair | U0 | Codec fix + behavioral regressions |
| U1b | Actual legacy native recording admission | U1a | Separate compatibility fix + original fixtures |
| U2 | Authored behavior and selected media ownership | U0 | Importer/selection corrections + preservation tests |
| U3 | Named draw semantics and typed catalog boundaries | U1a | One coherent passive-data migration |
| U4 | Explicit composition and source registration | U2, U3 | Behavior-preserving metadata/executor migration |
| U5 | Finite completion and consumer capability checks | U2; coordinate with U3/U4 shared files | Bounded compiler/authoring fix |
| U6 | Correct wall-cap visual registration | U4 | Intentional visual correction, separate from migration |
| U7 | Coverage, portability and touched live/review parity | U3–U5 | Reporting/contracts; bounded admission extraction if touched |
| A1 | Lean private installation and forward untracking | Existing preserved archive | Separate setup/index change; can precede renderer work |
| A2 | Selected runtime release and payload aliases | U2, A1 | Packaging selection + resource remap |
| A3 | Atlas and indexed packet packing | U4, A2 | Reader/metadata first, then generated private media |
| A4 | Proven small bakes; measured compression decision | A3 | Optional, independently justified changes |
| U8 | Integrated acceptance and exact handoff | Required U/A units | Results/docs and any necessary integration fixes |

Renderer and asset work may run in parallel when their files do not overlap.
Give one owner `animation_types.py` / `animation_data.py` while their shared
contracts change. The packer consumes the finalized registration/storage boundary;
it must not race a second agent rewriting the same bindings. Reviewers can work
independently on a stable diff throughout.

## 4. U0 — establish working references without building a framework

**Owners:** existing review captures and `.runtime` inputs,
`devtools/animation_review/cli.py:source_identity`, existing tests.

1. Record the current commit and changed production paths once. Use targeted Git
   queries; the previous review already measured a multi-minute full `git status`
   walk over the asset tree.
2. Make review provenance cheap: branch/commit are enough by default. If a dirty
   state is not checked, record unknown/omitted rather than false. Keep a full
   working-tree check explicit, never mandatory for clip generation.
3. Select existing saved inputs for the acceptance matrix in section 15. Preserve
   their bytes and approved output references. Do not rerun native mechanics to
   manufacture a supposedly identical baseline.
4. Record the known failure groups from section 16. Run only a narrow reproducer
   when needed for the current unit; do not repeat the 32-minute selected suite
   just to rediscover the same decoder failure.
5. For a case blocked by the current decoder, establish the byte-boundary repair
   first and document that no pre-fix cold-render comparison was possible. Existing
   reviewed videos still witness intended appearance; they are not proof that the
   broken decoder worked.

**Done when:** reference inputs are available, capture metadata cannot trigger an
unrequested whole-tree audit, and each later unit has a named validation case.
No new golden-video service, screenshot registry, hashing protocol or pixel-test
framework is part of U0.

## 5. U1 — restore the existing event/replay boundary

### U1a. Current public destruction facts

**Owners:** `game/player_facts.py:PlayerFact`,
`game/recording_compat.py:upgrade_player_fact`,
`game/player_reduction.py:decode_player_sequence`.

1. Reproduce fresh real prop destruction through native scenario generation,
   public projection, encode, reset and decode. The failure is strict nested
   placement tuples reaching Python validation after the union-wide before-hook.
2. Move/narrow the historical spell-field adaptation to its actual spell or
   intake boundary. Preserve JSON-mode validation for unrelated fact branches.
   Do not loosen placement, broadly coerce every tuple, or recreate objects from
   current native registries.
3. Retain explicit modern propagation fields unchanged. Verify the narrowly
   supported old propagation fallback against an actual retained example; do
   not enlarge the spell-name fallback into rendering policy.
4. Exercise a representative neighboring strict fact through the same public
   sequence boundary, not just direct `ObjectDestroyedFact` parsing.
5. Run the affected destruction/liquid/device tests to reach their previously
   blocked assertions. A fixed codec does not by itself prove every downstream
   placement, privacy or timing assertion passes.

**Observable gate:** the same serialized facts replay after resetting native
registries; resulting object identity, placement, remnants, damage and spill
state remain recorded values. No EventQueue/BaseObject/DiceRoll registrations
or native mechanic calls arise during passive playback.

### U1b. Older native recordings

**Owners:** `game/event_record.py:decode_event`, named compatibility at intake,
`game/replay.py:RecordedSequence`, cancellation projection where relevant.

1. Keep the original retained door/device/Web fixture bytes. Inspect their
   generation and absent fields; do not replace them with today's events.
2. Admit only the demonstrated additive-field gap through the existing passive
   decoder, on the exact affected families and completed/noncanceled rows.
   Payment, harmfulness and targeting details absent from an archive are not
   evidence of historical false/default outcomes. If model defaults are needed
   solely for admission, they must not generate unsupported public facts.
3. The actual failing fixtures contain completed, noncanceled Action/Spell rows.
   Restore their completed replay without inventing support for old canceled
   actions. Scope any missing-value handling to recorded admission/projection;
   native live action definitions and cost rules stay unchanged.
4. Preserve what is known: ancestry, amounts, condition ownership, destruction,
   fixture identities and sensory grants. If a later actual archive needs an
   unavailable presentation distinction, report that specific limitation rather
   than consulting a live object or silently guessing.

The first implementation should not require a new unknown-value model for an
unobserved canceled archive case. Missing-payment legacy cancellations remain
explicitly unsupported unless a real retained case requires more. Check existing
`test_presentation_boundary.py` live/captured encoding and decode/re-encode
contracts before choosing an omission-preservation mechanism. Pydantic field
presence is not automatically historical provenance: fresh live events also
leave authoritative defaults unset. Resolve this narrow codec decision with a
small probe; do not introduce a general event-presence subsystem.

**Native round-trip gate:** decoding, re-encoding and decoding the actual old
recording must not promote absent payment/targeting additions into supposedly
recorded receipts. Completed public output alone would miss this, because the
current encoder emits model defaults. Preserve explicit current true/false values
and the existing live/captured encoding contract as well. A narrow omission-aware
codec choice is allowed; a new generic archive metadata model is not prescribed.

**Tests:** existing `test_passive_event_replay.py`, `test_recorded_history.py`,
`test_prop_destruction.py`, `test_device_destruction.py`, `test_liquid_barrel_replay.py`
and the retained fixture consumers. Use the narrow public caller for new cases.
Do not demand every native event family acquire a new archive representation.

## 6. U2 — one owner for authored behavior and selected deliveries

**Owners:** selected `spell-studio-drafts.json`, resource/storage `bindings.json`,
`projectile-assets.json`, existing media importers and their tests.

1. Use the completed inventory to list which converter owns each selected media
   delivery. Selection already exists in bindings; prefer those records and an
   explicit offline command list over introducing a second runtime registry.
2. In `devtools/import_aoe_surfaces.py`, remove writes that recreate Thunderwave
   tracks, Color Spray placement/scale or Sleep/Ice Knife facing choices. Preserve
   their current effective values in the selected authored records.
3. Separate source-derived registration updates from behavior. Pixel dimensions,
   source camera rows, frame addresses, measured emission registration and coordinate
   bounds may change when accepting an explicit new delivery. Cast timing,
   attachments, physical size and track choices remain authored.
4. Prevent ordinary rebuild/install paths from running superseded Fireball or
   Ice Knife converters over selected XYZ storage. Historical adapters may remain
   callable for explicit historical conversion; they must not claim current
   output identities as an incidental side effect.
5. Apply the same boundary to the other selected importers actually found to
   write behavior or overlapping storage. This is a scoped sweep of the known
   23 importers, not a new converter framework or rewriting every tool.
6. Restore practical authoring: editing one selected recipe must be sufficient;
   a later import cannot silently undo it or inherit a different spell's settings.

**Validation:** in a temporary metadata tree, deliberately change authored timing,
scale and placement, invoke the relevant real importer with a tiny delivered
fixture, and assert the public output documents retain those values while media
registration updates. Existing `test_spell_media_imports.py` expects old Fireball
layers in one path; revise that test around intentional selected-delivery ownership,
not around preserving the obsolete converter's output. Repeating the selected
conversion must not progressively mutate authoring. No runtime file hashing.

**Done when:** selected deliveries can be rebuilt without reconstructing recipes,
and private installation copies produced files/metadata without running importers.

## 7. U3 — typed passive values at the existing boundaries

### Drawing semantics

**Owners:** `game/draw_commands.py`, producers in `animation_draw.py`,
`choreography_draw.py`, environment/device/portal drawing, consumers in `app.py`
and `portal_draw.py`.

1. Enumerate current semantic reads of `DrawCommand.evidence`, including device
   routing, contact coordinates, deposit visibility and portal body identity.
2. Add named passive fields for the actual required role, owner/contact and
   optional device pose/frame. Keep existing surface, destination, blend,
   area/depth/volume and composite-group fields. Choose one minimal value shape
   for those existing cases; do not create renderer subclasses.
3. Migrate producers and consumers together. Diagnostics may be derived from
   named values or remain purely diagnostic. They must not become a second source
   of semantic truth. Remove positional reads and their broad casts.
4. Preserve composite grouping: smoke/fire siblings retain ordered blending
   within common external depth partitions. New role typing must not sort them
   independently and reintroduce flicker.

### Object and condition catalogs

**Owners:** `device_art.py`, `portal_art.py`, `environment_art.py`,
`condition_media.py`, `world_animation.py`; existing initialization in
`animation_data.py`; the active world catalog at `assets.py:catalog_from_documents`
and `asset_types.py:image_resources`.

1. Add constrained source records to the existing owning modules for bank/state
   selectors, frame markers, camera/pose arrays, muzzle/aperture points, and
   condition media. Give numeric fields their current units and tuple dimensions.
2. Decode once at the current JSON boundary, then produce the same passive runtime
   values. Do not validate the art corpus or instantiate game objects.
3. Keep import direction acyclic. `animation_types.py` already depends on several
   catalog modules; those modules must not import it back. Put local source models
   with their owners. Move a genuinely shared existing base to a lower dependency
   module only if necessary; do not add a general model layer for its own sake.
4. Preserve aliases and explicit legacy selector branches. Unsupported authored
   combinations should fail or be reported at load/bind where they become known,
   never silently substitute gameplay behavior.
5. Include the active general world resources, water and prop bindings decoded by
   the catalog owner. Type their existing document shapes at that boundary too;
   object-bank typing alone would leave part of current authoring as raw dicts.
   Reuse the actual `AssetSpec`/resource values and preserve fallback precedence.
   This does not authorize importing dormant catalogs or a universal catalog model.

**Gate:** whole-game typing remains clean; existing device, portal, fixture,
environment, condition and world-depth behavior tests pass. Selected same-input
draw comparisons show no placement, depth, palette or timing change. Diagnostic
text changes alone are not a pixel regression. Explicitly compare drawing with
diagnostic evidence omitted against the same named commands: device pose/frame,
portal clipping and deposit visibility/lighting must still work. That establishes
that diagnostics no longer carry a hidden required rendering protocol.

## 8. U4 — explicit composition and registration, preserving output

**Owners:** `animation_types.py`, selected media/catalog JSON,
`animation_data.py`, `registered_media.py`, `animation_draw.py`,
`spatial_field_media.py`, existing area/volume/fixture composition modules.

### Separate the decisions currently conflated

| Decision | Owner | Examples that remain distinct |
| --- | --- | --- |
| Storage | Media registration | Legacy sheet; PNG page/parts; cropped XYZ packet; later indexed packet |
| Attachment/contact | Authored track + received contact | Actor body/hand, ground arrival, departure, world field |
| Composition | Authored supported rendering mode | Billboard, grounded material/clump, XY volume, XYZ surface volume |
| Coordinate basis | Source registration | Source pixels; world XY footpoints; camera-local XYZ; scalar fixture depth |
| Scale | Shared registration + authored size | Reference pixel conversion, physical size delta, separate zoom/actor/radius factors |
| Lifetime | Existing recipe and recorded state | Finite cast/media; maintained owner; witnessed apply/remove; quiet acquisition |

1. Document the current effective transform for every existing mode using the
   completed scale inventory. Preserve the fact that `.5 × 128/64 = 1` at zoom 1.
2. Introduce explicit selectors at all three current implicit switches:
   projectile impacts in `animation_draw.py`, `cast_media_draw_commands` selecting
   volume behavior from `layer.positions`, and maintained-line drawing in
   `spatial_media_draw.py` using positions plus line geometry inside its legacy
   branch. Replace misleading `legacy`/`volume` routing with explicit XYZ/XY
   meaning. Normalize old authored records once at intake; samplers receive the
   explicit meaning. Preserve the maintained line's observed geometry and clock.
   Assign the local schema revision and legacy normalization in this same unit;
   do not temporarily publish new meanings under an unchanged old identity.
   U7 documents and verifies that versioned contract rather than retroactively
   making already-migrated files distinguishable.
3. Do not claim new capabilities merely because a format parses. Current XYZ
   impacts require their supported ground/field contacts and authored camera
   banks. Arbitrary rotated actor-local XYZ projectiles are not added here.
4. Make reference projection/units and authored physical scaling agree for
   both pixels and coordinate samples. Retain source-specific vertical conversion
   and preserve Color Spray's current pixel/position ratio exactly.
5. Keep `registered_media_samples` as the shared crop/pivot/paired-sampling owner.
   Source-space crop offsets, normalized or measured pivots, per-facing anchors,
   component order and shared-edge rounding remain intact. Do not rebuild a full
   1536² Fireball raster to simplify an interface.
6. Keep screen hand correction explicitly screen-based. It is not secretly a
   measured world socket. Preserve Fire Bolt alignment, cannon muzzle/launch
   curves, tangent rotation and sleeping target contacts.
7. Maintain separate inputs for gameplay propagation boundaries and visual
   occluders using already received metadata. Both can originate in the same
   observed object; their meanings must not be inferred from one another.
8. Migrate by consumer family: ordinary projectile/direct media, maintained
   XY/XYZ fields, liquid/deposit geometry, then object/fixture registration where
   shared fields apply. Do not force all families into XYZ or a giant schema.

**Gate:** unchanged saved inputs at four cameras and five supported zooms for
representative registration cases retain the same sampled timing, source frames,
anchors, geometry and final pixels. Check paired color/coordinate samples at
subpixel boundaries. Compare disposable frames in memory or local output; no
permanent screenshot framework. Metadata normalization and intentional U6 visual
correction must remain separate changes.

## 9. U5 — close demonstrated type/execution gaps

**Owners:** `animation.py:media_track_duration`, `_compile_anchored_cast`,
`compile_cast`; source storage records in `animation_types.py`; stationary/contact
media bindings at their existing consumer boundary.

1. Share the finite-media end calculation between direct and projectile casts.
   Compute the join before existing recovery scheduling. Keep release/contact,
   child application and damage anchors unchanged; only genuinely finite tails
   that the selected recipe asks to play can extend completion.
   Existing stationary/contact emissions have a separate nonblocking owner and
   must not begin extending every action just because they also use media tracks.
2. Add the demonstrated legal combination to the existing timeline tests:
   projectile delivery with a longer existing finite media track. Test completion
   and recovery ordering through compiled/sampled output, not a private helper's
   call count. Ordinary current casts must retain their original duration.
3. Constrain actual storage alternatives at JSON decode: a layer has one source
   among pattern/pages/parts/parts-by-facing; a phase selects layers or surface
   frames; packet frames select a pattern or component patterns. Validate nonempty
   selected sources and ordered numeric bounds in memory.
4. State what each existing contact/stationary consumer executes. If a broad
   Studio record has fields that this consumer ignores, narrow/check that usage
   at binding. Do not implement dormant media/recovery features to satisfy every
   old optional field.
5. Preserve accepted omissions: potion source strips, empty optional locomotion
   media and the already working jump/OA behavior are not reopened by this work.

**Gate:** existing timeline, interruption and condition-lifetime tests plus the
small demonstrated finite-tail case pass; invalid source combinations have a
clear authoring error without disk access. No new scheduler or track language.

## 10. U6 — fix the real wall-cap mismatch separately

**Owners:** observed boundary/visual wall registration in `app.py`,
`volume_media.py:compose_volume` / current area composition, fixture/art registration and
`test_area_scene_occlusion.py`.

1. Reproduce the audited native height-2 stone wall case. Identify the exact cap
   pixels and rays passing at heights above 2 while the drawn cap occupies them.
2. Correct the visual cap/thickness/registration contract to match the intended
   occluder. Choose the smallest art/visual geometry correction supported by the
   source probe. Do not raise native wall height, alter area propagation, or
   blanket-mask all opaque wall pixels.
3. Keep near-face flame contact and charring, hidden far-side suppression,
   above-wall particles and open-door connected spread as separate expectations.
   Check all four camera directions and a raised support.
4. Repair obsolete silhouette tests around those expectations. Distinguish the
   current visible-cap bug from old height-1/blanket shadow fixtures. Do not delete
   an inconvenient wall matrix or approve all overlap by changing its oracle.
5. Restore the wall-memory test's one-sided native setup by closing the actual
   connected route around the wall. Preserve its independent-face disclosure and
   hidden-removal assertions; do not simply expect both scorched faces everywhere.

**Gate:** corrected geometry cases pass and focused before/after views explain
the intentional pixel changes. One simultaneous depth-bearing effect case records
the compositor's actual interpenetration limit. If the representation cannot
support a newly demanded result, report that bounded limit; do not build a general
3D transparency engine as part of this cleanup.

## 11. U7 — coverage, TS contract and live/review parity

**Owners:** `game/presentation_coverage.py`, existing
`devtools/presentation_coverage.py`, `condition_types.py`, source version readers,
`PRESENTATION_CONTRACT.md`, `encounter_play.py`, review `record.py`.

1. Extend initialized reporting across object banks, device/portal bindings,
   spatial/deposit media and current condition capabilities. Use loaded registries
   and declared bindings; never walk the asset tree to discover rendering support.
2. Include actual portal cues in bound-lineage traversal. A received event with
   no cue may be state-only, omitted, unsupported or irrelevant; it is not
   automatically a missing animation.
3. Keep mechanical/replay checks, binding gaps, authored selection and human
   visual approval separate in reports. A generated clip marked passed is not
   automatically artistically approved.
4. Keep original NeuroStudio v6/v12 readers/reference data. Give local extended
   condition recipes an honest local schema identity, consistent with the existing
   local spell extensions. Preserve source round trips without dropping `media`,
   `contact`, `childAttack`, `effectDrafts` or condition additions.
5. Document the portable shapes and exact transform/time semantics in the
   existing contract: coordinates/units, rounding, direction/bank selection,
   source frame sampling, component blending, finite joins and state lifetimes.
   Small ordinary JSON input/expected-value fixtures can accompany those shared
   algorithms for a future TS port. No TS renderer, code generator or new schema
   publishing framework is required now.
6. Put mutable blood/material color choices into existing records only where
   their owning path is cleaned; retain deterministic geometric/selection
   algorithms as shared code. Do not turn equations into a shader DSL.
7. If U3–U5 touch duplicated live/review head admission, extract the existing
   bookkeeping into a small shared function after demonstrating same-input parity.
   Preserve condition/media/feedback/deposit/body-history admission. Do not redesign
   scoped old demos into complete executors or create another queue.

**Gate:** registry reports cover all initialized families; a genuine portal
sequence reports its existing bound cue; accepted omissions remain explicit.
Portability fixtures contain JSON values rather than Python/Pygame objects.
Live and recorded presentation produce equal sampled state/contact/phase results
for the touched lifecycle cases. No current runtime requires TypeScript or Node.

## 12. A1 — private setup and forward Git separation

This can proceed alongside renderer work. **History rewriting is not a gate.**

Prepared setup commit: `59aa7262fdb` in the separate private-assets task. Current
preserved installation: `/home/tommaso/Dev/neurodragon_art`. It contains 62,769
installed files and the final inventory records. Remote creation/upload remains
separate from local correctness; no publication or billing change is implicit.

1. Review and integrate setup code/docs/ignore rules deliberately rather than
   blindly cherry-picking tracked deletions over the active installation.
   A checkout applying deletion commits can remove previously tracked local art.
2. Keep public code, schemas, recipes, resource identities and authored registration
   in Git. Ignore media, binary geometry, generated images/video and original vendor
   payloads. Do not blanket-ignore JSON: source-side delivery metadata and authored
   public behavior have different owners.
3. Preserve the existing installed art locally; use `git rm --cached` for the
   forward index change after confirming the archive exists. Include the known
   legacy logo outside `game/assets`. Keep the two public native fixture/policy
   JSON files under `output/fireball-propagation`.
4. Make routine explicit installation lean before adopting the prepared installer.
   It currently hashes the entire source bundle, compares every existing file byte
   by byte, then scans installed outputs. Remove unconditional full-content
   verification from ordinary install/reinstall. Keep any requested exhaustive
   integrity check explicit; do not move it into startup.
5. Define install/update behavior plainly: consume the selected release's file
   list, copy its payloads, preserve unlisted local files/caches and report missing
   required inputs. Reuse a small installed-release receipt/previous manifest to
   skip unchanged release entries; an explicit reinstall can restore files. This
   is not proof against manual disk edits: explicit `check` owns that question.
   Normal copying must not add a separate full-library read just to prove identical
   bytes. Do not build a content-addressed validation system or trust filenames/
   equal sizes alone as evidence that a changed release's payload is unchanged.
6. Preserve filesystem correctness at this explicit boundary: paths stay under the
   intended destination, invalid/unhydrated inputs fail usefully, credentials
   remain outside source. These are existing installer responsibilities, not a new
   compliance subsystem. Move the current same-size-corruption expectation to
   the explicit integrity-check test instead of silently weakening its meaning.
7. Verify a fresh code checkout plus local source installation can initialize the
   declared content and replay a representative recording. Verify local assets are
   ignored/untracked and public authoring remains tracked, using targeted paths.

**Gate:** tiny setup-fixture tests pass; one real local installation smoke test
works; ordinary gameplay startup never invokes install/check/export. The active
working installation remains usable. Private remote authentication/upload and
the deferred clean-public-history question do not stall renderer implementation.

Distinguish a missing selected payload (a release defect) from the known content
gap in the baseline: 216 equipment selections lack complete art; equipment and
permitted appearance together request 81 absent categories / 1,134 clip bindings,
including premade `Head17`. The same limitation must
remain explicit after installation; do not hide it with substitute art or turn
this cleanup into generation/import of missing outfits. The gate is no lost
baseline dependencies, plus working supported rigs/scenarios, not a claim that
all declared equipment now has artwork.

## 13. A2–A3 — build the lean runtime payload and pack it

### A2. Selection and sharing before new compression

**Inputs:** preserved final inventory, existing selected bindings, source snapshot.
**Owners:** explicit offline packaging tool/selected importer outputs; resource
and storage mappings. Use existing tool locations rather than a runtime service.

1. Build into a separate staging directory. Never prune or mutate the preserved
   originals in place. Keep authoring sources/review media out of the default
   runtime install payload.
2. Apply the per-file and per-frame selection to the current declared content.
   Archive-only means absent from this runtime release, not deleted from source.
   Retain the confirmed conditional branches, all supported directions, first-frame
   preloads and the complete reachable travel phases.
3. Preserve logical media IDs. Map identical selected payloads to shared physical
   resources through their existing storage references; keep each use's crop,
   pivot, coordinate bounds, material and clock. Do not infer those from a shared
   filename or embed content hashes in runtime behavior.
   Start sharing explicit page/part resources: about 5.712 GB of the measured
   5.782 GB duplicate excess is already in persistent media with those address
   forms. Pattern-only packets wait for the explicit addressing in A3b.
4. Use the existing offline alias evidence for this baseline. If a selected delivery
   changes, update its packaging inputs explicitly rather than revalidating the
   full corpus every launch or import.
5. Produce a release-local file/region index from the pack operation and record
   compatible code/art release identifiers. Routine installation copies that
   release; it never regenerates gameplay recipes from art.
   Keep normalized resource/storage binding changes in public `game/data` with
   the matching code release. Private payloads contain the media and asset-local
   indexes/manifests. The installer continues to write only `game/assets` paths;
   it must not overwrite public authoring or bindings. Its existing `contained`
   boundary enforces that separation.

**Expected baseline arithmetic:** 5,551 source-only files account for
5,959,706,594 bytes. Retained references total 20,700,948,428 bytes; their duplicate
payloads account for 5,781,548,704 bytes. Unique retained payload is 14,919,399,724
bytes before new packing/compression. This is a 44.04% candidate reduction, not a
promised final download size. Recompute output counts from the built release;
indexes and changed encodings affect the result.

### A3a. Color sheets and existing page/part media

1. Keep current sparse/page storage; do not unpack existing atlases merely to
   repack them under a new label. Remap logical sample addresses where real unused
   cells justify compaction.
   For raw XY footpoint pages, preserve paired layouts: `PackedFootpoint` carries
   file/bounds but the reader uses the color part's rectangle for both images.
   Pack color and coordinate pages with matching rectangles. Independent repacking
   would break this current contract; matching layouts need no extra schema.
2. Atlas the eight loose color phases (Acid Splash, Eldritch Blast, Guiding Bolt,
   Fireball carrier) through the existing page/part reader. Preserve transparent
   boundaries, alpha/additive material order, offsets and original frame clocks.
3. Repage oversized legacy strips and environment banks into bounded pages.
   A 2048² page is a useful starting measurement, not a universal maximum: it
   occupies 16 MiB decoded. Check the actual renderer/cache cost before fixing
   page sizes for a family.
4. Compact the demonstrated subsets: 48 of 1,152 indoor structural-frame cells,
   actual hatch body/front-mask columns, partial portal last pages and top-row
   ashen motifs. Keep the door body/depth sequences and all reachable portal
   opening/hold/closing samples.
5. Environment/body readers currently expect regular sheets in several places.
   Add the smallest explicit frame-to-page/rectangle adapter where repaging really
   needs one. Preserve the same environment selector/sampler and rig layer
   composition; do not add a second object-animation executor.
   Concrete seams are `EnvironmentBank`, `environment_draw._frame` and
   `fixture_depth._depth_cell`; paired color/depth cells can have different source
   dimensions. Loose mechanisms need an explicit optional region in the existing
   `AssetSpec`/image resource and `SurfaceCache.canonical` path. Hatch masks use
   equivalent frame addressing; portal loops already have pages. Character sheets
   stay unchanged in this packing pass.
6. Keep water's repeating texture domain intact. Native character source cells
   and neutral equipment layers stay separate and dynamically composable.

### A3b. XYZ packet bundles

1. Preserve the current cropped packet bytes/components initially. Packing and
   new numeric compression are different changes.
2. Extend the current `PackedSurfaceFrames`/component addressing with an indexed
   packet bundle alternative. Prefer a standard `ZIP_STORED` container per effect/
   view holding the unchanged `.bin.gz` packet members: its directory already
   supplies an index and independent member reads. Keep logical source-frame and
   component mappings in the current storage data. No custom archive format,
   hash-derived identity or giant monolithic decompression unit is needed.
3. In `projectile_media.py`, separate obtaining selected packet bytes from the
   existing decode. Loose sources remain supported for the archive/current rollout;
   indexed sources feed the same decoder and shared cache. Make cache addresses
   distinguish the bundle range/sample as well as material treatment.
   Before canonicalizing packet addresses, fix the demonstrated interpretation
   hazard: `_surface_packet` currently caches bounds/verticalScale/positionScale
   inside its decoded value without those fields in the key. A tiny shared-packet
   probe returned the first owner's values for a differently registered second
   owner. Either key that interpretation explicitly or cache immutable raw numeric
   samples and wrap each use's registration separately. Prefer the smallest
   verified change; do not introduce an asset-manager hierarchy. This is a
   prerequisite for new sharing, not evidence all present distinct-path effects
   are wrong.
4. Keep loads lazy. Do not read/decompress every camera or a whole effect bank to
   display one frame. Count retained decoded color/XYZ/ownership in the existing
   cache; compressed indexes/handles must have explicit bounded lifetimes.
5. Start with the selected 384 Fireball packets and one multi-component area
   bank, prove equivalence, then apply the same address representation to the
   other selected XYZ families. Preserve ordered smoke/additive siblings.
6. Share duplicate coordinate payloads separately where the existing page/part
   representation can express it. Raw numeric alpha remains data; do not apply
   palette, premultiplication or ordinary image filtering.

**Gate for A2/A3:** tiny packing fixtures verify source-frame mapping, crop/pivot,
color/geometry correspondence, blend order and alias selection. Real selected
phases compare decoded values and representative final pixels before/after, with
source cache limits intact. Record installed file count, encoded bytes, cold
selected-frame load time and peak decoded memory on the same filesystem/environment.
Exercise a non-first page/member, repeated frame aliases, different registrations
sharing one payload, eviction followed by backward seek, and paired environment
color/depth across a page boundary. Keep reverse opening, state-change markers
and final wreck holds intact. Install into an empty asset destination for final
reachability proof; leftover files in today's full tree would hide omissions.
Do not claim the 42,968 unique source payloads are the final number of installed
files; bundles/pages should reduce it substantially, and the actual build reports it.

## 14. A4 — limited resizing and compression, never a hidden prerequisite

After the exact selection/packing wins, evaluate only identified opportunities.
Most media already have native fixed pixel scale; camera zoom, actor size and
field radius remain dynamic. Do not halve the entire library because recipes
contain `.5`.

| Candidate | Action |
| --- | --- |
| Ashen floor | Bake the four exact 70² intermediate motifs already made by the reader; preserve later rotation/opacity and compare those outputs. |
| Color Spray | Evaluate 768² → approximately 683² only if it saves meaningful runtime/storage cost without unacceptable registration/pixel change. Keep world position scale unchanged. |
| Small Shocking Grasp / Blur / Mirror Image uses | Source is also needed larger. A derivative adds storage; do not build one absent measured benefit. |
| Palette noise | Keep the 512² source: the bounded probe already disproved equivalence of a 128² intermediate for 64² consumers. |
| Actor sheets, field radius, camera zoom | Preserve dynamic transformations. Do not bake one encounter/outfit/zoom as the universal answer. |

Numeric compression follows exactness and cost: test representative unique
coordinate pages/packets after deduplication, with exact decoded values, decode
time and peak allocations. The previous ten-page experiment is not a library
forecast; some smaller encodings decoded slower. Select a format only if that
tradeoff improves the actual runtime package. A new codec is optional, not required
to close the primary cleanup. No lossy coordinate compression or frame-rate
thinning is included. Full-resolution/full-cadence source remains archived.

## 15. Validation matrix and runnable lanes

Use the prepared WSL uv environment. Record whether source/media live on `/mnt/c`
or a Linux filesystem when comparing timings; do not attribute filesystem effects
to engine or renderer algorithms.

```bash
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv \
  /home/tommaso/.local/bin/uv run --no-sync python -m pytest -q <selected test files>
```

Use dummy SDL for headless cases as existing fixtures require. Use the project's
Pyright invocation for changed production and finally all `game`; do not change
strictness or suppress types to get green. Read the current testing guide before
adding tests. New tests describe actual caller-visible behavior and use small
data cases; structural/private-helper assertions are not behavioral proof.

| Contract | Existing files/cases to extend or reuse | What must remain observable |
| --- | --- | --- |
| Fresh and legacy replay | `test_passive_event_replay`, `test_recorded_history`, `test_prop_destruction`, `test_device_destruction`, `test_liquid_barrel_replay` | Exact recorded facts, passive cold replay, original fixture compatibility |
| Import ownership | `test_spell_media_imports`, `test_aoe_surfaces`, selected `test_*_media_import` modules | Tuned recipes survive; current selected media stays selected |
| Clock and causal interruption | `test_animation`, `test_area_cast_timeline`, `test_animation_volley`, `test_interruption_replay`, `test_movement_interruptions` | Release/contact/child timing; true finite completion; canceled effects do not invent hits |
| Body/state | `test_sleep_condition_pose`, `test_lifecycle_playback`, `test_equipment_animation`, `test_forced_movement_playback`, `test_occupancy_layer_replay` | Falling/waking, stopped/dead subcell pose, gear changes and jump contacts |
| Registration and raw media | `test_animation_space`, `test_projectile_media`, `test_xyz_media`, `test_aoe_surfaces`, `test_fixture_depth`, `test_world_depth_commands` | Same source samples, anchors, crops, raw coordinates, ordering and bounded source cache |
| Geometry/visibility | `test_area_scene_occlusion`, `test_area_spell_projection`, `test_globe_replay`, `test_paired_environment` | Front/behind/above wall; connected doors; protection and per-observer disclosure |
| Maintained/condition/deposit lifetimes | `test_spatial_field_media`, `test_condition_media_lifetime`, `test_condition_transition_media`, `test_deposit_media`, `test_web_replay` | Creation/removal versus acquisition/loss, independent material release |
| Objects/portals | `test_environment_presentation`, `test_portal_replay`, `test_portal_draw`, `test_device_replay` | Break clearance and remnant timing; actual portal transfer and device pose |
| Reporting | `test_presentation_coverage`, `test_media_coverage` | Correct bound/state-only/omitted/unsupported distinctions |
| Private setup | Prepared `tests/test_private_art_setup.py`, tiny fixtures plus one real local smoke | Correct installation and index boundary without runtime auditing |

Run only the touched lane per unit. Once integrated, run the same broad selected
game lane used by the audit with the same documented gallery exclusions, then
selected actual video capture/playback cases separately. This is not permission
to permanently skip failing gameplay tests or treat omitted slow capture tests
as passing. Do not rerun the broad suite after every metadata adjustment.

The integrated commands are:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv \
  /home/tommaso/.local/bin/uv run --no-sync python -m pytest -q tests/game \
  --ignore=tests/game/test_animation_review.py \
  --ignore=tests/game/test_weapon_motion_review.py \
  -k 'not gallery and not paused_lifecycle_clip'

UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv \
  /home/tommaso/.local/bin/uv run --no-sync pyright game
```

The selected baseline population was 2,052 passed + 206 failed + 7 setup errors,
with 15 deselections inside this lane. Added regression cases may increase that
population; record that difference. Dedicated capture validation remains a
separate slower lane with its own actual result, not an implied pass.

The visual sample set should cover capabilities, not all 75 bindings individually:

- Fire Bolt alignment and a bent device projectile, including sleeping target.
- Fireball/Globe/door contact, a raised support and one simultaneous depth case.
- One XY maintained volume, one XY liquid and one body-local healing/condition.
- Destruction with clearance and spill markers, and portal fall/transit/emerge.
- Walk → OA → death, jump OA before takeoff, and melee/ranged equipment transition.

Take all four camera views from the same saved inputs; preserve both observer
perspectives when disclosure matters. Five zooms are for shared registration
comparisons, not five complete encoded videos per scenario. Exact migration
comparisons and intentional U6 cap changes have different acceptance criteria.

## 16. Closing the known failure ledger

| Existing outcomes | Owner and closure |
| --- | --- |
| 112 failures + 5 errors on fresh destruction JSON | U1a; rerun downstream assertions after admission works |
| 3 failures + 2 errors on old native archives | U1b; original fixtures and passive compatibility retained |
| 64 foreground wall/door failures | U6; distinguish obsolete fixture/oracle from real cap defect |
| 25 rear-face shadow failures | U6; replace blanket shadow premise with actual contact/depth expectations |
| 1 wall-face memory setup failure | U6; restore real one-sided setup, retain privacy assertions |
| 1 full Fireball allocation expectation | U4/A3; require registered equivalence, not full-canvas allocation |

Every group gets an actual result and explanation. New failures revealed behind
the codec blocker are investigated within the touched contract. Do not use this
ledger to launch speculative mechanics work or change a test simply because the
implementation currently disagrees. If an unrelated issue is exposed, record its
evidence and scope explicitly instead of silently calling the cleanup complete.

## 17. U8 — deliverable and restart record

1. Record completed units, exact changed ownership contracts, test results,
   representative saved-input comparisons and intentional visual changes.
2. Update `RECOVERY_PLAN.md`, `PRESENTATION_CONTRACT.md` and the inventory's
   implementation status. Keep historical audit measurements labeled historical.
3. Record the actual private release layout, selected code/art version pair,
   install command, file/byte totals and source archive location. Preserve the
   final inventory records outside ignored `.runtime` cleanup.
4. Separate local setup completion from private remote publication. Historical
   Git cleanup remains deferred; do not claim previous commits have lost their art.
5. Retain a short continuation entry: last completed unit, next unit, outstanding
   real limitation and exact saved-input/artifact paths. Do not let a compaction
   turn the work back into spell-by-spell VFX authoring or a fresh inventory.

Optional derivatives/compression and unintegrated content are not hidden blockers
for primary cleanup completion. Conversely, tested local installation is not a
claim that a remote private package has been published, and clean types are not
a claim of correct pixels.

## 18. Independent double validation

Two independent reviewers inspected the actual source, reviewed the written
draft, and reread the revised complete plan. A third reviewer validated asset
and installation work and then rechecked its corrections. All approved the final
implementation scope and contracts; no required plan changes remain.

| Review | Material corrections incorporated | Final result |
| --- | --- | --- |
| [Anti-slop/correctness](audits/CLEANUP_IMPLEMENTATION_ANTISLOP_REVIEW_2026-09-24.md) | Explicit legacy native round-trip absence preservation; distinguish missing baseline art from new package omissions; literal comparable validation commands | Round 2 approved |
| [Anti-OOP/ECS/portability](audits/CLEANUP_IMPLEMENTATION_ECS_REVIEW_2026-09-24.md) | Include active world catalog typing; prove drawing independent of diagnostic evidence; actual volume owner; version normalization alongside new fields | Round 2 approved |
| [Asset/setup](audits/CLEANUP_IMPLEMENTATION_ASSET_REVIEW_2026-09-24.md) | Preserve paired color/raw-XY rectangles; explicit public binding/private payload split; lean install, packet cache interpretation and standard indexed storage reviewed | Final revalidation approved |

The source pass additionally established the installer full-read cost and a
small reproduced shared-packet cache interpretation hazard, now explicit in A1
and A3. These are concrete implementation dependencies, not a justification for
a new asset-management framework.

Approval applies to the plan and its acceptance contracts. No production code,
installed art or Git asset tracking changed during this planning turn. No broad
suite or new video gallery was run. Actual code, packages, pixel equivalence and
performance still must pass the stated implementation checks.
