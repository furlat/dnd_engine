# Cleanup implementation: independent ECS / anti-OOP / import-DAG review

**Disposition: REQUEST CHANGES.** Reviewed the current uncommitted implementation,
not merely the approved design. One cleanup regression and two retained ownership
blockers are established below. The import DAG and new passive export boundary
pass this review's checks; those results do not discharge the ownership defects.

Comparison revision and current HEAD:
`981079bc0208dbb23f3ccc927347eef77fef4c30` (`pre-cleanup`). Review date:
2026-10-03. Source is the shared WSL checkout
`/mnt/c/users/tommaso/documents/dev/dnd_engine`. The fingerprint section records
the actual reviewed files, including new untracked schema files.

This review followed `AGENTS.md`, the current recovery checkpoint,
`HISTORY_BEFORE_ME.md`, the cleanup plan and `HOW_TO_TEST.MD`. It inspected the
movement/value, condition, action-discovery, item resource, content-composition
and passive-schema changes with their relevant callers. Presentation ownership
was checked at the shared type/import boundary; this is not a separate approval
of every choreography or rendering change. No production or test files were
edited, no source was patched at runtime, and no subagents or external chats were
used by this reviewer. This document is the only authored file.

## Prioritized findings

### ECS-1 — P1: reject an unadmitted concentration owner before committing its dependent effect

Locations: [SpellAction.apply_owned_condition](../../dnd/actions.py#L4999),
especially lines 5004–5008, and
[SpellAction.ensure_concentration](../../dnd/actions.py#L5035), lines 5035–5039.

**Observed defect:** on a deployed actor with standard actions, install an ordinary
event handler which cancels `CONDITION_APPLICATION` at `EFFECT` only when the
condition is `Concentrating`. Then call the public `Fly(..., alt_skip_slot=True).apply()`
with that actor as caster and recipient. It raises `KeyError('Concentrating')`.
Afterwards `active_conditions` contains `Fly`, there is no `Concentrating`, and
`action_economy.current_speed(FLYING)` is 60. The condition and flight grant have
been committed before the required owner was admitted.

`ensure_concentration` ignores the return/cancellation from `owner.add_condition`,
sets `cast_concentrating_uuid` to the rejected object, and indexes the active
condition by name. With an older surviving concentration it can also retrieve an
owner other than the one it just attempted to create; this latter branch was
identified in source, not separately executed here.

**Classification:** pre-existing blocker retained by cleanup, not a newly
introduced regression. Baseline `roster_support.py:45–54` contains the same effect
then concentration ordering; baseline `actions.py:5094–5098` ignores the same
admission result. The public-path failure was reproduced both in the current
checkout and the existing baseline checkout `/tmp/dnd-cleanup-baseline-981079b`,
using the same interpreter and `PYTHONPATH` set to the baseline source.
It directly violates cleanup steps 4–5's required condition admission, failure
cleanup and concentration ownership contracts.

**Minimal correct remedy:** keep this in the existing spell/condition ownership
boundary. Admit the required concentration owner and dependent effect through
the existing condition admission/commit mechanism, propagate rejection, and
verify the exact installed owner before recording the cast UUID or linking its
child. Do not leave an accepted dependent effect without its required owner.
Preserve the plan's committed action-cost/item-release semantics and unrelated
completed child operations; no general ancestry rollback or refund mechanism is
needed. Cover the public cast rejection and retained-owner replacement paths.

### ECS-2 — P1: discarded retained effects leave direct runtime state installed

Locations: [ShillelaghEffect](../../dnd/spells/transmutation.py#L2216),
lines 2216–2236; [ProduceFlameEffect](../../dnd/spells/conjuration.py#L4970),
lines 4970–4989; [FireShieldEffect](../../dnd/spells/evocation.py#L5277),
lines 5277–5291. The existing rejection owner is
[BaseCondition.discard_uncommitted_runtime_state](../../dnd/core/base_conditions.py#L835),
lines 835–848.

**Observed defects:** use the same ordinary handler boundary to cancel the named
condition at `CONDITION_APPLICATION/EFFECT`, then cast it through `.apply()`.
Every case returns `CANCEL` and leaves no active condition, but these state
changes survive:

| Canceled effect | Publicly observable state left behind |
| --- | --- |
| Shillelagh on a canonically built, looted and equipped wooden quarterstaff | `attack_damage_die(actor.uuid)` is 8, `attack_is_magical(actor.uuid)` is true, and the exact weapon retains the orphan override. |
| Produce Flame on the caster | One additional attached light source and the registered `Hurl Produce Flame` / `Dismiss Produce Flame` actions remain. |
| Fire Shield on the caster | One additional attached light source and the registered `Dismiss Fire Shield` action remain. |

The direct grants/override/light are installed inside `_apply`. Their cleanup is
implemented only in `_remove`, which correctly belongs to admitted removal.
Rejected application instead calls the existing `_release_owned_runtime_state`
hook and removes the tracked modifier/handler UUIDs. These three effects do not
implement that hook. In particular, the leaked Shillelagh enhancement has no live
condition duration or release handler to remove it.

**Classification:** pre-existing blockers moved into the school modules.
Baseline `roster_support.py:136–155`, `:316–332` and `:443–468` have the same direct
state and `_remove`-only release; the current rejection lifecycle remains the
same. All three public-path failures were reproduced in both current and baseline
source. This is incomplete
cleanup of the explicitly retained effects, not justification for new lifecycle
machinery or removal of the spells.

**Minimal correct remedy:** implement the existing idempotent
`_release_owned_runtime_state` contract on these owners and keep a single release
implementation for their exact weapon override, action IDs and light ID. It must
run on discarded application and accepted removal, while vetoed removal leaves
the active effect intact. The new Fly/InnateFlight implementations already use
this lifecycle boundary. Cover rejection through real handlers and check visible
weapon/light/action results, including failed replacement preserving the prior
effect.

### ECS-3 — P2: current_speed now mutates the live serialized contextual cache

Locations: [ActionEconomy.current_speed](../../dnd/blocks/action_economy.py#L1025),
lines 1025–1038; [ContextualValue.additive_score](../../dnd/core/values.py#L854),
lines 854–860; [ContextualModifier.evaluate](../../dnd/core/modifiers.py#L353),
lines 353–368. `cached_results` is a serialized field at modifiers.py:262–265.

**Observed defect:** create a normal default actor, compose it, build
`armor.plate`, loot it and equip it in `BodyPart.BODY`. With its ordinary unmet
Strength requirement, record
`action_economy.model_dump(mode='json', exclude_computed_fields=True)`, call
`current_speed()`, record again, then repeat. Both reads return the expected 20
feet. Both reads nevertheless change the serialized economy: the contextual
penalty's `cached_results` receives a newly generated numerical-modifier UUID
each time. Excluding computed fields ensures the serializer itself is not the
operation causing this result.

**Classification:** cleanup-introduced regression at this query boundary.
The identical armor probe on baseline source returns 20 twice with **no**
serialized-state change on either call. Previously `current_speed` evaluated a
detached value copy; now it evaluates
`walking_speed` / `flying_speed` directly. The existing evaluator writes its
result into the live modifier every time. This is narrower than alleging a
wrong movement distance: the directly demonstrated failure is serialized-state
churn caused by reads. Cleanup step 3 explicitly requires pure queries and says
repeated reads cannot alter serialized state. The new purity test uses only
static effects and therefore does not exercise this contextual case.

**Minimal correct remedy:** provide side-effect-free contextual resolution at
the existing value boundary for speed queries, keeping any diagnostic/evaluation
cache outside authoritative serialized movement state and avoiding fresh live
registered modifier ownership merely to read a number. Do not restore the deep
copy, split speed ledger or cleanup-on-read workaround. Extend the existing
public purity case with actual contextual speed content such as the armor
penalty or Barbarian Fast Movement, while preserving contextual arithmetic.

## Checks and positive conclusions

Executed using
`UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv /home/tommaso/.local/bin/uv run --no-sync`.
Interpreter: Python 3.13.12 at
`/home/tommaso/.cache/dnd-engine/venv/bin/python3`; Pydantic 2.13.4;
pytest 9.0.3. Source reads were from `/mnt/c`, not a Linux-native source copy.

| Check | Observed result |
| --- | --- |
| `python -m pytest -q tests/architecture/test_dependency_boundaries.py` | 21 passed in 26.05s. Includes import cycles, function-local/dynamic imports, type-checking import workarounds, dependency direction and leaf-owner checks. |
| `python -m pytest -q tests/engine/test_item_resource_lifecycle.py tests/engine/test_roster_support_spells.py tests/engine/test_modifiable_value_semantics.py tests/engine/test_roster_ability_batch.py` | 104 passed in 14.22s. |
| Fresh interpreter importing `game.export_schema` and generating each exported model's serialization JSON schema in memory | PlayerSequence: 131 definitions; StudioDraftFile: 42; WorldBindingsSource: 28. No errors. |
| Fresh-process imported-module inspection after that generation | No `dnd.entity`, `dnd.core.events`, `dnd.core.base_block`, `dnd.core.base_actions`, `dnd.core.base_object`, `dnd.core.content.runtime`, Pygame or server modules loaded. |
| Focused public condition-veto and contextual-speed probes | Failures detailed in ECS-1 through ECS-3; not committed as tests. |
| The same probes in `/tmp/dnd-cleanup-baseline-981079b` with its source on `PYTHONPATH` | Both ownership findings reproduce, including all three leaked-effect cases. Both contextual speed reads return 20 without changing the serialized economy. The interpreter reported `dnd.actions.__file__` from the baseline checkout. |

The baseline probe owners (`actions.py`, `blocks/action_economy.py`,
`spells/roster_support.py`, `core/base_conditions.py`, and
`items/property_composition.py`) were compared against the Git revision before
using these results for classification. Their text matches; `base_conditions.py`
differs only in newline encoding.

The implementation makes the intended ownership improvements in the inspected
paths. Movement has one expenditure ledger and mode-specific values; exact
factors use existing modifier ownership. Innate flight and spell flight compose
shared Move rather than inheriting a spell. Multiattack receives a complete
authored replacement record. Weapon semantics survive the canonical builder.
Powered wearables compose existing item/armor/spell capabilities with a typed
equipped-source requirement. The removed ammunition and three task-owned runtime
modules have no remaining active Python consumers in `dnd` / `game`.

Finite resource preparation consults the existing operation history for terminal
and stale commits, and the action's `finally` closes pending prepared children
without refunding completed releases. The focused lifecycle tests verify that
behavior; they are not evidence for every possible handler exception/reentrancy
path. Concentration publication now has a commit owner for child-removal batches.
The new passive event/appearance/world-binding types and exporter are real shared
declarations, not runtime-loading aliases or duplicated transport owners.

These observations establish useful architectural progress. No additional
cleanup-introduced gameplay regression was established by this pass beyond
ECS-3. The complete game/native/AI suites and all renderer privacy/timing cases
were not independently rerun here; their published broad-suite failures and the
other implementation review remain separate evidence. No global green claim or
implementation approval is made. The three actionable findings require review
after correction; the two baseline findings remain blockers to claiming this
plan's ownership acceptance is complete.

## Reviewed snapshot fingerprints

The following hashes identify source read or examined in focused diffs and its
supporting contracts/tests. A hash is an identity receipt, not a claim that every
line of each file received equal-depth review. New schema files are included
explicitly because a tracked-only Git diff omits them.

Fingerprint time (UTC): 2026-10-03T01:05:37.228956+00:00.

Tracked-scope binary diff command: `git -c core.safecrlf=false diff --binary 981079bc0208dbb23f3ccc927347eef77fef4c30 -- dnd game tests/architecture/test_dependency_boundaries.py`.

SHA-256: `ad6dbdb5067da3d98ee9aac9f2024818e163f240c8a03c17102d558984c98ec9`. This matches the pre-report fingerprint; no tracked implementation drift was detected during the bounded checks.

Manifest SHA-256 (the exact `hash  relative-path` lines below): `174c247274f65b7ea1835c30487388dfb1ccaf50992ab7433d63447c6c8de02c`.

```text
f55bd11c068b4a3cf31e889a9d1faf177227a119cf999867ad0f390fae5cff14  AGENTS.md
079fbab21737c0c9f5ff7127f40ffa17824128a7e3b47fa74c79c0c1f4dd9745  RECOVERY_PLAN.md
7d02cf6ab9285bcad24ce386299ecf26a9b27ebe88494ccbb70907bfb317342c  HOW_TO_TEST.MD
6fc466f87c66b5398af39655d27abbf7614389c19f548f851cd847f0edc34f58  agent_docs/ANTISLOP_CLEANUP_PLAN_2026-10-03.md
afc9f8fd1914eff9496b97977231e7009b592b52b615fc323febb010f53ab939  agent_docs/ANTISLOP_CLEANUP_IMPLEMENTATION_2026-10-03.md
49d929db1db01accb8fc46b76981ee21ba7d797405b4039c38b76aa2956f396f  dnd/actions.py
78b09eb254b2e9e80c9fc83083a1ff65f7783fc77102209ac4e4f7cdaef466b4  dnd/actions_functional.py
001078733ea7a5b74e4a7023539c88b3578c18fff42f788c99242c25ca59f5ce  dnd/entity.py
2279e56c06cd3b97466db261e0e10f3be5428d751f61ffb38f424da4472e5511  dnd/conditions.py
0680c5ce69bc2834e5f51ca24f14d50debd526f71d88d734f0048243936c7057  dnd/actor_projection.py
ab7b4b7f28bebf984b3ad79dc865fcc09c11e294924d73683770142acff97b9a  dnd/blocks/action_economy.py
fd65c7032cd5bc115cc025f31494c74c2bb1f003f5f37683a8dee3cb8aaa0224  dnd/blocks/base_item.py
12e526a382fa88bd379617f7ced603d11066af30b530a4c5c171ea38aed39aec  dnd/blocks/equipment.py
9ea65c77cd5e6621810d37e5bd639fd28d38fd24b342cf17ebf0ce9785d0f078  dnd/core/base_actions.py
f47a0d368848771b386a45e29cbb8a370c1199504c8319a7c1816b2c3913aa76  dnd/core/base_block.py
39a166b6d765a4b0bfa8ae359fde163d7874c186912b17d0f25c9ac77bfb159e  dnd/core/base_conditions.py
f1c83a9117de5fdd13aaade57999bdcbf59f29f36acd57c1a9ac1f1b152ba183  dnd/core/base_object.py
311f2fc1b5d27494518f350f1f9330284d6416191b5504909e9e92da580cc52d  dnd/core/events.py
f27d6b0e4235deed2cde5c90bb3d860d7770aa8c2cea0e7cab2b6470103bca91  dnd/core/effect_types.py
5c5eed5f140b235d2d98061d4b195c5a42b50149b936752de02aff635d382f40  dnd/core/values.py
ffb95f52ea8386e69031d8011e0dc726898c1458c3fdba2b87d0f72984897681  dnd/core/modifiers.py
7a3d9701d283df3e1ed00a3cf68a3a1df85800d5a12db047e1627df7d2f8a74d  dnd/core/attack_types.py
b656a6173fc3028a1e2b8aa24cc85e2f99616a3dba6fd63276cdfc12e8b1d332  dnd/core/equipment_types.py
9d99c9ff66c0ee6587ff69fc045df6fee4ba675b847b6bd3da55702aae16bf56  dnd/core/item_types.py
8c65aaee4f66eb8379409fff3c0a08b956f16515d7926af383a47e63b3ffd795  dnd/core/item_properties.py
32e6c57e716c84620a5efe7b281a947f9ce81b48082d4ca5cc9ddccb3815dc17  dnd/core/combat_log.py
6626be0330805d2e44ddd34c32757827cee6aeeeb1f230c1857d0bec5accc390  dnd/core/world_edges.py
d6c0d6fb3dfd879f81a63f1cf0b6fbca0a191d953023fb161eb9aaa69cf0a2a4  dnd/core/traversal_connectors.py
6bdbc3be60a1c3f9cdf980d356ff9059ae65dd3af4ca9cd4fb3fc8fbf7691efb  dnd/classes/sorcerer.py
fff06a46b3723936a194443c69477a647920a18348fb241829c6ec1487001dcd  dnd/classes/barbarian.py
0c3c16e6f54663fc11d693d9b8e2076737dbbd98b6f661ab144b6c1e3593f953  dnd/content/items/authored_item_builders.py
3d6c51aa29fe69a3e9ac3c8f7013d7deb9121c407dacc3e2fb545993298cb309  dnd/content/items/authored_item_definitions.py
434045bd0e0d30170f205ef9df1c23b930e873e46bbcfdaada9533b95bbec32c  dnd/content/characters/barbarian_grants.py
590105af213d0016b6c078e537379f9ca23c19a5faee8e9c7677a6e56e2f7c83  dnd/content/characters/sorcerer_grants.py
b2540ff72abb4bea6a4544ebbdefd0c893a6099013da76f88a8fa1b542fa2150  dnd/items/spell_items.py
97efe49a283ed81fdbbeba651b9005d1dd608d5ded329cd68de50134a1ca4728  dnd/items/property_composition.py
2f1c110f4250b6656b3b3a1ba2f50e34c64e56ae08fcf2b6547246e5dafd3daf  dnd/monsters/traits.py
7c77f4294c8cdb642ae6b29ebea68f04f74ffa3fa7d872394ec6a52d97718af8  dnd/spells/transmutation.py
aa67d3e1215d1df940fa28b38b62498bd0fcdda0a1e1a846694f033bbbf6dde5  dnd/spells/conjuration.py
a511c8f60a443c28111c6f2513a7b17df65368ec5f38ae8d4d0a319852d6c3dd  dnd/spells/evocation.py
49334898d030606b0a05b367c2061e5e7fb517192ae71315f746d9ce3db6be9d  dnd/spells/abjuration.py
c75d59273a6b339211d4112c0e28b549899fbad112a726a96c07e62772626834  dnd/types/event_facts.py
ad07246b376d0f954d47c0012a06c960f62b77783169bcead928449ecc0a8849  dnd/types/appearance.py
db0c1640337561f46a6da2b5c975520263d258c3b87950f6190079f94d0f776c  dnd/types/actor_facts.py
8bdc67725225b9ae3fc2631bea9a51a598d36969eacc0e93704da7b09efab2ed  game/export_schema.py
2e36cbb993f446b7bcf63d1d2ffa6b0fa935ce473213923f5e3cc60e2c40c74e  game/world_binding_types.py
d6508e126c340df34ded13f5efbede662cf2213c964260781a9792aa5df65563  game/player_facts.py
f4e68929a92f4dd3acd98badf9f8225d955c51d96456e33e6e7f4dd396df0ac4  game/player_reduction.py
4530337d89a76bbcaf23104fa8411d976963cf3216626c67a51c48ba7815dba1  game/recording_compat.py
27dfac55e70944990abf0dc02ac1cb986c444bc83a031733140603b299cfa4cf  tests/architecture/test_dependency_boundaries.py
86e447e778b06de23f371fb6bbaa3abd5d4e88bc8a6446c8ac444e686a243bbf  tests/engine/test_item_resource_lifecycle.py
032eaa2f14835ca5e002a3490338ab1b89562b6d86604337bf1588743ff3dca3  tests/engine/test_roster_support_spells.py
7ef2335bb7f5efa207228b1c7e8ca28bfbab30bd069071c09f9aa5db186f6989  tests/engine/test_modifiable_value_semantics.py
a81a19d1b9d50de19f1c64aa1134357e5cbd917ada4d742db96784d81c7e1b2c  tests/engine/test_roster_ability_batch.py
```
