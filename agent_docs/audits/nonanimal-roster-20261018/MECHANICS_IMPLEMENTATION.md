# NPC mechanics implementation

2026-10-18. Branch `codex/npc-abilities-mechanics`, base `5779fecb60f0d65e5b9c70070ed190a17e0f930b` from `codex/event-native-deltas`. Worktree: `/home/tommaso/.codex/worktrees/remaining-npc-authoring/dnd_engine`.

The human requested the new abilities/mechanics first, specifically avoiding state searches in inappropriate owners and needless event publication. This record covers that shared batch under the [authoring plan](../../plans/REMAINING_NONANIMAL_CHARACTER_AUTHORING_PLAN_2026-10-18.md); character recipes, roster reconciliation, artwork, client playback and CR calibration remain later work.

## Implemented behavior

| Plan item | Result and owner |
| --- | --- |
| A01 Help | Native registered enemy/ally selection grants one attack advantage against the selected enemy. The enemy owns the exact ally grant; a rolled miss consumes it. Expiry uses the helper's next turn, departure and actual encounter cleanup. Existing restorative AllyHelp remains available. Discovery/selection previews publish no events. |
| A02 Assassinate | Contextual attack advantage reads the exact encounter's authoritative first-turn-start fact; surprise critical eligibility uses its live first-turn interval. Skipped turns, late joins, restart and natural-1 misses are covered. Sneak Attack accepts selected 4d6 through its existing feature and now receives final attack advantage directly on the existing damage-roll result instead of reading a parent event with getattr. |
| A03 Evasion | Health applies DEX-half-on-success save defense from immutable DamageSaveContext on existing incoming damage, whose amount already includes the ordinary save adjustment. Success deals zero; failure halves each typed component before affinities. Other save rules remain unchanged. Real Fireball, Burning Hands, native breath and trap checks pass. Existing spell walls, persistent fields, payloads and other DEX-half routes carry their local facts through the same owner. |
| A04 Spell damage resistance | Health combines actual packet/event spell provenance with existing damage affinity in one resolution. Matching type resistance does not quarter damage, immunity wins and magical body/weapon attacks remain ordinary attacks. Source-owned spell origins now survive older direct spell and elemental-surface delivery sites. |
| A05 Assassin poison | One consumed real dose coats an actual selected melee or ranged weapon. DC15 CON, 7d6 Poison, half on success, without Poisoned or critical doubling of the separately saved poison. Source ownership, weapon transfer, expiry, miss, immunity/resistance, object exclusion and admission refusal are covered. |
| A06 Brute | One additional die from the actual held melee weapon, including Shillelagh's existing override. Replacement weapon, critical and independent buff behavior remain composed; no unarmed/shield die is added. |
| A07 Undead Fortitude | Existing incoming damage carries critical provenance. The feature uses normal HP and the shared post-defense damage preview for lethal qualification/DC, preserves temp-HP allocation and skips critical/radiant/already-zero-HP cases. It prevents death before commitment rather than reviving afterward. |
| A08 Parry | Uses the existing post-roll attack boundary. A visible ordinary melee hit must be preventable with the actual held weapon and available shared reaction. Misses, critical/automatic hits, unavailable weapon/visibility/reaction and ranged attacks spend nothing. |
| A09 Leadership | One d4 from overlapping leaders, shared known language, hearing/range/incapacitation gates, ten source turns, native short-rest resource. Exact action teardown releases its owned resource. Refused activation installs no aura. Silence contributes an explicit blocks_sound fact read through the existing local spatial index after ally/range gates. |
| A10 Shield Bash | Real equipped Shield UUID through existing Attack composition: +7, 2d4+4 Bludgeoning; DC15 STR Prone only for Tiny/Small/Medium, with ordinary damage to larger targets. Native item admission, transfer/stale swap, stance activation, buffs and critical rules remain in the same executor. A selected three-hit Multiattack can substitute one bash. |
| Phase1 source qualification | Existing finite LearnedReactionSpellSource facts now participate in Shield/Counterspell cost selection and commitment. The chosen innate daily resource and shared reaction are consumed, exhausted innate sources cannot impersonate a slot source, and source ownership is rechecked at commitment. Public casts on an actual Fellwing body with test-only source grants cover finite use, rest, fallback, refusal and source removal; no new Devil recipe was authored. |

## Ownership and publication

Evasion and spell resistance are source-UUID grants in Health, released by native condition admission rollback/removal. Neither installs a per-damage event handler. Minimal save, critical, advantage and item facts travel on existing event types; this batch adds no event family or replacement combat executor.

Coating dispatch extends the existing Trigger index with an optional exact source-item UUID, restricted to damage-roll results. It uses the striking item's retained UUID directly. With two active coatings, passive dispatch evidence records **1 / 0 / 1 / 0** matching invocations for the coated weapon, an unrelated dagger, the same weapon after transfer and removal of its coating. There is no wielder cache, inventory/world scan or event-history lookup. Brute no longer installs an unnecessary turn-reset handler or registers transient bonus values.

Help encounter expiry uses the existing condition removal-trigger vocabulary and encounter-owned combatant loop. Only actual expiring grants publish ordinary removals. Previewing damage repeatedly and previewing native Help selection publish zero events.

## Explicit remaining choices and limits

- **A11 updated by human clarification2026-10-18:** use SRD5.1 Monk level-scaled single-die unarmed damage: d4 at1–4, d6 at5–10, d8 at11–16, d10 at17–20. The old2d6/3d4 proposals are superseded. Existing unarmed data supports this; each final kit still needs an explicit training tier, ability modifier, attack count and separately selected defense. This clarification changes authoring direction; it adds no Monk class or combat runtime and does not adopt the old CON-based Martial Guard formula.
- The poison lifetime question describes two possible lifetimes of the same Assassin Poison item, not duplicate objects. Assassin Poison uses the existing configurable ten-round coating adaptation as its current builder default. This is a finite dose, with no ammunition model. Each future character's possession count and final lifetime treatment remain kit authoring choices; no unlimited poison is inferred.
- Shield Bash's size-limited Prone rider is omitted from the current AI target-effect profile because that profile cannot express the size restriction. Gameplay and ordinary damage discovery are complete; this batch adds no AI schema.
- Sound propagation across room geometry remains outside scope. Leadership reads its leader's current Silence membership and the recipient's Deafened condition.
- A real daily Devil caster recipe remains future authoring. The shared reaction-source behavior is qualified on an existing materialized fiend with explicit test grants.

## Verification

The root agent and defense implementation checks use Python3.13.12 and dependencies isolated in `/home/tommaso/.cache/dnd-engine/npc-mechanics-venv`; source is on the Linux worktree above. The plan guard used the README-prepared `/home/tommaso/.cache/dnd-engine/venv` for its147-test source/reaction and40-test surface batches, with the same Python version and source. Root commands use `env UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/npc-mechanics-venv uv run --no-sync python -m pytest`.

- Final broad owner/integration batch: **731 passed, 22 existing xfailed, 11 failed in47.10s**. All11 failures reproduce at the untouched base, described below. This batch includes all seven new gameplay suites, existing poison/roster/Goblin/gear/resource/reaction/encounter/trap/wall/summon/spell/discovery regressions, progression source/save checks, creation declarations and block/model architecture checks.
- New mechanics plus creation-declaration batch before the final innate/ranged additions: **131 passed in9.25s**. The final broad batch includes those later additions.
- Independent ECS review's final integration batch: **194 passed, 22 existing xfailed in8.25s**. Independent root damage-defense suite: **35 passed in0.74s**.
- Finite innate-source and existing source/reaction/summon batch: **147 passed in13.47s** in the README environment. The final root broad batch independently covers the new innate-source suite in the isolated environment. A sibling independently reran all10 new source-cost and4 surface cases: **14 passed in0.72s**, with no review correction needed.
- Existing schema-build performance and sensory-settlement oracle controls: **5 passed in18.83s**. The three gameplay scenarios build no deferred schemas; indexed sensory settlement matches the full-recompute oracle. This is a scoped regression control, not a general latency certification.
- `git diff --check` passes. Independent implementation addenda are in [ANTISLOP_REVIEW.md](ANTISLOP_REVIEW.md) and [ANTIOOP_ECS_REVIEW.md](ANTIOOP_ECS_REVIEW.md). A separate same-task plan-adherence agent supervised implementation.

### Existing base failures

Clean source was exported once from5779 into `/tmp/dnd-npc-baseline-5779` using `git archive HEAD dnd tests pyproject.toml uv.lock content_data content_packs`; comparisons ran from that directory in the same isolated environment.

`tests/engine/test_wall_of_fire.py` plus `tests/architecture/test_source_model_hygiene.py`: **11 failed, 58 passed in4.30s** on the clean base. These are exactly the11 broad-batch failure names: two wall position-discovery StopIteration cases, combat-log metadata/docstring hygiene, encounter hygiene, and stale server API/session/error references. The new CombatantState field's own Attributes entry was added after the broad batch; its focused hygiene recheck now reports only the original AdvanceResult.use_register complaint. Unrelated existing failures were preserved.

Additional touched-owner probes also reproduced existing failures at the clean base: empty-visible-area Fireball discovery raises StopIteration before spell execution; Ice Storm's old environment-step terrain-expiry assertion fails; four dependency-boundary checks refer to missing retired game/server modules or pre-existing leaf imports. The clean Ice Storm/dependency comparison reports5failed17passed in8.71s. These do not invalidate the new native Fireball/Evasion/source tests and are not presented as passing checks.

## Human clarification follow-up

The current plan incorporates the human's Monk level-scaling reference and clarifies the single Assassin Poison item. No engine or test code changed in this follow-up: existing unarmed damage data already accepts every referenced die size. The prior gameplay/performance results above remain the implementation evidence; this documentation correction is not a claim of authored Bruiser/Brawler kits. Anti-slop and anti-OOP reviewers checked this bounded correction in the existing review addenda.

## Subsequent native character authoring

The human subsequently authorized all remaining nonanimal NPCs in this worktree.
The [native authoring record](NATIVE_AUTHORING.md) supersedes the future-authoring
notes above: all123 new kits now exist, including both level11-reference trained
fighters, finite three-dose Assassin supplies and actual daily Devil caster
recipes. That record, its complete180-row ledger and family evidence own the
new authoring tests, source omissions and presentation status. The earlier
mechanics-only validation above remains historical evidence for that batch.


## Corrections made when merging into the integration line

2026-10-18, branch `codex/npc-merge`. These supersede the statements above where they differ.

- Assassinate's opening-turn read: `dnd/core/encounter_facts.py` is gone. It cast a registry object to a reader Protocol to call up into Encounter. `OpeningTurnFacts` now lives in `dnd/encounter.py`, and the trait reads `Encounter.get(...)` directly.
- Assassinate's advantage now also requires the assassin's own first turn to be in progress (SRD: "during its first turn"). A late joiner in the assassin's second turn no longer grants it.
- Leadership has no shared-language gate. Most existing creatures carry no language data, so the gate silently disabled Leadership for every SRD ally. Hearing, Silence, range and the leader's incapacitation still gate it. Sight and the "ends if incapacitated" wording remain open.
- Protection is no longer listed as a retired Fighter declaration, so the inventory needs no exemption. Every creature installs it through `dnd/monsters/protection.py`.
- Shield Bash: the Gladiator's +7, 2d4+4 numbers are now fields of the `ShieldBash` action, as with WightLifeDrain. The core `ShieldAttackSpec` has no defaults. Shield Bash and Life Drain substitutions use `register_multiattack(..., attack_replacement=...)`.
- Innate casts: daily uses ride the existing `alt_skip_slot` + `alt_extra_costs` path, the same one Tiefling Darkness uses. Innate reaction spells are typed rows (`SHIELD_REACTION_SPELL`, `COUNTERSPELL_REACTION_SPELL`), not spell-id string tables. The unused at-will reaction branch is removed.
- Recipe data replaces identity checks:
  - humanoid foundations carry their resistances, immunities, condition immunities, bleeding, Magic Resistance, spell damage resistance and innate Invisibility (previously `profile is ARCHMAGE/SENTINEL`);
  - undead profiles carry their expertise;
  - the Wing Regent's deferred legendary note is a field (previously `source_id == "C08"`).
- Brute's held-weapon die is a feature field, not a subclass hook.
