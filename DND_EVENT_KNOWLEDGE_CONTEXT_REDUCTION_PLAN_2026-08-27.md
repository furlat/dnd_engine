# Event knowledge-context reduction plan

Date: 2026-08-27
Status: candidate; no implementation is authorized by this document
Consumer: `DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md`

## 1. Relationship to the earlier study

This is a separate replacement candidate for the reduction-specific design in
`DND_EVENT_REDUCTION_FIRST_PRINCIPLES_STUDY_2026-08-27.md`. The earlier file is
preserved unchanged because its engine inventory, perception analysis, and
edge-case catalogue remain useful evidence. Its canonical-view architecture
does not govern this candidate.

The earlier study made censorship an endomorphism only after converting real
mechanics events into a second `CanonicalEventView` universe. That avoided
parallel objective and subjective DTO families, but it still duplicated the
event ontology:

```text
AttackEvent             <-> CanonicalKind.ATTACK
real event fields       <-> FactAtom values
real event inheritance  <-> a second dispatch vocabulary
```

This candidate rejects `CanonicalEventView`, `CanonicalKind`, `FactAtom`,
projection-native event identities, and per-family normalization into a
second schema.

## 2. Outcome

Reduction is an information-context operation over the existing event
algebra. The engine produces real `Event` subclasses. Capture freezes those
same concrete values once. Objective and subjective consumers read the same
captured event through different knowledge contexts.

```text
authoritative EventQueue
    -> one detached capture of each real Event subclass
    -> EventKnowledge[E]
         -> TOP knowledge for objective diagnostics
         -> party knowledge for ordinary presentation
    -> existing-event subclass dispatch
    -> scene, animation, text, and receipts
```

Conceptually:

```text
AttackEvent[Identity] -> AttackEvent[Knowledge]

Knowledge[T] = Known(T) | Unknown
```

Python does not need a higher-kinded-type framework to express this. The
practical implementation is one small generic reader around one detached event
reference plus an immutable readability mask. It never copies event fields
into a parallel event model.

The user and renderer are not adversarial. The purpose of `Unknown` is to make
subjective correctness explicit and catch accidental reads. This is not a
security, sandboxing, serialization, or cryptographic boundary.

## 3. Governing principles

1. **The event subclass is the semantic type.** `AttackEvent`,
   `StepMovementEvent`, `SensoryUpdateEvent`, and the other real subclasses are
   the only event dispatch identities.
2. **The value exists once.** A captured event field remains on the captured
   event. A knowledge context says whether a consumer may read it.
3. **Unreadable is not absent.** `Unknown` differs from `Known(None)`, an empty
   tuple, zero, `False`, or an event that never happened.
4. **An occurrence may itself be unknown.** An entirely unperceived event
   produces no ordinary delivery. A perceived event may still have unreadable
   participants, positions, rolls, or consequences.
5. **Objective and subjective use the same operation.** Objective diagnostics
   use top knowledge; party presentation uses the join of the two controlled
   observers' knowledge.
6. **Perception is computed once.** `SpatialSensesSystem`, its frozen
   event-time evidence, and its `SensoryUpdateEvent` after-values are the sole
   authority for sight, effective light, contacts, invisibility, and special
   senses. Reduction does not perform FOV, lighting, stealth, or range rules.
7. **Late knowledge opens real source values.** First sight of an entity or
   tile exposes selected fields on already captured real events. It does not
   manufacture an `EntityDisclosureView` or a second snapshot DTO.
8. **Current state and remembered knowledge are distinct.** Sensory deltas
   determine what is currently visible or contacted. Previously delivered
   terrain or appearance may remain remembered without claiming current
   presence.
9. **No live mechanics reads after capture.** Presentation and reduction may
   read the detached event archive and replay state, but not live `Entity`,
   `GridMap`, `Encounter`, registries, controllers, or `Senses`.
10. **Missing information stays unknown.** A missing rule or missing
    event-time fact is reported; it is never repaired by querying live state or
    inventing a best-effort value.

## 4. Current engine facts this plan relies on

### 4.1 Real event identity and lifecycle

`EventQueue` already stores concrete subclasses across `DECLARATION`,
`EXECUTION`, `EFFECT`, `COMPLETION`, and `CANCEL`. Every phase version has its
own UUID and shares a lineage UUID. The queue also stores parent/child
causality and closed nested batches.

The stored objects are not archival immutables: parent child lists can be
updated after an earlier version was stored. Capture must therefore deep-copy
the exact closed source range once the outer batch ends. The copied object is
still the same concrete event subclass; it is not normalized into another
type. Current Pydantic event models remain mutable even after
`model_copy(deep=True)`. The archive therefore owns each detached snapshot and
treats it as logically immutable; neither reducer nor reader may mutate or
expose the snapshot itself.

### 4.2 Event-time observer evidence

Before storage, `SpatialSensesSystem` records on events:

- participant identity grants;
- participant current-location grants;
- independent coordinate grants;
- affected positions and perceivers for logs.

These maps answer whether a particular observer could identify or locate a
particular participant or coordinate at that event boundary. They do not need
to be recomputed by presentation.

### 4.3 Replayable sensory state

`SensoryUpdateEvent` already records observer-specific after-value deltas for:

- observer position;
- visible and explored cells;
- observer-effective light;
- entity and object contacts;
- visual versus special-sense contact mode;
- sense modes, passive perception, and visual-access changes;
- path-dirty state.

`Senses.apply_sensory_update()` demonstrates replay from those deltas without
consulting the current map. The knowledge reducer must reuse that replay
semantics rather than recreate it.

### 4.4 Cold and incremental source facts

The accepted Tile/world-item migration made real engine events carry
renderer-neutral committed facts:

- `WorldInitializedEvent` carries tiles, world objects, connectors, bounds,
  elevation, surface, and light state;
- `EntityCreatedEvent` carries stable identity, appearance semantics, owned
  mechanics, items, and equipment;
- spatial, item, condition, entity, and life-state events carry committed
  after-values;
- `StepMovementEvent` carries committed endpoints, trajectory, disclosed
  geometry, and endpoint elevation;
- sensory events carry subjective access changes at the correct event-system
  boundary.

The knowledge layer indexes these source values. It does not translate them
into new fact-record classes.

## 5. Minimal information-context types

Only four small concepts are required.

### 5.1 `Knowledge[T]`

The read result is a closed sum:

```text
Known(value: T)
Unknown(reason_code)
```

`Unknown` contains no substitute value. A compact reason code exists for the
developer trace, such as `EVENT_NOT_PERCEIVED`, `IDENTITY_NOT_KNOWN`,
`POSITION_NOT_KNOWN`, `NOT_CURRENTLY_VISIBLE`, or `NO_RULE`. It is not a
second payload and ordinary rendering must not turn it into guessed content.

### 5.2 Detached source archive

Each captured source slot owns exactly one detached deep snapshot of the
mechanics event:

```text
CapturedEvent[E]
    source_index
    snapshot: E
```

`E` is the real concrete subclass. The archive is the only retained event
payload store used by reduction and presentation. Objective diagnostics and
party presentation refer to the same archive entry. Logical immutability is
an ownership rule verified by mutation-canary tests; this plan does not add a
proxy freezer or mirror model merely to make the Pydantic object physically
frozen.

### 5.3 `EventKnowledge[E]`

The knowledge value contains:

```text
EventKnowledge[E]
    captured_event_reference
    immutable readable-path mask
```

It exposes:

```text
read(path) -> Knowledge[object]
known_items(collection_path) -> the authorized source elements only
event_class -> type[E]
source_index -> int
```

`read()` is deliberately runtime-typed. Python erases `E` on
`EventKnowledge[E]`, and this plan does not compensate with generated
overloads, typed field-token mirrors, or lenses. The concrete-class handler
knows the expected source field type, validates/narrows the returned object,
and reports a contract error on mismatch.

It does not expose a public raw-event escape hatch to ordinary presentation
code. Because this is an in-process correctness boundary rather than an
adversarial one, a private reference plus architecture tests is sufficient.
There is no proxy-hardening framework, serializer, capability service, or
event-shaped copy-on-read layer.

Paths identify fields and collection elements on the existing typed event
models. They do not define new field values or a second schema. A parent path
with mixed readability returns `Unknown`; consumers read its independently
authorized children or authorized collection members. Enumerating an
authorized collection does not expose hidden keys, elements, or counts.

Only reviewed cold leaves and reviewed collections of cold leaves are
readable. Event methods are never called by reduction or presentation.
Callables, mutable mechanics owners, `BaseObject` graphs, handlers, arbitrary
`context`, `ModifiableValue`, dice/damage behavior objects, and live condition
objects are not readable as whole values. If presentation information exists
only behind such an object, the authoritative domain event must be enriched
with a committed scalar or existing typed cold record at its current owner
boundary.

Mutable list/dict/set objects are never returned from the archive. A reviewed
collection read exposes a deterministic immutable tuple, frozenset, or
read-only sequence of the exact admitted source elements. Mutable nested
elements are not admitted wholesale; their cold leaves are read separately.
This defensive container does not create a second event or semantic value
model, and object identity of a source container is not a contract.

The implementation plan may choose the smallest typed path spelling supported
cleanly by Python and Pydantic. It must not build an HKT emulation library, a
lens framework, generated mirror classes, or a generic recursive serializer.

### 5.4 Delivery envelope

One presentation delivery needs only queue metadata around an
`EventKnowledge[E]`:

```text
EventDelivery[E]
    delivery_id
    batch_id
    knowledge: EventKnowledge[E]
    disclosure_cause_source_index?
```

Ordinary occurrence delivery has no disclosure cause. Late disclosure points
to the current sensory or state-change source slot that opened knowledge of an
older captured event. This distinction prevents a historical
`EntityCreatedEvent` from replaying a birth animation when it is first seen;
it is applied as idempotent scene state.

The envelope does not introduce another event kind, payload, lineage, or
identity system. `event_class` and every semantic value still come from the
captured real event.

## 6. Formal model and laws

Let:

- `A*` be closed sequences of captured real mechanics events;
- `M` be the source archive and its field-provenance index;
- `K_o` be replayed knowledge for controlled observer `o`;
- `P = {hero_a, hero_b}` be the controlled party;
- `J_P` be field-wise party knowledge join;
- `D*` be sequences of deliveries of actual event subclasses under knowledge.

Reduction is:

```text
(M, K_a, K_b, next closed source batch)
    -> (M', K_a', K_b', zero or more EventDelivery[E])
```

It must satisfy:

1. **Type preservation:** every delivery of source event `e: E` dispatches as
   `E`; no new semantic kind is introduced.
2. **Source-value preservation:** a known cold scalar or immutable value is
   value-equal to the selected captured source value. A collection contains
   exactly the authorized source elements in deterministic immutable form.
   Reduction does not reinterpret semantic values.
3. **Single storage:** objective and subjective views reference the same
   captured source value.
4. **Top identity:** every admitted field read under objective top knowledge
   returns `Known(source_value)`.
5. **Idempotence:** applying the same knowledge mask twice changes nothing.
6. **Mask composition:** sequential restrictions equal intersection of the
   corresponding readable paths.
7. **Party join:** a path is party-readable exactly when at least one
   controlled observer can read it; the value is the same source value.
8. **Known-null distinction:** `Known(None) != Unknown`.
9. **Occurrence distinction:** no delivery is different from a delivered
   event whose every requested field is `Unknown`.
10. **Collection law:** an authorized collection contains only exact source
    elements whose keys and values are authorized; it does not expose hidden
    cardinality.
11. **Replay law:** replaying captured sensory deltas from the exact cold seed gives
    the same observer knowledge used by online reduction.
12. **No-live-read law:** replacing every live-world accessor with a failure
    after capture does not change reduction or presentation output.
13. **Order law:** occurrence deliveries preserve source order; disclosures
    occur at the source boundary that grants them and retain their original
    source index as provenance.
14. **Current-state law:** losing current visual/contact access removes current
    scene presence even when historical intrinsic knowledge remains known.

## 7. Capture, lifecycle, and causality

For every accepted mechanics decision boundary:

1. record EventQueue generation and source cursor;
2. execute the complete mechanics boundary inside the existing outer batch;
3. record the exclusive source cursor after the batch closes;
4. deep-copy each source event in that contiguous range exactly once into the
   archive's logically immutable ownership;
5. record objective combat-log slots created in the same boundary;
6. verify generation, contiguity, and uniqueness;
7. update source-field provenance and observer replay in source order, while
   staging pre-completion sensory disclosures as described below;
8. resolve every staged disclosure against its exact causative terminal fact;
9. produce one presentation batch of occurrence and disclosure deliveries.

`SensoryUpdateEvent` is intentionally emitted before its causative parent
completion is stored. A sensory delivery therefore must not blindly open the
latest provenance available at its earlier source slot. Within the closed
batch, reduction stages that disclosure through `cause_event_uuid` and parent
lineage, resolves the matching terminal committed event version, and samples
that causative after-state while retaining the sensory source boundary as the
delivery cause. Missing or ambiguous terminal facts are fatal. The resolver
must never sample an unrelated later change to the same subject in the batch.

The objective event trace may show every phase version. Ordinary presentation
does not need a second lifecycle model. Its class policy marks each actual
source version as one of:

- terminal semantic occurrence;
- committed per-step occurrence;
- direct subjective state delta;
- lifecycle/technical source slot with no presentation delivery;
- unperceived occurrence.

These are coverage dispositions, not event kinds.

Raw parent and lineage identities remain on the captured event. If a visible
child's parent occurrence is not delivered, the parent path is `Unknown` and
the presentation scheduler treats the child as a local root. No synthetic
projection IDs or graph-reparenting objects are required.

## 8. Dispatch and policy ownership

Both reduction and presentation dispatch on the exact concrete event class.
One internal router reads `type(captured.snapshot)` solely to choose the
existing-class handler, then passes only `EventKnowledge` to that handler.
Do not use `singledispatch` on `EventKnowledge` because its generic parameter
is erased at runtime. Do not dispatch through `EventType` alone because
several concrete classes intentionally share one coarse `EventType`.

Each admitted concrete event class has one reviewed readability policy that
answers:

1. is occurrence known to observer `o` at this boundary?
2. which existing event paths are readable?
3. which paths are controlled-owner-only?
4. which collections are filtered by authorized element key?
5. is a delivered historical source occurrence state-only?

There is no second class per policy and no `if/elif` switch over a parallel
enum. The one class-keyed router is not a second semantic vocabulary: its keys
are the actual event classes. Coverage tests enumerate the concrete source
classes emitted by the scripted encounter and prove that each resolves to
exactly one policy.

Unknown event classes are visible in objective diagnostics, produce a
structured reduction error, and stop the headless proving run before
acknowledgement. They are not copied wholesale into subjective presentation.

## 9. Perception and subjective authority

### 9.1 One computation

The reducer consumes, but never recreates:

- `identified_entity_observer_uuids` for identity;
- `located_entity_observer_uuids` for exact participant position;
- `located_position_observer_uuids` for independent coordinates;
- `SensoryUpdateEvent.visible_cells_*` for current visual cells;
- `seen_cells_added` for exploration memory;
- `effective_light_levels_changed` for observer-effective brightness;
- entity/object contact changes and removals;
- contact `visual` and `special_senses` modes;
- passive-perception, sense-mode, and visual-access after-values.

Darkvision, Truesight, Devil's Sight, See Invisible, blindsight,
tremorsense, invisibility, magical darkness, ordinary darkness, optical
obscurement, and walls have already contributed to those event-time results.
The knowledge layer must not contain another rules table for them.

### 9.2 Knowledge dimensions

Readability remains field-specific:

| Knowledge | Authorizes |
| --- | --- |
| Controlled ownership | Admitted private fields of that controlled entity or its direct consequence |
| Known occurrence | The real event class and safe occurrence-level status |
| Identified participant | Existing identity/name paths for that participant |
| Located participant | Exact participant position paths at that event boundary |
| Located coordinate | That exact carried coordinate only |
| Current visual cell | Current terrain/elevation and observer-effective light at that cell |
| Explored cell | Last delivered terrain/elevation, not current contents |
| Entity/object contact | Current presence and contact position |
| Visual contact | Existing appearance/equipment/object-surface paths |
| Nonvisual contact | Contact marker and supported sense modes, not normal sprite appearance |

The occurrence being known does not automatically make every field readable.

### 9.3 Exact sensory replay seed and changed-flag laws

Observer replay starts from the current engine's actual cold values:

```text
position = (0, 0)
visible = {}
seen = set()
entities = {}
objects = {}
effective_light_levels = {}
sense_modes = []
passive_perception = 0
visual_access = 1
```

Delta replay follows exact replacement semantics:

- `observer_position_changed=False` retains the prior position;
- `sense_modes_changed=False`, `passive_perception_changed=False`, and
  `visual_access_changed=False` retain prior values even if an ignored payload
  is present;
- a true changed flag requires its matching after-value and replaces the prior
  value exactly;
- a true changed flag with no matching after-value is a reduction error;
- the first ordinary update at unchanged visual access `1` replays from the
  cold seed without requiring a visual-access payload.

These are replay rules for recorded sensory facts, not new perception rules.

## 10. Minimal reducer state

The reducer retains only:

1. the logically immutable, archive-owned detached event snapshots;
2. a provenance index from a semantic subject/path to the latest captured
   event path that owns its committed value;
3. replay state for each of the two controlled observers;
4. paths already delivered to the party, including last delivered terrain;
5. source and delivery cursors required for receipts.

The provenance index stores archive references and paths, not copied tile,
entity, item, effect, or connector DTOs. It is not a second world and exposes
no rules behavior, queries, controllers, registries, or mutation commands.

The observer replay state is the state already implied by
`Senses.apply_sensory_update()`: visible cells, seen cells, contacts,
effective light, observer position, sense modes, passive perception, and
visual access. Do not create another subjective GridMap or EventQueue.

## 11. Bootstrap, hidden changes, and late disclosure

### 11.1 Bootstrap

`WorldInitializedEvent` is captured once. The local MVP may immediately read
battlefield identity and bounds. Tile, object, connector, and objective-light
paths remain unknown until existing sensory evidence authorizes them.

The two controlled `EntityCreatedEvent` records are readable according to the
owned-field policy. Non-owned creation occurrences can remain entirely
undelivered.

### 11.2 First sight or first contact

When a controlled `SensoryUpdateEvent` grants a visible cell or contact, the
provenance index locates the latest real source event paths for:

- tile surface and elevation;
- visible boundary/center-object placement and appearance;
- entity identity, appearance semantics, life state, and visible equipment;
- connector appearance when currently observable;
- any other explicitly admitted current scene value.

The current batch delivers `EventKnowledge` over those archived source events
with only the newly readable paths open. The delivery records the sensory
source index as its disclosure cause. The renderer applies the values as
idempotent scene state and does not replay historical action animation.

### 11.3 Hidden changes

An unseen committed change updates only the provenance index. It does not
alter current party scene state or remembered terrain. On later access, the
latest source event path is disclosed. This guarantees current event-time
state without querying live mechanics and without maintaining a duplicate
objective snapshot model.

### 11.4 Loss and reacquisition

Current visible cells and contacts are non-monotone. Their removals are
applied directly from `SensoryUpdateEvent`.

- explored terrain may remain as last-known fog memory;
- a lost entity/object contact is no longer drawn as currently present;
- a nonvisual contact uses a diagnostic contact marker rather than visual
  appearance;
- reacquisition discloses the latest committed source paths;
- historical knowledge is not confused with current visibility.

## 12. Two-character party semantics

The player controls exactly two characters. Each observer's sensory replay
remains separate. Party readability is the path-wise join:

```text
party_readable(path) = hero_a_readable(path) or hero_b_readable(path)
```

Current scene union follows the same rules:

- visible cells are the union of current visible cells;
- explored cells are the union of remembered cells;
- entity/object contacts are the union by source identity;
- a contact is visual if either observer currently has visual contact;
- special-sense modes are the union of contributing contacts;
- shared brightness uses the highest observer-effective light supplied by a
  currently visual controlled observer for that cell;
- removal from one observer does not remove a value still current for the
  other.

Changing which hero is active never changes the party perspective. Split
knowledge, delayed communication, charm, and competitive secrecy are not MVP
requirements.

## 13. Tiles, contents, boundaries, vision, and light

The knowledge mask preserves these distinctions:

- knowing a tile surface does not imply knowing every entity or object on it;
- a visible cell opens admitted terrain/elevation paths;
- an entity requires an entity contact;
- a center object or boundary structure requires its own object contact;
- a wall may be visible from the observing side while cells beyond it remain
  unobservable;
- two adjacent tiles may each own separate wall-like objects and retain their
  separate UUIDs and placements;
- objective blocking, traversal cost, objective resolved light, subjective
  effective light, and visible material appearance remain distinct source
  paths.

Ordinary presentation reads observer-effective light from
`SensoryUpdateEvent`, not objective `resolved_light`. A purely nonvisual
contact does not make the tile visually readable and does not authorize a
normal visible sprite.

The MVP remains brightness-based. The event stream currently does not retain
every per-cell visual-mode detail needed for darkvision grayscale or similar
styling. The renderer must not guess. A later requirement may enrich the real
`SensoryUpdateEvent`; it must not add a projection-only visual DTO.

## 14. Entity, item, condition, and effect disclosure

### 14.1 Entities

`EntityCreatedEvent` remains the sole cold source for composed entity facts.
Controlled actors may read admitted owned fields. A non-owned visual contact
may open only existing public identity/appearance paths such as kind, name,
size, body semantics, life state, and visible equipment. Ability scores,
resources, actions, spells, hidden inventory, and non-owned HP remain
`Unknown`.

### 14.2 Items and equipment

`ItemLocationStateEvent` remains the committed item-location owner.
Controlled ownership or a current visual contact opens only the existing
identity, appearance, placement, and equipment paths needed by presentation.
Charges, value, hidden contents, mechanical statistics, and hidden inventory
stay unknown unless a direct controlled-owner rule explicitly admits them.

### 14.3 Conditions

Condition occurrence, public presentation identity, source identity, target
identity, and private mechanical payload are independently readable. A
controlled target may know its direct condition consequence even when the
source remains unknown.

### 14.4 Persistent spatial effects

Subjective effect presence must be a sensory-system result, not a second
stealth/DC calculation in the knowledge reducer. Before the MVP admits a
persistent spatial effect, preflight must prove that the real event stream
contains replayable observer-specific current-effect contact changes and
removals.

If that fact is missing, enrich `SensoryUpdateEvent` at the existing
`SpatialSensesSystem` computation boundary with typed effect-contact
after-values. Reuse the existing spatial-effect identity and state types.
Do not add reducer-side DC logic, a projection effect model, reset atoms, or a
parallel effect registry.

If the scripted encounter does not create persistent spatial effects, this
enrichment is deferred and the encounter preflight rejects actions that would
create one.

## 15. Movement and elevation

Movement presentation consumes real committed movement events.

- `StepMovementEvent` is the authoritative per-step occurrence;
- only committed steps animate;
- a controlled mover may read its committed endpoints and trajectory;
- a non-owned step exposes exact endpoints only when event-time evidence makes
  both endpoints readable;
- if the actor disappears and later reappears, sensory contact deltas update
  current presence without inventing the hidden segment;
- root movement paths are not treated as observable merely because the root
  action occurred;
- opportunity attacks remain their real child event subclasses;
- visible children can present even when their parent path is unknown;
- endpoint elevation is read with the corresponding known endpoint.

Z remains engine support elevation plus a renderer pixel offset. This plan
adds no volumetric LOS, free altitude, or within-cell 3D mechanics.

Dynamic FOV, effective light, and contacts continue to update at every
movement step through the existing pre-completion sensory event boundary.
Animation timing must not delay mechanics emission of those facts.

## 16. Event-family readability policy

Policies operate on the real class and its existing paths.

| Real event family | Occurrence rule | Typical readable paths | Typical unknown paths |
| --- | --- | --- | --- |
| World bootstrap | Public bounds; later path disclosure through senses | Bounds, authorized tile/object/connector paths | Hidden contents, costs, objective light |
| Entity creation/progression | Controlled ownership or later current contact | Owned state; authorized identity/appearance | Non-owned stats, resources, spells, hidden inventory |
| Sensory update | Observer is one of the two controlled actors | That observer's complete replay delta | Other observers' subjective state |
| Spatial/world change | Current visual/contact evidence or direct controlled consequence | Authorized committed changed paths | Hidden coordinates, contents, topology |
| Step/forced movement | Controlled mover or known occurrence plus known endpoints | Committed readable segments and elevation | Requested paths and hidden segments |
| Root action/jump/connector | Controlled actor or perceived occurrence | Existing semantic presentation kind and readable participants | Hidden targets, paths, controller internals |
| Attack/spell/action | Controlled participant or perceived occurrence | Separately known participants, safe public outcome, presentation kind | Hidden target lists, private modifiers, provenance internals |
| Roll/check | Controlled participant or known parent occurrence | Public result; controlled-owned details | Hidden actor, DC, bonuses, private modifiers |
| Damage/heal/temp HP | Controlled affected actor or perceived target | Applied consequence and separately known source/type | Non-owned resulting HP and defenses |
| Life/death/revive | Controlled actor or current perceived contact | Known identity and life-state transition | Hidden killer and private counters |
| Item/equipment | Controlled ownership or current visual contact | Admitted identity, appearance, placement | Charges, value, contents, hidden inventory |
| Condition/effect | Controlled consequence or perceived current effect | Public presentation identity and current known area | Full mechanics, hidden source, unperceived area |
| Encounter/round/turn | Public boundary or known active participant | Boundary and known actor | Hidden roster and autonomous decision detail |

The implementation preflight freezes the exact concrete class admission for
the scripted encounter. Family inheritance may share a policy implementation,
but every emitted concrete class must resolve unambiguously.

## 17. Combat logs without a second subjective model

Subjective logs use the same `Knowledge` operation.

1. Objective diagnostics retain the engine's actual `CombatLogEntry` tree and
   source order.
2. Subjective prose is formatted from the delivered real event subclasses
   through their `EventKnowledge`, after unreadable fields are known to be
   `Unknown`.
3. Objective comparison prose may use the same formatter under top knowledge.
4. A visible child whose parent occurrence is unknown becomes a local root in
   the subjective text tree.
5. Counts, totals, and summaries are recomputed from delivered children; an
   objective aggregate is never copied after hiding children.
6. Free-form objective strings and arbitrary `CombatLogEntry.data` are not
   sanitized or copied into subjective output.

If the proving encounter produces a standalone log entry with no source
event, preflight must either admit an explicit formatter over the original
typed `CombatLogEntry` under the same `Knowledge` reader or remove that
standalone source from the fixture. It must not invent a fake event or a
subjective log DTO family.

## 18. Batches, queues, timing, and receipts

The async architecture from the pygame MVP remains:

```text
engine coordinator
    -> immutable event-delivery batch queue
    -> human-speed presentation consumer
    -> receipt/acknowledgement queue
```

The batch contains:

- one batch ID;
- the closed source range for developer correlation;
- ordered `EventDelivery[E]` values;
- structured reduction errors;
- source-coverage dispositions for diagnostics.

There is no server-shaped transport envelope and no serialization contract.

Player-side scripted commands wait until their preceding required
presentation work is acknowledged. Autonomous enemy commands may continue
resolving and enqueue multiple batches while presentation animates. Before the
next player decision, simulation waits until presentation catches up.

Every delivered event receives exactly one terminal presentation disposition:

- animated;
- scene state applied;
- text/badge fallback using only `Known` reads;
- intentionally silent with a reviewed reason;
- errored.

Hidden and lifecycle-only source slots receive source-coverage dispositions
but no ordinary badge. A missing presentation handler for a known occurrence
must produce a visible fallback and an error receipt; a missing readability
policy stops the proving run.

## 19. Presentation consumer

Presentation imports the existing event subclasses for dispatch. It does not
receive or query live engine objects. A handler receives `EventKnowledge[E]`,
not the raw captured event reference, and can obtain values only as
`Known/Unknown`.

Examples:

```text
present_attack(EventKnowledge[AttackEvent])
present_step(EventKnowledge[StepMovementEvent])
apply_senses(EventKnowledge[SensoryUpdateEvent])
```

There is no mapping from `AttackEvent` to `ATTACK` before dispatch. The
subclass is already the type-system answer.

The scene reducer owns current visual state. It may retain sprites, animation
cues, fog memory, current contacts, and receipts. It may not become a second
mechanics world or answer rules questions.

## 20. Debugging surface

The MVP retains four read-only traces:

- objective events under top knowledge;
- party events under joined knowledge;
- objective combat logs;
- party combat logs formatted from joined knowledge.

Rows align on real source index, real event UUID, lineage, concrete class, and
phase. Because this is a local developer tool rather than an adversarial
client, those technical identities may remain visible in the diagnostic rail.
Ordinary scene and log prose do not use them as game facts.

For each formatter or presentation handler, the trace records every requested
path and whether it returned `Known` or `Unknown(reason)`. This is the primary
diagnostic for missing subjective representation.

Artifacts also record:

- capture and delivery cursors;
- occurrence and field-policy coverage;
- disclosure causes;
- animation/state/fallback receipts;
- attempts to read a path with no rule;
- live-world access violations;
- terminal simulation/presentation alignment.

## 21. Required engine-event enrichments

Do not assume an enrichment until preflight proves it is needed. When needed,
the fact must be added to the real authoritative event at the system that
already computes it.

| Missing replay fact | Correct owner | Forbidden workaround |
| --- | --- | --- |
| Current observer-specific spatial-effect contacts | `SpatialSensesSystem` -> `SensoryUpdateEvent` | Reducer recomputes stealth, DC, area, or visibility |
| Rich per-cell visual mode for styling | `SpatialSensesSystem` -> `SensoryUpdateEvent` | Renderer guesses from brightness |
| Missing committed appearance/state after-value | Domain mutation's real completion event | Live registry read or presentation snapshot DTO |
| Missing participant/coordinate evidence | Real event's evidence method at completion | Field-name inference in reducer |

For the brightness-only scripted MVP, rich per-cell visual modality remains
deferred. Persistent-effect contact enrichment is required only if the frozen
script can create a persistent effect.

## 22. Implementation slices and checkpoints

No slice begins until this plan and the corresponding reduction amendments to
the pygame MVP plan are accepted.

### K0 — exact preflight

- run the scripted encounter headlessly with the accepted mechanics fixture;
- freeze every emitted concrete event class, phase, and combat-log kind;
- identify every presentation handler's required existing source paths;
- admit only reviewed cold leaves/collections and identify every requested path
  that currently resolves only through a mutable mechanics owner or event
  method;
- prove current sensory replay and per-step update boundaries;
- decide whether persistent-effect contact enrichment is required;
- record the exact baseline and create one implementation ledger.

Checkpoint: no production changes; exact admission and missing-fact list.

### K1 — capture archive and knowledge primitive

- add one closed-batch archive of detached deep snapshots of actual event
  subclasses under logically immutable ownership;
- add `Known/Unknown`, immutable masks, and the minimal event reader;
- add objective top-knowledge reads;
- prove type preservation, source-value equality, immutable collection
  exposure, mutation isolation, known-null distinction, idempotence, mask
  composition, and no public raw escape in presentation.

Checkpoint: objective diagnostics can read captured real events through the
same API intended for subjective use.

### K2 — observer replay and party join

- replay the two controlled observers from real `SensoryUpdateEvent` values;
- derive field readability from captured event evidence and replayed contacts;
- implement party path-wise join and current scene union;
- prove movement-step sensory updates, loss/reacquisition, light changes,
  invisibility, darkness, walls, and special-sense contacts without a second
  mechanics calculation.

Checkpoint: representative real events produce correct `Known/Unknown` reads
for each hero and the party.

### K3 — provenance and late disclosure

- index latest committed source event paths without copying their values;
- disclose tiles, entities, objects, equipment, and connectors by reopening
  archived real-event paths at the granting sensory boundary;
- stage pre-completion sensory disclosures and resolve them through the exact
  matching causative terminal event rather than a later global value;
- preserve last-known terrain while removing current contacts;
- prove hidden changes reveal the latest committed event value;
- add only preflight-approved real event enrichments.

Checkpoint: cold bootstrap through reveal/re-hide/reacquire replays without a
live-world query or projection DTO.

### K4 — real-class formatting and presentation dispatch

- register reduction, formatting, and rendering by actual concrete subclass;
- implement movement, attack, damage, life state, conditions, equipment,
  turns, sensory changes, and fallback coverage;
- format subjective logs from the same knowledge reads;
- prove visible children survive unknown parents without synthetic IDs.

Checkpoint: objective/subjective event and log rails use the same source
events and display explicit readability differences.

### K5 — queue and timing integration

- enqueue immutable delivery batches;
- apply scene state and human-speed animation;
- emit one terminal receipt per delivery;
- enforce player acknowledgement and enemy run-ahead;
- stop at the next player decision until presentation catches up;
- prove no source or delivery gap deadlocks the encounter.

Checkpoint: the scripted encounter runs end to end using only known reads.

### K6 — certification

- run the complete admitted engine, sensory, movement, light, condition,
  action, log, geometry, async, and architecture lanes;
- run no-live-query, no-parallel-event-schema, locality, and dependency gates;
- run the deterministic headless encounter and reviewed visual encounter;
- freeze exact manifests, node hashes, receipts, and run artifacts;
- obtain independent correctness and anti-slop approval of the exact
  candidate.

Checkpoint: accepted reduction/presentation MVP boundary with no required work
remaining in this scope.

## 23. Required test scenarios

At minimum:

1. `Known(None)` differs from `Unknown`.
2. Top knowledge reads every admitted source path exactly.
3. Objective and subjective access reference the same captured event and
   preserve its concrete subclass.
4. Mutating a returned collection is impossible and cannot alter the sole
   archive snapshot; repeated replay is deterministic.
5. Event methods, mutable mechanics owners, callables, handlers, live
   conditions, dice/damage behavior objects, and arbitrary context are not
   readable values.
6. A real authoritative event enrichment supplies any required cold value that
   previously existed only behind a forbidden mechanics object.
7. Applying a mask twice is idempotent; joining the same observer twice is
   idempotent.
8. Party join exposes a path known by either hero and never changes its value.
9. The exact sensory cold seed replays the first ordinary unchanged-visual-
   access update; false changed flags preserve prior values and true flags
   replace exactly or error when their after-value is absent.
10. A completely unperceived attack produces no ordinary delivery.
11. A perceived attack can expose occurrence and damage while source identity,
   target identity, or modifiers remain independently unknown.
12. A controlled actor receives direct owned consequences even when the cause
   is unidentified.
13. An enemy creation event is initially undelivered, then its existing public
   paths become known on first visual contact without a new entity-view type.
14. A hidden tile change updates provenance but not fog memory; reacquisition
    exposes the latest real event value.
15. A sensory update emitted before its parent completion discloses the exact
    causative committed tile/object/contact after-state; an unrelated later
    change in the same closed batch is never sampled.
16. Missing or ambiguous causal completion makes reduction fail before
    delivery.
17. A visible wall object is known while the cell beyond remains unseen.
18. Two adjacent tile-owned walls remain distinct.
19. Ordinary sight, darkvision, magical darkness, Truesight/Devil's Sight,
    invisibility, See Invisible, blindsight, and tremorsense outcomes match the
    real sensory events exactly and are not recomputed.
20. A nonvisual contact produces a marker and no normal visual sprite.
21. One hero losing contact does not remove the other hero's current party
    contact.
22. Every committed visible movement step updates FOV/light/contacts before
    its causative parent completes and can animate using real endpoints and
    elevation.
23. A hidden movement segment is not fabricated between disappearance and
    reacquisition.
24. A visible opportunity attack child presents when its movement parent is
    unknown.
25. Subjective log prose never copies objective free text or hidden child
    aggregates.
26. A missing readability policy stops the proving run; a missing renderer
    handler for a known event produces a fallback and terminal receipt.
27. Replacing every live-world accessor with a failure after capture leaves
    the headless run green.
28. Presentation acknowledges the terminal simulation cursor after every
    delivery has one terminal disposition.

Tests assert state, reads, event classes, receipts, and cursor outcomes. Async
tests wait on explicit acknowledgements, never arbitrary sleeps.

## 24. Amendments required in the pygame MVP plan

Before implementation, the accepted pygame MVP plan must be amended and
revalidated as follows:

1. Replace `CanonicalEventView`, canonical kind, canonical fact, normalization,
   and censorship-view language with the knowledge-context model in this file.
2. Replace the statement that presentation cannot import raw event subclasses:
   it may import their classes for dispatch, but receives only
   `EventKnowledge[E]` over frozen capture references.
3. `ReducedPresentationBatch` contains real-class event deliveries, not
   canonical DTOs.
4. Objective and subjective traces read the same captured event through top
   and party knowledge respectively.
5. Presentation receipts key deliveries and real source events, not invented
   canonical view IDs.
6. Remove projection-native UUIDs, canonical-kind coverage, fact-atom
   manifests, and structural view serialization from the MVP scope.
7. Preserve the existing two async queues, player acknowledgement, enemy
   run-ahead, decision catch-up, renderer scene authority, geometry, asset,
   animation, and error-artifact requirements.
8. Preserve the rule that rendering never queries live engine state.
9. Make actual event-class admission and readability-path coverage the M3
   proof boundary.
10. Require missing perceptual facts to be enriched on the real event at the
    existing computing system, never in a projection DTO.

The old plans remain historical evidence until these amendments are accepted;
this candidate does not silently edit them.

## 25. Anti-slop gates

- No `CanonicalEventView`, `CanonicalKind`, `FactAtom`, objective/subjective
  event DTO families, or mirror event subclasses.
- No HKT emulation library, lens framework, generated access models, or custom
  serialization layer.
- No copied objective catalog of tile/entity/item/effect state; provenance
  indexes point into the single detached event archive.
- No subjective EventQueue, GridMap, Senses system, rules engine, or second
  combat-log generator.
- No reducer-side FOV, lighting, darkness, invisibility, special-sense,
  stealth, spatial-effect, range, or movement legality computation.
- No server, SDK, HTTP, websocket, TypeScript, transport, replay persistence,
  save, or networking work.
- No opaque identity system where real local source identities suffice.
- No mapper/controller/service hierarchy around class dispatch.
- No generic recursive event dump, sanitizer, or dictionary-shaped payload.
- No live registry reads after capture.
- No objective free-text copy into subjective output.
- No hidden-event fallback badge.
- No arbitrary sleeps, event dropping, batch coalescing, or acknowledgement
  across a gap.
- No renderer mechanics authority.
- No persistent-effect support until real sensory effect contacts are
  replayable.
- No scope expansion into MapEditor schemas, interactive UI, campaign flow,
  networking, or full VFX.

## 26. Acceptance boundary

This plan is acceptable only if reviewers can answer yes to all of the
following:

- Is the existing event subclass the only semantic dispatch type?
- Does each source value have one frozen owner rather than a copied view
  payload?
- Is `Known/Unknown` the only subjective value distinction?
- Can objective and subjective traces read the same captured event through
  different contexts?
- Are current senses and event-time evidence the sole perception authority?
- Can two controlled observers join knowledge path by path?
- Can bootstrap, hidden changes, and late disclosure work by reopening real
  source event paths without a second world snapshot?
- Are tile, contents, boundaries, contacts, light, identity, and location kept
  distinct?
- Can movement and elevation present only real committed known segments?
- Are subjective logs formatted from known reads rather than censored DTOs or
  scrubbed prose?
- Can the async renderer run at human speed while enemy mechanics proceed?
- Are missing rules and missing visual handlers observable and non-deadlocking?
- Does the design remain local, in-process, renderer-neutral, and smaller than
  the deprecated replication architecture?

Until this candidate and the corresponding pygame-plan amendment are accepted,
implementation of the event-reduction boundary remains blocked.
