# Packet 2: exact actor and item retirement

Implemented only the approved native retirement boundary. Source is the shared
checkout `/mnt/c/users/tommaso/documents/dev/dnd_engine`; runtime is the existing
UV environment. No art, presentation code, spell rules or controller code changed
in this subtask. Independent implementation review is required before accepting
this packet; these are implementation notes, not reviewer approval.

## Native APIs

- `Game.prepare_entity_retirement(entity_uuid, *, cause: TerminalOwnerRelease,
  parent_event=None) -> PreparedRetirement | None`.
- `Game.commit_entity_retirement(prepared)` consumes the admitted release once.
- Entity owns `prepare_retirement`, `cancel_retirement`, `commit_retirement`.
  Preparation excludes the exact existence condition currently being removed;
  commitment requires that membership to have already ended. The high summoning
  owner commits at the settled condition-graph boundary.
- BaseItem owns prepared retirement/cancellation/commit and `retire() -> bool`.
  A rejected condition/floor admission returns false without silently removing
  live container membership. Already absent identity returns true.
- Equipment owns prepared item release/commit/publication. Normal unequip hooks
  run, real items retain their conditions and resources, intrinsic anatomy ends.
  `ItemReleaseReason` and equipment-event `release_reason` distinguish transfer,
  retirement and departing owner; parent events remain causal.
- BaseBlock exact composition traversal and lower ModifiableValue channel release
  replace mutable source-UUID sweeps for terminal aggregates. Imported target
  channels and unrelated recipient effects are not retired.

## Ownership behavior

Current inventory and equipment membership decide possession; stale initial
composition references do not. Real acquired possessions are placed intact on
the actor's current supported nonblocking ground. This engine commits movement
at supported ground destinations; missing/corrupt ground raises an invariant
error while preserving items. Containers retain their contents; coatings and
charges remain attached to the same UUID. Intrinsic items do not become loot.

Voluntary retirement retains condition and equipment veto admission. Mandatory
ending uses only the exact typed terminal context. World item placement accepts
that context at the existing GridMap owner. `Game.remove_entity` remains the
ordinary reversible absence operation.

Condition/item release, attached light, spatial observer/membership, owned
handlers/values/actions and exact actor/block registrations are released.
Spatial terminal publication happens while actor identity and coordinates are
still present. Historical facts are retained. Independent effects with the same
source UUID remain alive.

Encounter/controller membership is intentionally owned by the next packet.
Review/integration must verify live content binding ownership through the actual
content gateway; there is no existing unregister API assumed or fabricated here.

## Checks

`uv run --no-sync pyright` over base_item/equipment/inventory/values/gridmap/entity/game:
**0 errors**.

`uv run --no-sync python -m pytest -q`:

- `test_summon_retirement_ownership.py`, `test_item_destruction_events.py`,
  `test_gear_ownership_regressions.py`, `test_equipment_state_facts.py`,
  `test_item_transfer_admission.py`: **74 passed in 5.05s**, including 10 new cases.
- `test_items_inventory_equipment.py`, `test_equipment_domain_ownership.py`,
  `test_item_resource_lifecycle.py`, `test_world_entity_initialization.py`:
  **68 passed in 7.05s**.

The new cases observe preserved loot identity/coating/charges/container contents,
intrinsic retirement without physical destruction, action authority release,
mandatory versus voluntary veto, failed item retirement without partial removal,
independent source-equal effects, isolated observer failure, attached-light
removal and idempotent repeated terminal commit. Passive observer failures are
logged by the existing queue and cannot veto gameplay commitment.

Full native and wall-regression suites remain parent-level packet validation;
142 focused passing tests are not claimed as whole-project acceptance.

## Review correction: concentrated construction removal

Native prepared concentration replacement now commits Ice/Stone wall section
retirement without publishing item, spatial, or sensory completions. The exact
GridMap removal effects retain after-values; their completion transitions run
only during publication because even an unregistered completion transition runs
the existing pre-completion sensory callbacks. No event buffering or new global
force policy was introduced.

`BaseItem.commit_retirement(..., publish=False)` is deliberately bounded to
unowned world objects. Held/stored items reject that mode. Its paired
`publish_retirement` emits retained condition, floor, light and location facts
once. Silent GridMap object removal likewise requires caller-owned location
cleanup and no attached connectors. Existing ordinary retirement wrappers keep
their publication behavior. Wall cleanup consumes admitted native item tokens;
it does not destroy sections or create frigid air when concentration ends.

All section membership, registrations, optical occupancy and resulting lamp
illumination commit before any cleanup callback. Rejected replacement keeps the
same wall, section UUIDs, placements and concentration. Antimagic and Banished
cleanup changes belong to the condition-seam packet, not this implementation.

Validation after this correction:

- Original wall rules plus four prepared replacement cases: **37 passed**.
- Additional stone lighting case plus those four replacement cases:
  **5 passed**, including no event-cursor advance during commit.
- Original focused item/retirement set: **142 passed in 11.82s**.
- Scoped BaseItem/GridMap/wall-construction typing: **0 errors**.

An existing independent formation issue was observed: adding a Stone wall in
front of an already-active lamp does not recompute that lamp after the zone's
optical occupancy is attached. The removal regression starts with a lamp added
after the wall exists, so its starting darkness is authoritative. That unrelated
formation issue is reported to the parent for disposition rather than silently
changing formation rules in a retirement fix.

## Review correction: exact typed composition children

`BaseBlock.owned_child_blocks()` and `owned_values()` expose explicit native
composition edges. Health includes its `hit_dices`; Weapon, Equipment and
Spellcasting include their three typed extra-damage bonus lists. Existing
retirement preparation therefore includes HitDice conditions, and release ends
the exact blocks, values, local channels and modifiers. Imported target channels
and real acquired weapon bonuses remain alive. No reflection or source-UUID
sweep is used. Existing hit-die removal now calls the same value cleanup instead
of keeping a duplicate local implementation.

A real canonical Wolf retirement proves HitDice and all three bonus lists end,
while an unrelated value with the same source actor and an acquired flaming
scimitar's bonuses survive. The test observes the separate native block/value/
object registries through their public lookup APIs.

- Canonical bodies, retirement, wall rules and prepared-wall cleanup:
  **125 passed in 15.75s**.
- Existing inventory/equipment/resource/destruction/transfer ownership cases:
  **132 passed in 12.04s**.
- Progression source-owned primitives after shared HitDice value cleanup:
  **13 passed in 0.45s**.
- All seven touched native modules: **0 typing errors**.

The exceptional failed-formation cleanup retains its ordinary item-retire
wrapper when no prepared wall graph exists.

## Mandatory wall-section owner proof

The condition packet's mandatory preparation path now stages wall sections
through `prepare_removal_state`, while ordinary cleanup retains its existing
vetoable admission. `BaseItem.permits_terminal_retirement` normally accepts only
the exact intrinsic owner. WallSection extends it only when all of these live
edges are present: section UUID in its SolidWallZone, wall's explicit parent link,
that parent's reciprocal linked-condition edge, matching ending actor, and the
parent already admitted in the native removal scope. The read-only
`BaseBlock.prepared_condition_terminal_release` query uses the existing accepted
graph/context, not a second registry or a same-source sweep. GridMap validates
the same provider hook before skipping ordinary object-removal veto phases.

Two additional real Ice/Stone cases show mandatory terminal cleanup bypasses
the section veto, and an unrelated same-source dagger cannot use that authority.
All seven prepared wall cases pass (**2.33s**); the preceding wall/retirement
combined run passes **49 cases (10.62s)**; affected-module typing remains **0
errors**. Root owns the independently reviewed general spatial mandatory event
staging and child-first publication changes. No new rendering behavior or art
was introduced.

Final combined condition lifecycle, prepared wall, and actor-retirement check:
**47 passed in 5.23s**.

## Independent ECS review correction I7: failed admission cleanup

Wall, item and actor preparation now retain each accepted native token before
calling the next provider. A later raised exception drains all earlier accepted
condition, supported-item and floor preparations. Cancellation attempts continue
after a cleanup exception; raised admission failures and cleanup failures are
preserved together in `BaseExceptionGroup`. The narrow lower
`BaseBlock.prepare_owned_condition_removals` exception path does the same.
No transaction framework, new ownership scope or gameplay rule was introduced.

Item and actor tokens mark cancellation before draining, making repeat cleanup
idempotent and preventing a canceled token from committing. The newly added
actor validation remains intact and rejects canceled tokens. Equipment admission
remains its existing nonpublishing preflight: there is no additional equipment
reservation or slot mutation to undo.

Accepted spatial effects retain `use_register=False` even when explicitly
registered by GridMap admission. Cancellation now explicitly registers the cancel
fact when the accepted effect already exists in the queue. Entirely unpublished
mandatory preparations remain unpublished. Batch object cancellation attempts
every accepted effect even when an earlier cancellation callback raises.

`test_retirement_admission_failure.py` uses native events and real state to cover:

- A real two-section Ice wall whose second removal admission raises; the first
  section and the second section's earlier condition preparation both cancel,
  and the original wall remains intact and removable on retry.
- An actor whose third drop admission raises while both condition cleanup and
  the first drop cancellation also raise; the second drop still cancels and all
  carried items/conditions retain their original ownership.
- A later supported-item admission exception plus a parent cleanup exception;
  the earlier attachment still cancels and retry succeeds.
- A native multi-object removal batch whose first cancellation raises; every
  accepted object cancellation is still delivered and all placements remain.

Focused combined wall, item, actor and condition regressions: **148 passed in
18.08s**. Scoped native typing: **0 errors**. Source is frozen for independent
I7 review; this report is not a reviewer approval.
