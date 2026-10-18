# Native Bevy exposure contract review — 2026-10-16

This is an independent antislop/antiOOP review of the source findings in [foundations](foundations.md), [spells](spells.md), [features/world](features-world.md), and [content/grants](content-grants.md), against [the proposal](../../BEVY_REACTIVE_ENGINE_DESIGN_2026-10-16.md). Those reports supply the gameplay inventory; this review checks the native exposure required by their concrete counterexamples. It does not turn their selectively inspected transitive callees or inventory-only action bodies into complete coverage. No production code, tests, probes, dependencies or original proposal were changed. No new executable qualification was performed.

## Verdict and evidence levels

**No public-API expressibility blocker was identified for the reviewed condition/handler families. Full semantic fidelity and parallel execution are unqualified.** The defensible claim is that concrete native Bevy systems can receive typed invocation data, query and mutate native components/resources, return typed receipts/results, and resume from explicit typed pending state. It is not a claim that arbitrary source callbacks become correct by giving them `&mut World`.

Keep three claims separate:

| Claim | Evidence and limit |
|---|---|
| Public API expressibility | Confirmed against local `bevy_ecs-0.20.0` source for typed input/output systems, mutable borrowed input, ordinary/exclusive execution, component lifecycle hooks and registered-system limitations. Concrete storage models below cover the discovered state/identity requirements. |
| Audited semantic fidelity | Source reports establish what must be preserved. Existing compiled toy probes establish only their named mechanisms. **No complete translated gameplay family is qualified by this review.** |
| Parallelizability | Ordinary query systems expose scheduler access. Direct `World::run_system_with`/safe `System::run` execution uses exclusive world access; `Commands::run_system_with` is explicitly exclusive. Even scheduled query systems require actual nonconflicting access plus domain ordering. No multithreaded gameplay result or speedup follows. |

Natural native Bevy translation is the default. Rewriting a badly coupled source mechanism is an escape hatch for a demonstrated integration corner, while preserving supported rules; this review does not authorize proactive cleanup or Python edits. The proposal already contains working-view modes, exact selected-execution lifetime, provisional claims, typed continuations and the Shield ignored-child-result exception. These are existing design obligations, not new impossibilities. Its broad “structurally possible” conclusion must remain conditional on the unresolved semantic cases below.

## Public native execution surface

Checked actual source under `/tmp/bevy-ecs-ownership-study/bevy_ecs-0.20.0/src/`:

- `system/system.rs:45–145`: `System` has associated `In` and `Out`, `initialize`, `run`, `run_without_applying_deferred`, and `apply_deferred`. Successful `run` applies deferred parameters before returning. A domain pending result can be returned through `Out`; Bevy does not interpret it as game completion.
- `system/input.rs:222–250`: `InMut<'_, T>` wraps an invocation-lifetime `&mut T`; tuple system inputs can combine borrowed event input with owner data, as the existing probe does. It is a synchronous borrowing facility, not permission to retain a component reference across queued work.
- `system/system_registry.rs:456,673–740`: `World::register_system` returns typed `SystemId<I,O>`; `World::run_system_with` accepts `I::Inner<'_>` and returns `Result<O, RegisteredSystemError<I,O>>`. It takes the running instance out, so direct same-ID recursion returns `SystemMissing`; it restores the instance before flushing queued commands.
- `system/commands/mod.rs:864–891`: `Commands::run_system_with` takes `'static` input, offers no output to the caller, and executes exclusively/single-threaded. A producer needing a child result must use an explicit result record/continuation, or a synchronous native call. Merely queuing a registered system is insufficient.
- `system/function_system.rs:931–975`: native function/closure systems accept `FnMut` with `Send + Sync + 'static` bounds. This allows suitable owned captures but does not expose captured world reads to scheduler conflict analysis. Per-installed gameplay state should be typed ECS data, especially if processor instances are pooled or shared.
- `lifecycle.rs:84,153–250`: `ComponentHook = for<'w> fn(DeferredWorld<'w>, HookContext)`, returning unit. Storage hooks are add/insert/discard/remove/despawn. `on_insert`/`on_discard` do not run on an in-place query mutation. They neither return admission results nor implement a queued gameplay callback protocol.
- `observer/mod.rs:54`, `observer/runner.rs:181`: exclusive observer systems are rejected. The proposal's existing default-order/command-timing/custom-trigger negative evidence remains applicable; this review adds no observer workaround.

Pinned upstream counterparts: [System](https://github.com/bevyengine/bevy/blob/v0.20.0/crates/bevy_ecs/src/system/system.rs), [input](https://github.com/bevyengine/bevy/blob/v0.20.0/crates/bevy_ecs/src/system/input.rs), [registry](https://github.com/bevyengine/bevy/blob/v0.20.0/crates/bevy_ecs/src/system/system_registry.rs), [commands](https://github.com/bevyengine/bevy/blob/v0.20.0/crates/bevy_ecs/src/system/commands/mod.rs), [lifecycle](https://github.com/bevyengine/bevy/blob/v0.20.0/crates/bevy_ecs/src/lifecycle.rs). Actual local source, rather than an assumption about latest Bevy, was the API authority.

The exposure can use typed native registration components for each concrete processor family, with `SystemId<In<FamilyInvocation>, FamilyResult>` where synchronous dispatch is appropriate; scheduled queue consumers instead write their typed result components. Separate input/output families do not require a universal effect interpreter, plugin ABI, domain trait-object hierarchy or reflection router. `Box<dyn System<In=..., Out=...>>` at the optional native execution seam is Bevy execution machinery, not a `dyn Condition` gameplay model.

## 1. Condition installation, commitment and removal

Expose concrete systems for prepare/install, commit membership, publish committed consequences, cancel preparation, release owned runtime state, prepare/validate/commit removal, and settle/publish removal scope. They need not all be separate functions for trivial conditions, but their domain boundaries must remain distinguishable. Native storage insertion and command flushing do not merge them into one successful operation.

Inputs carry exact source/recipient/condition identities, causal event, replacement/terminal-release context and typed rule configuration. Keep a typed condition header and recipient indexes for the actual name/key/tag/source queries as well as concrete payload components. `With<PronePayload>` alone does not replace a recipient lookup by `active_conditions["Prone"]`, nor same-name replacement rules. Behavior is distributed beyond condition classes: the standard actor handler `actions_functional._create_prone_auto_stand_handler:134–178` (directly checked) spends half base movement and removes named Prone at TURN_START/Effect. Include standard/global handler installation and these semantic indexes in exposure, rather than attributing all behavior to the Prone condition payload. Outputs or pending records retain exact installed artifacts: `(value ID, modifier ID)` pairs; handler registrations and spatial registrations; action/template/source IDs; capability/immunity/light tokens; linked condition and slot claims; family-specific displaced state. Validate receipt ownership before teardown where the source does so. Permanent grant receipts are concrete family data, not forced temporary conditions.

One modifier identity can be installed in multiple speed values (Fast Movement, Field Focus). Removal must remove every recorded pair and unregister that modifier once; a one-modifier/one-owner assumption fails. Shared learned reactions need source-set ownership, last-source handler release, prior enabled state, and restored dispatch order. Rage/Frenzy and sorcerer template displacement need the original UUID/list position/configuration. Bevy entities or allocation order cannot substitute for those domain identities.

Application failure cleans up what the source actually cleans up. Prone spends movement before cancellation; Exhaustion can cause death during provisional install; Dashing membership earns turn-owned credit that removal does not refund. AegisTraining mutates action registration during `_apply` without a corresponding provisional-release override; AegisSpark removes the old ward before independently adding the new one. Do not promise transaction-wide rollback or universal atomic replacement. Shield's ignored buff-admission result is already explicitly preserved in proposal §14; DeployFieldFocus/AegisSpark need the same discipline about ignored returns.

Native access: small value-map installers/removers can use typed `Query` plus exact indexes; graph/slot/return-cell admission owns the relevant typed graph and reservation data. An exclusive native owner operation is a valid initial implementation choice, but proving it accepts a graph and compensates its actual partial failure still requires gameplay cases.

## 2. Ordered mutable, replacement and pending handlers

Expose an installed handler record with stable handler UUID, exact processor registration, configuration/state handles, mutable dispatch rank, trigger data and explicit policies. Keep the selected invocation separate: current accepted event/version or working view, selection position, original identity/lineage, emitted-descendant membership and pending dependency. A handler can serve another event while its first invocation waits; pending data cannot be a singleton field on the installed handler.

A synchronous concrete processor can take `InMut<Attack>` and return `Option<Attack>`, or receive handles and mutate canonical typed components. A queued concrete processor returns/writes either a settled rule result or a pending continuation identity. This is an exposure description, not a newly compiled universal enum/interface. Preserve all three independent facts: in-place mutation, replacement return, and side effects. `None` means no replacement, **not** no world/resource/RNG/evidence change.

The domain dispatcher selects once in actual bucket/cell order and rechecks the source's live enabled/trigger/contribution policies before invocation. Accepted replacements, reposting and cancellation short circuit remain publication-mode operations. Only source APIs that actually invoke committed-notification dispatch use isolated per-handler deep working views; ordinary condition Effect uses its distinct shallow unpublished view; preflight prohibits child publication. Publication mode follows the actual producer API, not an event being described as factual/post-commit. In particular, `Entity._complete_damage_applied_event` (`dnd/entity.py:3583–3643`, directly checked) uses ordinary `phase_to` for Execution/Effect/Completion after HP commitment. Native exposure must accept returned DamageApplied annotations such as `body_release` and `concentration_broken`; it must not impose generic factual-event immutability. These policies cannot be inferred from Bevy `On<Event>` or from mutable input alone.

Removing a registration prevents future discovery immediately; retain selected state/configuration for the source-permitted already selected invocation. Completing a synchronous native system is not sufficient to release that retained state if it returned a pending child. Full native handler destruction must wait for those actual selected invocations to settle.

## 3. Cleanup owner, provenance and contribution gate are distinct

Do not derive all ownership from one relationship. The necessary records distinguish installing/cleanup owner, stable source/effect provenance, optional contribution-gating owner, source-set provider tokens, membership and selected-invocation lifetime. Their links may coincide, but none implies the others universally.

Concrete counterexample: the late Concentrating damage/death handler records exact cleanup ownership but has no `contribution_owner_uuid` and does not set `runs_while_suppressed`; BaseBlock registration does not add a contribution owner. Auto-gating every installed handler with its installing condition changes this source behavior. Invisibility reveal explicitly runs while suppressed; Greater Invisibility's check does not. Antimagic-return handlers belong to creation/existence owners, while vent-created gas can outlive the vent.

Provisional contributions must pass their actual registered-owner/parent/provider gate before membership commit when the source allows it. A universal `With<Applied>` query filter is incorrect. Conversely, retained history payloads cannot automatically regain active authority. Use explicit contribution validity and exact map/index removal, without inferring either from physical record existence.

## 4. Capture state, live values and aliases

| Source capture | Concrete native exposure |
|---|---|
| Immutable configuration/DC/ContentRef/source IDs | Owned typed installed configuration; retain stable IDs when optional live entities disappear. |
| Mutable installed counters/flags | Per-condition/handler state components: Guiding Bolt remaining ends, Divine Word rounds, expiry armed state, Greater Invisibility check count. No shared processor `Local` for unrelated installations. |
| Live Strength or Shield/Mirror Image modifier | Explicit stable typed value/modifier handle, resolving the current record at evaluation. Copying its numeric value at install loses later mutation. |
| Globe/Antimagic current footprint | Query the condition's current footprint handle and its current set. |
| Silence retained set alias | Source-level alias warning: its blocker captures the original set object, whereas live footprint consumers resolve the current set. This does not establish a supported movable-Silence rule or require a new alias-record mechanism. |

Silence source explicitly describes an established fixed origin (`illusion.py:1274`). Read existing `test_silence_zone_deafens_blocks_verbal_and_cleans_up` (`tests/manual/test_134_cleric_batch1_legacy_contract.py:691–760`) and shared-sensory tests: they support verbal blocking/nonverbal casting, overlapping memberships and exact cleanup. They do not establish blocker behavior after replacing or relocating the zone footprint. Therefore use ordinary fixed-zone typed data for the supported rule first; do not invent movable Silence or an alias-record framework for a latent implementation path. If a real integration case requires footprint replacement, compare that case against authored rules/tests before choosing current-footprint lookup or a retained-set handle. The latter is publicly expressible native data if actually needed, not a prerequisite or a proven defect. Mutable counters and live numerical captures above are concrete observed requirements independent of this conditional alias concern.

## 5. Nested outcomes and guards spanning queued jobs

Pending native records must own the original cause, exact child request/result identities, stage/cursor, authored state and cleanup guard. Borrowed world/component references and active Bevy system instances end before yielding. On resume, query the actual live state where the source does so; a completed child may have moved/removed the recipient, changed sight, spent resources or removed the producer.

Guardian of Faith needs actual completed applied damage associated with its damage operation before updating one shared budget and admitting later dependent triggers. A typed damage receipt carrying exact completed results can replace its incidental global-cursor scan when integrating queued execution; preserve applied-versus-requested accounting and authored ancestry membership. A global history cursor interval cannot attribute unrelated interleaved roots. Gust of Wind's `(zone,target)` in-flight guard persists until the nested save/movement and continuation settle or fail, matching source `finally`; releasing it at submission permits extra pushes. A selected pressure-plate output tuple and cursor survive nested release and still emit later originally selected pulses. Panicked/Flee resume after movement before applying turn restrictions or using new sight.

A readiness edge must name the consumed boundary: settled damage, accepted save, committed geometry, refreshed sight, graph settlement, or exact return reservation. Bevy schedules order systems, not arbitrary individual records automatically. Native `Commands` provides neither result ownership nor this semantic readiness. Default-error logging for queued registered calls cannot silently replace source-required failure propagation and guard cleanup.

Direct synchronous accepted-result operations remain possible through public `System` execution, releasing borrows before nested calls and querying again afterward. The existing inactive-native-instance cache proves its particular recursive seam. It does not prove any of the queued guard/continuation cases above, and pooling must never pool gameplay capture state.

## 6. Lifecycle exposure beyond EventHandler

Expose these as ordinary concrete native systems, with typed configuration/state and exact registration tokens only where registration exists in the source. They need not be Bevy storage hooks and should not be routed through ordinary interception merely for uniformity.

| Actual seam | Boundary and native exposure |
|---|---|
| `actions.py:440`, Telekinesis `transmutation.py:1678–1701`: `on_landing` | Invocation-specific native landing processor runs after admitted movement but before ForcedMovement completion and paid-entry retreat resolution. Only when endpoint changed; custom callback replaces default fall branch. Retain landing result/caster/target/DC/effect origin. Telekinesis orders force damage, bludgeoning damage, fall damage, then conditional Dex save/Prone. End movement completion waits through those required children. |
| `BaseCondition.on_membership_changed`, `BaseBlock.on_world_placement_committed` | Invoke concrete membership/placement systems after the corresponding authoritative index commitment and inside that exact cause. In-place placement mutation does not invoke `ComponentHooks::on_insert`; generic next-pump Changed filtering is not equivalent. Continual Flame/debris/return updates have causal completion requirements. |
| `BaseBlock._removal_participants` | Explicit prepare/validate/cancel/commit domain stages with typed family receipts and return-cell claims. No veto through `on_remove`, whose return is unit and whose storage operation is already underway. |
| `condition_removal_scope` settled hooks | Outer scope retains all nested receipts, calls every registered settled hook, attempts deferred removal completions, and aggregates failures while continuing required cleanup. A schedule `.chain()` alone does not create that scope or exception policy. |
| Spatial restraint pre-completion repair | Recreate/rebind the shared manifestation from surviving source leases before parent completion; retains canonical parent identity and must await replacement admission. This exceeds shared-child despawn prevention. |
| Summoning admission/direct Effect/pre-completion/close | Summoning registers separate validator, direct admitted cast processor, removal participant, settled hook, pre-completion system and game close callback. Native systems must retain each authority and failure boundary, including exact selected action identity and immediate agency revocation before deferred roster leave. |
| Optional passive observation | Native observers are appropriate only where the source permits optional failure isolation and no authoritative acceptance/result dependency. Their use does not grant purity or game-completion authority. |

Component storage hooks remain useful for exact indexes and mechanical structural invariants after admitted domain decisions. The public hook set is not an API for all source lifecycle methods.

## 7. Per-evaluation callbacks and evidence mutation

Expose a typed evaluation context carrying current source/target, event/cast/application lineage, condition/save/weapon interaction context and required world inputs. Concrete evaluator systems query their actual equipment/armor/ability/sunlight/sight/membership/adjacent-agency inputs. Returning a number is insufficient: return or write the exact explanation/result evidence for that evaluation identity.

Source contextual evaluation recomputes on repeated accesses, writes last-result evidence and has a permissive exception/logging boundary; strict callable execution is a separate boundary. Preserve those policies per consumer. Do not collapse duplicate accesses, memoize by installation, treat every contextual callable as pure, or let one concurrent invocation overwrite another's evidence. A composed result can use several evaluations in observable order. Greater Invisibility reads that evidence to decorate/complete its nested roll.

A narrow evidence-commit system can retain the source-compatible latest-result view while each in-flight evaluation keeps its own result. This is a proposed concrete representation, not proof that every current evidence-reading path has been migrated. RNG and stateful callbacks declare mutable component/resource access. Merely hiding a closure behind a function pointer does not expose its world dependencies to Bevy's scheduler.

## Remaining qualification and design corrections

1. State the separate cleanup/provenance/gate identities explicitly, including Concentrating's ungated late handler and shared learned-reaction ownership.
2. Preserve observed live values and per-instance mutable captures; prove owner/handler removal while a selected invocation still retains state. Classify Silence aliasing as a conditional implementation corner, without inventing a movable-zone contract or framework.
3. Specify concrete direct lifecycle exposure, particularly Telekinesis landing, placement, removal participants, graph-settled cleanup and restraint pre-completion repair. Select publication modes by actual producer APIs; keep ordinary DamageApplied annotations accepted after HP commitment.
4. Qualify Guardian applied-budget accounting and Gust guard lifetime under interleaved queued children/failures; distinguish “child finished” from “child succeeded.”
5. Qualify exact typed receipts/shared modifiers, provisional exceptions, actual nontransactional authored side effects, and template/source restoration order.
6. Qualify repeated contextual evaluation and evidence isolation with live equipment/senses and source-compatible exception paths.
7. Preserve the companion reports' larger unqualified cases: Frightened source transfer/retreat history, multislot concentration/return reservations, shared Harm/Feast winner and HP updates, Antimagic presence returns, overlapping material admission, summon existence/control and progressive retirement.

These are finite source-backed exposure/qualification obligations. Do not respond by building a universal callback framework, generic effect transaction log, custom unsafe observer runner, actor hierarchy, or global owner cascade. Begin with ordinary native typed systems/components/resources and preserve exact boundaries. Schedule parallel work only where actual native access and these domain dependencies permit it; the current reports/probes establish no general parallel safety or performance advantage.
