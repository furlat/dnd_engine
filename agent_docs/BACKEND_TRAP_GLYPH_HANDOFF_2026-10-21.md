# Backend trap anchors and retired Glyph attribution

21 October 2026. Follow-up to
[the production handoff](BACKEND_CLIENT_PRODUCTION_HANDOFF_2026-10-20.md)
and the client's `BACKEND_CONTENT_BLOCKERS_2026-10-20.md`.

Fixes commit: `2948cf033cb87271707081c568d38b9fc166d9b2`.

The implementation is backend-only, on `feature/rules-checking` in the main
`dnd_engine` checkout. No client source, artwork, recording or frozen engine
export was changed by this work.

## Producer corrections

The existing `anchor_item_uuid` now identifies the actual attached, currently
perceived WORLD_OBJECT for Gas Vent, Jaw Trap, Pressure Plate, Tripwire and
Spike Trap, including both poison spike variants. Custom descriptions, pressed
state, trap state, direction, discovery and footprint rules remain intact.
Two bodies with the same content retain distinct exact identities. A spatial-only
installation or unobserved housing publishes no object anchor.

A regression also exposed stale sensory descriptors: opening a door revealed a
spike housing, but closing it left the old anchor on the still-visible remote
spike cells. The existing fixture pass now re-observes the visible footprint of
an object-anchored condition when that exact object's contact changes. This
uses a temporary settlement-local changed-object index and the existing single
condition traversal. It adds no persistent cache or broad visibility invalidation.
The grid protocol merely declares the condition's existing `anchor_kind` property.

Glyph's native damage already named its zone. Publication stripped the UUID
because the one-shot zone correctly retires before applying its payload. A
completed `DamageResultFact` can now retain that exact `source_condition_uuid`
when the seat witnessed its actual removal under the same immediate native
cause. Admission authenticates both the condition-removal parent and the
TakeDamage parent against the exact zone UUID. It is confined to the current
publication group. Hidden sources, prior sightings and unrelated removals—even
under one operation root—grant no attribution. No spell mechanics changed.

## Client adoption

Re-export the new engine revision and make new recordings. Existing packets do
not gain missing anchors or damage attribution. Protocol remains 1, schema 16,
with unchanged digest
`2c11d7a9919c8aa9b1490628fff224627f19d6388c3884171d14a4a5cbecea22`.
There are no generated SDK or schema changes in this follow-up.

One client correction is independently necessary. The inspected
`NDClientGodot/presentation/world.gd` uses `apparent_presence` as a current
visibility prerequisite in both `native_object_owner` and `spatial_projection`.
That rejects legitimately observed traps, including finite traps whose anchors
were already present. `apparent_presence=False` describes how concealed effects
are remembered when a cell is seen without them; it does not negate current
membership in `senses.spatial_effects`. Keep the existing client memory/absence semantics unchanged. The client should admit current disclosed effect cells while retaining
its exact identity, currently visual object, placement, direction, suppression
and ambiguity checks. Never substitute remembered effects for current membership.
The client production owner is responsible for this correction and visual tests.

For the five elemental Glyph contacts, use the actual damage result's exact zone
UUID and its native damage type/save evidence. The observed pre-removal source
and actual mechanical removal can support finite contact playback. A removal
alone is not proof of a hostile trigger: rest and recasting also retire wards.
This repair does not add `armed`, selected-payload or trigger fields, and does not
extend damage-request attribution. A neutral held ward can use already disclosed
presence/geometry. Exact Sleep/Detonation trigger presentation remains separate;
do not infer either payload from missing damage.

## Why the previous tests missed these defects

Ground-hardware tests verified internal attachment, discovery and destruction;
public anchor assertions covered FiniteTrap, whose observation override already
supplied the link. They did not inspect the five custom overrides through
serialized player updates. The new trap tests also exercise a housing leaving
sight while part of its footprint remains visible, exposing the stale descriptor.

Existing Glyph mechanics tests verified activation, damage and one-shot cleanup.
Existing source-attribution tests predominantly used owners still present at the
damage event. Neither established that a witnessed retired owner survives the
public damage-result boundary. The new tests cast through the character-created
Wizard's real available action and move a real recipient into the held Glyph.
They serialize and reduce both seats' initialization and subsequent operations.

## Verification

- **25 new public regressions:** eight trap cases and seventeen Glyph cases.
  The trap suite includes three spike payload variants, two simultaneous owners,
  hidden and spatial-only controls, discovery, destruction, and door-driven
  addition/removal of the exact anchor. Glyph covers five elements with visible,
  never-seen and previously-seen-then-blind recipients, plus unrelated removal
  causes in one operation and under one shared root.
- **Failing-first:** all eight trap cases failed on missing public anchors.
  Adding those fields exposed the door-close stale-anchor failure; the targeted
  sensory correction made it pass. The initial Glyph matrix failed fifteen
  genuine trigger cases while its unrelated-removal control passed.
- **Combined regression batch: 788 passed, 1 xfailed in 252.02 seconds.** This ran
  all `tests/player`, the ground-hardware/trap suites, BG3 spell fields and the
  relevant sensory suites. One existing transport-fixture serializer warning
  names `version_rows=()` where `VersionRows` is expected. This is a scoped
  regression result, not a claim that the entire repository suite is green.
- Focused Pyright matched the exact pre-change checkout: **11 existing
  diagnostics, zero new errors**. The unchanged diagnostics are eight sensory
  errors and three `CreatesModels` class-variable errors.
- Independent plan, antislop and antiOOP review found no remaining blocker.
  Production Play/Studio recordings and visual acceptance belong to the client.

## Timing evidence

The comparison uses the exact pre-change `8d4a185e79` checkout and the repaired
source in Linux temporary folders, the same Python 3.13 environment and fixed
inputs. Our tests/static tools were stopped. Measurements include native work,
publication and JSON encoding; they exclude process startup, setup, discovery
and client display. They are not player input-to-animation latency.

Medians below retain all measured batches. Glyph and installation each have
15 measured samples per side, with one excluded warmup per five-sample batch;
the repeat batches alternate side order. Door transitions have five per side.
Crowded Fireball has three fresh-process runs per side with alternating order.

| Case | Median total ms, before → after | Largest update bytes, before → after |
| --- | --- | --- |
| Glyph held entry | 31.277 → 29.767 | 22,236 → 22,362 |
| Five trap installations | 32.189 → 31.634 | 12,011 → 12,301 |
| Housing door open | 5.668 → 6.001 | 3,211 → 3,281 |
| Housing door close | 5.083 → 4.752 | 1,919 → 1,955 |
| Crowded Fireball | 125.794 → 124.868 | 133,102 → 133,102 |

The initial small-case batches showed increases; alternating repeats did not
show a consistent median increase. These runs are noisy: Glyph ranged
24.792–34.313 ms before and 26.642–49.302 ms after. This is measured evidence,
not a guarantee against tail regressions or a claim of a speedup. Packet growth
carries the newly supplied exact identities/clears; native event-version counts
are unchanged. Fireball retains the same 571 event versions, zero runtime schema
builds and packet size. Its pre-existing 100 ms/100 KB targets remain unmet.

[The audit](audits/BACKEND_TRAP_GLYPH_2026-10-21.json) includes all 96 small-case
samples (16 excluded warmups), six complete Fireball reports, phase timings,
ranges, client-fold/collection measurements and the standalone reproduction
scripts. Preserve old client recordings and qualify fresh production recordings
separately after adopting the fixes revision.
