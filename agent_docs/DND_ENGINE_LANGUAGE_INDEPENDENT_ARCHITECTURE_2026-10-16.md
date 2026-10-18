# DND Engine Language Independent Architecture

The engine models Dungeons and Dragons through composed creatures, addressable rule owners, contextual values, actions, conditions, and synchronous reactions. An operation can publish an event, let handlers change its accepted meaning, execute nested operations, and continue against the resulting world. Reactive consequences finish at the boundaries chosen by their owners. They are not collected for a later simulation frame.

This account describes the current headless gameplay architecture. Source names identify the implementation evidence; the responsibilities and interactions below do not depend on a programming language, inheritance mechanism, or ECS library. The companion [Bevy reactive design](BEVY_REACTIVE_ENGINE_DESIGN_2026-10-16.md) proposes a different implementation of these same relationships.

## 1 The engine is a composition of owners and reactive systems

A creature composes abilities, skills, saving throws, health, equipment, proficiencies, action economy, senses, inventory, spellcasting, and other structural facts. These blocks supply data and capabilities to actions and rule systems. A monster, species, character class, or character build chooses and configures that composition. It does not define a separate universal execution model.

Actions ask existing owners to perform operations. An attack combines the attacker's weapon, abilities, proficiencies, and outgoing modifiers with the defender's armor and outgoing modifiers. Receiving damage asks the health owner to resolve defenses and hit point pools, then asks the creature lifecycle owner to resolve dying or death. A spatial change asks the grid to commit membership, then lets the affected spatial rules react.

The event service owns event publication, selection of matching handlers, accepted handler results, causal history, and observation seams. It does not contain the implementation of every attack, spell, condition, item transfer, or terrain rule. Those systems continue to own their state changes.

The architecture is reactive, but it is not a universal event-sourcing system. Initial unpublished composition can install state without publishing gameplay events; low-level value and health primitives also exist. Individual modifier changes are not universally separate events. Domain owners publish the mechanically meaningful boundaries their callers and observers need.

Evidence: [creature composition](../dnd/entity.py#L338), [standard action installation](../dnd/actions_functional.py#L88), [initial progression](../dnd/content/characters/progression.py#L346), [direct health primitive](../dnd/blocks/health.py#L665).

## 2 Identity is distinct from ownership and participation

Several identities coexist and must not be collapsed:

| Identity | Meaning |
| --- | --- |
| Creature or world-object identity | The particular live participant. |
| Block and value identity | An addressable part of an aggregate and the exact value receiving a contribution. |
| Condition identity | One installed or provisionally prepared rule instance. |
| Modifier or handler identity | One removable contribution owned by a condition, item, feature, or other source. |
| Action template identity | The owner/provider-configured grant from which an execution was selected. |
| Action execution identity | The selected runtime invocation. |
| Event version identity | One published occurrence or version. |
| Event lineage identity | The logical event across its phases and same-phase replacements. |
| Application identity | One ordered application within a multi-target action, including repeated recipients. |
| Turn execution identity | The actual encounter turn that caused an operation and its descendants. |
| Content and behavior identities | Which authored definition and executable rule supplied the behavior. |

An event's source and target identify participants. A contribution owner says whether a retained modifier or handler may currently contribute. An item's current holder, container, equipment slot, original intrinsic owner, and rule provider are separate relationships. Mutable source metadata is not a reliable substitute for those relationships.

Blocks retain independent identities and value ownership. The base block mechanism can opt into conditions and handlers, but ordinary built-in statistic blocks do not all enable that capability. Creatures, items, and tiles are the principal enabled block owners. Preserving the language-independent ownership model does not require reproducing every source-language object as a separately scheduled object.

Evidence: [base identity and contribution gates](../dnd/core/base_object.py#L20), [block ownership](../dnd/core/base_block.py#L139), [item location](../dnd/blocks/inventory.py#L129), [action template selection](../dnd/core/base_actions.py#L1769), [behavior identity](../dnd/core/content/runtime.py#L35).

## 3 Values are contextual rule expressions

A modifiable value retains contributions rather than only a final scalar. Each contribution has its own identity and source. This permits exact removal, suppression, contextual evaluation, and an explanation of the resulting value.

The channels have different directions:

| Channel | Responsibility |
| --- | --- |
| Self static | Always-applicable contributions to this value. |
| Self contextual | Contributions evaluated for a particular source, target, and context. |
| Outgoing static | Contributions offered to the other participant's corresponding calculation. |
| Outgoing contextual | Contextual contributions offered to that other calculation. |
| Imported target static | The other participant's outgoing static contributions used in this evaluation. |
| Imported target contextual | The other participant's outgoing contextual contributions used in this evaluation. |

An attack's attack bonus and defensive armor value import each other's outgoing channels. The context can include weapon slot, range, spell provenance, condition meaning, and event lineage. A condition such as Prone or Frightened can consequently affect an interaction between two creatures without replacing either creature's base statistic.

Evaluation includes numerical modifiers, arithmetic factors, normalization and bounds, advantage/disadvantage voting, critical and automatic-hit policies, damage typing, and resistance. Combining values merges corresponding channel/bucket maps keyed by contribution identity; it does not globally deduplicate every occurrence across all channels and modifier families. These are existing arithmetic rules; a port must not silently replace them with a different interpretation of tabletop rules.

Numerical behavior includes exact rational factors and deliberate rounding boundaries. Ability modifiers use floor division, including negative results. Final rational score conversion truncates at a different boundary. Current bound aggregation selects the lowest active minimum and highest active maximum; advantage uses the sign of the aggregate votes. These formulas are mechanically observable and are distinct from a storage choice.

Contextual evaluation and its recorded explanation are different operations. Evaluators run when the value is requested. Retained last-evaluation results support explanation; they do not universally memoize the authoritative calculation. Roll-result handlers such as Bless, Bane, and Guidance separately alter recorded rolls and may consume a condition. Neither mechanism should be approximated by a scalar periodically recalculated after any component change.

Evidence: [value channels](../dnd/core/values.py#L1407), [numerical evaluation](../dnd/core/values.py#L1563), [target imports](../dnd/core/values.py#L1916), [contextual evaluation and retained result](../dnd/core/modifiers.py#L331), [roll modifications](../dnd/spells/enchantment.py#L1243).

## 4 Events describe an operation at a rule boundary

An event contains its category and phase, source and target, accepted payload, cancellation facts, version and lineage identities, causal parent, children, and turn identity. Concrete event families carry the corresponding attack, roll, damage, condition, movement, item, world, sensory, or encounter facts.

The familiar progression is Declaration, Execution, Effect, Completion. Cancellation records an aborted lineage and the phase from which it was canceled. This vocabulary does not make every producer a strict four-step state machine: producers can publish multiple versions at one phase, skip phases appropriate to a fact, or publish a noncancelable completion after committing a domain invariant.

Posting publishes a new version and can redispatch handlers. Returning an updated value from a handler carries it to the next handler without redispatching the same phase. Those two operations are observably different. A published version is not necessarily the last accepted version; callers that depend on interception must use the accepted publication result.

Event history is causal information used during mechanics, not only an output log. Rules inspect parents, siblings, phase history, and application identity. A handler can discover whether a damage packet belongs to a particular attack or spell application. Completion gathers lineage relationships and structured log data after required child work has settled.

The live history is not an immutable archive of the complete world. Current records can contain live rule/value references, and parent-child bookkeeping grows as child events are registered. Removing an owner from live registries does not invalidate those retained references: a condition event can still expose the removed condition, and an event can retain composed values after creature retirement unregisters their live ownership. Retirement actively clears the retired owner's own contribution channels; separately composed event values can retain their merged entries. Retaining data therefore means preserving its actual lifetime and mutations, not freezing every retired value at its old score. Detached recording and player projection have separate responsibilities.

Evidence: [event lifecycle](../dnd/core/events.py#L183), [phase and cancellation publication](../dnd/core/events.py#L408), [posting versus unposted updates](../dnd/core/events.py#L640), [item rule inspecting causal attack](../dnd/items/property_composition.py#L33), [retired value cleanup](../dnd/core/values.py#L1445), [condition fact capture](../dnd/player/capture.py#L772).

## 5 Handler matching and ordering are part of mechanics

A trigger matches an exact event category and phase, optionally filtered by exact source and target. Event inheritance does not broaden matching to all related categories. A handler also has an owning source, enabled state, optional player toggle, suppression policy, and executable processor.

For a nonspatial event, unfiltered category-and-phase handlers are selected first. Remaining matching filtered handlers follow their registration order. For an event with dispatch positions, each position contributes its position-indexed handlers, then simple global handlers, then matching filtered global handlers. Selection deduplicates handler identities across the supplied positions. This is bucket precedence, not one universal numeric priority sort.

Ordinary dispatch discovers a candidate list from the submitted event. Each selected handler receives the current accepted event. A returned modification is recorded and becomes input to later handlers; cancellation stops the current chain. Handler-level matching and contribution gates are checked again on invocation, but a newly matching handler is not automatically added to that existing candidate list. Explicit reposting starts another dispatch.

Direct system invocation is a separate path. An admitted Effect can name one exact registered system owner with no broadcast trigger conditions. That owner executes after ordinary admission, without redispatching the veto handlers or fabricating a second command. Summoning uses this path.

Nested dispatch is synchronous. A handler may publish another event, execute another action, remove a condition, or move a participant. Those consequences can themselves reach the same rule before the original handler returns. After nested execution, remaining handlers and the outer owner see the resulting current world.

Evidence: [trigger and handler contracts](../dnd/core/events.py#L980), [ordinary dispatch](../dnd/core/events.py#L1807), [candidate selection and ordering](../dnd/core/events.py#L2232).

## 6 Publication has several mechanical meanings

The event service supplies distinct paths because a proposed mutation and a committed fact have different authority.

| Publication path | Authority and handler behavior |
| --- | --- |
| Ordinary intercepted event | Store the submitted version, dispatch candidates, accept replacements, stop on cancellation. |
| Transactional preflight | Evaluate an unpublished declaration/execution proposal through validation-only handlers. Event emission is rejected. |
| Publish accepted preflight | Store the already accepted proposal without rerunning its validators. |
| Committed execution or effect | Store the committed fact, invoke reactions on detached copies, ignore returned replacements/cancellations, continue notifying later handlers. |
| Completed fact | Run required pre-completion work and publish the noncancelable resulting fact. |
| Completion sequence | Store individually identified simultaneous completion facts, then notify sequence consumers with the complete sequence. |

Condition-application effect cancellation has a specific rollback path: the cancellation can be returned without publication while the owner releases provisional state; it is then published after restoration. That does not establish a general rollback transaction around every action.

Publication failure and admission failure also differ. Some owners have already committed and must attempt to publish every resulting fact even if one publication raises. Retrying or undoing a committed operation merely because a passive consumer failed would create a different state history.

Evidence: [publication paths](../dnd/core/events.py#L1873), [preflight](../dnd/core/events.py#L1914), [committed publication](../dnd/core/events.py#L1999), [completion sequences](../dnd/core/events.py#L2051), [condition publication after commitment](../dnd/core/base_block.py#L1473).

## 7 Pre-completion systems close reactive consequences

Before a parent event completes, registered lifecycle systems may react and emit child events. These systems include sensory consequences, restraint preservation, and summon lifecycle work. They are part of mechanics and causal closure, not passive listeners delayed until the end of a frame.

The service invokes general pre-completion callbacks and systems indexed by the parent's event category. It guards reentry on the same event version; sensory update events bypass this work to avoid recursive sensory closure. Children emitted here exist before this completion metadata is finalized. This is not a universal immutable or sealed-event guarantee: cold world initialization can publish a completed fact and subsequently use it as the cause of dynamic activation.

Passive observation has separate granularities. Immediate event observers see each stored version. Sequence observers receive a group after all its members are indexed. Batch observers receive the ordered causal batch when the outer action scope closes. Nested actions share that passive batch, but their mechanics and immediate callbacks still execute synchronously.

Evidence: [pre-completion dispatch](../dnd/core/events.py#L1724), [passive action batching](../dnd/core/events.py#L1640), [sensory system installation](../dnd/blocks/sensory.py#L641).

## 8 An action is a configured grant and a selected invocation

An actor owns ordered action templates. Usable items can also supply their own templates and produce selected user-bound configurations during discovery. A template contains source-specific configuration such as weapon slot, spellcasting source, item source, costs, targeting policy, or a restraint source and escape difficulty. Selecting an action retains the exact relevant grant/provider configuration; item-provided choices need not become permanent entries in the actor's action list. The authored definition, installed grant, selected execution, root event lineage, and per-target applications remain distinguishable.

The ordinary action owner performs the following work, with interception at the published boundaries:

1. Check affordability and publish a declaration.
2. Validate current targeting, access, prerequisites, and placement using an unpublished proposal.
3. Admit any finite item charge and recheck its source contact.
4. Commit action economy costs.
5. Publish execution and accept execution-time interception.
6. Revalidate access that handlers may have changed; interruption here does not refund committed costs.
7. Commit the admitted item charge and execute the authored consequence.
8. Finish concentration-related cleanup and publish root completion after child applications.

This sequence is an action-owner contract, not an event service automatically applying changes at every Effect phase. Some authored actions add their own phases and internal repeated Effect/Execution publications.

Multi-target and area actions create ordered application identities. Repeated applications to the same creature remain separate. Subjective previews and objective execution targets are distinct: actual application recomputes authoritative recipients and reach. A root total or a recipient set cannot substitute for the individual application history.

Resolution references distinguish an event-owned resolution from one particular application of a root action. Descendant damage, visibility, and observed-change facts retain that reference. An application's own event lineage is distinct from the root-action lineage carried by its application membership; parent pointers or target identity alone cannot recover repeated A/B/A applications reliably.

Spellcasting retains source-specific ability, provider, progression, rank and ritual entitlements. A cast opens a scoped execution context keyed by its event lineage so once-per-cast contributions remain separate from action-object identity and per-target applications. Nested casts restore the enclosing context when they finish.

The selected runtime invocation is itself addressable during execution. Summoning resolves the exact live spell action named by its application, and successive target applications can update the invocation's selected concentration instance. This is real shared execution state, separate from the configured template and the cast's recorded event lineage.

Concentration is an identified sustain graph with slots, not one generic boolean. Each slot retains its spell and cast identity and linked effect entries. A cast can be attributed to a creature while an item with concentration capacity is its actual sustainer. Adding an owned spell condition coordinates admission of the recipient effect and the sustain link; replacing or dropping a slot releases its exact graph and can preserve other slots. Damage and death reactions cause involuntary sustain loss at their own reactive boundaries.

Evidence: [templates](../dnd/core/base_actions.py#L915), [instantiation](../dnd/core/base_actions.py#L1769), [action execution](../dnd/core/base_actions.py#L2273), [ordered applications](../dnd/core/base_actions.py#L2111), [registered grants](../dnd/entity.py#L5466), [cast context](../dnd/core/spell_execution.py#L22), [actual sustainer and coordinated effect](../dnd/actions.py#L5111), [concentration slots](../dnd/conditions.py#L1838), [temporarily addressable summon invocation](../dnd/spells/summoning.py#L73), [exact summon action lookup](../dnd/summoning/system.py#L120).

## 9 Attacks rolls damage and life state form a reactive chain

An attack composes the relevant attack bonus and armor calculation, installs interaction context, and publishes a roll boundary. Rolling produces typed roll-result events so rules can replace or augment the effective result while retaining the original roll and modification evidence. The attack then republishes its rolled outcome for interception, including Shield.

The actual Shield processor first adds its incoming armor modifier, then spends reaction/slot, runs buff application, and returns the changed attack outcome. It does not branch on the buff application's return value. Preserving that sequence does not mean inventing a new rule that rejected buff membership restores the already-spent resources or automatically restores the hit. Counterspell likewise spends its exact resources before its automatic result or ability check and publishes its own reaction fact.

On a hit, the attack constructs typed damage packets, publishes damage-roll results, and uses the accepted rolls to request damage from the target. Incoming damage is interceptible before hit points change. The health owner resolves per-type affinities, packet reduction, temporary hit points, normal hit points, survival caps, and overkill. The result retains a typed accounting of what each defense prevented.

Positive applied damage produces its own event boundary. Concentration checks react to damage actually applied, including the resulting hit point pools. Creature lifecycle then resolves dying, death-save failures, massive damage, or death before the incoming damage lineage completes. Derived life-state facts cannot independently veto an already accepted invariant.

DamageApplied uses ordinary mutable phase dispatch after HP commitment. Body responses can return body_release annotations and concentration can return concentration_broken; those returned versions are accepted. This differs from the explicit committed-notification API's detached deep working views and ignored replacements. Publication authority follows the producer operation, not an event name or the word factual. Annotation changes do not undo committed HP.

Death, spatial absence, retirement, and destruction are different outcomes. An ordinary dead creature can remain deployed and continue to occupy a pressure plate. A temporary summon may instead have an existence owner whose lifecycle removes its world presence and encounter agency. Reviving and healing use their own admitted operations and resulting facts.

Evidence: [attack resolution](../dnd/actions.py#L2198), [Shield](../dnd/spells/abjuration.py#L283), [Counterspell](../dnd/spells/abjuration.py#L945), [damage receipt](../dnd/entity.py#L3658), [health resolution](../dnd/blocks/health.py#L500), [concentration reaction](../dnd/conditions.py#L2194), [life-state commitment](../dnd/entity.py#L2492), [death aftermath](../dnd/entity.py#L2680).

## 10 Conditions own contributions and form a graph

A condition is a runtime rule package. It can own modifiers, ordinary handlers, spatial handlers, durations, same-owner subconditions, cross-owner linked conditions, action grants, and specialized spatial or lifecycle state. Removing the package releases its exact contributions rather than reconstructing every statistic on the recipient.

Ordinary membership is indexed by name, instance identity, and source. Same-name application generally replaces the previous membership after both application and replacement removal are admitted. Specialized owners can implement ownership transfer. Internal spatial membership leases can deliberately have source-distinct names. The architecture does not establish unrestricted stacking of every named condition.

The ownership graph supports a primary parent, additional parents sharing an effective child, cross-owner links, and reverse child-removal policies. A shared effective child survives removal of one parent while another valid parent remains. An independently existing child borrowed by a condition retains its independent lifetime.

Condition application preparation can install provisional mechanics. It publishes declaration/execution, invokes the authored application, retains the returned contribution identities, and attaches their contribution owner. Those provisional modifiers can already affect queries and Effect handlers before authoritative membership commits; there is no universal rule hiding all pending contributions. The recipient commits membership only after admission and replacement checks succeed. Rejection releases the exact artifacts covered by that path's cleanup before publishing cancellation; this does not establish rollback of arbitrary authored effects. Prone can consume movement then cancel, Dashing earns turn-owned credit at membership, and Exhaustion can cause death during provisional application.

Removal prepares the affected graph before changing authoritative membership. It accounts for shared children, specialized owner admission, and conflicting return destinations. Accepted commitment cleans children before parents and retains resulting snapshots. Graph settlement and resulting completion publication happen after the corresponding owner state has committed. Mandatory terminal release is a distinct context, not a blanket permission to ignore every lifecycle rule.

Evidence: [condition-owned state](../dnd/core/base_conditions.py#L613), [shared children](../dnd/core/base_conditions.py#L923), [application preparation](../dnd/core/base_conditions.py#L1024), [membership and replacement](../dnd/core/base_block.py#L1774), [graph removal](../dnd/core/base_block.py#L1304), [children-first commitment](../dnd/core/base_block.py#L1367).

## 11 Suppression retains existence while gating contribution

Magical suppression can retain a condition, its duration, its graph relationships, and its identities while disabling some mechanical contributions. Providers add and remove suppression tokens. Shared parent state and spatial suppression can affect whether a contribution is active at a particular cell.

Handlers can explicitly run while their owner is suppressed. Duration, final cleanup, and movement of an anchored field can therefore continue while its benefits or hazards are inactive. Suppressing the entire owner as if it ceased to exist would lose those lifecycle reactions.

Cleanup owner, source/provenance and optional contribution-gating owner are separate. The condition contribution gate itself does not check applied membership. Concentrating's damage/death handler is installed late, after general handle binding, with no contribution_owner_uuid; cleanup ownership does not introduce a suppression gate. Invisibility reveal explicitly runs suppressed while Greater Invisibility's check does not. These exact policies must remain distinguishable.

Evidence: [contribution owner gate](../dnd/core/base_object.py#L76), [condition suppression](../dnd/core/base_conditions.py#L571), [handler suppression policy](../dnd/core/events.py#L1038), [spatial anchor handling](../dnd/spatial/area_conditions.py#L481).

## 12 Items and permanent features compose existing owners

Items have their own identities, placement or container membership, equipment state, optional integrity and finite charges, and installed conditions/properties. Moving an item between the floor, inventory, equipment, and other supported ownership states admits the source removal before committing destination membership. Equipment contributions belong to the exact installed item/property and are released through recorded handles.

Permanent character origin and class features are not universally conditions. Typed source records and family-specific grant receipts retain the abilities, proficiencies, resources, senses, action grants, handlers, formulas, and other contributions a progression step installed. Corresponding family cleanup removes those exact contributions. Initial composition installs progression on an unpublished aggregate; later progression publishes the admitted resulting level facts.

Content admission is a separate cold-runtime responsibility. Definitions and dependencies are validated before an immutable content set becomes the world's behavior authority. Runtime records distinguish executable behavior identity, direct provider, durable origin root and encounter-local owner. A different content set cannot silently replace the authority already used by live rules.

Evidence: [inventory transfer](../dnd/blocks/inventory.py#L101), [typed item properties](../dnd/core/item_properties.py#L15), [property installation and release](../dnd/items/property_composition.py#L58), [typed progression receipts](../dnd/types/character_receipts.py#L1), [initial progression](../dnd/content/characters/progression.py#L346), [content admission](../dnd/content_system/pack_loader.py#L674), [behavior identity](../dnd/core/content/runtime.py#L35), [live authority protection](../dnd/core/content/runtime.py#L140).

## 13 The world owns occupancy geometry and indexed spatial dependencies

The grid owns tile storage, committed creature membership, object placements, connectors, spatial-condition footprints, cell subscribers, light sources, and dependency/revision indexes. A tile is an addressable rule owner with movement costs, optical/propagation policy, elevation, lighting, and optional conditions and handlers.

Current objective addresses use two grid coordinates with support heights and occupancy layers. Objects can span cells and vertical volumes; directed boundaries separate movement, optical, propagation, and physical-contact passage rules. The proposed XYZ work is not already a current runtime capability.

A creature has one authoritative objective position and an occupancy layer relative to support. Position changes commit creature position and tile membership together before spatial departure and arrival facts are published. Both departure and arrival handlers inspect the already-committed world. The departure fact does not mean the creature is still occupying its old cell.

Spatial effects are independent owners indexed over their footprints. Some affect traversal, optical behavior, light, contact, damage, restraint, or mechanisms. Position indexes select relevant handlers without scanning all spatial rules for every change. Footprint movement must update owned contributions and handler indexes together.

Evidence: [grid state](../dnd/core/gridmap.py#L198), [position commitment](../dnd/entity.py#L894), [membership change publication](../dnd/core/gridmap.py#L2573), [tiles](../dnd/core/base_tiles.py#L65), [spatial effect ownership](../dnd/spatial/area_conditions.py#L57).

## 14 Movement is a sequence of reactive commitments

Voluntary movement begins from a selected route through the actor's known world, but each step is authoritatively revalidated. A step publishes its Effect before position commitment, enabling opportunity attacks and other interception. After reactions, movement checks capability, transition legality, destination, and available movement again. The movement owner then commits the supported cost/position changes and publishes committed-step completion.

Committed spatial entry can trigger hazards, forced retreat, portals, new knowledge, or other movement. The outer movement observes the actual resulting position and may terminate when it diverges from the intended step. Controller-aware movement can revalidate its decision after a committed step and stop before the root movement completes.

Jumping, connector transfer, forced movement, and teleport-like relocation are separate authored operations with their own trajectory, contact, provocation, collision, and commitment rules. They are not interchangeable writes to position. Spatial facts distinguish grounded arrival from passing through space and distinguish a physical boundary crossing from deployment or relocation.

Evidence: [step resolution](../dnd/actions.py#L943), [controller movement boundary](../dnd/core/action_execution.py#L37), [opportunity attack](../dnd/reactions.py#L16), [tripwire crossing filter](../dnd/spatial/triggers.py#L182), [portal transfer](../dnd/spatial/portals.py#L117).

## 15 Spatial rules react to occupants and to moving fields

Area rules distinguish an occupant entering/leaving, a field appearing over occupants, a field moving over or away from occupants, and turn-start/turn-end exposure. These trigger kinds can have different authored effects. First-per-turn rules fence by the actual causative turn identity, rather than merely a round number or the recipient's own turn.

An area can hold exact source-to-occupant membership leases. In the restraint specialization, several sources can share one effective Restrained condition while retaining separate escape actions and difficulties. Reactive preservation reconnects source leases if the public manifestation is replaced, or recreates it from surviving sources when appropriate.

Material surfaces can arbitrate overlapping ownership per cell. Different materials can require an authored transformation. Terrain flags alone cannot represent the owners, source leases, suppression, and transformations involved.

Elemental contact is published as a spatial interaction; the contacted material owner chooses its authored response. A fire contact can ignite oil, replace the admitted oil footprint with fire, and settle displaced ownership and memberships synchronously. Destroying a liquid barrel can spill a material and then publish a new ignition caused by that destruction. Physical destruction may retain an inert wreck with the same identity. Similarly, a gas vent can create an independently living cloud: producer identity does not imply that ending the vent ends the cloud.

Some areas react to newly exposed flames as well as to creature movement. A torch ignited inside Sleet Storm can be doused by a nested reaction before the outer ignition finishes. Optical obscurement, emitted light, physical fire contact, and damage are separate effects of the participating owners.

Area resolution can also react to topology changes within one action. Fireball retains a finite geometric envelope, visited recipients, and ordered reach stages. After a stage destroys a barrier, an actual propagation-revision change can open another stage and expose new recipients during the same cast. Each stage records its preceding stage and prerequisite destruction lineages. This is not a universal one-time target collection.

Evidence: [trigger admission and installation](../dnd/spatial/area_conditions.py#L1264), [activation and footprint change](../dnd/spatial/area_conditions.py#L1504), [source memberships](../dnd/spatial/memberships.py#L24), [shared restraints](../dnd/spatial/restraints.py#L173), [material arbitration](../dnd/spatial/area_conditions.py#L305), [elemental contact](../dnd/spatial/ignition.py#L10), [material reactions](../dnd/spatial/transitions.py#L41), [retained wreck](../dnd/blocks/base_item.py#L762), [staged Fireball](../dnd/spells/evocation.py#L925), [reactive flame dousing](../dnd/spells/conjuration.py#L4107).

## 16 Pressure plates and portals demonstrate reentrancy

A pressure plate computes pressure from current grounded occupancy. On an actual edge it opens a state-change event, commits its new pressed state, and sends its authored outputs. If an output activates a portal, the portal can synchronously transfer the occupant away and re-enter the same pressure rule to release the plate. The original activation then continues sending every pulse selected for that press, even though current pressure has changed.

```text
Committed entry onto plate
  Pressure plate commits pressed
    First output activates portal
      Portal reveals its activated state
      Transfer commits new position and membership
        Departure reaches the same pressure plate
        Pressure plate commits released
      Transfer completes
    Remaining authored press outputs run
  Original plate change completes
Outer movement observes actual position
```

Activation of a ready portal publishes its revealed entrance before moving witnesses away. Its completed state-change fact and the subsequent transfer use the still-open triggering event as their cause; the transfer is not appended as a new child of the already completed state-change fact. An already active portal can transfer without a new activation reveal. A stale entry callback must use current membership and must not manufacture a duplicate press after the creature has already transferred. These requirements demonstrate why a delayed global update of changed components would alter mechanics and observation.

Evidence: [pressure state and output](../dnd/spatial/triggers.py#L56), [portal reveal and transfer](../dnd/spatial/portals.py#L91), [behavior cases](../tests/engine/test_pressure_plates.py#L132).

## 17 Senses navigation and knowledge have different owners

The sensory system derives visible cells, perceived contacts, spatial effects, and light information from committed world facts. It retains dependency footprints and revision channels so relevant changes can update affected observers. Pre-completion execution publishes sensory child facts before finalizing the causal parent.

Geometry-driven light changes already have a batching rule: each affected in-range emitter recomputes its illumination delta, while sensory processing defers the geometry parent's affected observers until those emitters have settled. Light facts remain separately published. The current implementation executes this through synchronous calls and revision invalidation; construction-event buffers are not a general work scheduler. This is a concrete foundation for the queued Bevy redesign, rather than evidence that every existing call needs to stay synchronous.

Navigation is derived for a particular actor and its known world. It uses movement capability, occupancy/contact knowledge, perceived hazards, and revision-aware caches. It is distinct from optical visibility and from the authoritative grid's actual transition legality.

Event-time knowledge is retained evidence. Identity and exact location are different grants. An identity known when an event began is not erased because its participant subsequently dies, moves away, or becomes hidden; causal children inherit the parent's recorded identity grants. Exact-location evidence is refreshed at each stored version. Each projected delivery still uses its own entry sight for spatial/visual disclosure, rather than indiscriminately borrowing the root's earlier sight.

The grid's conservative dependency indexes identify observers whose derived data might need recomputation. Membership in those indexes grants no knowledge. Actual perception still applies light, invisibility, concealment, special senses, and observation rules.

Evidence: [sensory system](../dnd/blocks/sensory.py#L641), [light-parent observation boundary](../dnd/blocks/sensory.py#L1634), [geometry-driven light recomputation](../dnd/core/gridmap.py#L3175), [in-range emitter deltas](../dnd/core/gridmap.py#L5967), [sensory sequence publication](../dnd/blocks/sensory.py#L1808), [event-time grants](../dnd/core/events.py#L2129), [ordered player projection](../dnd/player/projection.py#L1020).

## 18 World lifetime encounter membership and agency are distinct

A creature can be constructed, composed and born, deployed into the world, admitted to an encounter, assigned to a controller, temporarily absent, dead, or retired. Those are distinct transitions. Birth publishes the completed aggregate; deployment commits world presence; encounter admission commits initiative/controller membership.

Cold battlefield construction creates an actor-free world while ordinary construction events are disabled, validates the resulting tiles/objects/connectors, and publishes World Initialized. It then activates authored dynamic props and spatial rules through their ordinary lifecycles caused by that initialization fact. Actor assembly similarly distinguishes unpublished initial composition from deployment and from deferred effects applied after deployment. Creating storage records alone does not mean that gameplay entry or damage should already fire.

Summons use ordinary creature composition and add exact origin, control, sustain, and existence relationships. Preparation can involve placement, initial conditions, encounter membership, and other owners before a coordinated commitment. Their ending releases agency and ownership according to the cause; it is not synonymous with an ordinary corpse remaining on the map.

Encounter departure can revoke agency immediately while deferring roster/initiative edits until an active membership-execution scope closes. A departing active combatant still needs the corresponding turn termination facts. Removing a runtime storage record alone would not perform that protocol.

Evidence: [birth](../dnd/entity.py#L1686), [deployment](../dnd/game.py#L45), [summon preparation and commitment](../dnd/summoning/system.py#L155), [encounter departure](../dnd/encounter.py#L455), [cold battlefield construction](../dnd/scenarios/battlefield_catalog.py#L1409), [actor assembly](../dnd/scenarios/encounter_assembler.py#L414).

## 19 Turns controllers and action discovery use the same mechanics

Encounter flow advances explicit rounds and turns. Turn start publishes its lifecycle, resolves death saves, advances applicable conditions and item durations, resets action economy, and publishes the resulting budgets. Pre-completion sensory consequences settle before controller decisions use the resulting state. Turn end exposes its own reactive boundaries and resulting accounting.

A controller supplies a decision at an explicit action boundary. Human waiting, deferred AI work, completed actions, and encounter termination are meaningful outcomes. AI and human commands invoke the same native action owners. A continuous frame loop is unnecessary for turn progression.

Finite resources retain capacity sources, current uses, and recovery contributions. Turn start, short rest, and long rest are explicit recovery boundaries. Short rest can spend identified hit dice through healing; long rest coordinates condition expiry, item recharge, health recovery, and resource recovery through their existing owners. These are requested operations rather than elapsed-real-time polling.

Action discovery reads the actor's exact installed grants, current budgets, capabilities, and subjective world. It retains the selected template rather than reconstructing an approximate action from a name. Discovery generations and state revisions prevent stale choices from being treated as current authority. Previewing is informational; execution performs its own current validation and objective application.

Evidence: [turn start and end](../dnd/entity.py#L2914), [encounter controller handoff](../dnd/encounter.py#L783), [one-action advancement](../dnd/encounter.py#L1343), [discovery and preview](../dnd/player/session.py#L325), [command execution](../dnd/player/session.py#L457).

## 20 Capture and delivery preserve causal facts without driving mechanics

Capture takes the ordered retained event history and complete lineages, detaches the facts appropriate for recording, and projects separately for each audience. An audience's controlled actors and observing actors are separate grants. Sharing a delivered view does not grant each controlled creature another creature's action range or senses.

Public reduction must respect the original commitment order. A committed spatial fact identifies its commitment occurrence separately from its later completion. Otherwise a late outer entry completion could incorrectly overwrite a newer position produced by a nested portal transfer. Completion order alone is insufficient to reconstruct committed state.

Structured combat logs retain original rolls, modifications, and child relationships. They are one consumer of mechanics, alongside actor/world projection, analytics, and presentation. Log prose does not reconstruct the authoritative action. Delivery batching, public cursors, native history cursors, and causal lineages serve different purposes and are not interchangeable identities.

Evidence: [capture](../dnd/player/capture.py#L283), [per-audience application](../dnd/player/application.py#L70), [commit-aware reduction](../dnd/player/reduction.py#L264), [audiences](../dnd/player/audience.py#L1), [recording codec](../dnd/player/event_record.py#L121).

## 21 Boundaries a replacement must preserve

The replacement must keep direct composition, source-owned contributions, contextual value evaluation, exact action grants, and the accepted-result dependencies of reactive operations. Event category, phase, lineage, application, and turn identities retain their separate meanings. Matching/order and the distinction between an updated value and reposting remain explicit. The user's requested redesign permits queued independent damage, lighting and sensory work; the current call-stack serialization is not itself a blanket replacement requirement.

Admission, provisional contribution, commitment, reaction to a committed fact, required causal closure, and passive capture remain separate operations. Their dependencies are chosen by the owning gameplay system. Native queued processors can advance independent work without waiting for every descendant; the consumer's required facts must settle before it proceeds. No single global phase pipeline or automatic end-of-frame recomputation can stand in for those owner-specific contracts.

World occupancy, condition graphs, item ownership, encounter membership, and player knowledge remain coherent at their published boundaries. A replacement can change storage and implementation techniques while preserving these dynamics. The Bevy design is evaluated against those responsibilities rather than against a one-class-to-one-component translation.

## 22 Source coverage and behavioral checks

The source paths above cover event publication and matching; composed creatures and values; actions, attacks, damage, life state and turns; condition preparation, replacement, graph removal and suppression; items and progression; grid/movement, pressure plates, portals, area memberships and restraints; sensory closure; summon/encounter lifetime; and discovery/capture/projection. Concrete source-language representation details are evidence for these relationships, not an instruction to reproduce their incidental layout.

The companion design records the completed behavioral checks and compiled native Bevy diagnostics. They establish their named cases, rather than acceptance of a complete port.

The subsequent [condition/handler audit](BEVY_CONDITION_HANDLER_EXPOSURE_AUDIT_2026-10-16.md) adds a reproducible inventory and source review of all declared condition/handler families plus discovered integration seams, with explicit source-read limits. It refines ownership, post-commit annotation and nontransactional application details above; it is not complete native gameplay qualification.
