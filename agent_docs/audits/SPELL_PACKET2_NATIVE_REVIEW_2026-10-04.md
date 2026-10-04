# Packet 2 native review — 2026-10-04

**Approved within this native review scope after correction.** Independent read-only review against packet 2 of `agent_docs/SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md`, using the working changes over `95a47cd5ca508838bce8a2e67d6fe1fc591ce4e6`. Scope: Shillelagh, Barkskin, Produce Flame/Hurl/Dismiss, Fire Shield, the shared non-cast declaration change, Sanctuary/Metamagic compatibility, and condition-source damage propagation/projection. Continual Flame, Telekinesis/shared landing, packet 3 and visual acceptance are excluded. No production file or test was edited by this reviewer.

## Correction verification

Both findings below are resolved in the revised source. Initial and retained throws now use `validate_single_recipient` before payment, while self-target retention remains admitted. Hurl still emits a nonverbal `BASE_ACTION` `SpellEvent` and now retains its actual condition's original `EffectOrigin`. Globe and Antimagic extend their existing guarded spell-effect handlers to that event category; unrelated ordinary actions remain outside their type guard. Counterspell remains cast-only. No second attack executor was introduced.

Independently reran `uv run --no-sync python -m pytest -q tests/engine/test_nature_spell_delivery.py`: **13 passed in 2.74s**, matching `/tmp/dnd-nature-reviewed.log`. This includes both range rejection forms, protected retained throws, original provenance, Silence, Sanctuary, metamagic exclusion and critical death-save handling. The prior diagnostic failures below are retained as history, not current blockers.

Correction source pins: `dnd/actions.py` SHA256 `3277b3e8a2d8147df4cfe7338cce2499463592e365a6b11a4d36cefb3a995ade`; `dnd/spells/conjuration.py` `5a9d266e55dff8e12393457dac28b9a4b381248abd28019688b0f2b32de012ab`; `dnd/spells/abjuration.py` `459f32bd60d6fa860dc27b2e0140882efe5ed2c0a0eb8537ec96d91b30f1b1c7`; `tests/engine/test_nature_spell_delivery.py` `e9cc338dc0e666269623ff21b06ab95bde83fb8687290d009d7f728e9eecc334`. Other packet work may subsequently change these whole files.

## Original findings — corrected

1. **Enforce Produce Flame's 30-foot range before spending or consuming the flame.** `ProduceFlame` has no `_validate` override (`dnd/spells/conjuration.py:4854`); `HurlProduceFlame._validate` checks only the retained condition UUID before delegating to `BaseAction._validate` (`:4905`). That base validation does not admit a single spell recipient or enforce its range. `physical_access_error` checks barriers, not distance. A direct native initial throw and a granted retained throw from `(2,2)` to `(9,2)` both completed and dealt 4 HP despite the 35-foot separation. Apply the existing recipient/range admission to both throw forms, with the self-target hold branch kept valid. Reject before action expenditure and retained-flame removal. Do not introduce a new sight prerequisite solely for this correction; preserve the engine's supported recipient policy.

2. **Preserve spell-effect protection when Hurl is a non-cast action.** The new `SpellAction._create_declaration_event` selection correctly emits `BASE_ACTION` for retained Hurl (`dnd/actions.py:5419`), but Globe's blocker only subscribes to `CAST_SPELL` (`dnd/spells/abjuration.py:1242`) and explicitly rejects other event types (`:1204`). Antimagic's blocker also subscribes only to `CAST_SPELL` (`:3471`). Both now miss this retained magical projectile. In separate native probes, a caster at `(2,2)` retained the flame, an enemy at `(7,2)` installed Globe or Antimagic, and Hurl completed, dealt 4 HP and consumed the flame in both cases. Extend the existing spell-effect protection path to this typed non-cast spell-effect event. Keep Hurl outside Counterspell, verbal casting and metamagic; do not change it back to a spell cast or add another attack executor. Verify protected throws produce no damage and leave no duplicate consumption/removal events.

## Bounded positive findings

- Shillelagh selects an actual held wooden club/quarterstaff in the active melee set, records its exact UUID, rechecks that same weapon at application, and stores its override on that weapon with the caster UUID. The condition snapshot exposes `affected_item_uuid`; removal clears only its own override key. Unequip/drop and switching to another weapon set remove the actor-owned condition. The d8/casting-ability/magical treatment continues through ordinary weapon attack composition. No second item condition or attack route was added.
- Barkskin uses the existing complete-AC minimum constraint, a 600-round duration and exact concentration ownership. Touch admission is explicit. Existing native cases cover AC below/above 16 and concentration cleanup.
- Produce Flame and Fire Shield each use the native 100-round condition clock and an owner-anchored bright-10/dim-additional-10 light. Exact removal releases light and granted actions; rejected provisional applications have existing cleanup regressions. Produce Flame's stored caster level and spellcasting source feed the existing ranged spell attack and cantrip scaling. Miss consumes the retained flame; critical-hit provenance reaches ordinary death-save handling.
- Fire Shield retains the real warm/chill choice, opposite-energy resistance and 2d8 retaliation without reaction expenditure. Its handler rejects canceled, missed, ranged and more-than-five-feet-away attacks; support elevation participates in that distance. Retaliation has its own damage resolution while remaining causally parented to the actual hit and attributed to the original shield effect. Its condition UUID propagates through `TakeDamageEvent`, `DamageAppliedEvent` and the player facts. Projection only retains the source condition UUID when that observer's source actor exposes the corresponding non-internal condition.
- Sanctuary sees the typed Hurl declaration/effect without treating ordinary unrelated base actions as spell events. Quickened, Twinned and Distant metamagic now exclude non-spell `SpellAction` instances. These are targeted changes to existing owners, not a replacement rules framework.

These findings do not approve every duration boundary, race, protection interaction or renderer output. Both reproduced failures have now been corrected and independently rechecked as recorded above.

## Evidence and limits

Read `/tmp/dnd-nature-delivery3.log`: **17 passed in 8.03s**. That receipt is supplied combined evidence, not a new independently run full native suite. Read `tests/engine/test_nature_spell_delivery.py` and relevant cases in `tests/engine/test_roster_support_spells.py`; the current `test_spell_handoff_control.py` contains packet 1 control cases, not packet 2 utility cases.

Ran only four in-memory native diagnostic cases using the existing `actor`/`cast` helpers, `Game`, `reset_engine_runtime` and deterministic dice. The first range cases used faces `(15,4)`; the corrected protection cases used `(15,4,20)` so the protected caster's concentration save had a face. An initial protection probe exhausted the fixed faces after damage had already been applied; the repeated complete probes above are the evidence. No rendering, asset import, external chat or new test file was involved.

Reviewed candidate SHA256 values (whole files include other agents' excluded work):

| File | SHA256 |
| --- | --- |
| `dnd/actions.py` | `69da6ececc03721d593e8d70b7ee4344f2412d3d356475c1bec1dbc5709854c9` |
| `dnd/spells/transmutation.py` | `7d9be987e4c52f1c44587d4fe817263c5f2b717759a62992565a922e6e702f44` |
| `dnd/spells/evocation.py` | `6a76389c4e8914219c4f15b38e0ea5c9ee4e8136d6e26924e2755dce5472958e` |
| `dnd/spells/conjuration.py` | `79a3d65ed776543d976d6f62a55aef4db3606060525696777934f2f6543360e7` |
| `dnd/spells/abjuration.py` | `20c6654cda245580020d47bc814d032895743917afefc3e705afa2082844f9bb` |
| `dnd/classes/sorcerer.py` | `b4f5bd5903cde14e5599d8afbb428bad4d76569cd555823d1418e280ced2f325` |
| `dnd/entity.py` | `4fb39336f316d6e6b16aa14d25cf77f5e1cf30cee7e47adb48548f0ffb6cc066` |
| `dnd/core/events.py` | `1de52035d4a53307cee21fc704e14577918b10e6a29d168334c4a63f702b8347` |
| `dnd/types/actor.py` | `0c3c0834ba1ea7d61d7629eb5ae288d2300e82579e5b56b30894176b0bebef98` |
| `game/player_facts.py` | `9493e00792376c2c72de5d4065ff9575bdbd1dab662055074bfe8d6b417c3588` |
| `game/player_projection.py` | `761682cfa2050011a282deb3043640de233f1fc1671cbdaa2fb3d8c980525102` |

The table records the original reviewed candidate. The correction verification above supersedes its two failed behaviors; other scope exclusions remain unchanged.
