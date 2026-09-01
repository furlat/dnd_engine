# Primitive behavior-fact and direct-item sequence amendment

Status: `ACCEPTED — BF-0 DOCUMENTATION PREFLIGHT AUTHORIZED`

This amendment corrects the sequencing assumption in
`DND_CONTENT_RECOVERY_DIRECT_ITEM_HARD_CUT_CR1_CR3_IMPLEMENTATION_PLAN_2026-08-31.md`.
It keeps the broader content-recovery goals and the atomic 147-item hard cut,
but stops treating runtime behavior identity as family-local while the engine
still exposes one shared `ContentRef`-shaped fact contract.

## 1. The actual shared seam

The current behavior mechanics are already owned by their concrete action,
condition, handler, reaction, and spell classes. The coupling is narrower:

- `BehaviorBinding` stores `definition_ref`, `provided_by_ref`, and
  `origin_root_ref` as `ContentRef` values;
- `Entity` refuses to expose an action without that binding;
- `AvailableActionInfo` requires `AuthoredBehaviorAttribution` with the same
  refs;
- `ActionEvent` captures the active binding;
- condition saving throws store `cause_ref`/`condition_ref`;
- spell-execution context stores `cause_ref`; and
- item/condition/action child ownership is authenticated through the installed
  behavior gateway and live provider declarations.

This makes partial declaration removal impossible without a direct/legacy
branch. The correction is one shared value-shape hard cut, not a new behavior
framework.

## 2. Target runtime fact

Every runtime behavior fact uses only these primitive values:

```text
behavior_id: str
provided_by_id: str
origin_root_id: str | None
```

- `behavior_id` identifies the concrete executable rule.
- `provided_by_id` identifies the action, condition, item, feature, or other
  direct semantic owner that installed it.
- `origin_root_id` optionally identifies the durable root from which the
  ownership chain began.

All non-null values are non-empty namespaced IDs. They are immutable Event and
discovery facts; no live component, registry row, or Python class crosses that
boundary.

This is the same small direct fact shape proven in accepted checkpoint
`513dd97`. That checkpoint is implementation evidence only: package moves,
deleted content domains, callback/history mistakes, and unrelated refactors
must not be transplanted.

## 3. What remains legacy in this prerequisite

Behavior declarations and the existing installed behavior gateway temporarily
remain as admission/catalog metadata for behavior families not yet recovered.
Their `ContentRef.content_id` is converted once at admission to the primitive
`behavior_id`. Provider and root refs likewise contribute `content_id`, or an
already-authored direct root ID after that root's owning cut. The composite
`identity_key` (pack, kind, version, and contract hash) is never used as a
direct behavior ID. No `ContentRef` used for **behavior attribution** survives
on live actions, conditions, handlers, discovery rows, action Events,
saving-throw contexts, or spell-execution contexts. Separately governed facts
such as configured-action identity and authored effect/catalog metadata remain
outside this prerequisite.

This is not claimed as CR-2 or CR-9 completion. BF-0 first freezes all 395
currently admitted runtime declaration sources in two truthful cold partitions:

- 393 class-admitted mechanics rows. Each owning domain exposes an immutable
  by-class view beside its existing declaration tuple/row, including co-located
  extension, item, infernal, origin, class, and reaction declarations not
  covered by today's three broad maps.
- two provider-only function rows:
  `trait.origin.half_orc.relentless_endurance` and
  `trait.origin.halfling.lucky`. Their functions install private handler arms;
  the rows are explicit structural-provider IDs, not mechanics classes.

Cold bootstrap proves the partitions are disjoint and cover exactly 395 rows.
The class partition has exactly one class and one direct `content_id` per row,
with no missing class, duplicate class, or conflicting ID. The existing gateway
receives only that merged 393-row read-only class view as constructor data. The
two provider-only IDs enter only the existing explicit structural-grant path;
generic `EventHandler` is never mapped to either function declaration. These
are gateway inputs, not a second registry or resolver.

Admission is then an exact `type`-key lookup; it does not inspect a class
decorator, call `get_content_declaration(type(...))`, build the view from live
classes, or query the frozen registry during live binding. After admission the
engine carries only primitive facts. The later complete behavior cut will put
the same IDs directly on all mechanics owners and delete declarations, gateway,
and behavior admission tables.

There is one runtime fact path. The prerequisite must not add:

- optional `ContentRef`/string unions;
- parallel legacy and direct attribution DTOs;
- per-family switches or converters;
- synthetic `ContentRef` values;
- a new registry, resolver, service, manager, controller, or provider object;
- a second discovery/Event/save path; or
- reflection, `getattr`, `TYPE_CHECKING`, late imports, or cycle exceptions.

## 4. Slice BF-0 — exact preflight

Documentation/test inventory only.

1. Freeze every production and maintained-test consumer of
   `BehaviorBinding`, `AuthoredBehaviorAttribution`, the behavior-gateway bind
   functions, active provider context, saving-throw refs, and spell-execution
   refs.
2. Freeze the declaration-to-primitive-ID equality for every currently
   admitted behavior row: behavior/provider/root refs map by exact
   `ContentRef.content_id`, and the complete admitted ID inventory is non-empty,
   namespaced, unique, and collision-free.
3. Freeze the complete 395-row declaration-source union as exactly 393
   class-admitted mechanics rows plus the two named provider-only function
   rows. Prove partition disjointness, total coverage, exact `content_id`
   equality, and zero missing classes, duplicate classes, duplicate IDs, or
   cross-view conflicts. The merged 393-row read-only class view exists only as
   cold constructor input to the existing gateway. The two provider-only IDs
   are accepted only by explicit structural grant; generic `EventHandler` type
   admission for them is forbidden.
4. Freeze all root/provider call sites, distinguishing Entity, item,
   condition/action child, origin/class grant, and independent behavior.
5. Freeze every undeclared private handler and its exact construction owner.
   A private handler is an implementation arm of that provider's behavior, so
   it intentionally receives the provider's `behavior_id` rather than a new
   name-derived identity. Any independently meaningful public reaction must be
   present in the exact reaction by-class inventory instead.
6. Freeze public action-discovery, typed connector, source-propagation,
   saving-throw, condition lifecycle, reaction, Event serialization/replay,
   item-use, runtime-reset, and fresh-bootstrap proofs.
7. Freeze every `semantic_key` consumer. Within actions, conditions, and
   handlers it remains only a non-authoritative policy/grouping key; it never
   supplies or overrides behavior provenance. Missing handler policy keys fall
   back to the admitted `behavior_id`, never to display names, callback code
   identity, or Python paths.
8. Add the reviewed direct-item 409-node affected lane and its four current
   regression dispositions without changing or hiding them.

BF-0 is a mandatory reviewed checkpoint before production/test edits. Stop
only for a genuine conflicting semantic ID, a private handler that is actually
an independent public rule, or a consumer that cannot receive the primitive
facts without a new runtime abstraction.

## 5. Slice BF-1 — shared primitive fact cut

Perform one coordinated edit over the existing owners.

### 5.1 Runtime attribution

- Change `BehaviorBinding` to immutable primitive semantic fields
  `behavior_id`, `provided_by_id`, and `origin_root_id`, while retaining
  `runtime_owner_uuid` solely as encounter-local, non-serialized correlation
  used to reject rebinding one live behavior to a different owner. The public
  semantic fact remains exactly the three IDs.
- Remove `AuthoredBehaviorAttribution`; discovery copies the same three
  primitive fields directly.
- Change the existing active behavior context to carry that same immutable
  fact. Reuse the current context boundary; do not stack another context or
  callback layer on it.
- Keep the behavior gateway only as the current declaration admission check
  and declaration-`content_id`-to-ID source. It receives BF-0's complete frozen
  393-row class view at cold bootstrap; the explicit grant entry receives one
  of the two provider-only primitive IDs. Neither path performs reflection,
  live view construction, or registry/dependency queries. The returned live
  binding is primitive plus the internal owner UUID.

### 5.2 Actions and discovery

- `BaseAction` holds one primitive binding after admission.
- `Entity.register_action` and discovery bind once, then expose the three
  primitive fields.
- `AvailableActionInfo` stores the three fields directly; it no longer imports
  content identity types for behavior attribution.
- executable clones and variants preserve the exact same values.
- `semantic_key` remains policy/grouping data and cannot override or generate
  the binding's behavior ID.
- configured action identity remains outside this cut when it is a distinct
  authored configuration fact.

### 5.3 Events and causal children

- `ActionEvent` stores and serializes the three primitive fields directly.
- action execution exposes the same active primitive fact while emitting child
  Events/conditions/handlers.
- handler dispatch evidence and effective-handler presentation carry direct
  primitive identity.
- undeclared private handlers inherit the active provider's behavior ID because
  they are implementation arms of that same rule; public reaction handlers
  receive their own ID from the exact reaction by-class inventory.
- handler policy keys may be explicit, otherwise they equal the admitted
  behavior ID; no handler identity is derived from its display name or callable.
- item, action, and condition child admission receives explicit primitive
  provider/root IDs; it does not receive or inspect a live provider object.
- Event lineage, phases, completion, reduction, replay, and queue chronology do
  not change.

### 5.4 Conditions and saves

- `BaseCondition` receives the same primitive binding before admission.
- condition application/removal facts freeze the condition behavior ID.
- `SavingThrowContext` changes from `cause_ref`/`condition_ref` to
  `cause_id`/`condition_id` strings while preserving `effect_id`, magical
  status, and ordered tags.
- authored content effect profiles remain cold declaration metadata in this
  prerequisite; only runtime save/effect provenance changes.

### 5.5 Spells

- spell execution context changes `cause_ref` to `cause_id`.
- spell actions derive the default saving-throw effect ID from the primitive
  behavior ID without parsing a `ContentRef` object.
- counterspell, concentration, damage-affinity, origin innate spells, learned
  reactions, variants, clones, and source propagation retain their current
  mechanics and exact IDs.
- `SpellCatalogCompositionRow.declaration` and character/origin/scenario spell
  holders remain unchanged here; they are cold/catalog construction data, not
  runtime behavior facts.

### 5.6 Roots and providers

- Until their owning domain hard cuts, a legacy root may supply its declaration
  `content_id` as a primitive `origin_root_id`.
- After the item hard cut, an item supplies its required direct `item_id`.
- No runtime API accepts `ContentRef` as a behavior provider/root after BF-1.
- Dependency-graph validation remains a cold bootstrap concern over the same
  declarations and existing dependency graph. Live child binding consumes the
  active primitive provider fact and explicit primitive root ID; it does not
  query the registry, inspect a provider class, or receive a provider object.

## 6. Slice BF-2 — hard deletion and proof

Delete from live runtime contracts:

- `BehaviorBinding` `ContentRef` fields;
- `AuthoredBehaviorAttribution`;
- live-provider-object binding APIs;
- action/Event/save/spell-execution `ContentRef` behavior facts; and
- tests whose only assertion is the retired ref-shaped runtime DTO.

Add public proofs that:

1. registered action discovery and execution expose identical primitive facts;
2. executable variants and child conditions preserve provider/root identity;
3. item-use actions identify the item provider using a primitive item semantic
   ID;
4. condition saving throws and spell damage use primitive cause/condition IDs;
5. action Events serialize/replay without content imports or registry access;
6. handler/reaction dispatch exposes the same direct facts;
7. bootstrap rejects unknown declarations before admission but no live runtime
   object stores a `ContentRef` behavior fact; and
8. runtime reset leaves no binding/provider context residue.

Additional architecture proofs reject decorator/class reflection during live
admission, live frozen-registry queries from the binding path, display-name or
callable-derived handler identity, and use of `semantic_key` as behavior
provenance.

Checkpoint gates:

- all frozen behavior, discovery, Event, save, spell, reaction, item-use, and
  architecture lanes pass;
- the complete 409-node direct-item affected lane retains an explicit
  disposition for its four pre-existing regressions;
- compileall, diff-check, fresh-import, dependency-DAG, no-late-import,
  no-reflection, and no-server/SDK/renderer scans pass; and
- correctness, anti-slop, and anti-OOP/ECS/import-DAG reviewers approve the
  exact candidate.

Any production/test repair after freeze invalidates affected validation and
all reviews.

## 7. Direct-item plan consequence

After BF-1/BF-2 acceptance, the direct-item implementation plan is amended as
follows:

- CR-2I declaration deletion is no longer a prerequisite for CR-I.
- Existing concrete item actions/conditions/spells continue to execute through
  the primitive runtime fact contract while their declarations remain
  temporary catalog/admission metadata.
- All 147 public items and the private Guardian item still migrate atomically
  to required direct `item_id`; no 135/12 split or mixed `BaseItem` schema is
  allowed.
- Item declarations, recipes, presets, materializers, item `ContentRef`, and
  item-specific generic construction are still deleted by the existing atomic
  item cut.
- Guardian's spell may remain catalog-admitted while constructing the private
  direct Guardian item. Its spatial-zone identity remains deferred to CR-9.
- Fresh-process item construction requires no item registry. Behavior
  execution may still use the temporary behavior declaration gateway until
  the later complete behavior cut; this limitation is explicit and is not
  mislabeled as CR-2 completion.

The Wall Torch and three door regressions remain bounded repairs in the item
candidate. The human explicitly authorized proceeding with `WEST` for the
range-only manual door fixture in this task on 2026-08-31. This authors one
fixture value; it is not a runtime default, inference rule, or cardinal-direction
architecture dependency.

## 8. Later behavior completion

CR-9 remains responsible for the true behavior hard cut:

- put the already-frozen primitive IDs directly on every concrete mechanics
  owner;
- migrate cold presentation/rules metadata to domain-local ID-keyed rows;
- delete all attached behavior declarations, binding maps, installed gateway,
  and remaining behavior-content dependencies; and
- prove fresh-process execution for the complete behavior inventory.

BF-1 deliberately makes that later deletion smaller; it does not pretend to
have completed it.

## 9. Review requirements

Before implementation, three independent reviewers must approve the same file
bytes:

1. correctness/completeness: full runtime consumer closure, one primitive fact
   shape, spell/catalog boundary, and item-sequence consequence;
2. anti-slop: no compatibility membrane, dual runtime authority, extra
   attribution layer, speculative CR-9 implementation, or unnecessary type;
3. anti-OOP/ECS/import-DAG: behavior classes remain mechanics owners, Events
   remain value facts, provider/root identity is explicit data, and no manager,
   callback graph, reflection, late import, or circularity is introduced.

Substantive edits invalidate all approvals.

## 10. Acceptance record

The exact substantive candidate with SHA-256
`7a91ed5d2d7e9fbcaf914a6ca0f0b95c9b00d657dc946fc59756960d789467cd`
was independently approved on 2026-08-31 by:

- correctness/completeness: approved, including the exact 393-class / two
  provider-only partition and the human-authored `WEST` fixture value;
- anti-slop: approved, finding one cold gateway input and no second registry,
  resolver, compatibility membrane, or duplicate runtime fact path; and
- anti-OOP/ECS/import-DAG: approved, finding explicit data ownership, truthful
  private-handler inheritance, no live provider objects, and no reflection,
  late imports, circularity, managers, or callback layers.

The edits in this section and the status line are metadata only. The three
reviewers must reconfirm the final file bytes before BF-0 is recorded complete.
