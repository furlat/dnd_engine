# Whole-codebase machinery audit — September 12, 2026

**This is a critical design/work failure in the recovery, not an isolated coding
slip.** The rollback retained substantial defensive infrastructure, and later
work both preserved that infrastructure and added repeated work of its own.
Working animations and passing tests did not establish that the overall design
served a fast, scalable game. Treating them as sufficient evidence allowed the
recovery to repeat part of the failure it was supposed to escape.

**Implementation remains stopped.** This audit performed source/history study
and documentation only. No further game changes, tests, benchmarks, generators
or rendering were run after the audit stop. Earlier uncommitted changes remain
for review; they are not an accepted performance solution. The branch is
`codex/recovery-design`, checkpoint `14b27f7`.

## What went wrong in the work, with concrete evidence

| Decision pattern | Evidence in this recovery | Consequence |
|---|---|---|
| Inherited implementation acquired authority without rechecking its purpose | Built-in source authentication, global pack rollback, fixed inventory counts and old server contracts survived July. Adding Dretch also updated the old roster count from 27 to 28. | New work complied with old machinery instead of questioning whether the game needed it. |
| A passing local test or visible clip substituted for overall design review | The startup failure was described as an eight-second budget miss before examining nearly four seconds of imports and over two seconds of native diagnostic setup. Ordinary drawing constructs expected/actual proof lists from the same draw commands. | Correct output and test agreement concealed unnecessary work and weak evidence. |
| The first available optimization displaced the underlying question | The initial response to source authentication was to consider making the audit cheaper. The pending asset patch moved validation but left other runtime validators and added duplicate offline parsing. | The mechanism's premise survived, even when its implementation improved locally. |
| New connections repeatedly reconstructed already-available information | Capture rescans all native history per root; admissions refold from births; projection rebuilds world diffs after unrelated nodes; active reactions are sampled repeatedly; body media is decoded again at later heads. | Costs and maintenance obligations accumulate across individually plausible functions. |
| Review accepted the given framing too readily | Earlier reviewers checked preservation of exact validation behavior; the pending boundary optimization still constructs a key only to validate and discard it. | Review could confirm a patch while overlooking whether the obligation itself belonged there. |

The required change in judgment is to establish the actual game purpose and
owner of work before preserving or expanding it. This is not satisfied by a
new checklist, another assurance system, or a promise to be more careful. Each
proposed disposition below names a concrete mechanism and its real callers.
The pending changes were subjected to the same scrutiny as inherited code.

## Coverage: whole-source scan, targeted semantic review

All **1,031 Python/TypeScript/JavaScript source files, 530,068 lines**, tracked or
nonignored, were text-scanned. All Python files were AST-parsed with no parse
errors. Imports, definitions and hashing/validation/copying/serialization/
reflection/cache/filesystem/concurrency sites guided targeted owner and caller
reads. The source ledger names every file:
[SOURCE_SCAN_2026-09-12.csv](SOURCE_SCAN_2026-09-12.csv).

| Assigned scope | Files | Lines | Detailed report |
|---|---:|---:|---|
| Native rules, entity/event/condition/spatial systems, scenarios | 139 | 101,727 | [Native audit](NATIVE_RUNTIME_AUDIT_2026-09-12.md) |
| Content, authored composers, registries and durable models | 59 | 27,030 | [Content and test audit](CONTENT_AND_TEST_AUDIT_2026-09-12.md) |
| Native/remote AI, server, services, SDK including SDK tests/generated TS | 217 | 115,755 | [AI/server/transport audit](AI_SERVER_TRANSPORT_AUDIT_2026-09-12.md) |
| Game, presentation, devtools, executable documentation tools, setup | 57 | 20,791 | [Presentation/tooling audit](PRESENTATION_TOOLING_AUDIT_2026-09-12.md) |
| Main test tree | 378 | 177,253 | [Test findings](CONTENT_AND_TEST_AUDIT_2026-09-12.md#tests-can-preserve-the-wrong-premise) |
| Tracked archive | 181 | 87,512 | [Archive scope](CONTENT_AND_TEST_AUDIT_2026-09-12.md#archive-and-non-code-scope) |

Additional reads cover both HTML files, inline observer JavaScript, gallery CSS,
the archived shell API test, dependency/test configuration and relevant authored
JSON loaders/data. Generated descriptors were traced to their owners rather than
treated as thousands of separately authored decisions.

This is exhaustive source **scanning**, followed by targeted semantic review;
it is not a claim of independently proving every rule or manually reading every
line of every test. Binary sprites, lockfile entries and all historical Markdown
are not claimed as semantically audited. The reports explicitly identify those
limits and distinguish confirmed redundancy from an unresolved design question.

## Findings that affect the current game or presentation

The references in the last column name sections in the detailed reports. These
are dispositions for review, not an automatically authorized cleanup queue.

| Mechanism and actual cadence | Assessment | Evidence / disposition |
|---|---|---|
| Built-in import walks and hashes Python sources and a reference document | No required in-process gameplay purpose; major measured startup cost | Content C1. Already removed in pending edits at the user's request; incomplete validation, no cache replacement. |
| Trusted item visual ledger reserializes/hashes itself and recomputes historical collision/count evidence at import | The renderer needs its category/layer data, not a repeated historical audit | Native N01. Separate survivor after source-hash removal; presentation caller, not per-turn native hashing. |
| Asset loaders exhaustively resolve/stat/check shipped media; other drawing loaders still validate on repeated decode | Authoring checks and actual decode have been coupled | Presentation 8/10 and pending-patch review. Narrow loader edits do not finish the job; offline relocation also grew duplicated checks. |
| Whole installed content digest contains complete descriptors, including cosmetic metadata | Mechanical installation identity is coupled to descriptor presentation changes | Content C2. Review identity purpose/granularity. Necessary appearance/active-equipment facts remain game state. Arbitrary PNG edits are not in this digest. |
| Built-in-only bootstrap snapshots engine globals and enters external-pack rollback/cache-invalidation code | The protected external import is absent when there are no packs | Content C3. Confirmed empty-path work; small measured aggregate boot cost, substantial ownership coupling. |
| Internally built recipes are hashed at creation, model validation, resolution, materialization and binding; descriptors are dumped/rebuilt/revalidated | Multiple internal owners repeatedly prove data just constructed or accepted | Content C4. Review boundary and representation; explicit IDs and typed external inputs are different requirements. |
| Every terrain cell eagerly allocates four full modifiable-value graphs | Real terrain modification capability, expensive default representation | Native N04. Major measured construction cost; no replacement designed here. Shared mutable defaults would break cell ownership. |
| Boundary queries build complete edges/band snapshots, then discard unused fields or ordering | Repeated allocation in the native perception path | Native N06. High measured aggregate query cost; existing pending fast path is narrow and still preserves a validation-only allocation. |
| Native AI constructs remembered copies that `setdefault` immediately discards; movement guards rebuild the whole subjective world each step | Unused copies are demonstrably redundant; full projection is broader than the guard's actual question | AI A1/A2. Preserve actual new-threat/hazard/actor-state interruption rules and memory. No alternative sensing policy. |
| Native AI dumps engine outcome DTOs and validates mirror policy DTOs inside the same process | Duplicate schema/adaptation ownership; some primitive conversions are real | AI A3. Review actual differing fields before deciding what must remain. Existing caches/GC control compensate for allocation; another cache is not the default answer. |
| Every captured root rescans accumulated history and refolds actor admissions from births | Record-once lineage semantics do not require repeatedly rebuilding the same indexes and prior facts | Presentation 1. Preserve complete ancestry and acquisition-time privacy. No truncation or invented initialization state. |
| Public projection rebuilds world differences after unrelated action/roll/cost nodes | No world/sensory change occurred for many of those nodes | Presentation 2. Narrow cadence must retain the actual timing of sensory children and transient visibility. |
| Choreography binding repeatedly derives prefixes/subtrees/final states; active movement reaction is sampled three times; scene appearance is resolved repeatedly per frame | Same results are often recomputed within one compile/sample | Presentation 3/4/7. Different historical prefixes are necessary; duplicate derivation is not. Costs of these individual findings remain unmeasured. |
| Later heads decode/crop body rows already loaded earlier; catalog scans repeat for equipped items | Cross-head reuse is missing in actual media callers | Presentation 7/8. New gear needs new rows, not a full repeat of old rows. No new renderer or VFX work is required to understand this. |
| Normal drawing builds diagnostic expected/actual sets; ordinary interactive play retains a frame record every frame until exit | Test/review evidence production is in the default game loop and grows with session duration | Presentation 9. Some draw metadata serves real ordering/labels; expected/actual proof duplication and unconditional history are separate. |
| Frozen contact/item leaves are deep-copied; some actor-only sampling copies full world containers | Copy depth and scope exceed the mutation being performed in specific callers | Native N07; Presentation 5/6. Mutable latest/history containers and native event detachment remain necessary. |
| Constructor registration is followed by local compensating cleanup, including `BaseException` wrappers around simple modifier dictionary insertion | Generic failure defense has spread into concrete rules; larger owner-admission issue | Native N03. Distinguish arbitrary insertion-failure scaffolding from actual cancellation, concentration, linked-condition and deployment ownership. No broad lifecycle rewrite authorized. |
| Fixed counts (312 behaviors, 28 creatures) gate import; a parallel condition-effect catalog must be synchronized with executable rules | Historical census and catalog audit have become ordinary content-extension obligations | Content C5; Native N08. Counts are not rules. Effect profiles have cold registry/server consumers but do not execute current conditions or drive current playback. |
| Small validators, broad preview-cache signatures and reflection survive | Some are redundant, some protect real input/derived state, some are just readability debt | Native N05/N09; Presentation 10/12. Do not turn every scalar check into a new work item or infer timing from keyword counts. |

## Retained architecture that must not silently become current authority

The native controller is `dnd/ai`; it does not run the top-level remote `ai`,
HTTP server, TypeScript SDK or external policy service. Their code therefore
cannot be charged to native-turn timings. But it matters to the recovery because
reusing those owners without scrutiny would restore substantial old machinery.

The AI/server audit confirms these retained patterns:

- The old advanced policy reads and hashes 22 source files, then reads 15 partly
  overlapping implementation files, during import to authenticate its selected
  Python implementation.
- Server modules reread and rehash generated event manifests and generate/hash
  multiple schemas on import. Objective event capture deep-copies, serializes,
  validates, stores bytes that validate again, then validates again on reads.
- Server spatial memory stores JSON strings and rehydrates them for projection.
  Its separate objective, AI, player and replay journals have repeated guards
  and derived stores, including reverifying a batch against the engine callback's
  own event history.
- The SDK validates wire frames, checks continuity, compares serialized duplicate
  frames, then validates the whole locally reduced world. These layers answer
  different questions and cannot all be justified by the need to decode bytes.
- Old durable character types and an unused installed-creature materializer
  survive alongside current direct character composition.
- Static resolution found **15 distinct missing engine module targets** in
  retained server imports. The SDK generator already failed on `dnd.core.senses`
  before this stop. Restoring retired models to satisfy those imports would
  reconnect the architecture the recovery displaced.

The server and remote AI trees are effectively unchanged from `16a6bfe`, apart
from the pending obsolete artifact-field removal. This is inherited scope, not
an excuse. It establishes that rollback alone did not establish a clean base.
The detailed report records each stream's actual consumer instead of declaring
all perspective-specific state identical.

## What must survive the audit

The user's design remains the authority: native rules produce complete causal
lineages; existing subjective grants determine disclosure; complete received
lineages reduce independently of historical playback; recorded events are
sufficient for passive replay; Studio data and per-rig mapping drive shared
presentation. Legal origin and interrupted visual position can differ.

Those requirements explain some state and work that must not be removed by a
blanket "no copies/no validation/no hashes" campaign. Specifically:

- Event versions, parent/child relationships, source/provider identities and
  event-time visibility grants have actual causal consumers.
- Conditions, modifiers, handler receipts and source-owned removal preserve
  real rules, including reactions that interrupt movement or change life state.
- Latest, historical and sampled state represent different times. Sharing mutable
  containers between them would undo the independent-clock design.
- Detaching a native mutable event at the recording boundary and decoding actual
  incoming bytes are distinct from repeatedly verifying locally produced values.
- Pixel surfaces are mutable; copies before tinting can protect canonical assets.
  Optional gallery encoding/trace output is the requested review product.
- Secret-token/HMAC checks in retained networking code are unrelated to source
  attestation. Ordinary hash-map lookup is unrelated too.

These distinctions are not a defense of every current implementation. They name
what an eventual simplification has to preserve, without inventing new rules.

## Existing measurements: game, projection and rendering are different costs

No timings were collected during this audit. The prior evidence is retained and
must be read with its workload:

| Prior workload | Observation | Practical meaning |
|---|---|---|
| Old 64×64 map diagnostic, 12 frames | 8.897–9.000s whole process; representative import 3.897s, native production 2.457s, asset catalog 0.948s, decode 0.439s, drawing 0.348s, reduction 0.0006s | The process is far too expensive, but calling all nine seconds "rendering twelve frames" hides where work occurs. |
| Native-only four-actor encounter | Imports 10.789s; content installation after import 0.018s; setup 0.298s; roughly 4.10s for eight human turns plus native AI across four rounds and 1,175 event versions | No Pygame. Startup and steady native execution both need attention; they are not the same problem. |
| Instrumented native run | Source walk 6.825s; 812 Pydantic class constructions 3.749s; perception recomputation 6.218s; boundary-evidence 3.581s; world projection 2.209s | Profiler overhead applies. These nested spans overlap and cannot be added as promised savings. |
| Instrumented capture/projection variant, 83 roots | Capture 0.593s including admissions 0.337s; public projection 0.086s; public reduction 0.0056s | Source-confirmed repeated capture work is more significant here than the public reducer. |
| Historical compatible 4,096-tile rectangle, one sample each | Construction 1.817s at `14b27f7`, 1.675s at `16a6bfe`, 1.357s at April `2cc3f36` | Expensive tile representation predates recovery; earlier world/perception capabilities differ. This is not full game feature parity or proof of acceptable speed. |

The committed [startup profile](../STARTUP_PROFILE_2026-09-12.md) describes the
first workload. Native/profile/capture records are under
`.runtime/performance-recovery/` (`native-before.json`,
`native-profile-before.prof`, `project-before.prof`, `historical-grid.json`).
Historical snapshot execution used the same installed virtual environment;
the baseline's reference `.txt` was normalized to the existing working-tree
bytes to avoid its source-hash line-ending gate, and an empty configured pack
folder was supplied. No gameplay source was altered for those baseline runs.

A single pending-patch native sample completed before the audit stop: import
4.426s, setup 0.446s, with the same 1,175 event count. It is **provisional**, not
complete validation or an accepted recovery result. In particular setup was
slower in that sample; reporting only the import improvement would be selective.

## Pending edits are not exempt from this review

The source-hash removal is the user's already-authorized change, but its whole
consumer path is not fully validated. The asset patch removes measured runtime
filesystem checks yet leaves other loaders' checks/JSON conversion and introduces
duplicate parsing in its new offline validator. The native patch removes narrow
redundancies but leaves the expensive default graph representation, relies on
Pydantic empty-default copying and preserves a validation-only allocation. The
immutable item-copy change is narrower than the repeated-history capture owner.

Before the stop, one grouped run reported **208 passed / 13 failed**. The failures
are in external-pack tests: the run retained live engine state between groups,
and the logs also expose a stale private attribute. They were not rerun in
isolation, so the result must not be summarized as "all behavior tests pass" or
all failures dismissed as order-dependent. The log remains at
`.runtime/performance-recovery/first-pass-tests.log`.

Full SDK generation failed on a stale server import. The pending generated files
received a structural field removal using the existing generator's aggregate
hash rule; that is not full regeneration/parity. Final Pyright, offline asset
validation, targeted later changes and final serial comparisons were not
completed. No additional tests were run to bypass the user's audit stop.

## Review outcome and current boundary

The anti-slop reviewer audited native ownership and challenged the content/test
conclusions; the anti-OOP reviewer audited AI/server boundaries and challenged
content identity and presentation conclusions. Both were asked to distinguish
actual consumers from inherited assertions, and to critique pending work they
had helped produce. Corrections included moving the visual-ledger finding from
native gameplay to presentation, distinguishing cosmetic metadata from PNG
bytes in the content digest, and recognizing condition profiles' cold dependency
outputs without claiming they execute rules.

The audit establishes enough to reject continuing feature work on the previous
assumptions. It does not certify the codebase clean, promise all possible waste
is located, or authorize a mass rewrite. The next decision is which concrete
owners and obligations should be simplified, based on these findings. No
implementation order, replacement framework or new repository skill has been
silently adopted. Implementation stays paused for review of this result.
