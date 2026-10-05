# Step A: concrete ECS schema-fit review

2026-10-05. Independent prerequisite review for implementation of the full presentation plan. No production edits or tests. Current source mappings are checked below; historical recorded values are examples, not current visual acceptance. The companion `schema-fit-ecs-examples.json` contains verbatim selected public packets, version rows and bound records from four retained cases, with provenance.

## Verdict and boundary

Approve a **small passive reference layer**, subject to the explicit mappings below. Do not approve replacement lifetime stores, a universal track payload, or deriving narrative solely from graphical cues. The existing specialized records already encode most required family data. Reference them; do not copy their values into a second executable event model.

The minimum common records can be:

- Evidence identity: generation, observer, source channel, native event UUID when present, source version/cursor and channel member discriminator where one event has several received records. Retain ResolutionRef separately. Initialization has its actual initialization cursor, not a fake event.
- Bound owner reference: family discriminator plus stable existing owner UUID, optional child/application/track identity. A recipe ID is attribution, never instance identity.
- Milestone reference: bound owner plus finite named field. A date is read from that field or a specifically supplied equation. It does not resample or mutate the owner.
- Semantic occurrence: evidence reference, semantic phase/template, permitted participant/value payload and bound milestone reference. Eventual descriptive state has a separate inspection record.

Names above are illustrative, not a demand to create four new registries. Common references must be passive values, with direct functional consumers. Do not export BodySample/ActorPose surfaces or NumPy buffers as evidence.

## 1. Condition application, later expiration and repeated ownership

**Actual retained input:** `persistent-shield` in the all-spells recording. Application node `82df38ee-0599-4ee7-873d-ddf5adf041a6`, source index 42, lineage `f3f3cd0f-9bf9-44d7-b511-419b1107fb7b`; ResolutionRef is event lineage `295fdad2-d78f-46be-a6cd-4d4f0ed78af1`. Recipient `184c3696-2110-4f48-9444-817e4eb3f727`; condition owner `c5457fb6-ad46-4f71-b913-b4a34fcd7385`; behavior `condition.spell.shield`.

Historical bound condition start is 797.1014492753624 ms within a head beginning at 437.5 ms, thus the application date is 1234.6014492753624 ms. Body action `spell.shield` has effect at that same local date, body/join/complete at 1014.4927536231885 ms. **Application is not body completion.** Removal is a distinct node `8256a457-ab63-4e87-93c4-e0b6e631c917`, source index 177, in a head beginning 6953.351449275363 ms, local removal 0.

Concrete mapping:

| Common field | Existing value source |
|---|---|
| evidence event/version | PlayerNode.uuid and VersionRow.source_index above |
| resolution | PlayerNode.resolution_ref; retain independently from parent |
| owner | ConditionFact.condition_uuid |
| content | ConditionFact.behavior_id |
| application milestone | ConditionMediaLifetime.applied_ms |
| removal milestone | same retained owner's removed_ms |
| body recovery | BodyActionCue.body_end_ms / join_ms / complete_ms, separately |
| text | application/removal occurrences, each identified by its native edge; no duplicate application when nested timeline repeats membership |

Current producer: `condition_media_lifetime.register_condition_lifetimes`; it deduplicates membership edges, borrows an overlapping same-behavior clock where visuals are shared, and retains owner-specific response events. That borrowed **visual clock does not merge two real application occurrences**.

Suppression is derived from current effective appearance/membership metadata, not `removed_ms`. Hidden/reacquired membership gets `applied_ms=None` unless a witnessed application exists. Such a member belongs in initial/current-state inspection; do not narrate "casts Shield". Turn-triggered activation is `activated_ms`; consumption is `consumed_ms`; absence/return is `returned_ms` plus poses. None is an alias for expiration.

## 2. Consumption must follow packet evidence, not case titles

The historical case named `spell-handoff-guiding-mark-consumed` contains application `d7f12b2c-868d-4ebc-8d01-33a76a0d3000` (source index 95) and removal `b0c7552a-e3f4-409d-a7d0-f3ef85490773` (120) for owner `6471d783-efc3-4030-b244-a721ad103cbb`. Its recorded removal has **consumed=false**. Therefore this recording encodes removal, not a distinct consumption occurrence, regardless of its title. Current source supports explicit consumed membership and ConditionResponseCue(trigger="consumed"). A current consumption fixture is needed before claiming that distinction validated. Never repair old evidence by guessing from spell identity or clip title.

## 3. Item effects survive ownership transfer

`item_attachment_lifetime.item_attachment_members` collects floor items, visual equipment and controlled inventory into one mapping keyed by `effect.effect_uuid`, whose value includes `item.item_uuid` and the effect state. `ItemAttachmentStart(item_uuid, applied_ms, source_cursor)` is the existing clock record.

Mapping: item-effect native edge → `(effect_uuid, item_uuid)` owner reference → existing applied_ms milestone and applied_source_event_cursor. Equip/drop/loot changes placement and disclosure, **not effect identity or application time**. A cold item has applied_ms=None and may have source_cursor. Suppression and sight do not restart it. Text emits equip/drop/loot separately from effect application. No caster UUID inferred for an item source whose public record does not disclose one.

## 4. Concentration slot is not the Concentrating condition

`concentration_media.ConcentrationMediaLifetime` owns `slot_uuid, spell_id, actor_uuid, item_uuid, geometry, positions, elevation_steps, applied_ms, removed_ms`. Registration matches the public slot's `cast_lineage_uuid` to the creating node's lineage. It does not match just spell ID.

Actual ice case includes slot `74728c13-90e3-4a72-a4ec-f321f246188a`, cast lineage `000c2ffb-a2cf-4f59-8d36-3e77b2787d10`, spell `spell.wall_of_ice`. This is a source example of slot identity; Wall of Ice's construction rendering is not claimed to use the cosmetic concentration-media path.

Mapping: slot UUID is owner; exact matched cast evidence permits area geometry; applied_ms is head offset + cast start + release. `_slots` returns None for unknown, empty tuple for authoritative empty. Only the latter can retire a known slot. A cold snapshot cannot invent a cast area, and a root Concentrating replacement cannot retire surviving slots. Narrative may describe known concentration, but not undisclosed area creation.

## 5. Spatial fields, partial cells and contacts

`SpatialMediaLifetime` fields are already the required payload: effect, applied_ms?, removed_ms?, recipient_endpoints, damage_contacts, facings, retired_cells, committed_ms?. `SpatialEffectStateFact` supplies exact owner, operation and removed_positions. Observed membership is independently supplied through senses.

Actual `persistent-grease-true`: creation node `c40f0da4-5158-47ec-876d-c6c9655c8b43`, source index 53, spatial owner `203fb73a-634b-4ef1-be1d-9859b40cb91e`; removal node `69004229-b877-4b37-bc55-f61199cd77e6`, source index 166. The input is schema 1; it is historical evidence, not proof all current fields were present.

Mapping: owner=spatial UUID; creation evidence grants introduction; formation starts from bound WorldTransition(field="creation").start_ms; commitment is the relevant state edge; recipient-track arrival remains a distinct endpoint start_ms. `SpatialDamageContact(event_uuid, recipient, at_ms, formation)` is built from **committed DamageResultFact**, not proximity. Its packet identity is sufficient to deduplicate actual contact narration.

Partial retirement is keyed by `(owner, cell)` and requires `removed_positions ∩ previous.positions − following.positions`. Merely unseen cells cannot quench. Field motion interpolates geometry with separately disclosed old/new visibility; geometry movement does not translate visibility grants. Reuse existing samplers, not milestone expansion per frame.

## 6. Construction destruction and parent retirement

`construction_media_lifetime.register_construction_lifetimes` retains section objects by their object UUID, related through `object.item.construction_owner_uuid`. Existing WorldTransition payload distinguishes `object_dust`, `construction_collapse`, `membrane_contact`, creation/removal/destruction. Field label alone is insufficient.

Mapping: section identity for a hit/break; explicit construction parent for shared collapse; contact/release dates from the bound transition; committed_ms from first relevant received state. A membrane impulse can fan to sections sharing the parent without becoming multiple mechanical hits or multiple text damage occurrences. Whole-owner removal retires only actually removed section objects; sight loss is not destruction. Partial dust must keep the surviving object. Export semantic facts and logical payload identifiers, not draw commands.

## 7. Atomic world/tile updates and deposits

`WorldUpdate(event_uuid, tiles, objects, objects_removed, connectors)` is a **single received transaction**, not a group of new tile events. Reference its event and version; inspection payload is the provided tuple of WorldTileState and connector/object records. No inference from a tile label to a rule handler. Preserve existing reducer ordering and any delayed spatial commit cursor.

For deposits, `observed_deposits` groups only received fragment positions by `(MaterialDepositSource, material_id)`. `register_deposit_starts` uses witnessed ObjectDestroyedFact and authored environment bank release frame. Existing timing is `head + transition.start_ms + bank.frame_times_ms[release_frame]`. Deposit owner/source identity and fragment positions remain native; cold material sustains with no fabricated burst. Ground memory and airborne visibility must retain separate sampling permissions. Text may say observed material covers the known cells; it cannot extrapolate radius to unseen cells.

## 8. Reactions, canceled parents and factless evidence

`PresentationGroup(primary, lineages, reactions)` retains separately received roots. Only consecutive reaction roots with `ActionReaction.triggered_lineage_uuid` matching the following root are associated. `reduce_presentation_group` reduces original order. No new parent-child relation is authored.

Mapping: reaction node event/version is occurrence identity; triggered lineage is causal relation; succeeded/automatic are factual payload; body cue is optional. Failed reaction remains meaningful text. A canceled root must not suppress surviving children; cancellation carries phase/action_economy_spent/outcome_code separately from results. `PlayerNode.fact=None` may still carry combat_log, content_attributions, cancellation or be referenced by PlayerObservation/WorldUpdate. Graphical binder returning no cue does not erase those channels.

Effective-handler attribution uses its actual `triggering_event_uuid`, `triggering_lineage_uuid`, `emitted_lineage_uuids`, dispatch_index and outcome; it is not a synthetic spell occurrence. Actor/source-item attribution remains distinct from handler provenance.

## 9. Multi-cause sensory commitment

`SensoryFact.observed_changes` contains source-event references. `_observed_commit` maps them through source_lineages then the existing milestone dates and takes max only for resolvable sources. `AreaReachFact` separately includes prerequisite destruction lineages and previous reach. These are causal references, not children.

Concrete schema obligation: expand recorded references to scalar owner/milestone refs; preserve the evidence cut and unresolved disposition. Do not use the empty max as permission to commit at zero. The current helper can return None; integration must preserve existing admission behavior while reporting missing resolution, not manufacture an event or secret source.

## Hard checks for implementation review

1. Same native membership edge seen through two bound timelines produces one semantic occurrence; two distinct same-behavior owners remain two occurrences even with a shared visual clock.
2. Initial state and reacquisition create inspection descriptions, no application animation/narration without evidence.
3. Suppressed/hidden/expired/consumed/destroyed/returned remain representable separately.
4. Item/effect/slot/section/deposit identities survive cross-head sampling and seeking.
5. Every WorldUpdate remains atomic; contacts and source details cannot appear before their evidence commit.
6. Unknown concentration/visibility evidence cannot become empty membership or removal.
7. Graphical silence does not discard legitimate public outcomes, and graphical flourishes do not manufacture outcomes.
8. Runtime tests must bind current packets and inspect immediately before/at/after dates; historical trace examples alone do not satisfy this gate.

**Review disposition:** schema-fit approved for the common evidence/owner/milestone references under these mappings. Runtime binder/lifetime migration and final semantics require implementation review; the historical consumed example is explicitly insufficient, and current trace serialization omits some world/lifetime fields that Step B must expose. No claim of fresh visual validation is made.
