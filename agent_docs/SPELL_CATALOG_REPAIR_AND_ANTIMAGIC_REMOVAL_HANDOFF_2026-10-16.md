# Spell catalog repair and Antimagic removal: implementation handoff

Date: 2026-10-16. Worktree:
`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
Branch: `codex/spells-rank-one-two`.

Implemented the [approved repair plan](plans/SPELL_CATALOG_REPAIR_AND_ANTIMAGIC_REMOVAL_PLAN_2026-10-16.md).
The starting state is committed as `059ad0af4c9`; the human waived the push
prerequisite. This repair is in the working tree above that checkpoint.
No NDClient, NeuroClient, Godot or frontend source was changed.

## Delivered behavior

| Audit family | Implemented result and relevant native boundary |
| --- | --- |
| SC-09: rejected spell effects | The 34 audited spells admit their own EFFECT before changing health, conditions, size, areas or concentration. Simple retained effects use the existing owned-condition path. A further native True Strike regression now prevents its weapon attack when its own EFFECT is refused. |
| SC-06: Bestow Curse damage | The curse installs one existing hit rider in the accepted attack damage packet. Misses deal no curse damage, ordinary hits get one rider, and criticals use native critical dice. Weapon, natural and Flame Blade spell-weapon packets are covered. |
| SC-04: reactions | Removed AM-only reproductions with the feature. Shield, Counterspell and Hellish Rebuke have independent positive/refused native reaction coverage. Shield preparation stays inside native condition-removal scope; refusals cannot leak its buff or an interception. Counterspell and Rebuke honor their own declared/executing/effect admission and actual cost boundaries. |
| SC-01: Hold Person | Shares the admitted Paralyzed child through existing ownership leases, like Hold Monster. Ending one spell preserves paralysis still sustained by the other. A refused required child cancels the effect. |
| SC-12: Chill Touch | Recipient-owned, caster-specific healing prevention; ending one source preserves another source and unrelated No Healing. It ends at the proper source turn or source departure. The undead rider remains. |
| SC-10: Hypnotic Pattern | Requires admitted Charmed before incapacitation. Immunity/refusal cannot leave the incapacitating parent active. Relationships are source-specific. |
| SC-07: Enlarge/Reduce | Temporary size steps belong to the exact condition UUID and commit with membership. Replacement/refusal/removal/clamping preserve durable base size and other contributions. Corrected the goblin producer's Small structural baseline. |
| SC-08: Expeditious Retreat | Grants its exact bonus Dash only on admitted membership; native retirement removes only that action. Another Dash survives. Ordinary movement and bonus-action costs remain authoritative. |
| SC-02: Charmed | The condition owns harmful direct-recipient admission for native attacks, spells and authored harmful abilities. Includes secondary-only declared targets; friendly operations and incidental area damage remain possible. Lower action events expose neutral authored intent, without importing spell implementations. |
| SC-03: Charm Person | A ten-turn spell-specific owner shares only its own charmer relationship. Actual positive damage from the charmer or a current ally ends this owner. Generic Charmed is not made universally damage-breaking. |
| SC-05: Haste | Self-casting works with ordinary eligibility/contact and costs. Existing restricted additional-action budget remains. |
| SC-11: durations | Hold Person, Bless, Bane, Haste, Blur, Slow and base Bestow Curse have their finite native ten-turn deadlines, including actual turn-driven expiry. |

Bestow Curse rank policy is explicit: ranks 3/4/5/6 last 10/20/50/100 turns
with concentration; ranks 7/8 last 24 hours without concentration; rank 9 is
permanent without concentration. BG3 governs the ranks it implements, with the
approved SRD fallback above them.

**Bestow Curse damage scope remains attack packets.** Broadening it to saved,
automatic or ongoing spell damage is deferred under plan section 9. The engine
needs an explicit delivery/duplicate policy before claiming those cases. This
repair does not claim that every spell damage stream receives the bonus.

Additional interaction repairs found during qualification:

- Greater Restoration finds source-specific charm families through their native
  condition aliases, retires the exact sustaining owner and respects removal
  vetoes/shared leases. Charm Person and Hypnotic Pattern have positive/veto tests.
- Native area footprint/index/cache changes commit before light recomputation,
  preserving optics-before-light observations on ordinary Fog footprint changes.
- A stored concentration publication remains the committed observation even if
  an observer raises. The next unchanged publication produces no duplicate.
- Created-item/light, Banishment return, Globe clipping, shared-child ownership,
  summon lifecycle and ordinary physical/magical weapon paths remain native.

## What was removed

Antimagic Field's live spell, zone, metadata, class eligibility, condition identity
and icon rows are gone. Cold Cleric preparation and Wizard spellbook/preparation
inputs containing its identity fail through supported build validation.

Removed its queries, exception enum/origin fields, provider UUID tokens, saved
creation placement/return callbacks, all-item/area/entity refreshes, global light
refresh, magic-property suppression switches and AM-only action/item guards.
There is no disabled spell or replacement suppression service.

Kept the independent systems: Globe admission/formation/clipping and its factual
provider records; spatial contribution indexing; physical construction; ordinary
Banishment suspension/return; source ownership; item lifetime; and per-block light
presence. The neutral handler flag is now `runs_while_owner_inactive`, without an
old-name alias. Only real maintenance/expiry/anchor cases opt into it.

The old AM-only test suite/manual exercise were retired. Five AM-only cases in
the new audit suites were retired as specified. Independent structural item
immunity moved to `tests/engine/test_structural_item_condition_immunity.py`.
Mixed tests retain their ordinary/Globe/ownership/optical assertions using native
setups. Historical audit Markdown, inventory CSV and baseline measurements remain
unchanged.

## Current catalog

**186 installed identities: 181 primary catalog roots, three learned reaction
roots and two separately authored Infernal roots.** This is a count of existing
content after removal, not additional spells implemented by this repair.

| Level | Installed identities |
| --- | ---: |
| 0 | 20 |
| 1 | 41 |
| 2 | 35 |
| 3 | 25 |
| 4 | 16 |
| 5 | 14 |
| 6 | 18 |
| 7 | 7 |
| 8 | 5 |
| 9 | 5 |
| Total | 186 |

Installed class eligibility maps now contain Cleric **60**, Paladin **23**,
Wizard **106** spell identities. These overlap and must not be summed as unique
spells. Charm Person's spell owner has one new condition identity/icon mapping;
the two AM spell/condition mappings were removed. Other icon ledger rows,
ordering, metadata and pinned assets were preserved.

## Engine/player contract handoff

Live protocol remains **1**, player schema is **11**. Current server, Python SDK
and TypeScript SDK schema/identity copies agree. The current export has 325
shared definitions and 1,716 field rows. Exact identity:

```text
527c25d3f0050deb5147cdb376f22bd3ab5eda1d7ec519a3bbb93ab5a3021213
```

Removed public fields:

- `ConditionState.suppression_provider_uuids`
- `ItemPresentationState.suppression_provider_uuids`
- `ItemEffectPresentationState.suppression_provider_uuids`
- `VisualItem.suppression_provider_uuids`
- `FloorItem.suppression_provider_uuids`
- `SpellSuppression.antimagic`

Generic suppression/clipping records remain for Globe. Regenerated native exports
include schema, OpenAPI, field ledger and both SDK contract copies/types. Existing
identity handshake rejects mismatched live clients; no frontend work is included.

Native `RecordedSequence` stays schema **2**; public `PlayerSequence` stays **5**.
The exact preceding live schema-10 contract is preserved under
[`sdk/protocol/recordings/pre-antimagic-removal`](../sdk/protocol/recordings/pre-antimagic-removal/README.md).
The existing offline native event reader accepts named empty retired metadata
only on concrete origin/condition/item/protection fields. Active or malformed
retired suppression rejects explicitly: retain the original recording and old
contract. Opaque event `context` is never traversed or rewritten. Live models are
not relaxed. Destruction/spatial item snapshots, nested item effects and opaque
context have direct recording regressions.

## Measured recurring work

Post-repair evidence is saved in
[`SPELL_CATALOG_REPAIR_BENCHMARK_2026-10-16.jsonl`](SPELL_CATALOG_REPAIR_BENCHMARK_2026-10-16.jsonl).
Python 3.13.12 on WSL/Linux; measured operations exclude imports/setup and include
profiler overhead. The old audit benchmark is unchanged.

| Operation and scaling input | Post-repair work |
| --- | --- |
| Ordinary remote object move; 1/25/100 registered items | Two item snapshots in every case, no AM dispatch. |
| Ordinary caster move with 4/16 Goodberries | No creation-return handlers dispatch. |
| Unrelated actor turn; 1/10/40 Hold Person recipients | Zero Hold repeat-handler dispatches. Recipient-specific native Trigger filters do the routing. |
| Unchanged concentration; 0/1,000/10,000 unrelated target events | 107 profiled `isinstance` calls in every case, one publication request, no actor-history lookup. Uses one last committed event UUID and the existing exact event index. |
| Local Antilife move; 1/25/100 remote actors | One local occupancy query, two area-shape reads, 13 contribution checks in each case. Candidates come from old/swept footprint occupancy. |

The Antilife handler also limits crossing work to line cells. No new global
manager/cache registry was added. These work counts do not imply a percentage
improvement for whole-game performance.

## Qualification and remaining baseline failures

Results overlap; **do not sum them as unique tests**. Commands use
`/home/tommaso/.cache/dnd-engine/venv/bin/python` from this worktree.

| Executed lane | Result |
| --- | --- |
| Four retained audit suites, repair interactions, reaction admission, archived-field contract, removed-spell cold inputs | **140 passed** after all final review fixes. No strict xfails remain in the retained audit suites. |
| Final affected/shared engine selection: spell families, controls, items, summons, optics, travel, walls, spatial lifecycle and the repair suites | **960 passed, 6 baseline failures**. |
| Player suite, excluding its existing broken legacy collection file | **225 passed** before the final archive-owner extension; that extension was separately qualified below. |
| Final boundary follow-up: recording, capture isolation, schema, birth, item destruction, condition lifecycle, Sanctuary and spellcasting | **101 passed** after the final fixes. |
| Python SDK + player + progression + Python code generation | **587 passed**. |
| TypeScript SDK `npm test` | **63 passed**. |
| Native optics/sensory qualification | **50 passed**. |
| Frozen icon snapshot architecture check | **1 passed**, five unrelated cases deselected. |

The shared-engine selection completed before the last secondary-only targeting
and archive-owner fixes. The 140-case repair lane and 101-case boundary follow-up
ran after both changes.

The full engine run during implementation produced 3,288 passes and 92 failures.
Of these, **69 reproduce unchanged at checkpoint `059ad0af4c9`** in an isolated
source copy (69 failed, 385 passed). The remaining 23 introduced/migration
failures were repaired and their affected files passed the final selection.
The final six failures above are two stale Dimension Door source-ID assertions
and four pre-existing Globe propagation fixture failures (dice/footprint counts).
They are among the independently reproduced 69; their expectations were not
weakened for this repair.

The other checkpoint failures concern environment door reach fixtures, old
combat-log expectations, residue event assertions, world birth field coverage,
old audience fixture values and one window/door reach fixture. Exact baseline
node IDs, commands and lane results are saved in
[`SPELL_CATALOG_REPAIR_QUALIFICATION_2026-10-16.json`](SPELL_CATALOG_REPAIR_QUALIFICATION_2026-10-16.json).
This is not a claim that the full repository test suite is green.

Two unchanged files cannot collect with the current repository imports:
`tests/engine/test_solid_walls.py` imports missing
`tests.game.door_destruction_scenarios`; `tests/player/test_application_review.py`
imports missing `game.runtime_*` modules. They were excluded explicitly. No old
server modules were restored to accommodate them.

Reproduce the repair lane:

```bash
uv run --no-sync python -m pytest \
  tests/engine/test_spell_catalog_audit_admission_regressions.py \
  tests/engine/test_spell_catalog_audit_gameplay_regressions.py \
  tests/engine/test_spell_catalog_audit_damage_regressions.py \
  tests/engine/test_spell_catalog_audit_duration_regressions.py \
  tests/engine/test_spell_catalog_repair_interactions.py \
  tests/engine/test_spell_reaction_admission_repairs.py \
  tests/player/test_retired_magic_recording_contract.py \
  tests/progression/test_removed_spell_cold_inputs.py --assert=plain -q --tb=short
```

Source undefined-name/unused-local/syntax checks and `git diff --check` pass.
The final native contract export retains the identity above. Runtime AM search
is empty outside the explicitly offline compatibility reader; historical schemas
and documents deliberately retain their original evidence.

## Actual implementation review

- **Anti-OOP approved** after executing native secondary-only harmful-action and
  active archived-destruction counterexamples, then verifying the fixes. Its
  final focused run passed 62 cases. Also reviewed exact owner/lease treatment,
  True Strike admission, Shield preparation, publication, size and optics order.
- **Anti-slop approved** after the context-preserving archive fix, family-aware
  restoration and exact icon delta verification. Its independent earlier run
  passed 96 cases; its final boundary-delta review passed another 20 cases.
- **Plan adherence approved:** the monitor independently reran all 140 repair
  cases and checked finite family dispositions, cold inputs, test migration,
  baseline evidence, schema/archive consistency and current handoffs. Final
  confirmation is recorded in plan section 11.

No additional mechanic decision blocks this approved repair scope. The broader
Bestow Curse spell-damage policy remains the explicit deferred decision above.
