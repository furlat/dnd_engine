# Action execution bridge — Block 1 exact identity and privacy hard cut

**Status:** frozen-review candidate; planning and review only

**Date:** 2026-08-13

**Primary ledger ownership:** `X01–X10`

**Implementation authorized by this document:** no. Implementation starts only
after separate user authorization following the two detached acceptances defined
in §20.

## 1. Outcome

After this block, every included action execution has one exact engine-owned
behavior identity before it enters the event lifecycle. Subjective projection
then exposes exactly one truthful, lawful binding subject—or one closed
systemic subject—without leaking a hidden implementation, relabeling one role
as another, parsing display text, or joining grants from different observers.

The same selected subject and exact direct causal evidence survive through:

```text
engine execution
  -> subjective projection
  -> generated TypeScript SDK
  -> existing NeuroClient mapper / ClipIntent / VisualTransaction
  -> subjective replay through the same mapper
```

This is a hard cut in the existing path. It adds no identity service, registry,
presentation graph, journal, scheduler, compatibility adapter, or deployment
system.

## 2. Evidence baseline and authority

This plan is derived from the human-owned, second-pass source audit:

- `tools/ACTION_EXECUTION_BRIDGE_MANUAL_LEDGER.md`
  - SHA-256: `9a266a06c71bc19250e1dab078dfd5d64e2c3c1eda08a94d57ddcaf7384c964d`
- `tools/ACTION_EXECUTION_BRIDGE_IMPLEMENTATION_BLOCKS.md`
  - SHA-256: `c67e6a8480d8d9d8cd90d5dfa87bc32254365fa24a58d023b0699fe308a0911c`
- `HOW_TO_TEST.md`
  - SHA-256: `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013`

The source baseline manually reviewed for the plan is:

- engine repository HEAD:
  `52acf56df90e20ab733d9264512f200c8a405c1c`
- NeuroClient repository HEAD:
  `d274f2d62ca9c1c5ed62a77841cacf6cc0347491`
- engine tracked production diff at the start of this planning pass: empty

The ledger is semantic authority for the observed defects. This plan owns only
the Block 1 dispositions. If implementation discovers another live semantic
use of an open context key, another direct-apply producer, or another client
identity fallback not covered here, work stops and the reviewed plan is
amended; the discovery is not absorbed opportunistically.

## 3. Scope fence

### 3.1 Included

- exact behavior binding for normal and direct/nested action execution;
- exact configured-action, handler, and source-item provenance;
- visibility frozen with each exact content identity before projection;
- lawful subjective selection of one primary behavior subject from public
  definition, configured action, provider, or a closed systemic domain, plus
  independently lawful tagged public source-item attribution;
- deletion of presentation-only item/action classifications as identity or
  routing authority;
- removal of display-derived spell identity and string effect provenance;
- closure of action-reachable open semantic context channels;
- preservation of execution-owned application IDs that already exist;
- exact direct causal edges with privacy severing;
- action discovery API, generated SDK, NeuroClient binding, and replay
  adaptation required by that identity hard cut.

### 3.2 Explicitly excluded

- ordered application construction for target kinds that do not already own an
  application ID; that is Block 2;
- damage, healing, temporary HP, item-resource, item-location, condition,
  spatial-effect, encounter, or life-state result redesign; that is Block 3;
- attack payload redesign; movement or displacement redesign; reaction visual
  design; spell application or spell manifestation design;
- renderer media, animation, timing, color, audio, camera, local phase graphs,
  or clip scheduling;
- condition appearance authoring or redesign;
- unrelated scene or world-state representation;
- actor/body appearance, general icons, portraits, or equipment art;
- whole-catalog pre-stream admission; that is Block 8;
- legacy-data migration, bulk conversion, unrelated durable persistence,
  deployment coordination, rolling compatibility, or zero-downtime
  architecture. The V3-only active GameSummary store/validation path in §8 is
  included solely because X08 removes its display-derived identity;
- new gameplay rules or changes to an action's authoritative outcome.

Existing result and appearance payloads remain unchanged except where a field
must be removed from identity authority or from the open Event wire closure.

## 4. Ledger closure

| Row | Block 1 disposition | Observable completion condition |
| --- | --- | --- |
| `X01` | Preserve normal `BehaviorBinding`, adding frozen visibility to each existing exact ref. | A normally admitted action projects the same exact public definition independent of later registry or label mutation. |
| `X02` | Bind every direct/nested action before execution. | Drop, Retaliation, configured Multiattack children, Command flee, Sunbeam Strike, True Strike, Eyebite flee/strike, and Telekinesis Grab never execute unbound. |
| `X03` | Freeze exact binding on every effected handler dispatch. | A handler that emits events and returns `None` still produces exact internal handler evidence and lawful subjective attribution. |
| `X04` | Freeze the selected configured action on the root execution. | The ten public Multiattack configurations remain ten distinct binding subjects through SDK and client lookup. |
| `X05` | Retain exact source-item UUID/ref; remove the full presentation snapshot from `ActionEvent`. | Item-bound execution preserves exact source item identity without transporting UI/art classification as semantics. |
| `X06` | Delete `ActionPresentationKind` from action execution and projection authority. | Potion/item routing no longer depends on `DRINK` or another engine presentation tag. |
| `X07` | Close every enumerated action-reachable semantic context use with typed facts; exclude evaluator/cache context from wire. | Generated action-event closure has no open JSON/dictionary/callable/cache channel, while existing rule results remain the same. |
| `X08` | Replace `spell_id`/`EffectOrigin.source_id` with exact `ContentRef` provenance. | Renaming a spell or runtime variant cannot alter event, condition/zone origin, projection, or analytics identity. |
| `X09` | Select one truthful public/systemic primary behavior subject plus any independently lawful tagged source-item attribution, each with a one-observer proof. | OBSERVED/INTERNAL refs never cross; provider/source item is never placed in a definition field; no observer-union stitching. |
| `X10` | Preserve existing execution application UUID membership independently from exact authorized direct edges. | A hidden semantic parent produces a root/edge severance, never a bypass; lawful membership may survive independently, private engine indices do not cross, and application UUIDs are never synthesized. |

## 5. Core identity contract

### 5.1 Existing visibility

Keep the canonical `ContentVisibility` enum in its existing owner
`dnd/core/content/descriptors.py`; Block 1 neither moves nor duplicates it.
The new dependency-neutral `dnd/core/content/bound_identity.py` owns
`BoundContentIdentity` and uses that exact enum with canonical `ContentRef`.
`dnd/core/content/runtime.py` imports the value for `BehaviorBinding`. Values
remain exactly:

```text
PUBLIC | OBSERVED | DEVELOPER | INTERNAL
```

The enum and its meaning do not change. Block 1 does close the existing
unconditional public-catalog projection defect required by `X09`; it does not
redesign observer-scoped visibility policy.

### 5.2 Frozen bound identities

Add one canonical frozen value in `dnd/core/content/bound_identity.py`, then
reshape the existing binding models around it; do not create a parallel
identity model:

```text
BoundContentIdentity
  ref: ContentRef
  visibility: ContentVisibility

BehaviorBinding
  definition: BoundContentIdentity
  provider: BoundContentIdentity
  origin_root: BoundContentIdentity?
  behavior_owner_uuid: UUID
  provider_runtime_owner_uuid: UUID
  structural_provider: bool  # required; no default
```

`BehaviorBinder.bind()` resolves and freezes each identity from the installed
`FrozenContentRegistry`. It rejects a missing definition/provider/root or a
supplied ref whose contract differs from the registry entry.
`structural_provider` records only the distinction the current privacy rule
needs. It is a required binder-owned fact, not a general provenance taxonomy:

- `bind_root_owned()` and `bind_granted()` set it to `true`;
- `bind_independent()` and every `bind_child()` set it to `false`.

Only the existing binder entry points choose the value; their common resolved-
binding constructor stays internal and accepts no caller-selected value. Model/
binder validation requires `true` only for the two structural entry points,
preserves their existing owner/root coherence, and preserves the current owner/
ref derivation for independent, live action/condition, and item bindings.
Idempotent binding equality includes the boolean. Declared/private live handler
children are therefore `false`; structurally granted private handlers are
`true`.

The binder rejects a live provider whose derived owner conflicts with its
binding or item UUID. Block 1 does
not put `content_set_digest` on `BehaviorBinding`: its current owner is
`LoadedContentSystem`, and that digest includes complete descriptor/pack bytes,
including presentation data. Exact immutable `ContentRef` values plus frozen
visibility are sufficient for this occurrence-level contract; broad content
generation and deployment identity remain unchanged.

Owner equality is not provider-occurrence evidence: a live actor-owned provider
and child may share the same UUID as a structural grant. The required boolean
preserves only that distinction. It remains internal evidence, not an observer
grant: projection never treats an action/item/condition/handler instance UUID
as though it were an observed entity.

`AuthoredBehaviorAttribution` is reshaped to the same definition/provider/root
identity tuple without owner UUIDs or `structural_provider`. It remains an internal
diagnostic value, not sufficient disclosure evidence. It is not returned
directly by an HTTP or player-replication contract after this cut.

The mapper never asks the live registry for visibility or identity. Mutation or
replacement of a registry after declaration cannot change a frozen event.

### 5.3 Exact binding before action execution

One existing runtime function, renamed if necessary to
`ensure_action_execution_binding()`, is the only execution-entry binding
authority.

- `BaseAction.apply()` calls it before `runtime_behavior_provider(self)`, event
  batching, cost evaluation, or declaration.
- `SpellAction.apply()` calls the same function before opening
  `spell_execution_scope()`, then delegates to `BaseAction.apply()`; the second
  idempotent call validates the same binding.
- `Move.apply()` and `Attack.apply()` remain typed wrappers over the base entry
  and do not add another binding path.

This ordering guarantees that the spell scope and every
`create_saving_throw_request()` call receive the exact cause `ContentRef`.

The binding law is:

1. An already bound action is validated against its own declaration and owner;
   a binding whose definition does not match the concrete action declaration
   rejects.
2. An unbound action is independently bound to its own registered declaration.
   Ambient action, condition, spell, or handler scope never invents a provider
   relationship.
3. An authored grant that truly has a provider relationship must be bound
   explicitly before execution. A live action/condition/item provider uses
   `BehaviorBinder.bind_child()`; a structural authored grant with no live
   provider object uses `BehaviorBinder.bind_granted()`. Both require the
   registered content dependency and validate their respective §5.2 owner and
   `structural_provider` law.
4. An active handler is causal trigger evidence, never the content provider of
   a child action. Its child action binds to its own definition; the handler
   identity crosses separately as `trigger_binding_subject` when lawful.
5. If the gateway cannot identify that exact action declaration, execution
   rejects before cost consumption, mutation, or event publication.
6. No child copies its parent's or handler's `definition` merely because it is
   nested.

The owner check is exact and does not assume that every executable copy is
actor-owned. After resolving the coherent source-item UUID/identity pair:

- compute the item identity/owner marker coherence defined in §9 before any
  ordinary fallback;
- an item-provided action for which `item_supplies_behavior(...)` is true keeps
  `behavior_owner_uuid == provider_runtime_owner_uuid == source_item_uuid`;
  changing the executable copy's `source_entity_uuid` to the user does not
  rebind or invalidate that item ownership;
- a coherent non-item/all-false tuple may proceed through the ordinary owner law.
  Every other actor-owned action requires
  `behavior_owner_uuid == source_entity_uuid`; an ordinary weapon Attack may
  carry the weapon as auxiliary source-item provenance, but all three item-
  provider markers are false, so its action binding remains actor-owned;
- provider-owned live action/condition children require the exact provider
  relation installed by `BehaviorBinder.bind_child()` with
  `structural_provider=false`; the execution seam validates that existing
  relation rather than replacing it with ambient actor/handler scope.

A mismatched item UUID/provider owner or actor owner rejects before costs,
events, or mutation. Acid Flask and a spell scroll exercise retained item
ownership; an ordinary equipped-weapon Attack exercises actor ownership despite
its source-item pair.

The direct-site dispositions are frozen, rather than left to ambient scope:

| Direct site | Binding | Exact causal parent |
| --- | --- | --- |
| Drop (`dnd/actions_functional.py`) | Drop's own registered action definition. | Root execution: `parent_event = null`. `execute_drop()` is an API command seam, not an engine causal event. |
| Retaliation (`dnd/classes/barbarian.py`) | Child Attack's own definition; handler binding is not copied. | Exact triggering/handler event evidence. |
| Opportunity Attack (`dnd/reactions.py`) | Child Attack's own definition; delete the manual assignment from `active_runtime_behavior_binding()`. | The exact movement event already passed as `parent_event`, plus separate handler evidence. |
| Configured Multiattack children (`dnd/monsters/traits.py`) | Each child Attack's own definition. | The selected Multiattack root/application event. The configured ref stays on the root only. |
| Command flee (`dnd/spells/enchantment.py`) | Move's own definition. | The delayed Move's exact direct parent remains the `TurnStartEvent` passed to `_activate_commanded_turn`; the installed Command condition/handler binding is separate provider/trigger evidence. No edge bypasses back to the earlier spell effect. |
| Sunbeam initial strike (`dnd/spells/evocation.py`) | Sunbeam Strike's own definition. | Pass the Sunbeam effect event to constructor/application; no parentless first strike. |
| True Strike follow-up (`dnd/spells/evocation.py`) | Child Attack's own definition. | The exact parent is the executing True Strike `SpellEvent` passed by `TrueStrike._apply()` to `attack.apply(parent_event=execution_event)`. Declaration/execution/effect/completion aliases of that same spell lineage may collapse to one delivered Spell cue; no condition or handler is the parent or trigger evidence. |
| Eyebite flee/strike (`dnd/spells/necromancy.py`) | Each follow-up action's own definition. | Pass the exact Eyebite effect/trigger event, including the first strike. |
| Telekinesis Grab (`dnd/spells/transmutation.py`) | Grab's own definition. | Pass the Telekinesis effect event, including the first grab. |

The registered templates later granted by Sunbeam, Eyebite, and Telekinesis
retain their explicit installed binding. The immediate first follow-up and the
later granted action share definition identity but have their own truthful
execution parents. No bespoke presentation patch is added at any site.

### 5.4 Action declaration evidence

`ActionEvent` freezes the following internal facts at declaration:

```text
behavior_binding: BehaviorBinding              # internal, excluded from wire
configured_action: BoundContentIdentity?       # internal, excluded from wire
source_item_uuid: UUID?
source_item_identity: BoundContentIdentity?     # internal, excluded from wire
action_usage_domain: ActionSystemicDomain       # required Event-v2 fact; §8
public_action_usage_subject: PublicActionUsageSubject  # required Event-v2 fact; §8
```

`configured_action` is copied from the selected executable action row and must
identify a PUBLIC declaration before it can become an exact subjective
subject. The internal event may freeze a non-public identity for audit, but
projection cannot emit it.

The two public usage fields are selected and validated once from these complete
internal facts by §8's private pure function in the existing ActionEvent owner.
They are not subjective
observer grants; they are the privacy-safe objective identity required for
Event-v2 replay and GameSummaryV3. No caller may supply a different subject.

Required construction is explicit; `ActionEvent` has no identity default and
`model_post_init()` does not guess one from ambient scope. `BaseAction` owns one
small `_action_event_identity_fields(event_type)` method that validates the
already ensured binding, freezes configured/source-item identities, invokes the
private pure §8 selector, and returns the exact six constructor fields above.
This is part of the existing action/event owner, not a factory service or a
second evidence model. Every BaseAction declaration-event override must spread
that mapping into its concrete event constructor:

- `dnd/core/base_actions.py::BaseAction`;
- `dnd/actions.py::{Move, Attack, TraverseConnector, Jump, Shove, SpellAction}`
  and `create_weapon_attack_declaration_event()`;
- `dnd/spatial_restraints.py::EscapeSpatialRestraintAction`;
- `dnd/classes/rage.py::FrenziedStrike` and
  `dnd/classes/fighter.py::ExtraAttack`, through the shared weapon helper;
- `dnd/origins/dragonborn.py::DragonbornBreathWeapon`;
- `dnd/monsters/traits.py::NaturalAttack`.

The two production reaction constructors that do not execute a `BaseAction`
are closed separately, with no generic fallback:

- `dnd/spells/abjuration.py::_begin_counterspell_reaction()` requires the
  already bound Counterspell handler, freezes it as the internal binding, uses
  `EventType.TRIGGER_EVENT`, owns no configured/source-item identity, and
  freezes REACTION plus the lawful PUBLIC reaction definition (or systemic
  REACTION when that definition is not public);
- `dnd/spells/infernal.py::_rebuke_processor()` does the same for the already
  bound Hellish Rebuke handler before it constructs its direct `ActionEvent`.
  It preserves that event's existing gameplay `event_type`; the selector
  classifies REACTION from the exact bound reaction definition kind. The
  learned spell ref remains the typed saving-throw/effect cause; it is not
  relabelled as this reaction event's behavior binding.

Both reaction paths call the same private pure function in `base_actions.py`
with their explicit frozen facts, and both reject a missing/mismatched handler
binding before declaration publication or resource consumption. No event
constructor consults a registry, invents a systemic default, or accepts a
caller-selected public subject.

Delete `CounterspellReactionEvent.reaction_content_identity` and
`incoming_spell_content_identity`, the matching `_CounterspellEvidenceSnapshot`
copies, and the same two `SpellInterruptionLogData` string fields. They are
display-derived `identity_key` duplicates, not mechanics. Counterspell's
declaration validator compares its excluded exact `behavior_binding` directly;
the incoming occurrence is correlated only by the existing exact
`triggered_event_uuid`/`triggered_lineage_uuid`, whose own required Event-v2
subject/domain are the privacy-safe trigger authority. The combat log retains
the existing typed resolution, levels, check, UUIDs, names, and outcome, but no
authored-identity string. No compatibility field or string parser replaces the
deleted copies.

Synthetic tests receive no production fallback. The existing test-only
`tests/content_identity.py` owner adds one
`synthetic_action_event_identity_fields(...)` helper that creates an explicit
test-pack `BoundContentIdentity`/independent `BehaviorBinding`, calls the same
pure selector, and returns the complete required constructor mapping. Its
inputs include the source entity UUID, exact `EventType`, content ID, and
definition kind; it has no default systemic subject and cannot be imported by
production code. Direct synthetic event constructors spread this mapping.
Identity-specific tests continue to construct their deliberately configured,
structural-provider, item, hidden, or reaction evidence explicitly.

Only the configured root owns `configured_action`. A Multiattack child owns its
exact Attack definition and direct parent edge; it does not duplicate the root
configuration as its own binding or source field.

Declaration resolves the live `BaseItem.content_ref` and visibility once
through the same frozen registry. `source_item_uuid` and
`source_item_identity.ref` must describe the same live item. The pair may mean
the item that supplied an item-use action or a neutral participating item such
as the equipped weapon selected for an ordinary Attack. The exact frozen
provider relation below distinguishes those cases; source-item presence alone
never classifies an action. The full
`ItemPresentationState` is removed from both `BaseAction` and `ActionEvent`,
including Attack/Spell subclasses. `BaseItem.get_use_actions()`, spell-item
variant construction, and attack declaration pass only `source_item_uuid`;
they never call or pass `to_item_presentation_state()` into action execution.
Item charges and locations continue to be owned by their existing typed events
and are not duplicated here.

Replace `BaseAction.configured_action_ref: ContentRef?` with
`configured_action: BoundContentIdentity?`; there is no parallel ref alias.
Configured-action installation freezes the declaration's exact ref and
visibility when it constructs the executable template. `ActionEvent` and
discovery copy that value byte-for-byte. A configured-action identity is not
looked up later from the raw ref by declaration, projection, or HTTP code.

At `_make_action_info()`, the action-discovery builder still has the complete
frozen `BehaviorBinding`, configured identity, and source-item UUID. It resolves
the UUID to the live `BaseItem` once, requires the item's ref to match the
installed declaration, and freezes the resulting `BoundContentIdentity`;
absent UUID means absent identity, while a missing/mismatched item rejects the
row. It evaluates `item_supplies_behavior(...)` from those full facts. Action
and handler discovery never reduce the binding before disclosure selection;
`AuthoredBehaviorAttribution` is removed from discovery rather than retained as
a second internal truth or compatibility alias.

One ordinary required frozen Pydantic value owns the complete construction-
time selector evidence; it is not `PrivateAttr` and its facts are not
duplicated as independently mutable row fields:

```text
ActionDiscoverySelectionEvidence
  controlling_entity_uuid: UUID
  behavior_binding: BehaviorBinding
  configured_action: BoundContentIdentity?
  source_item_uuid: UUID?
  source_item_identity: BoundContentIdentity?
  action_category: ActionCategory?          # required for action; absent for handler
  item_provider_bound: bool

AvailableActionInfo
  discovery_evidence: ActionDiscoverySelectionEvidence

AvailableHandlerInfo
  discovery_evidence: ActionDiscoverySelectionEvidence
```

`ActionDiscoverySelectionEvidence` is frozen and `extra="forbid"`; the required
row field is `exclude=True` and `repr=False`, so it is absent from every public/
generated DTO. `item_provider_bound` has no default. The evidence validates
without a registry or live-object read that the source UUID/identity pair is
both present or both absent, that the boolean exactly equals
`item_supplies_behavior(...)`, that the pair/markers satisfy the §9 item-
provider coherence rule, and that the §5.3 owner/structural-provider law accepts the
complete tuple. Item-provided behavior requires all three exact item-provider
markers and both owner UUIDs equal to the source-item UUID. A coherent non-item/
all-false tuple may continue to the ordinary owner law; every other
discoverable action/handler requires
`behavior_owner_uuid == controlling_entity_uuid`; a distinct lawful provider
owner may remain different but cannot satisfy the PUBLIC_PROVIDER selection
rule. `AvailableActionInfo` requires evidence `action_category` present and
byte-equal to its existing public/mechanical `action_category`; neither copy has
a default. `AvailableHandlerInfo` requires evidence `action_category` absent,
configured/source-item fields absent, and `item_provider_bound=false`. A caller
therefore cannot mark an actor-owned weapon Attack, one-owner provider match,
mismatched item, incomplete pair, category-tampered action, or wrong-entity
handler as item-provided or owner-valid.

`Entity._make_action_info()` is the sole production action-row builder and
performs the installed-registry/live-item resolution above and freezes
`self.uuid` as `controlling_entity_uuid` and the template's canonical
`ActionCategory` in the evidence before constructing the row. The outer action
row copies that same frozen category rather than independently defaulting it.
`Entity.get_player_toggleable_handler_infos()` constructs the same evidence
with the entity UUID, complete handler `BehaviorBinding`, and null category.
All action collectors converge on the one builder, so none gets a second
identity path.
The explicit API adapter invokes the same pure selector from this one evidence
value; it also requires the evidence controller to equal the enclosing
`AvailableActionsResult.entity_uuid` or handler-route entity UUID. It cannot
reconstruct missing visibility or owner facts.

Internal engine/AI dispatch may use read-only accessors such as
`AvailableActionInfo.source_item_uuid` that return the value from
`discovery_evidence`; no accessor stores a duplicate or exposes it on the API.
There is no raw configured-ref compatibility accessor. Discovery carries no
`ItemPresentationState` and the adapter never asks HTTP code to look an item up.

Delete `ActionPresentationKind` from `BaseAction`, `ActionEvent`, action
discovery, and potion/item producers. The current specialized potion item cue
remains structurally until Block 3, with one exact replacement routing rule:

```text
PotionItemCueDefinitions = exact registered ContentRefs of
  _DrinkHealingPotionAction
  _DrinkGreaterInvisibilityPotionAction
  _DrinkHastePotionAction
```

The server presentation mapper compares the frozen PUBLIC behavior definition
to this closed three-ref set. A matching `ActionEvent` with a coherent
`source_item_uuid`/`source_item_identity` emits the existing
`ItemActionPresentationCue`; `item_uuid` comes from `source_item_uuid`, and its
unchanged transitional `USABLE`/`DRINK` presentation constants are populated
inside the server presentation adapter, never stored on an action/event or
used as identity. Client binding still uses the exact tagged action subject,
with `source_item_fact` only as auxiliary profile evidence.

An item-bound `AttackEvent` remains Attack, a `SpellEvent` remains Spell, and
every other item-bound action remains its ordinary event/cue family unless its
exact definition is in the three-ref set. There is no source-item-kind,
display-name, class-name, or semantic-key inference and no generic “all item
uses are drinks” rule. Block 3 later owns removal/redesign of the remaining
renderer-shaped fields on `ItemActionPresentationCue`; Block 1 only removes
their engine authority and preserves the current potion behavior exactly.

## 6. Handler identity contract

Every installed authored handler is bound before dispatch through the existing
handler-binding gateway. `HandlerDispatchEvidence` gains its frozen
`BehaviorBinding` and typed UUIDs; human-readable handler name and semantic key
remain diagnostics only.

For every handler invocation, dispatch computes its terminal outcome from the
actual before/after event queue and event version:

```text
NO_EFFECT | EMITTED_EVENTS | MODIFIED_EVENT | CANCELED_EVENT
```

Every outcome other than `NO_EFFECT` retains the exact handler binding,
triggering event UUID/lineage, emitted direct lineage IDs, and dispatch order.
This includes a handler that emits one or more events and returns `None`.
`EffectiveHandlerPresentation` becomes a view of this same evidence rather than
a second independently constructed identity record.

The dispatch evidence attaches to the exact triggering event version and the
emitted lineages before the handler scope closes. It never makes the handler an
ambient content provider for emitted actions. Retaliation and Opportunity
Attack therefore expose the handler as trigger evidence while their Attack
children retain the Attack definition.

Projection may disclose the handler as `trigger_binding_subject` only when the
role-specific privacy proof in §10 passes. Otherwise it emits a systemic
reaction subject or omits the optional trigger subject; result events retain
their own independently lawful facts.

## 7. Closed semantic context boundary

### 7.1 Wire closure

Open runtime context is not an Event or SDK fact.

- Mark `BaseObject.context` excluded from serialization.
- Independently exclude the redeclared `BaseBlock.context`, `BaseValue.context`,
  `Duration.context`, and every reachable evaluator/value surface.
- Exclude `ContextualModifier.callable_arguments`, cached results, evaluators,
  and callable payloads from serialization.
- Delete `DiceRollResultEvent.context`; do not retain a differently named open
  dictionary.
- Replace `combat_log_origin="standalone"` with one closed internal
  `Event.is_standalone_combat_log_carrier: bool`, excluded from serialization.
  `EventQueue.push_combat_log()` sets it and
  `server/agent_runtime/observation_journal.py` consumes it to preserve the
  existing wakeup behavior. Delete only the open string key.
- Delete the unread `death_save` context key.
- `DeathSaveEvent` receives explicit typed `encounter_uuid`, `round_number`,
  and `turn_index` fields because the producer already freezes those values.
- `ActionEvent.behavior_binding`, `configured_action`, and
  `source_item_identity` remain excluded internal evidence, while the required
  canonical `action_usage_domain` and `public_action_usage_subject` from §8 are
  included in Event v2. The generated contract has no other action-usage
  identity channel.

The event-contract generator recursively traverses every model reachable from
the included generated Event-v2 roots after honoring explicitly excluded
fields. A focused architecture check rejects `Any`, open JSON,
`Dict[str, Any]`, callables, evaluator registries, or caches in that Event-v2
closure. It also proves the new action subject/cue DTOs introduce no open
channel. This gate intentionally does not claim closure of pre-existing
objective replay world snapshots or combat-log payloads:
`APIFloorObject.state`, `CombatLogEntry.data`, and
`MultiEntityLogData.per_target_logs` remain outside Block 1 and are not
consulted for action binding. Timeline/replay versions rotate because their
embedded Event/cue contract hashes change, not because unrelated world/log
branches are redesigned. Domain tests below prove gameplay behavior.

### 7.2 Typed internal rule contexts

Internal rule evaluation may use typed, frozen, `extra="forbid"` context
objects that are explicitly excluded from wire serialization. It must not use a
mega transport union.

#### Attack rule context

```text
UnderwaterAttackCapability
  ORDINARY
  MELEE_DISADVANTAGE_EXEMPT
  RANGED_DISADVANTAGE_EXEMPT
  ALL_UNDERWATER_PENALTIES_IGNORED

AttackRuleContext
  attack_ability: AbilityName
  range_type: RangeType
  is_long_range: bool
  underwater_capability: UnderwaterAttackCapability
  light_exposure: LightExposure?
```

The executable attack source freezes the capability once before modifier
evaluation. It never passes a weapon display name to a rule evaluator.

Selection is exact and ordered:

1. `Entity.ignore_underwater_penalties` selects
   `ALL_UNDERWATER_PENALTIES_IGNORED`, independent of weapon, swim speed,
   range, or distance.
2. A REACH attack selects `MELEE_DISADVANTAGE_EXEMPT` when the actor has
   positive swimming speed or the exact weapon definition is in the existing
   dagger/javelin/shortsword/spear/trident exception set.
3. A RANGE attack selects `RANGED_DISADVANTAGE_EXEMPT` when the exact weapon
   definition is in the existing crossbow/net/javelin/spear/trident/dart
   exception set.
4. Every other attack selects `ORDINARY`.

Built-in equipped weapons are classified by exact item `ContentRef`, not name.
Intrinsic attacks declare the capability explicitly and default to `ORDINARY`.
This is a closed fact on the existing attack-evaluation path, not a new weapon
authoring system.

| Global ignore | Range/capability | Long range | Underwater disadvantage contribution | Underwater automiss |
| --- | --- | --- | --- | --- |
| true | any | any | no | no |
| false | REACH + melee exempt | false | no | no |
| false | REACH + ordinary/mismatched exemption | false | yes | no |
| false | RANGE + ranged exempt | false | no | no |
| false | RANGE + ranged exempt | true | no | yes |
| false | RANGE + ordinary/mismatched exemption | false | yes | no |
| false | RANGE + ordinary/mismatched exemption | true | yes | yes |

A ranged-weapon exception suppresses disadvantage only. Positive swim speed
suppresses only melee disadvantage. Only the global ignore state suppresses
both underwater attack penalties. The ordinary non-underwater Long Range
modifier in `Attack._resolve_against_current_targets()` remains independent and
unchanged: a globally underwater-immune or ranged-exempt attack at long range
may still have ordinary long-range disadvantage even though the table's
underwater-disadvantage contribution is `no`. Tests assert both contributions
separately and the final roll state. The existing entity flag remains the
movement/path-cost authority; Block 1 snapshots only its attack consequence and
changes no terrain, scene, or world inference.

One immutable `AttackRuleContext` is built once and supplied to attack bonus
and damage evaluators. Later code cannot overwrite it with a partial
dictionary. The unread `weapon_slot` context key is deleted. Rage, Reckless
Attack, and underwater modifiers consume the typed fields with unchanged
outcomes.

#### Saving throws

Use the existing `SavingThrowContext` directly. Remove the dictionary wrapper
and `SAVING_THROW_CONTEXT_KEY`. Delete legacy `condition_context: str` and
migrate each producer/consumer to the existing exact `condition_ref`,
`SavingThrowEffectTag`, and `is_magical` fields. No condition display name is a
rules key.

#### Condition-application and immunity rules

Condition immunity is keyed by the complete `ContentRef`, never condition
name, semantic key, Python class name, or `ContentRef.identity_key`.

```text
ConditionApplicationRuleContext
  condition_ref: ContentRef
  condition_tags: tuple[ConditionTag, ...]  # unique canonical enum order
```

`BaseBlock.condition_immunities`,
`BaseBlock.contextual_condition_immunities`, and every add/check/remove API use
`condition_ref` as their condition key. Static source labels may remain text
because they are diagnostics, not the blocked condition identity.
`ConditionImmunityHandle.condition_name` becomes `condition_ref`; install
rollback and receipt cleanup round-trip that exact ref. There is no string
overload or name-to-ref compatibility adapter.

`Entity.add_condition()` binds the incoming condition before immunity
evaluation, freezes its exact definition ref and canonical tag tuple, and calls
the immunity boundary with one typed context. Contextual callbacks receive
that object directly, never `Entity.context`, a live condition, or a dictionary
containing `condition`/`condition_tags`.

Preselection rules that check immunity before constructing an applied
condition pass the exact registered condition ref: Sleep uses Charmed, Color
Spray uses Blinded, and remaining spell/monster factories use their registered
condition refs. The exact production migrations are:

- Petrified, Protection from Poison, and Heroes' Feast use the Poisoned ref;
  Heroes' Feast also uses Frightened;
- Freedom of Movement uses Grappled, Restrained, and Paralyzed;
- Sleep and Color Spray use Charmed and Blinded;
- skeleton/zombie/ogre-zombie/ghoul/Marked factories use their exact Poisoned,
  Exhaustion, Charmed, Invisible, and Hidden refs;
- Mindless Rage receipts use Charmed and Frightened.

Renaming an incoming condition or immunity source cannot change the result; a
different ref with the same display name does not match. Existing name-keyed
`active_conditions` and player-facing condition text stay outside this rules-
identity cut. Condition state and appearance do not change.

Saving-throw context remains a separate exact boundary. Dark Devotion and
Brave match `SavingThrowEffectTag.CHARM`/`FEAR`; bite-prone, ghoul paralysis,
Undead Fortitude, and repeat saves carry exact cause refs and stable effect
IDs; Protection from Poison matches the Poisoned ref or POISON tag, never the
string `"Poisoned"`.

#### Perception modality and sunlight

`SensesType` is intentionally not reused here: it describes special senses
such as Darkvision and Tremorsense, not the ordinary hearing/sight/smell
modalities consumed by Keen Perception. Add the dependency-neutral closed
types:

```text
PerceptionModality
  SIGHT | HEARING | SMELL

LightExposure
  SUNLIGHT | NOT_SUNLIGHT

AbilityCheckRuleContext
  perception_modality: PerceptionModality?
  light_exposure: LightExposure?
```

Keen Hearing/Sight/Smell consumes the optional modality; absent modality keeps
the current “unspecified perception check” behavior. Sunlight Sensitivity
consumes `LightExposure.SUNLIGHT` from both `AttackRuleContext` and
`AbilityCheckRuleContext`. The existing tests pass these typed contexts instead
of dictionaries. There is currently no production sunlight/modality writer, so
Block 1 adds no scene inference: absence remains absence, and a future
production writer is a separate reviewed gameplay decision.

### 7.3 Divine Smite context removal

Move `ActionSelectionParameterKind` and `ActionSelectionParameter` to the
dependency-neutral `dnd/core/action_execution.py` owner so actions and handler
evidence share the canonical type.

Divine Smite replaces its four open keys as follows:

- duplicate prevention: detect the existing exact handler-owned APPEND
  modification from the Divine Smite `ContentRef`;
- selected slot level: one
  `ActionSelectionParameter(kind=LEVEL, value=<slot level>)` on the handler's
  typed evidence/APPEND modification;
- dice count: the appended `DamageRollPacket.damage.dice_numbers` remains the
  authority;
- creature-type bonus flag: stays internal derivation/debug information and
  does not cross the Event/SDK wire.

`RollModification(APPEND)` gains exact optional `source_ref` and
`selected_parameter` fields. Existing packet index remains internal ordering
evidence; Block 6 later decides the reaction presentation detail. Block 1 only
removes the open channel and preserves the same consumed resource, appended
dice, damage, and handler outcome.

## 8. Spell and persistent-effect provenance

Delete `SpellEvent.spell_id` and the runtime import/use of
`normalize_spell_id(self.name)`. Display name remains text only.

Reshape the existing `EffectOrigin` in place:

```text
EffectOrigin
  kind: EffectOriginKind
  source_identity: BoundContentIdentity?
  source_event_lineage_uuid: UUID?
  source_position: tuple[int, int]?
  base_spell_level: int?
  effective_spell_level: int?
```

This intentionally changes the current leaf-module boundary. Move
`EffectOrigin`/`EffectOriginKind` from `dnd/core/effect_types.py` to the exact
neutral owner `dnd/core/content/effect_origin.py`, beside the content identity
contracts. It imports the one canonical `BoundContentIdentity` from
`dnd/core/content/bound_identity.py`; it does not import runtime binding,
registry, action, or event code. `EffectOrigin.source_identity` uses that same
canonical value—there is no structurally duplicated origin identity.

All existing EffectOrigin consumers import from the new canonical owner.
Delete `dnd/core/effect_types.py`; do not leave a re-export compatibility alias.
Remove the deleted module from `SAFE_LEAF_MODULES` and add canonical-owner
assertions for `BoundContentIdentity`, `EffectOrigin`, and `EffectOriginKind`.
The existing content-contract dependency test already permits imports among
exact `dnd.core.content.*` siblings while forbidding gameplay/server imports;
extend its cold-import case to both new modules. Do not add a broad safe-leaf or
package exception.

`ActionEvent.get_effect_origin()` and `SpellEvent.to_effect_origin()` copy the
exact frozen `behavior_binding.definition` and typed lineage UUID. They do not
stringify `ContentRef.identity_key`, parse names, or consult the registry. The
embedded frozen visibility exists so a later delayed result can be reduced
without a live-registry lookup; it is not permission to disclose a non-PUBLIC
ref.

Existing condition, zone, spatial controller, and restraint consumers retain
`kind`, source position, and spell levels unchanged. This block changes their
provenance type only; it does not alter their state or appearance.

The subjective spell cue uses the selected tagged binding subject. Its
`spell_id` field is deleted. Exact catalog identity comes from that subject.

Analytics groups action use and action-rooted damage by a truthful public or
systemic subject, never a normalized display string, `effect_id`, event name,
or unrestricted implementation ref. `GameSummary` is objective/public and has
no player principal, so its closed reducer subject is distinct from subjective
disclosure:

```text
ActionSystemicDomain
  ACTION | ITEM_ACTION | SPELL | REACTION

PublicActionUsageRole
  CONFIGURED_ACTION | DEFINITION | SOURCE_ITEM | PROVIDER

PublicActionUsageSubject =
  PublicContentUsage {
    kind: PUBLIC_CONTENT
    role
    ref
  }  # ref must have frozen PUBLIC visibility
  SystemicUsage {
    kind: SYSTEMIC
    domain: ACTION | ITEM_ACTION | SPELL | REACTION
  }

ContentUsageCountV3
  subject: PublicActionUsageSubject
  usage: UsageCountV1

AppliedDamageByActionSubjectV3
  subject: PublicActionUsageSubject
  applied_damage: int

ActionEvent                             # Event-v2 wire facts
  action_usage_domain: ActionSystemicDomain
  public_action_usage_subject: PublicActionUsageSubject

DamageStatisticsV3
  incoming_raw: int
  applied: int
  normal_hit_point_damage: int
  temporary_hit_point_damage: int
  unapplied_remainder: int
  incoming_packets: int
  applied_packets: int
  blocked_packets: int
  applied_by_type: dict[str, int]
  effective_normal_hit_point_damage: int
  overkill_damage: int
  prevention: DamagePreventionStatisticsV2
  incoming_by_type: dict[str, int]
  after_affinity_by_type: dict[str, int]
  applied_by_counterparty: dict[str, int]
  applied_by_action_subject: tuple[AppliedDamageByActionSubjectV3, ...]
  applied_without_action_subject: int

CombatStatisticsV3
  turns_started: int
  turns_ended: int
  attacks: AttackStatisticsV1
  damage_dealt: DamageStatisticsV3
  damage_taken: DamageStatisticsV3
  healing_done: HealingStatisticsV1
  healing_received: HealingStatisticsV1
  movement: MovementStatisticsV1
  action_usage: tuple[ContentUsageCountV3, ...]
  item_action_usage: tuple[ContentUsageCountV3, ...]
  spell_usage: tuple[ContentUsageCountV3, ...]  # canonical subject order
  item_charges_spent: dict[str, int]
  action_economy_spent: dict[str, int]
  resources_spent: dict[str, int]
  conditions_applied: dict[str, int]
  conditions_removed: dict[str, int]
  kills: int
  deaths: int
  saving_throws: ResolutionStatisticsV2
  skill_checks: ResolutionStatisticsV2
  dice: DiceStatisticsV2

EntitySummaryV3
  entity_uuid: UUID
  side_id: str
  name: str
  initial: EntitySnapshotV1?
  final: EntitySnapshotV1?
  statistics: CombatStatisticsV3

SideSummaryV3
  side_id: str
  entity_uuids: tuple[UUID, ...]
  initial_combatant_count: int
  final_combatant_count: int
  surviving_combatant_count: int
  statistics: CombatStatisticsV3

GameSummaryV3
  schema_name: "dnd.game-summary"
  schema_version: 3
  game_id: str
  encounter_uuid: UUID
  started_at: datetime?
  ended_at: datetime?
  duration_seconds: float?
  rounds_started: int
  terminal_cursor: TerminalCursorV1
  outcome: GameOutcomeV1
  entities: tuple[EntitySummaryV3, ...]
  sides: tuple[SideSummaryV3, ...]
  unattributed_statistics: CombatStatisticsV3
  completeness: SummaryCompletenessV1
  provenance: SummaryProvenanceV1
  canonical_sha256: str
```

`dnd/core/action_execution.py` is the canonical dependency-neutral owner of
`ActionSystemicDomain`, `PublicActionUsageRole`, and the two public-usage
variants/union. `dnd/analytics/models.py` imports those exact classes;
`server/action_disclosure.py` imports the same `ActionSystemicDomain` for its
systemic binding variant. No structurally equivalent copy exists.

`PublicActionUsageSubject` is
`Annotated[PublicContentUsage | SystemicUsage, Field(discriminator="kind")]`;
both variants are frozen/`extra="forbid"` and their `kind` fields are the exact
Literal values shown above. Canonical ordering is by `kind`, then PUBLIC role
and complete canonical ref fields or SYSTEMIC domain. There is no implicit
class-name or key-shape discriminator. A `PublicContentUsage` may be frozen for
an action occurrence only from a `BoundContentIdentity` whose stored visibility
is PUBLIC.

The two required `ActionEvent` fields are privacy-safe objective Event-v2 facts.
`behavior_binding`, `configured_action`, and `source_item_identity` remain
excluded internal declaration evidence. `dnd/core/base_actions.py` owns one
private pure
`select_public_action_usage_evidence(...)` function over the complete frozen
binding/configured/source-item facts and exact event type. It selects domain in
this order: `EventType.TRIGGER_EVENT` or a bound definition whose exact
`ContentRef.definition_kind` is REACTION -> REACTION; coherent item-provided
action -> ITEM_ACTION; `EventType.CAST_SPELL` -> SPELL; every other ActionEvent
-> ACTION. The definition-kind clause closes the existing direct Hellish Rebuke
constructor without changing its gameplay event type; a handler-emitted Attack
still carries its own ACTION definition and remains ACTION. It selects subject
in this order: PUBLIC configured action; PUBLIC
definition; PUBLIC source item only for a coherent item-provided action; PUBLIC
provider only with `structural_provider == true`; otherwise the selected
systemic domain.

This split is deliberate: `action_execution.py` already owns the planned
canonical selection-parameter values and remains a dependency-neutral value
owner; `base_actions.py` already owns `ActionEvent` and imports the event enums,
binding values, and neutral usage types required by selection.
`dnd/core/content/runtime.py` remains the binding owner and does not import
event/public-usage models back through a cycle. No selector class, normalized
event model, or additional module is introduced.

Declaration validation recomputes both wire values from the excluded evidence
and requires exact equality before event publication, cost consumption, or
mutation. Missing, caller-selected, stale, or mismatched values reject.
Every enumerated BaseAction event override and both direct reaction constructors
in §5.4 use this seam. The complete
evidence/domain/subject tuple is immutable across `post()`, `phase_to()`,
`cancel()`, handler proposals, and model copies. A convolution child inherits
the root domain and subject byte-for-byte; no later phase or registry state may
reselect it. An ordinary weapon Attack cannot select ITEM_ACTION/SOURCE_ITEM,
and Acid Flask cannot expose its OBSERVED implementation.

`GameSummaryV3` is a standalone hard-cut schema. It reuses exact unchanged V2
value models, but does not inherit any action/effect identity field from V2.
In particular, `DamageStatisticsV2.applied_by_effect` is absent.
Delete `_build_effect_resolver()`, every `effect:/spell:/action:` key, and the
client's prefix stripping.

The remaining string-keyed maps in `CombatStatisticsV3` retain their existing
closed non-action meanings in this block: item semantic-key charge accounting,
action-economy/resource names, and condition semantic-key counts. They are not
binding subjects and are never consulted by action execution, projection, or
recipe selection. Migrating those independent metric vocabularies is outside
X01–X10. Unlike the removed action/spell/effect identity maps, their exact
field set is explicit above rather than inherited implicitly.

GameSummaryV3 never reapplies binding/configured/source-item precedence from
excluded event fields. The Event-v2 `public_action_usage_subject` is its sole
subject authority and `action_usage_domain` its sole usage-family authority.
Every `spell_id` read in `_build_effect_resolver`, `_reduce_terminal_event`, and
related statistics code is removed. Exact `EffectOrigin.source_identity`
remains internal objective provenance and never substitutes for the frozen
public subject.

`dnd/analytics/game_summary.py::reduce_game_summary()` remains the one and only
summary reducer and keeps its current authoritative event-history input and
lifecycle. For action identity it reads only the required Event-v2-visible
`public_action_usage_subject` and `action_usage_domain` fields already frozen on
the `ActionEvent`; it never reads a registry, `BehaviorBinding`, configured or
source-item identity, display text, Python class, or field-shape inference. No
normalized event model, serialized-input adapter, second reducer, replay reducer, or
parallel summary path is added.

An accounting action is exactly an ActionEvent with `application_id == null`.
Delete `_build_action_accounting_filter()` and its parent-name/source-UUID
heuristic. Every accounting action increments `action_usage` once under the
frozen subject; ITEM_ACTION additionally increments `item_action_usage`, SPELL
additionally increments `spell_usage`, and completion/cancellation update the
same `UsageCountV1` row. A convolution child has a non-null application ID and
cannot increment usage or costs. A genuinely nested action owns its own
declaration and null application ID and remains an accounting action.

For action-rooted applied damage, the reducer indexes the frozen subject by
ActionEvent lineage UUID. A `DamageAppliedEvent` resolves only through exact
terminal parent-lineage links or exact typed
`EffectOrigin.source_event_lineage_uuid`; it never searches for a nearest
name/type or reruns disclosure precedence. Root and convolution children carry
the same subject, so either exact lineage has the same grouping key. A cycle,
missing lineage, or lineage with no action subject increments
`applied_without_action_subject`. A real action root with no lawful PUBLIC
identity already carries its systemic subject.

Action-rooted applied damage increments one canonically sorted
`applied_by_action_subject` row. All applied damage also retains the existing
typed totals and affinity/type arithmetic. The invariant is:

```text
sum(applied_by_action_subject[*].applied_damage)
+ applied_without_action_subject
== applied
```

All three V3 usage families are ordered tuples rather than JSON maps. Rows are
grouped by the full tagged subject and sorted by discriminator/role/domain then
canonical `ContentRef` fields. Equal ref bytes under two roles remain separate;
no structured ref is degraded into a string key.

The active engine alias, worker/store/directory validation, history response,
SDK type, NeuroClient API type, and match-summary renderer accept V3 only.
The V3 reducer constructs `SummaryProvenanceV1` with exact
`reducer_id="dnd.analytics.game_summary.v3"`; neither the model's older default
nor the current explicit v2 constructor value may survive in a V3 summary.
Its persisted `MetricProvenanceV1(metric="damage_attribution")` sources/note
state the actual V3 law: action-rooted damage uses one structured lawful
PUBLIC/systemic subject and damage with no typed action root uses the explicit
unattributed bucket. Delete the legacy claim that an `effect_id` or nearest
typed parent action owns attribution; no display/effect/name wording survives
in canonical V3 bytes.
Existing V1/V2 bytes may remain physically untouched in old storage, but are
not an active union member and reject at the first schema boundary. Block 1
adds no old-summary decoder, converter, UI branch, dual writer, or migration.

`WorkerSummaryEvidence` remains the neutral envelope name but becomes frozen,
`extra="forbid"`, and V3-only:

```text
WorkerSummaryEvidence
  generation_id: UUID
  summary: GameSummaryV3
  source_event_digest: str
  source_combat_log_digest: str
```

It has no embedded component-version tag; the one durable component identity
is `WorkerTerminalComponentDescriptor.schema_id` in §14. The similarly named
`GameSummaryEvidenceV1` remains the unchanged reducer-input completeness model,
not the worker-summary component. `FinalSummaryRecord.summary` is
`GameSummaryV3`, not a union, and its outer `schema_version` is exactly
`Literal["dnd.game-summary.v3"]`. `_GAME_SUMMARY_ADAPTER` and
`_summary_from_row()` reject persisted V1/V2 rows on active read.

Objective replay v2 preserves the terminal action-identity subset for replay
parity; it is neither the complete reducer evidence nor a second reduction
input. Rename
`select_completion_frames_for_replay()` to
`select_terminal_frames_for_replay()`. From the replay seed through the terminal
cursor it retains every exact Event-v2 terminal frame whose phase is
`completion` or `cancel`, preserving original event index/cursor, combat-log
barrier, event UUID, lineage UUID, and source order; sparse frames are never
renumbered. Declaration, execution, and effect frames stay excluded. A duplicate
terminal frame for one lineage rejects. The final retained frame must still be
the terminal `EncounterEndEvent` completion at `terminal_event_cursor`.

`ObjectiveReplayBundle.events` therefore means every exact completion or
cancellation terminal frame after the seed. Its validator permits only those
two phases, requires strict source-cursor order, unique lineage UUIDs, exact
stream/generation/log barriers, and the final encounter-end completion. State
replay applies completion frames as today and treats cancel frames as typed
terminal no-ops. The one authoritative-history reducer counts both terminal
phases; replay merely preserves their auditable wire evidence. There is no
cancellation-to-completion coercion or compatibility reader.

`WorkerSummaryEvidence.source_event_digest` keeps its existing meaning: it is
the canonical digest of the complete ordered event history supplied to the one
reducer, including EncounterStart and every phase version. The only correction
is that its preimage uses the Event-v2 serializer, so the newly required public
subject/domain are included while excluded internal binding evidence is not:

```text
canonical_json_sha256([
  serialize_event(event)
  for event in authoritative_reducer_event_history
])
```

`source_combat_log_digest` likewise remains the digest of the complete ordered
combat-log sequence supplied to that reducer. Neither digest is redefined as a
digest of the smaller post-seed ObjectiveReplay bundle, and no downstream owner
pretends it can reconstruct EncounterStart, nonterminal phase versions, or
seed-time logs from that subset.

`WorkerGameSummaryStore._capture_end()` retains the existing full-input digests and
the existing replay coordinates; it does not build a second timeline. Extend
the existing internal `WorkerReplayCapture` with the already-known
`source_event_origin: int >= 0`, copied from
`_EncounterCapture.event_origin`; it is the inclusive EventQueue index of the
captured `EncounterStartEvent`. Add the matching
`source_combat_log_origin: int >= 0`, copied from the existing
`_EncounterCapture.combat_log_origin`; replay capture remains unavailable when
either source boundary is incomplete. Then make
the existing `build_worker_objective_replay()` require the matching
`WorkerSummaryEvidence` as well as the capture. Before it returns a replay it:

1. asks its existing `DndEventStream` source snapshot for the already-frozen
   slots from `source_event_origin` through `terminal_event_cursor`, validates
   and canonically decodes each existing `wire_event_json` as `WireEvent`, and
   requires the digest of that ordered Event-v2 object tuple to equal
   `source_event_digest`;
2. validates the existing combat-log backfill source from
   `source_combat_log_origin` through `terminal_combat_log_cursor` and requires
   its ordered canonical `CombatLogEntry` digest to equal
   `source_combat_log_digest`;
3. uses those same frozen event/log sources in its existing objective-frame/
   terminal-selector path exactly once; and
4. requires the returned post-seed completion/cancel frames to equal the
   corresponding cursor-indexed subsequence of that verified full preimage
   byte-for-byte.

Every existing production publication/GET caller already obtains evidence and
capture together and passes both. A wrong event/log origin, generation, game,
terminal coordinate, missing/reordered terminal event, or byte mismatch rejects before
the objective replay can enter local completion or the hosted spool. This uses
the existing replay builder at the existing terminal-publication seam after
the event-stream callback has drained; it adds no callback-order dependency,
second timeline builder, expected-frame cache, callback, or replay adapter.

The existing terminal spool manifest then hashes the summary-evidence and
replay components independently under the same generation/terminal
coordinates; `server/terminal_evidence.py` and
`server/worker_terminal_spool.py` validate those existing component hashes and
coordinates, not a fictitious replay-to-full-history digest equality.

One parity test runs `reduce_game_summary()` exactly once on the authoritative
event history and computes both existing source digests from its complete exact
inputs. It then proves that every post-seed completion/cancel replay frame is the
byte-identical terminal subsequence of the full Event-v2 event-digest preimage.
Configured, definition, structural-provider, source-item, systemic,
convolution-child, nested-action, parent-lineage damage, and EffectOrigin cases
therefore retain the exact subject/domain/application/lineage values selected by
the reduction, cancellation is not lost, both full-input source digests verify,
and the one produced `GameSummaryV3.canonical_sha256` revalidates. The test does
not rerun a reducer or claim that replay alone reconstructs the full summary.
This adds no service, registry, graph, snapshot, migration, adapter, or parallel
replay/summary path.

NeuroClient `GameSummary` is V3 only. `matchSummaryView.ts` renders every
ordered usage and applied-damage subject with its exact counts:

- `PublicContentUsage` joins the complete exact `ContentRef` to the existing
  installed public `ContentPresentationCatalogIndex` and uses that entry's
  display name as text only;
- if a historical PUBLIC ref is absent from the installed catalog, the row is
  still rendered as `Unavailable public <role>` with its counts and structured
  ref available to diagnostics; it is not dropped and no content-id/name parser
  is used;
- `SystemicUsage` uses the closed labels `Action`, `Item action`, `Spell`, and
  `Reaction` keyed directly by its enum member.
- `applied_without_action_subject` is rendered as `Unattributed`.

The role tag remains visible/evident and grouping always uses the structured
subject. Delete legacy `usageList()`/`labelEffectMap()` and all name/prefix
parsing. One client fixture covers all four PUBLIC roles, all four systemic
domains, a missing-catalog public ref, canonical row order, action-rooted
damage, unattributed damage, and exact counts.

## 9. Shared wire binding subject

`server/action_disclosure.py` is the single new shared server contract/policy
module. It is a pure function and closed DTO owner, not a service, registry, or
mutable authority.

```text
ActionBindingUse
  "behavior" | "trigger_behavior"

# ActionSystemicDomain is imported from dnd/core/action_execution.py

ActionBindingSubject = Annotated[
  PublicConfiguredAction {
    kind: Literal["public_configured_action"]
    use: Literal["behavior"]
    ref: ContentRef
  }
  | PublicDefinition {
      kind: Literal["public_definition"]
      use: ActionBindingUse
      ref: ContentRef
    }
  | PublicProvider {
      kind: Literal["public_provider"]
      use: ActionBindingUse
      ref: ContentRef
    }
  | Systemic {
      kind: Literal["systemic"]
      use: ActionBindingUse
      domain: ActionSystemicDomain
    },
  Field(discriminator="kind")
]

PublicSourceItemFact
  kind: Literal["public_source_item"]
  item_uuid: UUID
  ref: ContentRef
```

All variants are frozen and use `extra="forbid"`. The serialized `kind`, `use`,
and `domain` bytes are exactly the lowercase literals above; no class-name,
field-shape, or ref-kind inference is a discriminator. Exact variants require
a PUBLIC `BoundContentIdentity`. Subject validation enforces that configured
action is never trigger evidence; cue validators and the client compiler
enforce the complete §13.2 use/domain/cue matrix. The tagged role is part of
equality and client binding identity; the same `ContentRef` under two roles is
not interchangeable. Generated SDK decoding rejects a missing, unknown, or
mismatched `kind` before binding resolution.

`PublicSourceItemFact` is likewise frozen/`extra="forbid"`; its serialized
`kind` is always `"public_source_item"`, and its ref must come from the same
witness's coherent PUBLIC `BoundContentIdentity`. Missing/unknown tags or an
extra action-subject field reject.

The selected binding subject answers only “which behavior recipe/disposition
owns this action occurrence?” It does not erase other independently consumed
facts. For every cue:

```text
binding_subject: ActionBindingSubject?         # required on actionable roots
trigger_binding_subject: ActionBindingSubject? # only a distinct lawful trigger
source_item_fact: PublicSourceItemFact?         # auxiliary, never a binding role
owner_application_id: UUID?                    # §11
```

`source_item_fact` is a truthful tagged attribution row but not a primary
behavior binding role. This is the precise X09 split: one selected primary
`ActionBindingSubject` answers which behavior recipe/disposition owns the
occurrence, while the independently authorized
`{kind:"public_source_item", item_uuid, ref}` preserves the existing source
item consumer. It cannot select or relabel the action's binding subject.
Provider/root provenance remains frozen internally and crosses only when the
provider is itself the selected primary subject. This discharges the governing
block's source-item attribution requirement without pretending an item ref is
an action definition or inventing an item-generic body recipe.

Removing the old base attribution tuple must not remove condition identity.
`ConditionPresentationCue` gains a required `condition_ref: ContentRef` for
every delivered PUBLIC condition cue. It is frozen from the concrete
`ConditionEvent` binding and disclosed only when the same observer is
authorized for the target occurrence. A non-public condition emits no exact
condition cue. `condition_semantic_key` and `condition_name` remain diagnostic
or text fields and never select the recipe. Condition recipes keep consuming
the exact ref; condition appearance is unchanged.

Spatial-effect cues retain their existing direct state identity fields. They
are not reclassified as action binding subjects in this block.

Selection is deterministic:

1. lawful selected `PUBLIC_CONFIGURED_ACTION`;
2. lawful `PUBLIC_DEFINITION`;
3. lawful `PUBLIC_PROVIDER` whose provider principal is the acting entity;
4. the matching closed `SYSTEMIC` domain.

`ActionSystemicDomain` classifies the represented authoritative occurrence,
not the cue kind, `ActionBindingUse`, or renderer path. The pure classifier is:

```text
item_provider_markers(binding, source_item_uuid, source_item_identity) =
  (
    binding.provider.ref == source_item_identity.ref,
    binding.provider_runtime_owner_uuid == source_item_uuid,
    binding.behavior_owner_uuid == source_item_uuid
  )                                      # defined only for a present pair

item_provider_coherent(...) =
  if source-item pair is absent:
    true
  else:
    (not binding.structural_provider and all(item_provider_markers(...)))
    or not any(item_provider_markers(...))

item_supplies_behavior(binding, source_item_uuid, source_item_identity) =
  source_item_uuid is not null
  and source_item_identity is not null
  and not binding.structural_provider
  and all(item_provider_markers(...))
```

`dnd/core/content/runtime.py` owns these dependency-neutral predicates over the
existing frozen facts. Event validation requires the source-item UUID/identity
pair to be both present or both absent, to match the live declaration item, and
to satisfy `item_provider_coherent(...)` before any ordinary owner fallback.
The predicates neither import `ActionEvent` nor consult the registry. Event
projection evaluates both from frozen `ActionEvent` facts. Discovery evaluates
both earlier while the full binding still exists and freezes the classification
result and all of its inputs in the required
`ActionDiscoverySelectionEvidence` from §5.4. The HTTP
adapter does not rederive it from a reduced authored-attribution value or from
`is_item_use`. Every nonempty proper subset of the three markers is invalid, as
is a half-present source-item pair. An all-true tuple with
`structural_provider=true` is also invalid: a structural grant is not a live
item occurrence merely because its ref and owner values match an item-shaped
tuple. A partially coherent binding rejects rather than falling through to
ACTION or being advertised as ITEM_ACTION. Acid Flask, scroll, and lever item
behaviors have the boolean false and all markers true; an ordinary equipped
Attack has all markers false despite retaining its auxiliary source-item pair.

1. an `EffectiveHandlerPresentation` envelope or
   `CounterspellReactionEvent` root -> REACTION;
2. an `ActionEvent` for which `item_supplies_behavior(...)` is true ->
   ITEM_ACTION;
3. any remaining `SpellEvent` -> SPELL;
4. any remaining `ActionEvent` -> ACTION.

The discovery adapter applies the same subject precedence from only the frozen
evidence, including its controlling entity UUID and optional canonical category.
Its systemic domain is ITEM_ACTION when the validated `item_provider_bound` is
true, REACTION when the evidence category is absent (valid only for a handler),
SPELL when the evidence category is `ActionCategory.SPELL`, and ACTION for every
other present category. The adapter never reads a sibling category to classify.
It may not inspect `is_item_use`, execution token, name, Python type, ref kind,
or catalog. Configured, definition, and provider roles require their exact
frozen PUBLIC identities; provider additionally requires
`structural_provider == true` and
`provider_runtime_owner_uuid == behavior_owner_uuid == controlling_entity_uuid`.
A `bind_child()` provider never becomes `PUBLIC_PROVIDER`, even when both owner
UUIDs equal the actor; when no earlier role is lawful it falls through to
systemic. Item-supplied behavior is handled by ITEM_ACTION and the independently
authorized source-item fact. The same restriction applies to behavior and
trigger-behavior selection.
The optional source-item fact is selected independently from the exact frozen
UUID/identity pair only when its visibility is PUBLIC. Neither
`server/action_disclosure.py` nor `server/action_serialization.py` may import or
call a registry, content runtime, `BaseBlock`, declaration lookup, or catalog.

The exact provider/source-item test precedes the spell test, so Acid Flask is
ITEM_ACTION although its cue is Spell: its public item provider ref and runtime
owner equal the frozen source item. An ordinary equipped Attack is independently
bound to its Attack definition/actor provider; its weapon source-item pair
fails both provider equalities and cannot change the domain. An action emitted
by a handler classifies from its own event: Opportunity Attack is ACTION primary
behavior even when it uses an equipped weapon, while the handler is separate
REACTION trigger evidence.

`use="trigger_behavior"` does not imply domain `"reaction"`. Counterspell's incoming trigger is
classified from the incoming event (ordinary cast = SPELL; item-bound Acid
Flask = ITEM_ACTION). An exact handler identity or systemic handler envelope is
REACTION trigger evidence. Other triggering Action/Spell events use the same
four-step occurrence classifier. No domain is inferred from cue family,
display/class name, or client policy.

Source item selection runs independently after primary selection and may only
produce the auxiliary fact under the source-item row in §10.

The selector returns its evidence and selected row once. Server mappers, action
discovery serialization, SDK fixtures, and client tests consume the same
tagged result. Clients never repeat the precedence policy.

## 10. Privacy authorization function

### 10.1 General law

One observer must satisfy every atom required by one disclosed composite. Sets
from two observers are never unioned to authorize a subject or relationship.
Every exact ref must have frozen `ContentVisibility.PUBLIC`; OBSERVED,
DEVELOPER, and INTERNAL refs are ineligible even when their display name or
provider is known.

The event occurrence uses its frozen event-version observer sets. Action
discovery is for the controlling principal and uses that existing control
authority. The mapper does not perform later live-world or registry reads.

### 10.2 Closed role table

| Candidate | Required same-witness atoms | Fail-closed result |
| --- | --- | --- |
| Configured action | Actor identity; exact event/configured selection; PUBLIC configured identity; source position too if the cue discloses it. | Try the next role. |
| Definition | Actor identity; exact frozen behavior definition; PUBLIC visibility; source position too if carried. | Try the next role. |
| Auxiliary source item | Perspective controls the actor; frozen matching source-item UUID/ref; PUBLIC item identity. No non-controller source-item disclosure is added in Block 1. This produces `source_item_fact`, never the primary binding. | Omit the auxiliary fact. |
| Provider | Actor identity; PUBLIC provider identity; `structural_provider == true`; `provider_runtime_owner_uuid == behavior_owner_uuid == actor_uuid`. Equal owner UUIDs from `bind_child()` are not occurrence evidence. A distinct item/condition/handler instance is not observer-resolvable through current entity observer sets and is therefore ineligible. | Use systemic. |
| Systemic | Actor occurrence and any source position carried by the cue. No content ref. | Omit the action cue if even the occurrence is unauthorized. |
| Trigger behavior | All ordinary atoms for the chosen trigger role, plus the same witness's authorization for the triggering event occurrence and exact frozen direct trigger relationship. | Omit optional trigger subject; independently lawful result facts remain. |
| Condition state ref | Target identity; concrete condition-event occurrence; PUBLIC frozen condition definition; exact target/condition relationship, all for one witness. | Omit the exact condition cue; state projection follows its existing privacy path. |
| Direct causal edge | One witness authorized for the delivered child, its exact direct semantic-parent occurrence, and that exact relation; the parent cue is delivered in the same frame. | Set `parent_presentation_id` and every duplicate edge pointer to null; never search for an ancestor. |
| Application membership | One witness authorized for the delivered member occurrence and exact frozen application-owner/membership fact. Delivery of an application-owner cue or causal edge is not required. | Omit `owner_application_id` and any target-row membership reference without changing the causal-edge decision. |

Consequences frozen by this plan:

- Acid Flask's OBSERVED spell implementation never crosses.
- A controlling perspective may receive its PUBLIC auxiliary source-item fact.
- Acid Flask's primary binding is systemic item-action when its implementation
  is hidden; a non-controller receives no source-item fact.
- Multiattack exposes its selected PUBLIC configured-action subject, never the
  INTERNAL generic implementation.
- A hidden definition with a lawful PUBLIC structural provider is tagged
  provider, never definition. The same-owner live-provider form stays systemic
  and its provider ref is absent.
- `origin_root` remains internal provenance and is not a new subjective role in
  Block 1.
- A spell target row requires one witness for the spell root, its target or
  position occurrence, and the exact application membership. Withheld rows do
  not leak their engine index, UUID, target, or member references; an
  independently lawful result is not dropped merely because a row or parent is
  withheld.

### 10.3 Unconditional public-catalog closure

`/content/catalog` is an unconditional discovery surface, so it cannot rely on
an observer-scoped grant. Let `P` be the exact refs of installed declarations
whose frozen descriptor visibility is PUBLIC. A definition or recipe-preset
row is emitted only when its root is public, as today; every typed
`ContentRef` relationship carried by an emitted row must also belong to `P`.

`server/content_catalog.py::build_public_content_catalog()` applies one exact
projection rule before constructing `ContentCatalogResponse`:

- retain only `related_content_refs` whose target is in `P`, preserving source
  order;
- retain only `ContentDependency` rows whose `target_ref` is in `P`, preserving
  source order;
- apply the same public-target rule to preset `related_content_refs`;
- never mutate the installed declaration, delete an authoritative runtime
  dependency, relabel a hidden target, or emit a placeholder/systemic ref.

One manually enumerated typed postcondition in `server/content_catalog.py`
then validates all current catalog `ContentRef` carriers: entry roots, entry
and preset related refs, dependency targets, preset recipe refs, authored
condition-effect `source_ref`/direct `condition_ref`/selector-resolved refs/
origin-root gate refs, and spatial-transition replacement recipe refs. Each
must resolve to a member of `P`. This is explicit field code, not recursive
JSON inspection or a generic parser. If a future structured catalog field can
carry a definition ref, adding that field to the postcondition is a reviewed
schema-owner change; an unlisted mechanical subpayload cannot silently become
identity authority.

The field shapes remain content-catalog schema 7. `catalog_digest` and ETag
authenticate the filtered bytes. NeuroClient's existing
`contentPresentationCatalog.ts` index independently requires every returned
root to be PUBLIC and every typed related/dependency target to resolve to an
exact returned entry; a dangling or hidden-target fixture rejects. This is
defense in depth, not a second visibility policy.

The authoritative installed graph remains unchanged. In particular, an
OBSERVED spatial-effect implementation may still cross an existing
observer-authorized world/event surface; Block 1 changes no spatial definition,
world mapper, scene, ground, or runtime mechanic. The same boundary removes
the existing INTERNAL generic-Multiattack and OBSERVED spatial-effect relation
targets from unconditional catalog bytes without redesigning those systems.

## 11. Exact causality and application identity

Causal graph ownership and execution-application membership are independent
relations. Neither is derived from the other. Block 1 keeps the existing
presentation forest, target rows, SDK journal, mapper, and transaction; it adds
no graph, registry, or service.

### 11.1 Direct causal forest

Normalize only declaration/execution/effect/completion aliases sharing one
engine lineage and semantic subject. The direct semantic parent is then exactly
one of: (a) the immediate `Event.parent_event`; or (b) for a delivered
`EffectiveHandlerPresentation` envelope, the explicit frozen
`HandlerDispatchEvidence.emitted_lineage_uuids` membership naming that emitted
lineage. The handler case is a typed dispatch relation, not an ancestry search;
it does not make the triggering event the emitted result's parent. When that
exact parent has a delivered cue and the §10 same-witness proof passes, emit the
bidirectional
`parent_presentation_id`/`child_presentation_ids` edge. Otherwise emit the
independently lawful child as a root. Never walk to a grandparent, nearest
visible action, spell root, handler, application, condition, result, or
technical sibling. No other handler/event association creates an edge.

Two current duplicate edge pointers become nullable and must mirror
`parent_presentation_id`, including severance:

```text
ForcedMovementPresentationCue.actor_action_presentation_id: str?
LifeStatePresentationCue.causing_effect_presentation_id: str?
```

Their validators accept one exact delivered edge (both fields equal) or one
severed edge (both null). The mapper no longer raises or drops an otherwise
authorized forced-movement or life-state cue because its parent was withheld.
Parent-kind/source/target validation runs only when the edge exists. Existing
`ForcedMovementCause`, `LifeStateChangeReason`, result facts, and appearance do
not create an edge and are otherwise unchanged.

`SpellPresentationCue.child_presentation_ids` remains only the ordinary causal
child list. Remove the invariant equating it to the flattened target-row effect
IDs. This permits an application member whose structural parent is not a cue to
remain a graph root, and permits a genuine nested action such as True Strike's
Attack to be a Spell child without pretending it is a target-row result.

### 11.2 Exact execution-application membership

```text
PresentationCueBase.owner_application_id: UUID?
SpellTargetPresentation.disclosed_index: int
SpellTargetPresentation.application_id: UUID?
```

`ActionEvent.application_index` stays internal and never crosses the privacy
boundary. The delivered tuple's `disclosed_index` is projection-native,
contiguous `0..N-1`, and preserves the relative order of lawful source rows; it
is not renamed engine evidence. For an engine-backed convolution row,
`application_id` is the exact source `ActionEvent.application_id`. For a
root/position/fallback row where the engine allocated no UUID, it is null.
Non-null UUIDs are unique. Delete the old wire field `application_index` and
the mapper construction `presentation_id + ":application:" + index`.

If engine application 0 is withheld and application 1 is lawful, the delivered
tuple contains one row with `disclosed_index=0` and the exact UUID of engine
application 1. The private engine indices, UUID 0, target 0, and all its member
references are absent. This is explicit disclosed ordering, not silent
renumbering of an engine field.

Application membership follows the exact engine parent chain from the nearest
explicit `ActionEvent.application_id` owner until another explicit owner
begins. That walk computes membership only; it cannot create a graph edge.
Every authorized delivered member carries that UUID as
`owner_application_id`, including when the structural application event or its
direct causal parent has no cue. If the independent membership proof fails,
the owner UUID is null while independently lawful cue/edge dispositions remain.

`SpellTargetPresentation.effect_presentation_ids` is the ordered, privacy-
filtered cross-reference to delivered result cues belonging to that target
application; it is not a causal-child list. Each ID resolves to one permitted
result cue, occurs in at most one target row, matches the row's target/position
facts, and satisfies exact nullable membership equality:

```text
referenced_cue.owner_application_id == target_row.application_id
```

This equality is unconditional. A null row may reference only a cue whose
owner is also null; a non-null row may reference only the same exact UUID. A
referenced cue may have another exact parent or be a graph root. Withholding a
target row removes its references; a separately lawful result may still
survive with independently authorized membership.

`SubjectiveReplicationFrame` owns this whole-frame by-ID validation after it
has built its unique `presentation_id -> cue` map. The target-row DTO alone
cannot validate another cue. The generated SDK decodes the fields, then the
existing handwritten `subjectiveSse.ts` whole-frame validator repeats the
by-ID invariant for live and replay input before NeuroClient mapping; the
mapper never receives an asymmetric nullable pair.

Actions that do not already allocate an application UUID remain without one.
Block 2 owns their application model.

### 11.3 Existing client consumption

`buildCueGraph` validates only the delivered causal forest. `mapSpell` consumes
target `effect_presentation_ids` as application membership without requiring
those cues to be graph children. It builds one finite set of referenced member
presentation IDs: referenced members fold exactly once through the existing
spell-application seam and are not also emitted as roots; causal children
already consumed as members do not fold twice. Direct causal children not
named by a target row, including True Strike's Attack, remain ordinary graph
children. An authorized result whose target row is absent remains an ordinary
root. This is an index over existing DTO fields, not a second graph or hidden-
ancestry reconstruction.

`mapEncounter` retains its existing leaf rule for every encounter transition
except an authorized `TurnStartEvent` that is the exact direct parent of a
delayed action child. For that one existing causal seam, it maps the current
turn-start intent first and then folds each ordinary direct action child once.
Command Flee's Movement cue therefore remains a direct child of the delivered
TurnStart cue and is neither promoted to a root nor rejected by
`assertLeafCue`. This adds no encounter animation, timing, or movement policy;
it only makes the exact engine edge consumable by the existing mapper. All
other encounter transitions keep their current closed-child validation.

## 12. Action discovery API hard cut

The domain `AvailableActionInfo`/`AvailableHandlerInfo` must each retain the
one required frozen `ActionDiscoverySelectionEvidence` from §5.4. An action or
handler row without that complete evidence is invalid. The HTTP response does
not inherit either domain model directly.

Add explicit frozen `extra="forbid"` API DTOs in `server/api_models.py`; none
inherits a domain discovery model:

```text
APIAvailableActionInfo
  # every existing public mechanical/discovery field except source_item_uuid
  binding_subject: ActionBindingSubject
  source_item_fact: PublicSourceItemFact?

APIAvailableHandlerInfo
  name: str
  uuid: UUID
  enabled: bool
  trigger_event: str
  binding_subject: ActionBindingSubject

APIAvailableActions
  entity_uuid: UUID
  entity_actions: list[APIAvailableActionInfo]
  position_actions: list[APIAvailableActionInfo]
  self_actions: list[APIAvailableActionInfo]
  object_actions: list[APIAvailableActionInfo]
  remaining_movement: int
  handler_details: list[APIAvailableHandlerInfo]
  # existing authorization and resource fields

APIEntityHandlersResponse
  entity_uuid: UUID
  handlers: list[APIAvailableHandlerInfo]
```

The action and handler domain builders freeze the evidence as §5.4
requires. `server/action_serialization.py` invokes the one pure selector from
that value and explicitly maps every action group, nested handler detail, and
the separate `/entity/{id}/handlers` route. Delete the current
`AvailableActionsResult.model_fields`/`model_construct()` copy and
`APIAvailableActions(AvailableActionsResult)` inheritance.
`_serialize_entity_handlers()` returns only `APIAvailableHandlerInfo`; no raw
domain `AvailableHandlerInfo` remains in an HTTP response. The serializer
removes raw `behavior_attribution` and `configured_action_ref` from the API and
requires its controller UUID to equal the enclosing API entity UUID, and
contains no registry access, owner inference, or second precedence policy.
Execution tokens, display names, descriptions, and semantic keys remain their
existing command, text, or diagnostic fields and never become binding fallback.

`PublicSourceItemFact.item_uuid` is the sole public source-item UUID. The API
does not also expose raw `source_item_uuid`; engine dispatch retains the domain
UUID internally and NeuroClient uses `source_item_fact?.item_uuid`. No HTTP row
contains `discovery_evidence`, `behavior_binding`, `configured_action`,
`source_item_identity`, owner UUIDs, visibility, `item_provider_bound`, or
another internal evidence shape.

NeuroClient `actionBarModel.ts` and `gameIconResolver.ts` consume the tagged
subject plus the explicit auxiliary source-item fact. They do not choose
`definition_ref` over `provided_by_ref`, normalize a name, or reinterpret a
source-item ref as an action definition.

## 13. SDK, NeuroClient, and replay

### 13.1 Generated SDK

Regenerate the event contract and TypeScript SDK. Handwritten
`subjectiveSse.ts` validation accepts only the new discriminated subject union,
new contract versions, typed `EffectOrigin`, exact auxiliary source-item fact,
direct condition ref, and `owner_application_id`. Old `content_attributions`,
`spell_id`, raw discovery attribution, and open event context shapes are
rejected.

### 13.2 Existing client binding path

Keep `presentationBundle.ts::PresentationBindingIdentity` and
`PresentationBinding.key` as their existing compiled-source identities:
`definition`, `context`, or `system_profile`. They identify immutable compiled
rows, are covered by the bundle digest, and are not overloaded with
observer-specific subject role/use or a singular cue kind. One compiled
definition row may remain compatible with several cue kinds.

`presentationContentAttribution.ts` replaces plural/bare-definition selection
with one tagged-subject resolver and adds one pure resolved wrapper:

```text
ResolvedPrimaryPresentationBinding
  identity {
    subject: ActionBindingSubject      # validated use="behavior"
    cue_kind: Movement | Action | Attack | Spell | ItemAction | Shove | Counterspell
  }
  key: "resolved:" + canonicalJson(identity)
  compiled_binding: PresentationBinding
```

`identity` is deep-frozen; `presentationBundle.ts::canonicalJson` is the existing sorted-key
canonical encoder. The resolved key therefore includes exact subject `kind`,
`use`, complete ref or domain, and cue kind. The resolver first validates the
complete matrix below, then pairs the subject with exactly one compiled row:
configured/definition/provider subjects reuse `getDefinitionBinding(ref)` and
systemic subjects use the named exact system-profile row. Missing or
incompatible rows reject. Same ref bytes under configured/definition/provider
roles yield distinct resolved keys while lawfully reusing a compiled payload.

Mapper provenance, the presentation ledger, diagnostics, and replay store
`bindingKey=resolved.key` plus
`compiledBindingKey=compiled_binding.key`; recipe lookup consumes only the
compiled payload. Live/replay equality is over the resolved key. Trigger
subjects receive their own canonical tagged evidence key but never a
`ResolvedPrimaryPresentationBinding` or body payload. The bundle digest remains
over compiled rows, while the delivered frame digest covers the tagged
subject. No row multiplication, second bundle, registry, or role inference is
added. Primary binding and trigger evidence are resolved independently; a
trigger can never select or replace the root body recipe.

The existing bundle owns this finite primary matrix:

| Primary subject | Cue | Exact resolution |
| --- | --- | --- |
| `{kind:"public_configured_action", use:"behavior", ref}` | Action only | `getDefinitionBinding(ref)`; exact binding must include Action. All ten configured Multiattack refs are required. |
| `{kind:"public_definition", use:"behavior", ref}` | Exactly the cue kinds in that ref's compiled binding | Reuse that exact action/disposition/spell binding. |
| `{kind:"public_provider", use:"behavior", ref}` | Exactly the cue kinds in that provider ref's compiled binding | Reuse that exact binding payload; role remains part of the key. There is no provider-generic policy. |
| `{kind:"systemic", use:"behavior", domain:"item_action"}` | Spell only | `system_profile:action.systemic_item_spell`, `no_world_visual`; Acid Flask. |
| `{kind:"systemic", use:"behavior", domain:"reaction"}` | Action only | `system_profile:action.systemic_reaction_action`, `no_world_visual`; a hidden generic effective-handler envelope. |

Add the two systemic profiles to the existing
`presentationBundle.ts::SYSTEM_BINDINGS`/`PresentationSystemProfileId`. Their
exact profile IDs are `action.systemic_item_spell` and
`action.systemic_reaction_action`. This is an extension of the current bundle,
not another registry. Extend the existing `PresentationBindingPayload` union
with exactly one new discriminated branch:

```text
SystemicActionPresentationPayload {
  kind: Literal["systemic_action_profile"]
  profile: Literal[
    "item_spell_results_only"
    | "reaction_action_results_only"
  ]
}
```

`kind` and `profile` are literal bytes in the compiled bundle and its digest.
Each system binding names exactly one member; load, diagnostics, and the mapper
reject missing/unknown/mismatched values and switch exhaustively on the
profile. There is no callback or open policy payload. The item-spell
profile validates and folds the ordered target application member results via
§11, emits no cast body/projectile/route, never calls
`resolveAuthoredSpellPresentation`, and never needs the hidden Acid Flask ref.
Controlled `source_item_fact` remains auxiliary. The reaction-action profile
folds its lawful direct result children and emits no fabricated actor body.
Thus both profiles preserve result visuals while making no renderer claim for
the hidden root.

Privacy may lawfully leave either systemic root with no delivered visual
result: every Acid Flask application/member may be withheld, and a hidden
handler may modify/cancel its trigger without emitting a delivered child. Do
not fabricate an intent to satisfy disposition accounting. Extend the existing
`ClosedStateOnlyReason` with exactly
`"systemic_action_no_world_visual"`. After resolving one of the two exact
system profiles and mapping all lawful delivered members/children, the mapper
uses that reason iff the root produced zero intents. `exactCueDispositions()`
then records the existing `state_only` disposition with this reason and no
intent-evidence IDs. If any member/child produces an intent, the ordinary
folded/direct intent evidence path applies and this reason is forbidden. The
reason is accepted only for these two resolved system-profile payloads; a
public binding, another systemic domain/cue, or a missing/mismatched compiled
profile cannot use it. This extends the existing closed disposition channel;
it adds no empty clip, renderer route, graph, or fallback.

Every other systemic primary pair rejects in Block 1. In particular, the plan
does not invent generic Movement, Action, Attack, Spell, ItemAction, Shove, or
Counterspell recipes. A future non-public primary occurrence requires a newly
reviewed profile rather than a cue-family fallback.

The trigger matrix is evidence-only:

| Trigger subject | Resolution |
| --- | --- |
| `{kind:"public_definition", use:"trigger_behavior", ref}` | Retain exact tagged evidence for the authorized direct trigger relation. |
| `{kind:"public_provider", use:"trigger_behavior", ref}` | Retain exact tagged evidence; never resolve a body recipe from it. |
| `{kind:"systemic", use:"trigger_behavior", domain}` | Retain the occurrence classifier's exact lowercase domain; never resolve a body recipe. |
| `PublicConfiguredAction` | Reject; configured actions cannot be trigger subjects. |

Counterspell therefore retains incoming SPELL or ITEM_ACTION trigger evidence;
Opportunity Attack is ACTION primary plus REACTION handler trigger evidence.
Auxiliary source item still drives only its existing independent attack/item
profile selector. A direct `condition_ref` still selects the unchanged exact
condition recipe.

The two new `SYSTEM_BINDINGS` rows are complete binding rows, not entries that
fall through the current structural defaults:

| `profileId` | family | cue kinds | disposition | media failure | payload |
| --- | --- | --- | --- | --- | --- |
| `action.systemic_item_spell` | `action` | `spell` | `no_world_visual` | `fail_transaction` | `{kind:"systemic_action_profile", profile:"item_spell_results_only"}` |
| `action.systemic_reaction_action` | `action` | `action` | `no_world_visual` | `fail_transaction` | `{kind:"systemic_action_profile", profile:"reaction_action_results_only"}` |

The compiler preserves those fields verbatim while leaving the three existing
structural system rows unchanged. It may not rewrite the new rows to
`family="structural"`, `state_only`, or `{kind:"structural"}`. The existing
bundle digest covers the complete binding bytes; changing either identity or
payload changes the digest. The mapper switches on `payload.kind` and then
`payload.profile`; `identity.profileId` is lookup/evidence identity, not an
alternate rendering-policy switch.

These seven cue families remain the actionable-root domain in Block 1:
Movement, Action, Attack, Spell, ItemAction, Shove, Counterspell. Result/state
cues retain causal/application evidence but acquire no primary subject. The
matrix smoke enumerates every compiled compatible definition/provider pair,
all ten configured pairs, both systemic primary pairs, and rejects every other
primary subject/use/domain/cue-family tuple. A separate trigger test covers all
four systemic domains and proves trigger evidence cannot change the selected
primary binding. There is no open generic-policy arm. Block 8 later moves this
same finite closure to pre-stream admission.

`subjectivePresentationMapper.ts` continues to create the existing
`ClipIntent`, `NormalSubjectiveFramePresentationPlan`, and `VisualTransaction`.
Its existing client-owned evidence stores the exact tagged binding key and
direct-edge/application evidence. It does not infer identity from cue kind,
display text, recipe morphology, or scene state.

### 13.3 Replay and Studio

Player replay version 3 stores the projected v3 cue contract. Replay uses the
same SDK decoder and production mapper; there is no legacy adapter.

The exported/session evidence envelope rotates in place:

```text
ClientPresentationFrameArchiveSnapshot
  schema: Literal["neuroclient.client-presentation-frame-archive.v3"]
  player_replication_contract_version: Literal[3]
  player_replication_contract_hash: Literal[PLAYER_REPLICATION_CONTRACT_HASH]
  # existing client_run_id, retention, and entries unchanged
```

`CLIENT_PRESENTATION_FRAME_ARCHIVE_STORAGE` changes its exact session key to
`neuroclient.clientPresentationFrameArchive.v3` and its schema to
`neuroclient.client-presentation-frame-archive.v3`.
`presentationLedger.ts` uses that same v3 schema and exact version/hash in its
session-storage envelope and public snapshot. Before current-envelope
validation, the existing startup hard-cut owner unconditionally removes the
one retired key `neuroclient.clientPresentationFrameArchive.v2`; it never
parses or converts its bytes. A v3-key envelope with missing/wrong identity is
likewise dropped. `StudioEvidenceImport` accepts only a v3 archive, or the
existing reconciliation-incident envelope containing a v3 archive, and
validates the nested schema/version/hash before inspecting or decoding any
frame. A v2 archive, a missing identity, a wrong version, or a wrong hash
rejects even when its individual frame happens not to exercise a changed cue.
The reconciliation incident keeps its existing outer schema because the
nested archive is the frame-evidence contract owner. This is a version
rotation of the existing bounded evidence archive, not a new store, replay
format, or migration path.

Studio compatibility in Block 1 is deliberately mechanical. Except for the
one fail-closed source-item-preview boundary below, the current
Action/Spell/Condition Studio scenario builders, selection rules, fabricated
outcomes/HP/geometry/path facts, target cardinality behavior, and authoring UI
remain unchanged here. Replacing those builders with explicit SDK-valid
fixtures, freezing synthetic facts, proving authoring-selection coverage, and
removing catalog-order/cue-derived selection are the exclusive C07/C08 and
Block 8 work. Block 1 adds no Studio fixture generator, corpus, selector,
topology family, cardinality expander, default-selection law, or new Studio
module.

The player-replication v3 hard cut still requires existing Studio code to
compile against the new DTO. Adapt only the three current final synthetic frame
builders and their direct preview callers:

- `studioSubjectiveActionFrame.ts` remains the Action final-frame builder;
- `studioSubjectiveSpellFrame.ts` remains the Spell final-frame builder; and
- `ConditionStudioPreview.ts::buildConditionStudioFrame()` remains the
  independent Condition final-frame builder. It is not treated as a caller of
  either other builder.

- wrap the exact PUBLIC primary definition/configured-action ref already chosen
  by the current preview input in the matching tagged §9 behavior subject;
- wrap an already chosen exact PUBLIC trigger ref as
  `use="trigger_behavior"`; it remains evidence-only;
- carry an already chosen PUBLIC condition ref only in the direct condition
  field;
- never serialize a non-PUBLIC ref. A current synthetic branch lacking a lawful
  exact public subject may use only one of the two already-reviewed systemic
  §13.2 subject/cue pairs; every other missing/unlawful subject fails preview;
- set `application_id` and result `owner_application_id` to null for ordinary
  synthetic Studio rows, because Studio owns no engine allocation UUID. Keep
  the current target order/count and existing presentation IDs; do not invent an
  engine UUID or recover one from an index;
- in `buildConditionStudioFrame()`, replace the deleted cue base,
  `content_attributions`, and `spell_id` with the same v3 cue base, direct
  `condition_ref`, and tagged PUBLIC behavior subjects for the movement,
  attack, or spell definition already chosen by the current scenario. Replace
  its synthetic `application_index`/`application_id` pair with the current
  visible ordinal as `disclosed_index` and null application/result ownership;
  do not change its scenarios, topology, target cardinality, or fabricated
  neutral facts;
- copy only the direct parent/child relationships explicitly constructed by the
  current builder. Do not run nearest-visible reparenting or infer an edge from
  the selected recipe.

The current Action and Spell Studio source-item preview selectors are the one
necessary exception to unchanged preview controls. They own only catalog
definition refs; neither owns the coherent item-occurrence UUID/ref pair
required by `PublicSourceItemFact`. The literal `"action-studio-item"` belongs
only to the independent synthetic `item_action` scenario, is not UUID-shaped,
and is not an occurrence of an arbitrarily selected weapon definition. It may
not be reused, derived, hashed, or paired with the selected ref.

Until Block 8 supplies reviewed explicit synthetic occurrence fixtures under
C07/C08:

- disable and visibly label the Action preview source-item selector and the
  Spell item-provider preview selector as deferred to Block 8;
- stop passing their definition-only selections into the final-frame builders,
  and emit no Studio `source_item_fact`;
- remove the now-invalid preview-only source-item input/handoff fields rather
  than leaving ignored compatibility parameters; and
- preserve the Action recipe editor's existing authored source-item-match data,
  `selectActionPresentationProfile()`, public catalog relations, and every
  live/replay `PublicSourceItemFact` consumer unchanged.

This is the smallest X05/X09 privacy hard cut: a preview lacking an item
occurrence cannot claim one. It deliberately does not invent the synthetic
identity/substitution law owned by C08. All non-source-item Action/Spell
previews and every Condition preview retain their current behavior.

This is a schema adaptation for current preview behavior, not evidence that a
synthetic Studio frame occurred in gameplay and not a new identity authority.
It does not make Studio/live/replay semantic equality a Block 1 gate. The
existing Studio smokes cover representative current scenarios only: every
emitted v3 frame validates, PUBLIC refs keep their explicit tagged role,
non-PUBLIC refs are absent, synthetic application owners are null, and the
production mapper accepts the mechanically adapted frame. They do not claim
whole-catalog, all-scenario, or UI-selection closure; Block 8 owns those proofs.

`presentationDiagnostics.ts` validates the new tagged subject/resolution table,
auxiliary source-item consumption, and direct condition ref for any frame it is
given. It may not treat a missing definition recipe as permission to relabel a
provider or systemic subject. It gains no Studio catalog/admission policy.
## 14. Contract and activation hard cut

The following versions change atomically:

| Contract | Current | Block 1 |
| --- | ---: | ---: |
| Generated Event contract | 1 | 2 |
| Timeline contract | 1 | 2 |
| Objective replay contract | 1 | 2 |
| Player replication contract | 2 | 3 |
| Subjective player replay | 2 | 3 |
| Client presentation frame archive | 2 | 3 |
| Worker terminal spool schema | 2 | 3 |
| Worker summary evidence component | `dnd.worker-summary-evidence.v1` | `dnd.worker-summary-evidence.v2` |
| Active game-summary schema | 2 | 3 |

Event v2 changes `TIMELINE_CONTRACT_HASH`; timeline v2 in turn changes
`OBJECTIVE_REPLAY_CONTRACT_HASH`. The objective replay bundle, subjective
replay bundle, terminal spool content-type/schema, terminal evidence, generated
SDK constants, client frame-evidence archive, and rejection tests rotate in the
same packet. The summary
component descriptor changes independently to the exact schema ID
`dnd.worker-summary-evidence.v2`; its `WorkerSummaryEvidence.summary` field is
strictly `GameSummaryV3`. There is no duplicate inner evidence-version field.
The spool descriptor rejects the v1 component ID even when its JSON happens to
contain a V3 summary, and the v2 component rejects a V1/V2 summary even when
the descriptor ID is correct. No owner is allowed to silently retain the old
transitive hash or component ID under an unchanged version.

The exact component matrix is:

| Summary descriptor ID | Nested summary | Result |
| --- | --- | --- |
| `dnd.worker-summary-evidence.v2` | `GameSummaryV3` | Accept. |
| `dnd.worker-summary-evidence.v1` | `GameSummaryV3` | Reject in the component descriptor before file decode. |
| `dnd.worker-summary-evidence.v2` | structurally valid `GameSummaryV1` | Reject decoding `WorkerSummaryEvidence`. |
| `dnd.worker-summary-evidence.v2` | structurally valid `GameSummaryV2` | Reject decoding `WorkerSummaryEvidence`. |

The rejection fixtures recompute byte size, content digest, component path,
and ready-manifest digest so they prove this schema boundary rather than an
incidental integrity mismatch. No v1 alias, nested V1/V2 union, converter, or
compatibility decoder exists.

The server, SDK package, and NeuroClient build from the same reviewed
implementation. Old event/timeline/objective-replay/player-replication/
subjective-replay/frame-archive/spool contracts are rejected; no dual writer,
fallback decoder, or compatibility mapper is added. Historical game-summary V1/V2
bytes may remain inert in storage, but active stores/history/SDK/client do not
decode or serve them; they reject before use and are not relabeled.

No intermediate work packet is deployable. Activation occurs only after all
three implementation packets below pass together.

## 15. Implementation work packets

### WP1 — engine identity and closed Event v2

1. Reshape `BehaviorBinding`/`AuthoredBehaviorAttribution` and freeze visibility
   for each exact ref in `BehaviorBinder`; migrate every independent,
   structural-grant, live-child, item-materialization, arena, and map-editor
   call site to the exact two-owner plus structural-provider construction law;
   do not add a content digest.
2. Install the single ensure-binding function at `BaseAction.apply()` and
   before `SpellAction.spell_execution_scope()`; apply every direct-site
   binding/parent disposition in §5.3, including Opportunity Attack.
3. Freeze configured action and exact source item on `ActionEvent`; select and
   validate its canonical privacy-safe usage domain/subject for Event v2;
   route every enumerated BaseAction event override and the direct Counterspell/
   Hellish-Rebuke reaction constructors through the exact §5.4 constructor
   fields with no default or ambient fallback;
   delete the full item-presentation snapshot from BaseAction/Event and every
   producer, delete `ActionPresentationKind` authority, and install the exact
   potion cue rule in §5.4.
4. Freeze exact handler binding for every effected dispatch.
5. Close runtime rule contexts and transitive Event serialization as §7 states,
   including exact-ref condition immunities/receipt handles, the full
   underwater truth table, typed standalone combat-log wakeup, and excluded
   modifier caches.
6. Replace `spell_id`/string `EffectOrigin` with exact ContentRef/UUID fields.
7. Update every exact internal consumer and install GameSummaryV3 as the sole
   active summary schema, including Event-v2-field-only identity use by the one
   existing reducer, exact
   application ownership, structured damage attribution, completion/cancel
   replay parity, full-history Event-v2 source digests, and exact terminal-
   subsequence validation at the existing capture seam. Close
   `WorkerSummaryEvidence` and `FinalSummaryRecord` over V3 only; update worker
   production, local terminal publication, staged-adoption validation,
   directory persistence/history, and both generated SDK REST decoders. V1/V2
   reject at every active store/history/SDK/client boundary.
8. Generate Event contract v2; reject any remaining open wire member.

**WP1 gate:** domain outcomes for the audited action/reaction cases are
unchanged, every root is bound before mutation, and Event v2 is transitively
closed.

### WP2 — lawful projection, discovery, and replay v3

1. Add the closed shared subject DTO and pure selector.
2. Apply the exact privacy atom table to player replication and freeze the
   complete immutable selector-evidence tuple, including controller UUID, on
   every action and handler discovery row;
   close the unconditional public catalog over PUBLIC relation targets before
   any unconditional consumer receives it.
3. Replace plural ambiguous cue attribution and spell ID with one selected
   behavior subject, optional trigger subject, auxiliary source-item fact, and
   direct PUBLIC condition ref.
4. Remove nearest-visible semantic reparenting; make forced/life duplicate edge
   pointers nullable; decouple spell membership from graph children; add
   `owner_application_id`; replace wire engine indices with `disclosed_index`;
   preserve exact optional application UUIDs and lawful direct edges
   independently.
5. Replace inherited domain discovery DTOs with explicit API rows produced by
   the one pure selector from mandatory frozen inputs, never by a registry
   lookup or owner/role inference.
6. Rotate Event/timeline/objective replay/player replication/subjective replay/
   terminal spool identities and the worker-summary evidence component ID
   exactly as §14 states; regenerate SDK source.

**WP2 gate:** normal, direct, handler, Multiattack, Acid Flask, provider, hidden
parent, and anti-stitch cases serialize/decode exactly as §17 requires.

### WP3 — existing NeuroClient path and atomic activation

1. Consume the tagged subject and auxiliary source-item/condition facts in
   action discovery, recipe resolution, mapper evidence, replay, diagnostics,
   and summaries. The mechanical current-Studio DTO adapters consume tagged
   subjects and direct condition refs only; they emit no occurrence-free source
   item fact.
2. Add the exhaustive subject/use/domain/cue-family resolution matrix and the
   two explicit existing-bundle systemic no-world-visual profiles in §13.2.
3. Remove display-name, bare-ref, provider-as-definition,
   `presentation_kind`, and live/replay synthetic-application-ID fallbacks.
4. Mechanically adapt the existing Action/Spell/Condition Studio final frame
   builders to the v3 tagged fields as §13.3 states. Their scenario selection,
   fabricated neutral facts, topology, and cardinality do not change. Ordinary
   synthetic rows carry null engine application ownership. The only UI change
   is the fail-closed treatment of the two definition-only source-item preview
   selectors: disable/label them, remove their builder handoffs, and emit no
   false occurrence fact while retaining recipe authoring and live/replay
   source-item behavior. Explicitly defer C07/C08 fixtures, selection closure,
   and Studio fabrication removal to Block 8.
5. Rotate the existing bounded presentation frame archive to its exact v3
   schema/version/hash and make persistence/import reject v2 before frame
   decode; add no converter or store.
6. Prove live and replay frames produce the same binding key and direct graph.
7. Run the complete generation, backend, SDK, pure client, replay, and focused
   browser lanes.

**WP3 gate:** the complete v2/v3 generation is ready to activate as one hard
cut; no old live/replay contract or identity fallback remains. Current Studio
preview selection/fabrication remains visibly scheduled for Block 8 and is not
presented as Block 1 authority. The two source-item preview selectors are
visibly deferred rather than emitting an occurrence-free attribution.

## 16. Exact implementation inventory

This is a manual inventory, not an automated scanner. A newly discovered
semantic owner outside it is a plan-review event.

### 16.1 Engine/core owners

- `dnd/core/content/descriptors.py`
- new `dnd/core/content/bound_identity.py`
- new `dnd/core/content/effect_origin.py`
- `dnd/core/content/runtime.py` for the required structural-provider fact and
  strengthened item coherence; it does not own or import the Event selector
- `dnd/core/content/registry.py`
- `dnd/content_system/behavior_bindings.py` for binder-owned required
  `structural_provider` construction
- `dnd/content_system/action_definitions.py` as the canonical registered action
  declaration authority, including Drop; declaration bytes/behavior are
  otherwise unchanged
- `dnd/content_system/reaction_definitions.py` as the canonical registered
  reaction/handler declaration authority, including Opportunity Attack and
  Retaliation; reaction behavior is otherwise unchanged
- `dnd/content_system/runtime.py` for the reshaped binding gateway and exact
  two-owner/structural-provider forwarding law
- `dnd/content_system/item_materialization.py` for item-owned child binding
- `dnd/content_system/character_materialization.py`
- `dnd/content_system/dragonborn_character_grant_appliers.py`
- `dnd/content_system/extra_attack_character_grant_appliers.py`
- `dnd/content_system/origin_innate_spellcasting.py`
- `dnd/core/action_execution.py` for the canonical selection-parameter types and
  canonical `ActionSystemicDomain`/`PublicActionUsageSubject` values
- `dnd/core/base_actions.py` for the private pure selector, required event
  fields, and the BaseAction constructor-field method
- `dnd/core/action_types.py`
- `dnd/core/base_object.py`
- `dnd/core/base_block.py`
- `dnd/core/base_conditions.py`
- `dnd/core/values.py`
- `dnd/core/modifiers.py`
- `dnd/core/events.py`
- `dnd/core/combat_log.py` only to delete the two Counterspell authored-
  identity strings; typed interruption resolution/log behavior is unchanged
- delete `dnd/core/effect_types.py` after migrating all imports; no alias
- `dnd/core/saving_throw_types.py`
- `dnd/core/condition_types.py`
- `dnd/core/senses.py` (add ordinary `PerceptionModality`; keep special
  `SensesType` unchanged)
- `dnd/core/item_types.py`
- `dnd/core/naming.py` (remove action-runtime use only)
- `dnd/actions.py`
- `dnd/entity.py`
- `dnd/blocks/base_item.py`
- `dnd/blocks/equipment.py`
- `dnd/items/consumables.py`
- `dnd/items/spell_items.py`
- `dnd/items/weapons.py` for exact built-in underwater capability
  classification only
- `dnd/conditions.py`
- `dnd/spatial_restraints.py` for the explicit escape-action declaration event
- `dnd/spatial_effect_controllers.py` only to migrate the canonical
  `EffectOriginKind` import; controller behavior is unchanged
- `dnd/monsters/traits.py` for configured Multiattack execution,
  NaturalAttack declaration evidence, Dark Devotion/Brave and bite/ghoul/
  Undead-Fortitude saving context, and typed Keen Perception/Sunlight contexts
- `dnd/monsters/multiattack_definitions.py`
- `dnd/monsters/srd_roster.py`
- `dnd/monsters/srd_roster_items.py` for exact underwater-capability
  classification of roster-authored hand crossbows and javelins
- `dnd/monsters/bestiary.py`
- `dnd/monsters/skeleton_abilities.py`
- `dnd/maps/arena_layout.py` for the arena lever's exact item-owned child
  binding; arena/world behavior is otherwise unchanged

### 16.2 Direct action and typed-context owners

- `dnd/actions_functional.py`
- `dnd/reactions.py`
- `dnd/classes/barbarian.py`
- `dnd/classes/fighter.py` for the ExtraAttack weapon declaration helper call
- `dnd/classes/rage.py`
- `dnd/classes/paladin.py`
- `dnd/classes/sorcerer.py`
- `dnd/spells/abjuration.py` for exact immunity refs, typed saving context, and
  direct Counterspell reaction Event-v2 usage evidence
- `dnd/spells/conjuration.py`
- `dnd/spells/enchantment.py` for direct action identity, exact Sleep immunity
  preselection, and typed saving context
- `dnd/spells/evocation.py`
- `dnd/spells/illusion.py`
- `dnd/spells/infernal.py` for direct Hellish Rebuke reaction Event-v2 evidence
- `dnd/spells/necromancy.py`
- `dnd/spells/transmutation.py`
- `dnd/origins/dragonborn.py` for the breath-weapon declaration event
- `dnd/content_system/origin_character_grant_appliers.py`
- `dnd/content_system/condition_definitions.py`
- `dnd/content_system/condition_effect_population.py`
- `dnd/content_system/barbarian_character_grant_appliers.py`
- `dnd/content_system/character_grant_types.py`
- `dnd/content_system/character_grant_applier_runtime.py`
- `dnd/content_system/character_grant_receipt_cleanup.py`
- `dnd/analytics/models.py`
- `dnd/analytics/game_summary.py`
- `dnd/analytics/__init__.py`
- `dnd/ai/runtime/action_semantics.py` only to import the canonical moved
  `ActionSelectionParameterKind`; AI semantics are otherwise unchanged

### 16.3 Server, generated contracts, and SDK

- new `server/action_disclosure.py`
- `server/action_serialization.py`
- `server/content_catalog.py` for the unconditional PUBLIC-root/PUBLIC-target
  relationship projection and its manually enumerated typed postcondition;
  authoritative installed dependencies remain unchanged
- `server/api_models.py`
- `server/mapeditor_support.py` for the map-editor lever's exact item-owned
  child binding; map/world authoring is otherwise unchanged
- `server/world_projection.py` only for the canonical `BehaviorBinding`
  field-shape migration; world DTOs and projection behavior are unchanged
- action API handlers, the V3-only private `/game/evidence/summary` response,
  and every existing objective-replay call site passing its matching summary
  evidence in `server/event_server.py`
- `server/player_replication_contract.py`
- `server/player_replication/presentation.py`
- `server/player_replication/mapper.py`
- `server/timeline_contracts.py`
- `server/objective_timeline.py` for exact completion/cancellation terminal
  selection without renumbering
- `server/objective_replay.py`
- `server/worker_replay.py` for the same terminal selector plus full-source-
  digest/subsequence validation in its one existing replay builder
- `server/player_replay.py`
- `server/agent_runtime/observation_journal.py`
- `server/event_stream.py` as the unchanged existing terminal source-slot owner
- `server/game_summary_store.py` for the sole reducer invocation and the exact
  event/log source-origin coordinates on its existing internal replay capture
- `server/local_game_lifecycle.py` only where its typed terminal envelope
  carries and publishes V3-only `WorkerSummaryEvidence`
- `server/game_history.py`
- `server/game_gateway.py` only where it transports the hard-cut action API or
  adopts/revalidates V3-only staged terminal evidence, or transports versioned
  terminal/replay contracts; no deployment behavior changes
- `server/game_directory/contracts.py` and
  `server/game_directory/repository.py` only for the V3-only GameSummary
  canonical persistence/validation path
- `server/worker_terminal_spool.py` and `server/terminal_evidence.py` for the
  spool/replay rotations and the exact worker-summary component v2/V3-only
  validation
- `devtools/generate_event_contract.py`
- `server/event_contract.generated.json`
- `sdk/typescript/src/generated/contract.generated.json`
- `sdk/typescript/src/generated/contracts.generated.ts`
- `sdk/typescript/src/client.ts` for the V3-only worker-summary and hard-cut
  action-discovery REST decoders
- `sdk/typescript/src/directoryClient.ts` for the V3-only game-history summary
  decoder
- `sdk/typescript/src/subjectiveSse.ts`
- `sdk/typescript/src/replay.ts`: update the existing
  `assertObjectiveReplay()` in place for Objective Replay v2 terminal semantics,
  and keep subjective replay on the same whole-frame membership validator; no
  second decoder is added
- `sdk/typescript/src/tests/gameRouting.test.ts` for exact REST-boundary
  acceptance/rejection fixtures
- `sdk/typescript/src/tests/replication.test.ts` and
  `sdk/typescript/src/tests/replay.test.ts` for the identical nullable
  application-membership matrix in live decode and replay, plus the exact
  Objective Replay v2 terminal-phase/lineage/version boundary
- SDK replication/replay fixtures and tests
- `tests/content_identity.py` as the sole shared test-only constructor-evidence
  helper; it calls the production selector and is never a production binding
  or fallback owner
- `tests/manual/reactive_fixture_support.py` only to supply the complete
  required identity fields on its synthetic declaration event

### 16.4 NeuroClient owners

- `/home/tommaso/Dev/NeuroClient/app/src/engine/actions.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/ui/actionBarModel.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/ui/actionBar.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/ui/gameIconResolver.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/presentationContentAttribution.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/actionPresentationRecipes.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/actionPresentationDispositions.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/presentationBundle.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/presentationChannelRegistry.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/presentationDiagnostics.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/contentPresentationCatalog.ts`
  for PUBLIC-root and closed related/dependency-target validation only; it does
  not acquire a second visibility policy
- `/home/tommaso/Dev/NeuroClient/app/src/render/contentPresentationCatalogRepository.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/types.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationSemantics.ts`
  for the one closed systemic no-world-visual reason
- `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/runtimeResolver.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/types.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/render/presentationLedger.ts` for the
  changed binding evidence shape and v3 frame-archive identity/export
- `/home/tommaso/Dev/NeuroClient/app/src/engine/presentationPersistenceCut.ts`
  only to make the existing session hard-cut owner reject/drop archive v2;
  no migration or new persistence path
- `/home/tommaso/Dev/NeuroClient/app/src/replay/ReplayPresentationSession.ts`
  and `ReplayPresentationHeadDrain.ts` for V3-only generated replay/frame
  types, the shared whole-frame membership validator/production mapper, and no
  V2 adapter
- `/home/tommaso/Dev/NeuroClient/app/src/ui/actionStudio/studioSubjectiveActionFrame.ts`
  and `/home/tommaso/Dev/NeuroClient/app/src/ui/ActionStudioPreview.ts` only for
  the mechanical v3 DTO adaptation and fail-closed source-item preview boundary
  in §13.3
- `/home/tommaso/Dev/NeuroClient/app/src/ui/actionStudio/ActionStudioWorkspace.ts`
  only to remove the definition-only source-item preview handoff while retaining
  the existing recipe authoring data unchanged
- `/home/tommaso/Dev/NeuroClient/app/src/ui/studioSubjectiveSpellFrame.ts` and
  `/home/tommaso/Dev/NeuroClient/app/src/ui/SpellStudioPreview.ts` only for the
  same mechanical v3 DTO adaptation and removal of the definition-only
  source-item preview handoff
- `/home/tommaso/Dev/NeuroClient/app/src/ui/spellStudio.ts` only to disable and
  label its preview-only item-provider selector as Block-8-deferred; spell draft
  authoring and public catalog relations are unchanged
- `/home/tommaso/Dev/NeuroClient/app/src/ui/conditionStudio/ConditionStudioPreview.ts`
  for the mechanical v3 DTO adaptation of its independent
  `buildConditionStudioFrame()` final-frame builder; Condition Studio scenario
  selection, topology, cardinality, fabricated neutral facts, and appearance
  are unchanged
- `/home/tommaso/Dev/NeuroClient/app/src/ui/studio/StudioEvidenceWorkspace.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/ui/studio/StudioResolvedPresentation.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/ui/studio/StudioPlayerReplayImport.ts`
  as the strict V3 SDK replay decoder; a V2 bundle rejects before session or
  mapper construction
- `/home/tommaso/Dev/NeuroClient/app/src/ui/studio/StudioPlayerReplayPreview.ts`
  and `StudioReplayPresentationScene.ts` for V3-only replay transport/mapping
  and replacement of literal `V2 replay` UI/status text with `V3 replay`
- `/home/tommaso/Dev/NeuroClient/app/src/ui/studio/StudioEvidenceImport.ts` for
  strict player-replication-v3 frame evidence and replacement of its `full V2
  subjective replay` guidance; V2 frame/replay evidence rejects rather than
  being relabelled
- `/home/tommaso/Dev/NeuroClient/app/src/engine/gameSummary.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/api/encounterSummary.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/engine/encounterResult.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/ui/matchSummaryView.ts`
- `/home/tommaso/Dev/NeuroClient/app/src/ui/reconciliationDiagnosticsPanel.ts`
- relevant action bundle, subjective mapper, replay, reaction, and Studio smoke
  scripts named in §18
- `/home/tommaso/Dev/NeuroClient/app/scripts/action-profile-precedence-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/action-bar-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/action-ui-authority-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/presentation-bundle-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/condition-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/presentation-diagnostics-isolation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/presentation-disposition-matrix-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/potion-animation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/spell-studio-contract-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/action-studio-preview-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/studio-evidence-import-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/replay-presentation-head-drain-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/encounter-summary-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/encounter-result-window-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/ai-vs-ai-observer-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/catalog-action-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/counterspell-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/encounter-end-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/encounter-terminal-authority-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/equipment-transition-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/forced-movement-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/lifecycle-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/locomotion-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/movement-animation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/movement-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/presentation-head-drain-live-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/presentation-persistence-cut-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/reaction-presentation-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/subjective-presentation-semantic-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/subjective-production-adapter-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/subjective-animation-coverage-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/studio-transport-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/target-facing-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/targeting-authority-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/recovered-client-connector-vertical-smoke.mjs`
- `/home/tommaso/Dev/NeuroClient/app/scripts/vital-effect-presentation-smoke.mjs`

The result/movement/equipment scripts above receive schema-only fixture updates
for the removed base attribution field. Their domain payloads and appearance
assertions are not redesigned in Block 1.
- `tests/transition_sequences/emit_acid_splash_presentation_sequence.py`
- new
  `tests/transition_sequences/emit_acid_flask_systemic_item_spell_sequence.py`
- `/home/tommaso/Dev/NeuroClient/app/scripts/presentation-transition-sequence-check.ts`,
  extended with the closed case selector `acid-splash | acid-flask` rather than
  an arbitrary producer path. The Acid Flask case asserts hidden spell-ref
  absence, systemic ITEM_ACTION primary, controlled/redacted auxiliary source
  item, ordered result folding, and no authored-spell lookup/body/route in both
  the production live planner and isolated replay mapper.

### 16.5 Explicit deletions/no replacements

- `ActionPresentationKind` action-execution fields and potion producer use;
- `ActionEvent.source_item_presentation`;
- `BaseAction.source_item_presentation` plus every BaseItem/spell-item/attack
  writer that injects it into an action;
- `SpellEvent.spell_id` and `SpellPresentationCue.spell_id`;
- `CounterspellReactionEvent.reaction_content_identity` /
  `incoming_spell_content_identity` and their evidence-snapshot, combat-log,
  generated-contract, SDK, projection, and replay copies;
- `EffectOrigin.source_id: str` and string lineage UUID;
- `dnd/core/effect_types.py` after moving its canonical contracts to
  `dnd/core/content/effect_origin.py`; no compatibility re-export;
- every public-summary `spell_id` grouping key and remaining action-runtime
  `normalize_spell_id()` consumer;
- active GameSummary V1/V2 readers/writers, `DamageStatisticsV2.applied_by_effect`,
  `_build_effect_resolver()`, `effect:/spell:/action:` keys, and client prefix
  parsing;
- `_build_action_accounting_filter()` and its parent-name/source heuristic;
- completion-only `select_completion_frames_for_replay()` (replaced directly by
  the v2 completion/cancel terminal selector);
- Action Studio's preview-only `sourceItems` selection handoff,
  `selectedSourceItemRef()`, and `StudioActionFrameBuildInput.sourceItemDefinitionRef`;
  replace the interactive preview selector with a disabled Block-8-deferred
  notice, while retaining recipe-authored source-item match data and the
  production profile matcher;
- Spell Studio's preview-only `selectedSourceItemBySpellKey` state,
  `setSourceItemDefinitionRef()` handoff, and
  `StudioSpellFrameBuildInput.sourceItemDefinitionRef`; replace the interactive
  provider preview selector with the same disabled/deferred notice, while
  retaining public catalog relations and spell draft authoring;
- open `DiceRollResultEvent.context`;
- `SAVING_THROW_CONTEXT_KEY` dictionary wrapper and `condition_context: str`;
- name-keyed condition-immunity rule storage/APIs/receipt handles (replaced by
  complete condition `ContentRef`, without a string adapter);
- open `combat_log_origin` string key (replaced by the excluded typed carrier
  boolean), plus unread `death_save`, `weapon_slot`, and Divine Smite context
  keys;
- the manual Opportunity Attack child-binding assignment;
- base `content_attributions` tuple, after direct replacement by primary action
  subject, optional trigger subject, auxiliary source-item fact, and direct
  condition ref;
- `AuthoredBehaviorAttribution` as a discovery model, discovery
  `behavior_attribution`, raw `configured_action_ref`, and raw API
  `source_item_uuid`;
- `APIAvailableActions(AvailableActionsResult)` inheritance,
  `AvailableActionsResult.model_fields`/`model_construct()` HTTP copying, and
  raw `AvailableHandlerInfo` HTTP/error-detail serialization;
- client plural/bare-definition attribution selection;
- client presentation frame archive v2 storage/export/import identity,
  replaced directly by the v3 version/hash-bound envelope with no converter;
- nearest-visible semantic reparenting;
- mapper-synthesized application IDs, and the wire's misleading engine
  `application_index` name (replaced by projection-native `disclosed_index`).

## 17. Required observable cases

Tests are value-in/value-out at the smallest stable owner. They do not assert
private helper call order, class layout, mock choreography, exact animation
timing, or arbitrary sleeps.

### 17.1 Engine binding and provenance

1. A normally registered action emits the same exact definition/provider/root
   binding selected at admission.
2. Each known direct constructor in §5.3 executes with its own exact definition
   and exact causal parent; ambient scope does not invent a provider.
3. Missing direct-action declaration rejects before costs, events, or mutation.
4. Retaliation and another emit-and-return-`None` handler retain exact effected
   handler evidence.
5. Opportunity Attack retains its Attack definition, exact movement parent, and
   separate reaction trigger; it never copies the handler definition.
6. All ten configured Multiattack roots retain their distinct selected ref;
   child attacks retain their own definition and direct root/application edge,
   without duplicating the configured ref. The INTERNAL generic Multiattack ref
   never becomes the public subject.
7. `SpellAction.apply()` binds before spell scope, so its saving-throw cause ref
   is non-null and exact.
8. Sunbeam, Eyebite, and Telekinesis first follow-ups carry the spell effect
   event as direct parent.
9. Drop is a root; Command Flee's Move is parented to its exact TurnStart event
   with Command condition/handler identity kept separately.
10. Registry replacement or display-name mutation after declaration leaves
   frozen output unchanged.
11. Structural character grants freeze both owner UUIDs to the granted entity
    with `structural_provider=true`; a live action/condition child freezes its
    own supplied owner, the bound provider's existing owner, and
    `structural_provider=false`. Equal owners do not erase that distinction. A
    hidden child under a PUBLIC same-owner structural provider selects
    PUBLIC_PROVIDER; the same tuple from `bind_child()` stays systemic and leaks
    no provider ref in discovery, handler HTTP, live projection, or replay.
    Structurally granted trigger evidence remains eligible; same-owner live-
    provider trigger evidence does not. The required field has no default, and
    production construction outside the binder is forbidden.
12. A materialized Acid Flask and spell scroll use-action template freezes
    both owners to its source item and remains valid after the executable copy
    names the acting entity. An ordinary equipped-weapon Attack freezes both
    action owners to the actor while carrying only auxiliary weapon identity.
    All six nonempty proper subsets of the three item-provider markers reject
    both discovery classification and execution before costs or events; in
    particular, matching provider ref/owner with a mismatched behavior owner
    cannot fall through as an actor-owned ACTION. A half-present source pair
    likewise rejects; complete all-false markers remain the lawful auxiliary-
    item case.
13. Arena and map-editor lever action templates freeze both owner UUIDs to the
    concrete lever item. Their existing authored/environment behavior is
    unchanged, and a deliberately mismatched lever owner rejects.
14. Drop resolves its exact declaration through
    `dnd/content_system/action_definitions.py`; Opportunity Attack and
    Retaliation resolve their exact handler/reaction declarations through
    `dnd/content_system/reaction_definitions.py`. Binding tests compare the
    frozen definition to those canonical declarations and reject a mismatched
    declaration rather than constructing identity from Python/display names.
15. Every action and toggleable-handler discovery row owns the one required
    frozen selector-evidence tuple from §5.4. Configured Multiattack proves its
    PUBLIC configured identity without a registry read; an actor-owned PUBLIC
    provider proves `structural_provider=true` plus both owner UUID equalities;
    a same-owner `bind_child()` negative falls through to systemic; Acid Flask
    proves the item predicate; a missing/tampered controller, input, boolean, or action category
    rejects the domain row before HTTP serialization. Every action category must
    equal its frozen evidence category; a handler requires that category absent.
    The action and separate handler APIs use the same pure selector and contain
    no second precedence policy.
16. Every §5.4 BaseAction declaration override constructs the required internal
    evidence plus public subject/domain explicitly; a missing field rejects at
    construction. Counterspell and Hellish Rebuke each freeze their already
    bound handler, REACTION domain, and exact lawful reaction subject before
    publishing their direct event. A missing/mismatched handler binding rejects
    before reaction/slot/resource consumption, and neither path borrows the
    incoming spell/attack identity or invents a default.
17. Every direct synthetic ActionEvent-family constructor in the named test
    inventory supplies a complete coherent mapping explicitly. The shared
    test-only helper delegates subject/domain selection to the production pure
    selector; missing/tampered fields still reject, and no production owner can
    import or invoke the helper.

### 17.2 Context closure with gameplay parity

1. Rage and Reckless Attack produce the same modifiers from typed attack facts.
2. The full §7.2 underwater table covers ordinary/exception/swim-speed melee,
   ordinary/exception normal and long-range attacks, and global ignore. A
   ranged exception still automisses at long range; global ignore suppresses
   both attack penalties; protected/unprotected Swim cost stays unchanged.
   Roster-authored Spy hand crossbow and thrown-javelin definitions receive the
   same exact-ref capability as their corresponding built-in weapon facts.
3. Static immunity matches an exact bound condition ref despite display-name
   mutation; a different ref with the same name does not match.
4. Contextual immunity sees only exact ref/tags. Freedom of Movement blocks
   magical Grappled/Restrained/Paralyzed and preserves nonmagical behavior.
5. Two source-owned immunities for one ref install/remove independently through
   exact receipt handles; rollback and restart retain the complete refs.
6. Sleep and Color Spray preselection use exact Charmed/Blinded refs.
7. Dark Devotion, Brave, Protection from Poison, bite-prone, ghoul paralysis,
   Undead Fortitude, and Draconic Presence preserve saving outcomes with typed
   context; no condition-name key survives.
8. Divine Smite can append once, consumes the selected slot, appends the same
   dice packet, and cannot duplicate itself; no open context survives.
9. Death save round/turn/encounter facts survive as explicit typed fields.
10. Standalone combat-log carriers still wake observation projection through the
   typed excluded marker; normal registered completion logs are not duplicated.
11. Recursive generated schemas contain none of the forbidden open/runtime
   members.
12. Keen Hearing/Sight/Smell and Sunlight Sensitivity attack/perception cases
   preserve `test_53` outcomes using the typed modality/exposure values; absent
   context remains absent and no scene fact is inferred.

### 17.3 Exact spell/effect identity

1. Spell -> condition/zone/restraint provenance preserves the complete
   `ContentRef`, typed lineage UUID, position, and base/effective levels.
2. True Strike melee/ranged display variants resolve to the same exact spell
   definition without distinct normalized IDs.
3. Changing a spell display name cannot change projection or analytics
   grouping.
4. New summaries emit canonically ordered lawful usage and damage-attribution
   subjects copied from required Event-v2 facts; an OBSERVED Acid Flask
   implementation never appears. Missing/tampered domain or subject rejects at
   declaration/wire decode rather than being reconstructed by analytics.
5. Action-rooted applied damage groups by the same structured subject; damage
   without a lawful action root increments the explicit unattributed count, and
   their sum equals total applied damage.
6. GameSummaryV3 persists, serves, decodes, and renders without display-ID or
   prefix parsing. The existing `/games/{id}/summary` history route serves
   schema version 3, and active store/history/SDK/client boundaries reject
   V1/V2, including an old-version value reaching the history decode boundary.
   Its provenance reducer ID is exactly `dnd.analytics.game_summary.v3`.
   The persisted damage-attribution provenance describes structured
   PUBLIC/systemic action-root subjects and the no-action-root bucket, with no
   `effect_id`, nearest-parent, display-name, or prefix claim.
7. Match summary renders every V3 public/systemic row and exact count; a missing
   public catalog row uses the explicit unavailable disposition.
8. Worker terminal publication names its summary component exactly
   `dnd.worker-summary-evidence.v2` and embeds a V3 summary. Descriptor v1 plus
   V3 rejects at spool descriptor validation before component decode.
   Descriptor v2 plus V1/V2 rejects during typed component decode and remains
   rejected at gateway/directory active-read boundaries; the HTTP SDK routes
   independently reject unversioned worker/history envelopes containing V1/V2.
9. Objective replay retains the exact completion and cancellation Event-v2
   evidence used by the one authoritative-history reduction, preserves sparse
   cursors, rejects duplicate terminal lineages/nonterminal phases, and ends
   with EncounterEnd completion. Its retained subject/domain/application/
   lineage bytes equal the corresponding post-seed subsequence; the complete
   reducer inputs independently revalidate the full source event/log digests,
   and the one produced V3 canonical summary digest revalidates without a
   second reduction. The one existing objective-replay builder requires the
   matching summary evidence/capture and rejects a wrong event/log source origin,
   generation, terminal coordinate, full-source digest, or terminal-subsequence
   byte before terminal publication. The public TypeScript
   `decodeObjectiveReplay()` accepts the same exact completion/cancel language,
   enforces the same unique-lineage/final-completion law, and rejects v1.
10. Usage counts one null-application accounting root on completion or cancel;
    a convolution child with non-null application ID cannot count usage/cost,
    while a genuinely nested null-application action does. No parent-name/source
    heuristic survives.

### 17.4 Privacy and projection

1. Public ordinary action -> `PUBLIC_DEFINITION`.
2. Ten configured Multiattacks -> ten `PUBLIC_CONFIGURED_ACTION` subjects.
3. Controlled Acid Flask -> systemic item-action primary plus PUBLIC auxiliary
   source-item fact; its OBSERVED spell ref is absent.
4. Non-controlled Acid Flask -> systemic item-action primary and no source-item
   fact; no private ref.
5. Hidden definition + lawful PUBLIC provider with
   `structural_provider=true` -> provider tag, never definition tag. The
   otherwise identical same-owner `bind_child()` provider with the boolean false
   -> systemic, and its provider ref is absent.
6. PUBLIC definition + hidden provider -> definition only; provider omitted.
7. A definition atom from observer A and provider/location atom from observer B
   cannot be stitched.
8. Effected passive handler -> exact lawful trigger subject or systemic
   reaction; result facts stay independently projected.
9. Counterspell's ordinary incoming event is SPELL trigger evidence and an
   incoming Acid Flask is ITEM_ACTION; neither is relabelled REACTION.
10. Opportunity Attack is ACTION primary plus REACTION handler trigger; a
    hidden generic handler envelope uses the systemic REACTION+Action profile.
    Its equipped weapon may remain an auxiliary source-item fact but fails
    `item_supplies_behavior` and cannot relabel the Attack as ITEM_ACTION.
11. Unknown/unlawful occurrence -> no action cue rather than a fabricated ref.
12. A PUBLIC condition cue carries its direct exact `condition_ref` and resolves
    the unchanged condition recipe; a non-public condition ref is withheld.
13. Acid Flask's systemic ITEM_ACTION+Spell profile folds its lawful results in
   live and replay without exact spell lookup or fabricated cast visuals.
   Its item-provider binding satisfies `item_supplies_behavior`; an otherwise
   identical ordinary weapon Attack with a source-item UUID does not. A
   provider-ref/provider-owner match with an actor-owned behavior also does not
   freeze `item_provider_bound` and cannot be advertised as ITEM_ACTION.
14. Each allowed and rejected subject/use/domain/cue-family matrix pair behaves
    exactly as §13.2 specifies.
15. The compiled bundle contains the two exact systemic action rows in §13.2.
    Changing either payload changes the bundle digest; each row accepts only
    its one cue kind; and an identity/profile/payload mismatch rejects rather
    than falling back to `profileId` or the structural system-binding loop.
16. Same compiled definition bytes reused under two lawful role/cue
    combinations produce distinct canonical resolved keys but the expected
    identical `compiledBindingKey`. A resolved-key/subject/cue mismatch and a
    compiled identity/profile/payload mismatch each reject at their own seam.
17. A lawful systemic Acid Flask root whose every application/member is
    privacy-withheld and a lawful systemic handler root that modifies/cancels
    its trigger without a delivered result each emit zero intents and exactly
    one `state_only/systemic_action_no_world_visual` disposition. The same
    reason rejects for a public root, an unreviewed systemic pair, or a root
    that produced any intent.
18. The serialized public catalog contains the PUBLIC Acid Flask item but no
    occurrence of its OBSERVED spell ref in any typed field. Every entry/preset
    relationship target belongs to the exact returned PUBLIC entry set; all
    existing non-PUBLIC generic-Multiattack and spatial-effect relation targets
    are likewise absent, while their installed authoritative dependencies are
    unchanged. Standalone and gateway catalog bodies have the same closure and
    their digest/ETag authenticate the filtered bytes.
19. Legitimate PUBLIC `grants_spell` relations remain in the public catalog;
    a hidden-target edge does not. Block 1 does not redesign or certify Spell
    Studio's provider-option selection. Acid Flask's live/replay systemic
    observation contains only its systemic subject and lawful PUBLIC item fact;
    neither its hidden ref nor an identity hash derived from it appears.
20. NeuroClient catalog construction rejects a non-PUBLIC root and a dangling
    related/dependency target. The subjective Fog/zone smoke obtains its
    OBSERVED spatial ref from an explicit observer-authorized fixture, not from
    unconditional public-catalog metadata.

### 17.5 Causality, SDK, client, replay

1. A delivered exact direct parent produces one bidirectional edge. A hidden
   direct parent leaves the independently lawful child as a root; no ancestor
   bypass is created.
2. A lawful forced-movement result whose action parent is withheld survives
   with both parent pointers null. A lawful life transition whose impact is
   withheld likewise survives with both parent pointers null.
3. Same-lineage event-phase aliases collapse without changing semantic parent.
4. A spell target row may reference a lawful application member whose causal
   parent is severed: the result is a graph root, retains the exact authorized
   owner UUID, and is not falsely listed as a Spell causal child.
5. Given hidden engine application 0 and lawful application 1, one target row
   crosses with `disclosed_index=0` and exact UUID 1; no engine index, UUID,
   target, or member reference for application 0 crosses.
6. A fallback row without an engine application UUID carries null, and its
   results do not receive a synthetic owner.
7. True Strike's Attack engine parent is exactly its executing SpellEvent;
   after phase-alias collapse it is the Spell cue's ordinary direct child, not
   trigger evidence or a fabricated target effect.
8. Action discovery API and subjective cue select the same tagged subject for
   the same controlled execution. Discovery equality is derived from the
   required frozen evidence tuple; deleting or tampering with controller/owner/
   configured/source-item/category evidence, or substituting a reduced
   attribution, fails rather than invoking a registry lookup or recomputing
   precedence.
9. SDK decode, live NeuroClient mapping, and replay mapping produce the
   identical binding key and direct graph.
10. Same `ContentRef` under two different role tags remains two different
    binding identities. Missing, unknown, or mismatched `kind` bytes reject;
    field shape is never used to infer the role.
11. A missing delivered binding fails before render; no name/bare-ref fallback.
12. Auxiliary source-item fact selects the same existing attack/item profile as
    before but cannot alter the action binding subject.
13. All three potion drink definitions retain the existing specialized cue and
    visual result without any action/event presentation snapshot; a spell item,
    weapon attack, and ordinary item-bound action retain their own cue family.
14. Representative current Action, Spell, and action-reuse Condition previews
    compile through all three existing final-frame builders with the mechanical
    §13.3 v3 DTO adaptation. The independent Condition builder emits the new cue
    base, direct condition ref, tagged already-selected movement/attack/spell
    subject, disclosed ordinal, and null application ownership. Exact PUBLIC
    refs retain their explicit tags, hidden refs are absent, ordinary synthetic
    application owners are null, and no generated fixture/corpus/selector or
    Studio selection/topology change is introduced. The two definition-only
    source-item preview selectors are the sole exception: they are visibly
    deferred and cannot emit `source_item_fact`; source-item recipe authoring
    and live/replay profile behavior remain unchanged.
15. Old Event/timeline/objective replay/player replication/subjective replay/
    terminal spool versions each reject at their public decoder boundary.
16. When a spell target references an authorized result whose causal parent is
    severed, live and replay mapping emit exactly one result intent and one
    evidence association through the spell-application seam; the same cue is
    not mapped again as a top-level root.
17. True Strike's direct Attack child, which is absent from target membership,
    is folded exactly once as the ordinary Spell causal child in live and
    replay mapping; it is never discarded as an unreferenced application result
    or mapped twice.
18. An authorized Command Flee activation preserves the direct
    TurnStart-to-Movement edge. Live and replay mapping emit the existing
    turn-start intent followed by exactly one Movement child intent; the child
    is not rejected by the encounter leaf assertion, promoted to a root, or
    mapped twice. Encounter transitions without this exact delayed-action edge
    retain their existing leaf behavior.
19. An authorized generic effective-handler envelope is the direct parent of
    each emitted lineage named by its frozen dispatch evidence, and live/replay
    mapping folds each delivered result once. If the envelope or exact dispatch
    relation is withheld, the independently lawful emitted result is a root;
    it never bypasses to the handler's triggering event. Retaliation and
    Opportunity Attack retain their specialized primary/trigger dispositions.
20. Whole-frame validation accepts both a null application row referencing a
    null-owner result and an exact non-null UUID match. It rejects a null row
    referencing a non-null owner, a non-null row referencing a null owner, and
    unequal non-null UUIDs. Live and replay each exercise both valid forms and
    every invalid form before mapper execution.
21. `DndEngineClient` decodes new tagged action discovery and rejects the old
    `behavior_attribution`/`configured_action_ref` shape for both available
    action rows and the separate entity-handler response. Its worker-summary
    route accepts the unversioned `WorkerSummaryEvidence` envelope only when it
    contains GameSummaryV3 and rejects V1/V2 payloads; the durable v1/v2
    component-ID matrix remains the spool boundary in §14.
    `GameDirectoryClient.getSummary()` accepts the V3 history record and rejects
    V1/V2. `gameRouting.test.ts` supplies complete positive and negative JSON
    fixtures for both routes rather than asserting only the URL.
22. `StudioPlayerReplayImport` accepts a schema-valid subjective replay v3,
    seeks/maps it through `ReplayPresentationSession` and the production scene,
    and matches live resolved keys, graph, and nullable membership. A true V2
    bundle rejects before session/scene/mapper creation; Studio exposes only V3
    replay labels. `StudioEvidenceImport` accepts current player-replication-v3
    frame evidence and rejects true V2 frame/archive evidence before
    compilation, with no legacy guidance or adapter.
23. The exported client presentation frame archive is schema v3 and carries
    exact player-replication version 3/hash at its public boundary. Studio
    evidence validates those three fields before frame decode; archive v2,
    missing identity, wrong version, and wrong hash each reject, including a
    legacy frame whose cue subset is otherwise structurally valid. The
    existing startup persistence cut drops v2 session bytes without conversion.

## 18. Verification commands

### 18.1 Explicit generation step before candidate verification

```bash
uv run python devtools/generate_event_contract.py
uv run python devtools/generate_typescript_sdk.py
```

Generated files are then part of the implementation candidate. Verification
uses only non-mutating checks.

### 18.2 Engine and server

```bash
uv run python devtools/generate_event_contract.py --check
uv run python devtools/generate_typescript_sdk.py --check

uv run pytest \
  tests/manual/test_09_action_discovery_and_costs.py \
  tests/manual/test_18_sessions_api_client_contract.py \
  tests/manual/test_172_behavior_runtime_binding.py \
  tests/manual/test_181_action_content_identity.py \
  tests/manual/test_181_affordance_content_identity.py \
  tests/manual/test_168_content_catalog_contract.py \
  tests/manual/test_121_canonical_presentation_mapper.py \
  tests/manual/test_117_player_replication_contract.py \
  tests/manual/test_120_player_replication_journal.py \
  tests/manual/test_122_canonical_replication_runtime.py \
  tests/manual/test_139_condition_presentation_contract.py \
  tests/manual/test_178_spell_catalog_content_identity.py \
  tests/manual/test_neurodragon_spell_item_content_factories.py \
  tests/manual/test_170_neurodragon_consumable_content_factories.py \
  tests/manual/test_180_environment_content_identity.py \
  tests/manual/test_182_mapeditor_content_recipe_hard_cut.py \
  tests/manual/test_183_content_icon_bindings.py \
  tests/manual/test_50_counterspell_engine_contract.py \
  tests/manual/test_11_equipment_inventory_and_items.py \
  tests/manual/test_20_content_extension_basics.py \
  tests/manual/test_53_srd_monster_traits.py \
  tests/manual/test_125_haste_restricted_action.py \
  tests/manual/test_126_slow_legacy_contract.py \
  tests/manual/test_42_action_semantics.py \
  tests/manual/test_31_subjective_runtime_epochs.py \
  tests/manual/test_45_policy_routines.py \
  tests/manual/test_151_native_ai_execution.py \
  tests/manual/test_133_new_spells_batch4_legacy_contract.py \
  tests/manual/test_remaining_creature_content_factories.py \
  tests/engine/test_cold_presentation_facts.py \
  tests/engine/test_block_context.py \
  tests/engine/test_condition_content_evidence.py \
  tests/engine/test_counterspell_evidence.py \
  tests/engine/test_senses_light_stealth.py \
  tests/engine/test_condition_lifecycle.py \
  tests/engine/test_standard_conditions.py \
  tests/engine/test_manual_10_standard_conditions.py \
  tests/engine/test_spell_families.py \
  tests/engine/test_spatial_restraints.py \
  tests/engine/test_combat_actions.py \
  tests/engine/test_manual_20_encounters_turns_controllers_apis.py \
  tests/engine/test_monster_presets.py \
  tests/engine/test_effect_origin.py \
  tests/engine/test_spellcasting.py \
  tests/manual/test_13_spellcasting_core.py \
  tests/manual/test_21_spell_and_feature_extensions.py \
  tests/manual/test_37_authored_encounter_mechanics.py \
  tests/engine/test_manual_21_arena_game_sessions_client_state.py \
  tests/engine/test_dice_event_semantics.py \
  tests/progression/test_saving_throw_context.py \
  tests/progression/test_dragonborn_origin_runtime.py \
  tests/progression/test_barbarian_berserker_materialization.py \
  tests/progression/test_barbarian_character_grant_appliers.py \
  tests/progression/test_character_grant_receipt_cleanup.py \
  tests/progression/test_fighter_champion_materialization.py \
  tests/progression/test_fighter_character_grant_appliers.py \
  tests/progression/test_origin_structural_feature_applier.py \
  tests/progression/test_origin_innate_spellcasting.py \
  tests/progression/test_schema2_character_materialization.py \
  tests/progression/test_schema2_sorcerer_runtime_actions.py \
  tests/progression/test_sorcerer_character_grant_appliers.py \
  tests/progression/test_sorcerer_spell_source_materialization.py \
  tests/manual/test_97_event_wire_contract.py \
  tests/manual/test_28_subjective_observation_stream.py \
  tests/manual/test_114_timeline_contracts.py \
  tests/manual/test_115_objective_timeline.py \
  tests/manual/test_116_objective_replay.py \
  tests/manual/test_113_subjective_replication_routes.py \
  tests/manual/test_98_typescript_replication_sdk.py \
  tests/manual/test_102_game_summary.py \
  tests/manual/test_103_worker_game_summary_store.py \
  tests/manual/test_110_multi_game_gateway.py \
  tests/manual/test_110_gateway_restart.py \
  tests/manual/test_118_worker_replay.py \
  tests/manual/test_119_gateway_replay_access.py \
  tests/manual/test_101_game_directory_evidence.py \
  tests/manual/test_123_subjective_player_replay.py \
  tests/manual/test_189_worker_terminal_spool.py \
  tests/architecture/test_dependency_boundaries.py \
  tests/content_identity.py
```

Add table-driven cases to those stable suites; do not create one test file per
implementation helper. In particular:

- `test_189_worker_terminal_spool.py` proves all four §14 component rows with
  recomputed byte/path/content/manifest digests, and its positive case asserts
  outer spool v3 plus `dnd.worker-summary-evidence.v2`;
- `test_103_worker_game_summary_store.py` requires the real reducer's envelope
  to contain summary schema version 3. It invokes the existing reducer once on
  the authoritative history, then carries that history's terminal action
  evidence through Event-v2 into ObjectiveReplay-v2. Configured/definition/
  structural-provider/source-item/systemic, completed/canceled, convolution/
  nested-action, parent-lineage, and EffectOrigin cases must preserve the exact
  subject/domain/application/lineage bytes used by the reduction. The event
  digest equals the complete Event-v2 serialization of the reducer's full
  history, the log digest equals its complete log sequence, the replay events
  equal the exact post-seed terminal subsequence, and the one V3 canonical
  summary digest revalidates;
- `test_103_worker_game_summary_store.py` and
  `test_118_worker_replay.py` prove the retained event/log source origins select
  the exact full reducer-input slices and that the one existing replay builder
  requires its matching `WorkerSummaryEvidence`. A wrong evidence/capture
  generation or game, event/log source origin, terminal coordinate, full-source
  digest, removed/reordered cancel frame, or changed selected byte rejects
  before terminal publication. Mutating a live EventQueue object after terminal
  capture does not change the already-frozen source slots or repeated replay
  bytes;
- `test_101_game_directory_evidence.py` requires outer metadata
  `dnd.game-summary.v3` and injects structurally valid legacy V1 and V2 rows to
  prove active-read rejection;
- `test_110_multi_game_gateway.py` requires both V3 outer metadata and nested
  V3 from the real terminal/history route;
- `test_119_gateway_replay_access.py` updates its typed worker-evidence fixture
  to V3 and proves replay access remains correlated to that exact terminal
  generation. Together with `test_189_worker_terminal_spool.py`, it rejects a
  missing/reordered cancel frame, wrong terminal coordinates, or any tampered
  usage subject/domain, lineage, application ID, or log entry under the existing
  immutable component/manifest hashes. It does not claim the post-seed replay
  subset can reproduce the full reducer-input digest;
- `test_117_player_replication_contract.py` exercises whole-frame application
  membership with both-null and exact-UUID success plus null/non-null and
  unequal-UUID rejection; `test_121_canonical_presentation_mapper.py` and
  `test_123_subjective_player_replay.py` carry both valid forms through live
  and replay mapping;
- `test_98_typescript_replication_sdk.py` proves generated action-discovery
  rows contain `binding_subject` and omit both legacy fields.
- `test_09_action_discovery_and_costs.py`,
  `test_181_action_content_identity.py`, and
  `test_181_affordance_content_identity.py` require complete frozen discovery
  evidence on every action/handler row; configured/public-provider/item cases
  prove their exact visibility, controller, and owner atoms. Missing/tampered
  evidence, a wrong controller, and evidence/envelope entity mismatch each
  reject before either action or handler serialization.
- `test_168_content_catalog_contract.py` manually enumerates every typed
  catalog `ContentRef` carrier named in §10.3 and proves every target belongs to
  the returned PUBLIC set. It asserts the PUBLIC Acid Flask item remains while
  its OBSERVED spell ref is absent from the complete encoded catalog and both
  relation arrays; legitimate public Fireball/Magic Missile item-provider
  edges remain; model/digest revalidation and the standalone route preserve the
  same closure. `test_110_multi_game_gateway.py` repeats the Acid/public-target
  assertion through the gateway and checks the filtered catalog ETag.
- `test_172_behavior_runtime_binding.py` asserts both owner UUIDs for
  independent, structural-grant, live-provider, item-provider, and mismatched
  bindings and the exact required `structural_provider` boolean. It distinguishes
  a same-owner structural grant (`true`) from a same-owner live action/condition
  child (`false`); a missing field rejects, every binder entry point sets the
  exact reviewed value, and the architecture boundary rejects direct production
  construction outside the binder.
  Consumable/spell-item suites assert the retained item-owner pair and complete
  three-marker item predicate, including rejection of an all-true marker tuple
  with `structural_provider=true`;
  `test_37_authored_encounter_mechanics.py` and
  `test_180_environment_content_identity.py`/
  `test_182_mapeditor_content_recipe_hard_cut.py` assert both exact owner UUIDs
  on arena and map-editor lever templates and the mismatch rejection path.
- `test_cold_presentation_facts.py`, `test_counterspell_evidence.py`, and
  `test_181_action_content_identity.py` cover every required Event-v2 usage
  subject/domain precedence row, direct Counterspell REACTION evidence, missing/
  tampered subject or domain, hidden-ref absence, ordinary weapon versus item-
  provided actions, and immutability across phase/cancel/model copies.
- `test_counterspell_evidence.py`, `test_50_counterspell_engine_contract.py`,
  `test_97_event_wire_contract.py`, and the canonical mapper/replay suites prove
  the two legacy Counterspell identity-key strings are absent from the event,
  combat log, Event-v2, generated SDK, live projection, and replay. Exact
  reaction validation uses the excluded binding; incoming trigger identity is
  selected only from the correlated event's lawful subject/domain.
- `test_spatial_restraints.py`, `test_origin_innate_spellcasting.py`,
  `test_dragonborn_origin_runtime.py`, `test_53_srd_monster_traits.py`, and the
  existing fighter/rage suites exercise every §5.4 override family. Hellish
  Rebuke and Counterspell assert explicit bound-handler REACTION evidence and
  reject missing/mismatched bindings before any resource spend; Hellish Rebuke
  retains its existing gameplay event type while its exact bound reaction kind
  supplies the summary domain. Escape,
  breath-weapon, NaturalAttack, FrenziedStrike, and ExtraAttack declarations
  contain the exact required fields with no default/fallback path.
- `test_181_action_content_identity.py` and
  `test_181_affordance_content_identity.py` prove a hidden child under a PUBLIC
  same-owner provider with `structural_provider=true` selects PUBLIC_PROVIDER,
  while the same child from `bind_child()` with the boolean false is systemic
  and its provider ref is absent from discovery, handler HTTP, live projection,
  and replay. Structurally granted trigger evidence remains eligible; same-owner
  live-provider trigger evidence does not.
- `test_97_event_wire_contract.py`/`test_114_timeline_contracts.py` require the
  usage subject/domain, omit internal evidence, and reject bad discriminators or
  extras. `test_115_objective_timeline.py` retains completion and cancel frames,
  excludes nonterminals, preserves sparse cursors, and rejects duplicate terminal
  lineages. `test_116_objective_replay.py` accepts cancel, rejects nonterminal
  phases, and requires the final EncounterEnd completion.
- `test_102_game_summary.py` proves completion/cancellation counts; frozen
  subject grouping; exact parent-lineage/EffectOrigin damage attribution;
  unresolved no-action attribution; non-null-application convolution exclusion;
  and nested null-application accounting without the name heuristic.
- `test_172_behavior_runtime_binding.py`,
  `test_181_action_content_identity.py`, and
  `test_181_affordance_content_identity.py` resolve Drop, Opportunity Attack,
  and Retaliation through the canonical action/reaction definition owners and
  assert their frozen bindings match those declarations without a name/type
  fallback.
- `tests/content_identity.py` supplies the one test-only coherent constructor
  mapping. `reactive_fixture_support.py`, `test_senses_light_stealth.py`,
  `test_126_slow_legacy_contract.py`, and
  `test_28_subjective_observation_stream.py` use it for their generic synthetic
  ActionEvent/AttackEvent/MovementEvent rows; the full direct-constructor suite
  compiles with no constructor default, and an omitted or contradictory field
  fails at model construction.

### 18.3 TypeScript SDK

```bash
npm run check --prefix sdk/typescript
npm test --prefix sdk/typescript
```

In `sdk/typescript/src/tests/gameRouting.test.ts`, replace the current weak
empty-object terminal-summary check with immutable, schema-valid fixtures. The
worker route accepts `WorkerSummaryEvidence` containing V3 and rejects true
pre-cut V1/V2 summaries. The directory history route accepts a
`FinalSummaryRecord` with `dnd.game-summary.v3` plus nested V3 and rejects true
V1/V2 records. Action/handler discovery accepts exact discriminated
`binding_subject` rows for both `getAvailableActions()` and
`getEntityHandlers()`; old `behavior_attribution`/`configured_action_ref` rows,
and mixed new-plus-legacy rows, reject independently on both routes. Legacy
summary fixtures must contain the real V1/V2 statistics shapes; changing only
a discriminator is not evidence of strict decoding.

In `sdk/typescript/src/replay.ts`, change only the existing
`assertObjectiveReplay()` semantic validator. It accepts exactly
`phase === "completion" || phase === "cancel"` for retained frames, keeps
strict source-cursor/log-barrier order, and rejects a repeated
`event.lineage_uuid` across either phase. The last retained frame must still be
the exact `terminal_event_cursor`, have phase `completion`, and have
`event_type === "encounter_end"`; a final cancel cannot terminate an ended
replay. `decodeObjectiveReplay()` continues to use this one validator and
rejects Objective Replay v1 by its existing version/hash identity before any
consumer receives the value—no compatibility decoder or second path is added.

`sdk/typescript/src/tests/replay.test.ts` replaces its blanket
non-completion rejection with exact v2 cases: a completion/cancel/completion
sequence accepts; execution/effect/declaration phases reject; duplicate lineage
across completion/cancel rejects; an out-of-order cursor or log barrier rejects;
a final cancel rejects; and a structurally valid Objective Replay v1 fixture
rejects. The accepted cancellation fixture uses the generated model and the
same public `decodeObjectiveReplay()` entry as production.

### 18.4 NeuroClient pure, integration, and focused browser lane

```bash
npm run check --prefix /home/tommaso/Dev/NeuroClient/app
npm run action-ui-authority:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run action-bar:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run presentation-bundle:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run subjective-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run subjective-production-adapter:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run subjective-animation-coverage:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run target-facing:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run targeting-authority:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run recovered-client-connector-vertical:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run reaction-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run catalog-action-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run counterspell-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run ai-vs-ai-observer:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run action-profile-precedence:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run condition-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run presentation-diagnostics-isolation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run presentation-disposition-matrix:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run potion-animation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run studio-contract:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run studio-evidence-import:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run studio-coverage-workspace:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run studio-transport:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run action-studio-preview:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run replay-presentation-head-drain:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run presentation-head-drain-live:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run presentation-persistence-cut:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run movement-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run locomotion-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run movement-animation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run forced-movement-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run vital-effect-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run lifecycle-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run equipment-transition-presentation:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run encounter-end:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run encounter-terminal-authority:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run encounter-summary:smoke --prefix /home/tommaso/Dev/NeuroClient/app
npm run encounter-result-window:smoke --prefix /home/tommaso/Dev/NeuroClient/app

BLOCK1_TRANSITION_CAPTURE_DIR="$(mktemp -d)"
npm run presentation-transition-sequence:check --prefix /home/tommaso/Dev/NeuroClient/app -- \
  --capture acid-splash "$BLOCK1_TRANSITION_CAPTURE_DIR/acid-splash.json"
npm run presentation-transition-sequence:check --prefix /home/tommaso/Dev/NeuroClient/app -- \
  --replay acid-splash "$BLOCK1_TRANSITION_CAPTURE_DIR/acid-splash.json"
npm run presentation-transition-sequence:check --prefix /home/tommaso/Dev/NeuroClient/app -- \
  --capture acid-flask "$BLOCK1_TRANSITION_CAPTURE_DIR/acid-flask.json"
npm run presentation-transition-sequence:check --prefix /home/tommaso/Dev/NeuroClient/app -- \
  --replay acid-flask "$BLOCK1_TRANSITION_CAPTURE_DIR/acid-flask.json"
```

`catalog-action-presentation:smoke` requires every catalog root to be PUBLIC
and every related/dependency target to resolve to an exact returned row; a
non-PUBLIC root and dangling relation each reject. `studio-contract:smoke`,
`action-studio-preview:smoke`, and `condition-presentation:smoke` exercise
representative current Studio scenarios after the mechanical v3 DTO adaptation:
explicit PUBLIC refs remain tagged, hidden refs remain absent, synthetic
application owners remain null, and the existing target/order/scenario behavior
does not change. `action-studio-preview:smoke` additionally proves the
definition-only source-item preview selector is disabled/labelled while the
existing recipe's authored source-item match data and production profile
matcher remain intact. `studio-contract:smoke` proves the Spell preview-only
item-provider selector cannot emit an occurrence-free `source_item_fact` and is
visibly Block-8-deferred. They make no all-catalog, all-scenario, or
authoring-selection closure claim.
`subjective-presentation:smoke` sources OBSERVED Fog/spatial identity from its
explicit observer-authorized fixture and contains a retired-source assertion
against mining it from unconditional catalog dependency metadata.

The focused browser lane is required only for the existing production adapter,
action discovery/action-bar, and replay paths. It uses their existing backend
and browser prerequisites and proves decoded subject/graph behavior and visible
failure handling, not pixel identity or fixed animation duration.

`replay-presentation-head-drain-smoke.mjs` imports a schema-valid subjective
replay v3 through `StudioPlayerReplayImport`, seeks/maps it through the
production replay session/scene, and proves resolved binding keys, direct graph,
and nullable membership equal live mapping. A structurally valid v2 bundle
rejects in the SDK importer before session/scene/mapper construction, and all
mounted labels say V3. `studio-evidence-import-smoke.mjs` accepts current
player-replication-v3 frame evidence and rejects a true v2 frame/archive before
compilation; no legacy text or adapter remains.

`studio-evidence-import-smoke.mjs` and
`presentation-persistence-cut-smoke.mjs` additionally assert the exact archive
v3 schema/version/hash on the public snapshot and session envelope, validate
identity before any frame decoder call, and reject v2/missing/wrong-version/
wrong-hash envelopes without conversion. `studio-coverage-workspace:smoke`
continues to validate the existing compiled-bundle coverage workspace, and
`studio-transport:smoke` continues to validate the existing transport seam;
neither becomes a Block 1 fixture selector or Studio admission proof.

`action-profile-precedence:smoke`,
`presentation-disposition-matrix:smoke`, and
`subjective-presentation:smoke` cover both systemic profiles with visual
results and with zero delivered result intents. The zero-result cases require
exactly `state_only/systemic_action_no_world_visual`; mutation cases prove a
public binding, wrong systemic domain/cue/profile, and any root with intent
evidence cannot use that reason. Live/replay evidence retains the same
disposition and never creates an empty clip.

## 19. Completion gates

Block 1 is complete only when all are true:

1. Every included root action is bound before event publication or mutation;
   every spell is bound before `spell_execution_scope()` opens, and every
   independent/granted/live-child/item-child binding satisfies the exact
   two-owner plus structural-provider construction and execution law in
   §5.2–§5.3.
2. Every known direct constructor passes its exact §5.3 binding/parent seam and
   every declaration-event override/direct reaction constructor supplies the
   complete required §5.4 fields; every named synthetic test constructor uses
   the explicit test-only coherent mapping; no event identity default or
   ambient fallback exists.
3. Every effected bound handler retains exact binding evidence, including
   emitted-events/`None` returns.
4. All ten configured Multiattack root subjects remain distinct end to end;
   their child attacks keep Attack identity and direct root/application edges
   without copying the configured ref.
5. No OBSERVED, DEVELOPER, or INTERNAL action implementation ref crosses player
   replication, action discovery, or unconditional content discovery; more
   generally, every typed `/content/catalog` relationship target belongs to
   the exact returned PUBLIC entry set. Observer-scoped non-action identity
   remains governed by its existing subsystem and is not redesigned here. A
   same-owner `bind_child()` provider never crosses as PUBLIC_PROVIDER.
6. Source item and provider roles obey the one-observer table and are never
   relabeled; PUBLIC_PROVIDER additionally requires
   `structural_provider=true`, and
   the auxiliary source item still drives its independent existing attack/item-
   profile consumer without selecting the action binding.
7. `ActionPresentationKind`, full source-item presentation, display-normalized
   spell identity, and string effect provenance are absent from BaseAction,
   Event, and action identity authority; BehaviorBinding contains no broad
   content-set digest.
8. The included generated Event-v2 closure contains no open JSON, arbitrary
   semantic dictionary, callable, evaluator registry, or cache, and the new
   action subject/cue DTOs add no open channel. Pre-existing objective-world
   and combat-log JSON branches remain outside this claim and outside binding
   authority; standalone combat-log wakeup still works through its excluded
   typed marker. Event v2 includes exactly the required privacy-safe action
   usage subject/domain while excluding its internal selection evidence.
9. Typed-context domain cases preserve authoritative gameplay outputs; no
   weapon or condition display name remains a rule key, and the complete
   underwater/condition-immunity/saving-context matrices pass.
10. Exact direct edges are disclosed or severed independently of application
    membership; nullable duplicate edge pointers mirror the parent exactly and
    no semantic bypass is synthesized.
11. Target-row membership is not equated with Spell causal children; existing
    engine application UUIDs survive unchanged, private engine indices never
    cross, disclosed order is explicit, and absent UUIDs are not invented.
12. Every action/handler discovery row contains one complete validated frozen
    selector-evidence tuple, including the controller UUID and action-only
    canonical category; explicit HTTP DTOs are produced by the same pure
    selector without registry access or role/owner inference. Discovery, live
    projection, SDK,
    NeuroClient, and replay agree on that tagged binding identity;
    PUBLIC condition cues carry their direct lawful condition ref without
    changing condition appearance.
13. No client binding uses display names, bare refs with a lost role,
    `presentation_kind`, or hidden refs.
14. Event v1, timeline v1, objective replay v1, player replication v2,
    subjective replay v2, client presentation frame archive v2, terminal spool
    v2, and worker-summary evidence component v1 are rejected by their new
    public decoder boundaries.
15. Every command in §18 passes from the reviewed candidate.
16. GameSummaryV3 is the sole active summary schema and uses only its required
    authenticated Event-v2 PUBLIC/systemic subject/domain for usage and action-
    rooted damage; active V1/V2, `applied_by_effect`, `spell_id`, name/prefix
    reducers, the name-based convolution-accounting heuristic, and client
    fallbacks are absent. The one existing reducer runs once; Objective replay
    retains the byte-identical post-seed completion/cancel subsequence of its
    Event-v2 evidence, the two source digests cover the reducer's complete event
    history and complete combat-log input respectively, and the one canonical
    summary digest revalidates. Replay does not reconstruct the full digest. No
    normalized event model, adapter, or second reducer exists.
17. Every non-definition binding subject has one of the finite §13.2
    cue-family dispositions, including the two explicit systemic profiles; no
    open generic-policy subject or fallback exists. A lawful zero-result
    systemic profile uses only the exact closed no-world-visual reason and
    never fabricates an intent.
18. The three exact potion definitions alone retain the existing specialized
    item cue; all other item-bound actions preserve their natural cue family.
19. Existing Action, Spell, and action-reuse Condition Studio final frame
    builders compile through the mechanical player-replication-v3 DTO
    adaptation only: already-chosen exact PUBLIC refs receive explicit tags,
    hidden refs remain absent, ordinary synthetic application ownership is
    null, and explicit direct links are copied without nearest-parent inference.
    Block 1 adds no fixture corpus, generator, selector, topology/cardinality
    law, default-selection rule, or new Studio module; current scenario
    selection and fabricated preview facts remain unchanged and C07/C08 remain
    assigned to Block 8. Because the two existing source-item preview selectors
    own a definition ref but no item occurrence UUID, they are visibly disabled
    and their handoffs removed until Block 8; no Studio `source_item_fact` is
    fabricated. Existing source-item recipe authoring, public catalog relations,
    and live/replay source-item profile selection remain unchanged.
20. Every spell target/member cross-reference satisfies exact nullable
    application-owner equality; both-null is valid and every asymmetric or
    unequal pair rejects at whole-frame validation before mapping.
21. Both handwritten TypeScript REST decoders accept the new action/V3 summary
    contracts and reject old action-discovery, worker-evidence, and V1/V2
    summary payloads through complete `gameRouting.test.ts` fixtures.
22. Compiled bundle identity and per-cue resolved identity remain separate;
    evidence equality uses the exact resolved subject/use/ref-or-domain/cue key
    while recipe lookup uses the authenticated compiled payload.
23. Replay/session/Studio import production owners are V3-only; true replay or
    frame V2 evidence rejects before mapping, exported frame evidence carries
    exact archive-v3/player-replication-v3 version/hash before frame decode,
    and no `V2 replay` label remains.
24. No excluded representation, appearance, result, movement, spell-flight,
    unrelated persistence, legacy-data migration, or deployment surface was
    redesigned; durable changes are limited to the explicitly included V3-only
    active GameSummary contract/store validation needed by X08 and the existing
    bounded client frame-evidence envelope rotation required to prove the V3
    hard cut. Neither adds a migration or compatibility path.

## 20. Review and stop protocol

The plan is frozen by raw SHA-256 before review. It is then sent concurrently
to:

1. one internal reviewer with the full Block 1 audit context; and
2. the existing separate independent review task
   `019ff6ba-7b0e-7003-81ff-b815d9a9df29`, given the plan, ledger,
   implementation-block document, source roots, source baseline, and scope
   fence, but not the internal verdict.

Each reviewer must read the complete frozen plan and inspect relevant source.
The only accepting terminal form is:

```text
ACCEPT <exact-plan-sha256>
```

A rejection must name a material correctness, scope, executability, privacy,
or verification blocker. Editorial preference alone is not a blocker.

Any plan edit invalidates both verdicts and starts a new two-reviewer round on
the new hash. Verdicts are recorded beside the plan in a detached file named:

```text
ACTION_EXECUTION_BRIDGE_BLOCK_1_EXACT_IDENTITY_PRIVACY_PLAN_2026-08-13.md.reviews.<plan-sha256>.md
```

The reviewed plan bytes are never edited to record their own verdicts.

When both reviewers ACCEPT the same exact hash, planning stops. No production
implementation, branch, commit, generated-contract update, or client change is
performed until the user separately authorizes implementation.
