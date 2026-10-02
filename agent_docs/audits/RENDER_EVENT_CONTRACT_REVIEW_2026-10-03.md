# Event and rendering contract review

Source review on October 3, 2026. Implementation remains stopped. This extends
the [overall review](OVERALL_ANTISLOP_REVIEW_2026-10-02.md) and informs steps 5–6
of the [cleanup plan](../ANTISLOP_CLEANUP_PLAN_2026-10-03.md).

## Scope and evidence

Inspected current source, including committed code and untracked additions,
against HEAD `3f2158f934f198f7edcb93f559fb1fda8b70e1f0`. The shared checkout is not
a disposable diff. The active path examined in detail is native results →
subjective projection → saved player facts → reduction → binding/choreography →
lifetime registration → sampling/drawing. Native damage, effect provenance,
item/condition ownership and the existing presentation authoring contract were
included. This is not an assertion that every function was manually audited.

A fresh AST inventory covered **543 production modules / 3,644 internal import
edges**: `dnd` 272, `game` 105, `ai` 67, `custom_ai` 4, `server` 88, `services` 7.
It found no static cyclic components, function-local imports or parse errors.
The inventory includes the paused server; its behavior was not exercised or
added to implementation scope. Dynamic imports and semantic dependency ownership
are not certified by an acyclic static graph. No application imports, tests,
gameplay executions, previews or agent messages were performed in this review.

R1–R5 below were also located with `git show HEAD:<file>`: they are not solely
new uncommitted regressions. Findings distinguish source-proven restrictions
from runtime failures that have not been reproduced here.

## Foundation to retain

- `game/player_facts.py` already defines a discriminated `PlayerFact` union and
  a JSON `PlayerSequence`. `player_reduction.py` encodes/decodes that boundary.
  The private native archive's Python `wire_type` is a different format, not
  evidence that the public player packet requires Python constructors.
- `SpellFact` and `CastApplication` already carry application IDs; native events
  already have lineage/version identity. `EffectOrigin` and `SpatialDamageSource`
  provide provenance. Extend their actual meanings instead of inventing another
  event bus, ownership registry or set of anonymous IDs.
- Recipe/content lookup is already widely data-driven. The broad scan did not
  establish an everywhere-present chain of hardcoded spell names in drawing.
  A typed branch for a shared operation is not itself an architectural defect.
- `presentation_group.py:20` joins reactions using their explicit triggering
  lineage while preserving native reduction order. This is the kind of relation
  the remaining consumers should receive directly.
- `game/data/PRESENTATION_CONTRACT.md:160` explicitly rejects a second normalized
  recipe language. Keep the existing Studio/local authoring admission and sampler.
- Geometry, XYZ clipping, depth, palettes and sprite sampling need algorithms.
  Decorative support geometry in `spatial_field.py` is not proof of duplicate
  gameplay propagation. Preserve the accepted algorithms and visual behavior.

## Findings

### R1 — effect ownership depends on the availability of artwork

**High priority; committed.** `game/attack.py:296–309` and
`game/combat.py:208–227` walk descendants and stop at an `ActionFact` only when its
`behavior_id` exists in `data.drafts`. `game/choreography.py:699` also uses that
membership to classify a delivered action.

Consequently, adding or removing an animation binding can change which enclosing
action claims a damage subtree. That is more than selecting a visual: ownership
of gameplay results is being inferred from presentation availability.

Required correction: define resolution boundaries and result ownership from
typed native/projected facts. Bind available art afterwards. An unbound action
keeps its own results and reports a presentation gap; it must not donate damage
to its parent. Inspect existing ancestry/provenance first and add only the
semantic relation it cannot express.

### R2 — an application is recovered from target identity and animation time

**High priority; committed.** `game/choreography.py:1002–1005` associates a taken
damage fact with a cast delivery by matching the target and testing whether
`start_ms + travel_end_ms` is within `.001` of the current time. Application IDs
already exist upstream, but this association does not use them.

Retiming or repeated applications against the same target must not determine
causal identity. Carry/index the application reference through the result path,
including nested condition callbacks. Timing is an output of that association.
This is a source-proven fragile association, not a newly reproduced multi-hit bug.

### R3 — a single optional-heavy result cannot describe all existing outcomes

**High priority; committed restriction.** `game/attack.py:309` rejects binding
when its selected subtree has more than one applied damage packet.
`game/combat.py:220–227` permits zero or one matching applied packet and raises
for other cardinalities. `CastApplication` in `game/animation.py:90` stores one
damage total/result. This is not evidence that all enchanted attacks fail: one
native packet can contain multiple damage components.

Separately, `game/player_facts.py:226` makes committed damage/HP fields optional
for both `DamageFact.stage` values. `player_reduction.py:119` must reject missing
committed HP at runtime. `SpellFact` combines root/application cases with nullable
application identity/index. Its compatibility upgrade is not a relational
validator for these states.

Required correction: discriminate declaration/request versus committed results;
make each variant's required fields actually required. Distinguish cast root
from application membership without introducing separate per-spell events.
Preserve an ordered collection of result references per application, rather
than equating one application with one damage packet. Resolve R1 first so this
collection cannot absorb a nested retaliation or another action's results.
Do not sum away the individual committed HP changes or emit damage for a miss.

### R4 — choreography splits sensory facts to repair a missing timing relation

**High priority; committed.** `game/choreography.py:1177–1217` derives
`formation_starts` from damage sweeps, finds a sensory descendant by ancestry,
extracts one owner's `spatial_effects_changed`, and constructs a second
`SensoryFact`/node view at a different presentation time. Other observation
fields remain on the later view. The copies retain the source node UUID.

This does not mutate the native event stream. It does mean the renderer must
know how a gameplay observation was batched and manufacture a special partial
version to show formation before injury. Nearby passes also adjust observation
times after destruction and separately shift delivery/damage/feedback clocks.

Required correction: identify the observed changes and their actual causes at
the projection boundary, preserving source order and observer permissions. The
existing compiler schedules those changes through shared authored milestones.
If one recorded batch contains distinct changes, represent referenced components
explicitly; do not publish the same native mutation twice. Formation, damage and
destruction remain distinct causes, not spell-name-specific scheduling rules.
Native facts never carry sprite frames or animation milliseconds.

### R5 — spatial commit ordering is reconstructed during reduction

**Medium priority; committed workaround, not a proven incorrect reducer.**
`game/player_reduction.py:167–196` derives a spatial commit cursor from a
lineage's first version and keeps `spatial_commit_cursors` to stop an enclosing
completion overwriting a more recent nested arrival. This is meaningful existing
protection; deleting it without replacing its contract would recreate movement
regressions.

Required correction: specify which existing version/cursor owns each committed
change, distinct from the parent action's completion. Project that reference
once where it is missing. Reuse the existing version order; do not add a second
clock, counter or global mutation ledger. Keep a pure reducer's last-applied
cursor where necessary, but remove guesses about commit phase.

### R6 — missing owner links cause ambiguous persistent-media admission

**High priority; current untracked visual additions, already E4/E5 in the plan.**
`game/construction_media_lifetime.py:47` identifies a construction by membership
of its geometry in an effect's sections. `game/concentration_media.py:87–94`
subtracts old slots and matches a spell ID; ambiguous matches silently skip
admission. Native wall owner and concentration slot identities already exist.

Required correction: record the permitted owner/slot/section link, then select
the recipe by content identity. Geometry is shape; content identity is recipe
selection; neither is instance ownership. Preserve unknown versus removed state.
Do not replace the ambiguity with a nearest-object or first-match heuristic.

### R7 — the public schema is not yet the TypeScript-facing dependency boundary

**Medium priority; current structural gap.** `game/player_facts.py:13–34` imports
passive values from `dnd.core.events`, blocks and content runtime. The data itself
is serializable, but Python schema consumers inherit dependencies on native
module organization. The inspected `generate_typescript_sdk.py` targets native
and server contracts; neither it nor the checked SDK references `PlayerSequence`.
That existing SDK is not proof of coverage for the current in-process client.

Required correction: move only the shared passive declarations actually needed
by the public packet into dependency-leaf owners, retaining one definition of
each. Export the player schema and admitted presentation vocabulary, with version
and compatibility rules. Do not revive the server, hand-maintain duplicate TS
interfaces, or serialize `DrawCommand`: it intentionally contains Pygame
surfaces and NumPy data (`game/draw_commands.py:24`). The TS client will implement
the shared operations using its own raster backend.

### R8 — coverage and executable capabilities can disagree

**Medium priority; source-proven reporting issue.**
`game/presentation_coverage.py:107–112` labels every `wall_modules` binding partial
with the same hardcoded cardinal-only/ring-and-diagonal-pending description,
irrespective of the selected asset metadata. Meanwhile the presentation contract
at lines 166–167 explicitly documents `area.sprite` as parsed vocabulary without
an executor. Parsing, selecting media, executing it and visual approval are
different claims; the report already recognizes some of this distinction.

Required correction: report capabilities from the admitted binding and supported
primitive fields. Reject an active unsupported requirement, or expose a precise
gap where partial playback is permitted. Keep historical import vocabulary at
the boundary. No silent fallback, false global completion or new executor merely
to satisfy unused schema fields.

### R9 — repeated walks obscure who owns the playback clock

**Medium priority; E6 and overall finding 7.** Condition, spatial, concentration
and construction registration each traverse choreography/movement/reaction
nesting. `choreography.py` and binders also repeatedly reconstruct ancestry and
states around individual nodes. This is a source duplication finding; no speed
or memory measurements were made.

Required correction: index causal/version relationships once for a received
group; one compiler binds timing, and one walker exposes its resolved nodes and
absolute offsets to the distinct lifetime policies. Do not merge those policies
into a universal condition system. A traversal-only extraction would leave
R1–R5 intact, so the earlier cleanup scope was insufficient.

## What belongs in facts, recipes and code

| Information | Owner | Must not be inferred from |
| --- | --- | --- |
| Which action/application caused a result | Native causality, disclosed in player facts | Presence of art, target equality, animation time |
| Exact HP/item/condition/placement change and order | Committed native result and permitted projection | Animation frame, current live Entity, future final snapshot |
| Which instance owns a persistent effect | Existing condition/slot/item/field identity | Spell name, same geometry, nearest actor |
| Release/contact/formation/state-clear milestone | Existing authored recipe plus shared compiler | New gameplay events with frame numbers |
| Sprite bank, facing, pivot, palette, frame selection | Admitted presentation data | Concrete spell or weapon classes |
| Interpolation, sampling, clipping, XYZ/depth composition | Shared rendering primitives | Per-spell corrective branches or a JSON scripting language |

An example: one cast has two applications and each application can have several
committed results. Their links stay the same if one projectile is slower, two
targets share a contact time, or one animation is missing. The compiler resolves
the contact milestone for each application; HP/feedback follows its actual
result links. It never discovers those links by comparing the resulting times.

## Review boundary

These findings justify an amendment to the existing cleanup plan, not a new
renderer or immediate changes to accepted footage. The larger original review's
item, movement, action-economy and scope-removal findings still stand. Two author
self-review passes are recorded in the plan. The user subsequently required two
independent approvals. Both reviewers approved the revised design after
corrections; the [review receipt](ANTISLOP_CLEANUP_PLAN_REVIEWS_2026-10-03.md)
identifies the exact revision and limitations. Other agent coordination remains
stopped. Plan approval does not certify implementation correctness.
