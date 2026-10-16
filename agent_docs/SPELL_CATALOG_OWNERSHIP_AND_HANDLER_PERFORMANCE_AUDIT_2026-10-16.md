# Full spell ownership and handler performance audit

Date: 2026-10-16. Worktree: `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
Branch: `codex/spells-rank-one-two`; current uncommitted implementation over
`a1349f52e8b`. Status: source review and regression capture complete; redesign
and production fixes remain deferred at the human's request.

## Scope and audit procedure

Review all 187 installed spell identities: 182 primary catalog roots, three learned
reaction roots and two separately authored Infernal roots. Include their retained
conditions, areas, items, summon techniques and the shared event/spatial paths
that determine their behavior. Existing custom spell identities are audited too;
this does not expand the allowed spell implementation catalog.

1. Reconstruct the exact installed inventory and inspect every spell module.
2. Check effect ownership, admitted lifecycle and factual event use, distinguishing
   composing one's own effect from implementing another effect's behavior.
3. Inspect handler triggers and full item/entity/area/history enumeration;
   distinguish hot recurring work from necessary bounded casting/discovery work.
4. Reproduce high-impact candidates through native actions/events where practical;
   keep static inference separate from executed evidence and measured cost.
5. Report ranked findings, affected spells, exact code sites, impact and an
   existing-native repair direction. Save full root coverage beside the report.
6. Human scope update: save desired-behavior regression tests for reproduced
   defects, and maintained manual diagnostics for performance findings. Do not
   repair engine behavior before discussing the redesign and fixes.

Review roles: anti-OOP reviewer for ECS ownership/lifecycle; anti-slop reviewer
for recurring scan/dispatch cost and false positives; plan-adherence monitor for
complete finite coverage and scope. This is an audit and test batch, not a repair
batch. The anti-OOP reviewer checked the gameplay tests and the expanded
admission/duration matrices; the anti-slop reviewer measured the recurring work.

## Results and evidence boundaries

There are **12 confirmed correctness finding families and four performance
finding families** below. Several families affect multiple spells. This is not
a claim that only 16 individual defects exist or that every rule of every spell
has been qualified.

The four new gameplay suites contain **71 cases**: **61 reproduce existing
defects, and 10 are passing controls**. Pending defects use `xfail(strict=True)`
with a finding ID. Running `--runxfail` exposes the actual failed assertions;
those failures are expected until separately authorized fixes are implemented.
The maintained performance diagnostic completes **22 measured operations** and
does not impose machine-dependent timing or private-method call-count gates.

All 24 files under `dnd/spells` were inspected (32,248 source lines), including
retained conditions, areas, items, summons and relevant shared event, condition,
item and spatial owners. The inventory contains 187 unique spell identities;
51 identities were exercised in targeted native scenarios during this audit,
and 136 received source review without an individual runtime probe. A root used
as setup, an interaction partner or a passing control is not fully qualified by
that use. Per-root detail is in
[the coverage CSV](SPELL_CATALOG_AUDIT_COVERAGE_2026-10-16.csv).

The current installed pack labels are 173 SRD 5.1, 11 SRD 5.2 and three
Neurodragon. These labels describe registration provenance, not a fresh SRD
eligibility assessment. The three Neurodragon roots are Conjure Fiend, Ice Knife
and Necrotic Bless; Ice Knife is SRD 5.2 eligible. Existing roots were audited
without adding new spells or changing the permitted implementation catalog.

Priority below describes impact, not the implementation-difficulty ranks from
the earlier spell planning lists. Each source location refers to this worktree's
current source. Proposed owner directions are discussion notes, not an approved
implementation plan.

## Correctness findings

| ID | Priority | Confirmed behavior | Existing owner direction for discussion |
| --- | --- | --- | --- |
| SC-09 | P1 | 34 spells mutate HP, conditions, size or spatial effects after their own native spell EFFECT is canceled. | Honor the actual admitted effect before committing authored mechanics; use the existing owned-condition/area/payload paths. |
| SC-06 | P1 | Bestow Curse damages critical misses, pays its bonus twice on a normal hit, and bypasses accepted attack damage packets. | The curse owns one native hit rider at damage finalization. |
| SC-04 | P1 | Shield, Counterspell and Hellish Rebuke function from inside Antimagic Field. | Each reaction must admit its own magical invocation and respect cancellation before applying its effect. |
| SC-01 | P1 | Ending Hold Person removes paralysis still required by an active Hold Monster. | Preserve shared Paralyzed ownership, as Hold Monster already does. |
| SC-12 | P1 | Ending one caster's Chill Touch allows healing while another caster's Chill Touch remains active. | Preserve independent No Healing ownership. |
| SC-10 | P1 | Hypnotic Pattern incapacitates despite Charmed immunity or a rejected required Charmed application. | Its own parent effect must honor required-child admission. |
| SC-07 | P1 | Enlarge/Reduce has incorrect replacement, permanent size leaks on rejected admission, and active size changes under Antimagic. | Replace raw size snapshot/write cleanup with an owned size contribution. |
| SC-02 | P1 | A Charmed creature can paralyze its charmer with Hold Person. | Charmed owns harmful-recipient admission, in addition to attack modifiers. |
| SC-11 | P2 | Seven tested one-minute spells remain active after ten native duration intervals. | Give the relevant spell effect/sustain a finite native deadline. |
| SC-08 | P2 | Rejected Expeditious Retreat leaves bonus Dash; Antimagic suppresses the condition while Dash remains usable. | The condition owns the exact granted action, including admission, suppression and retirement. |
| SC-03 | P2 | Charm Person exposes only a permanent generic Charmed condition and survives damage from its caster. | Give Charm Person a finite spell owner and its own harmful-action ending handler. |
| SC-05 | P2 | Self-targeted Haste is rejected before normal casting. | Fix its authored self eligibility and self visibility requirement. |

### SC-09: accepted cancellation does not stop authored effects

The native matrix installs an indexed `CAST_SPELL / EFFECT` refusal handler,
submits a real paid cast, witnesses that the refusal boundary was reached, and
compares recipient HP, temporary HP, speed, AC, size, conditions and spatial
effects. Wounded targets make healing observable; Poisoned/curse fixtures make
removal observable; Power Word Stun receives a target below its HP threshold.

All 34 failures occur at the final before/after state comparison, not at setup,
collection or cost admission. Examples include False Life granting six temporary
HP, Haste granting speed/AC, Lesser Restoration removing Poisoned, healing
spells restoring HP, and Globe of Invulnerability creating its field even though
the cast result is canceled. They share a missing cancellation check or an
unguarded effect handoff after `phase_to(EFFECT)`; this is not evidence that
their own authored damage/healing belongs to a generic global manager.

Five useful controls reach the same refusal and preserve state: **Bless, Charm
Person, Magic Missile, Longstrider and Antilife Shell**. Multi-target admission
and the newer owned-effect paths already provide useful native references.

Tests: `tests/engine/test_spell_catalog_audit_admission_regressions.py`.
The exact affected-root/source table is appended below.

### SC-06: Bestow Curse listens to the wrong attack boundary

`dnd/spells/necromancy.py:2380–2444` listens to `ATTACK / EFFECT`, checks
`attack_outcome` with `getattr`, rejects MISS but not CRIT_MISS, and immediately
calls `receive_damage` with a standalone d8. Native attacks emit EFFECT before
and after weapon damage, so a normal hit pays this rider twice. A critical miss
still pays one rider. A later rejection of `DAMAGE_ROLL_RESULT` leaves the first
rider's damage already committed.

With deterministic faces of two, a normal hit deals six instead of four total
damage; a critical miss deals two instead of zero. The public attack result has
one damage component rather than the expected weapon plus curse components.
The current critical-hit total happens to equal the expected total through two
separate ordinary riders; that passing total is not proof of correct critical
packet ownership.

Reference: `dnd/spells/hit_effects.py:47` already installs a condition-owned,
critical-aware `DamageRollResultEvent` rider with spell provenance. Tests cover
ordinary miss, critical miss, hit, critical total, packet composition and a
native damage refusal in `test_spell_catalog_audit_damage_regressions.py`.

### SC-04: magical reactions bypass their own admission

Shield's attack interception at `abjuration.py:345–365` commits payment and
forces MISS even when the resulting Shield condition has inactive
contributions. Counterspell at `abjuration.py:1010–1026` pays and cancels an
outside spell while its caster stands inside Antimagic. Hellish Rebuke at
`infernal.py:205–221` continues through canceled execution/effect phases and
damages its outside attacker.

Native tests use an actual Wizard's learned Shield/Counterspell and an actual
Tiefling's innate Rebuke. They check attack/cast outcome, HP and reaction/slot
preservation. This finding concerns those three named casting paths; it is not
a claim that every reaction or Divine Smite has the same defect. No spell-name
branch should be added to Antimagic or the event dispatcher to repair them.

### SC-01 and SC-12: independent effects lose shared children

Hold Person (`enchantment.py:253–262`) creates/replaces a fixed-name Paralyzed
child instead of retaining the existing shared contribution. After Hold Monster
then Hold Person, ending Hold Person leaves Hold Monster active without
Paralyzed and restores an action. Reference: Hold Monster's existing
`add_shared_subcondition` use around `enchantment.py:475`.

Chill Touch (`necromancy.py:356–377`) similarly replaces the fixed-name No Healing
child and links the replacement only to the latest caster's tracker. After two
casters hit, ending the second tracker's effect permits actual Cure Wounds
healing while the first tracker remains active. The needed ownership is per
surviving source; a global condition-name check cannot express it.

### SC-10: required control manifestation is optional in practice

`illusion.py:458–472` attempts to add Charmed, ignores rejected admission, then
installs Hypnotic Pattern's incapacitation modifiers anyway. Native Charmed
immunity and an explicit native child-application refusal both leave the
recipient with zero actions despite having no admitted Charmed manifestation.
A normal admitted recipient is included as a passing control. This is a defect
in Hypnotic Pattern's own composition, not a reason for a spell-name exception
in generic immunity handling.

### SC-07 and SC-08: raw state and action grants escape their condition

Enlarge/Reduce writes `target.size` before membership admission at
`transmutation.py:1472–1478` and restores a raw snapshot in `_remove` at
`1510–1518`. Two allied Enlarge casts produce an active replacement at MEDIUM;
ending it leaves LARGE. Rejected membership also leaves LARGE. Ordinary
Antimagic suppresses the condition while the size change remains active.

Expeditious Retreat registers BonusDash before admission at
`transmutation.py:1247–1248` and cleans up by action name at `1257–1261`.
Rejected membership leaves the action registered. Under ordinary Antimagic the
suppressed effect still allows bonus Dash, spends the bonus action and increases
movement from 30 to 60. Reference: existing condition-owned granted actions use
an exact contribution owner and native suppression gating. These are ordinary
suppression defects as well as rejection-edge defects.

### SC-02, SC-03 and SC-05: incomplete older control/target rules

Generic Charmed (`conditions.py:543–562`) adds contextual weapon-attack and
social modifiers but no harmful magical-recipient admission. A recipient of
actual Charm Person can cast Hold Person on its charmer and paralyze them.
The admission belongs to Charmed's handler, using existing native harmful intent
and recipient facts. Test SC-02 does not require a new AI allegiance system.

Charm Person (`enchantment.py:213–218`) creates bare Charmed with permanent
duration and no spell-specific damage-break handler. Tests require a finite
positive spell-owned duration without deciding between BG3 and SRD duration
numbers, and require ending the charm after direct damage from its caster.
Charm Monster/Animal Friendship's own sustaining conditions and handlers are
useful references. Do not make every generic Charmed effect end on damage.

Haste's `transmutation.py:800–802` checks self against a visual-contact table
that excludes self; inherited self eligibility is also unsuitable. Its test
casts normally on the caster and checks paid resources, Haste and concentration.
Ordinary actions should remain spent by the cast; Haste uses a separate
restricted action budget.

### SC-11: missing finite lifetimes

Actual casts of **Hold Person, Bless, Bane, Haste, Blur, Slow and base-level
Bestow Curse** retain their effects after ten authoritative duration intervals.
Their effect/sustain graph has no finite deadline on the exercised path.
Hold Monster and Mirror Image expire correctly as passing controls.

The test advances the public `advance_duration` boundary without triggering
repeat saves, checks retention through interval nine and expiration at ten,
and permits either recipient-owned or caster-owned timing. It does not prescribe
a private duration field or separate clock framework. These one-minute base
durations are in the [official SRD 5.1](https://www.dndbeyond.com/attachments/39j2li89/SRD5.1-CCBY4.0License.pdf);
the test does not alter upcast Bestow Curse rules or choose new adaptations.

## Performance findings

| ID | Priority | Repeating work | Executed evidence |
| --- | --- | --- | --- |
| SC-P1 | P2 | Antimagic scans every registered item, snapshots unrelated items, rescans all areas/entities on field movement, and installs global creation-return callbacks. | Remote floor-object move: two item passes and 10/202/802 presentation snapshots for 1/25/100 items. Never-suppressed berries dispatch four/16 callbacks per remote move, even after field removal. |
| SC-P3 | P2 | Concentration publication searches the owner's historical target-event tail. | One unchanged publication: 108/1,108/10,108 `isinstance` calls after 0/1,000/10,000 unrelated target records. |
| SC-P4 | P2 | Moving Antilife Shell checks every entity before swept-footprint relevance. | One local move with 1/25/100 remote actors makes 3/27/102 antimagic queries. |
| SC-P2 | P3 | Recipient-specific handlers subscribe globally, then discard unrelated actor events. | An unrelated turn dispatches 1/10/40 Hold Person handlers; every one reports `no_effect`. |

### SC-P1: Antimagic work is not bounded by affected objects

`abjuration.py:3284–3326` enumerates every item and produces presentation
snapshots before checking whether anything changed. `BaseItem.get_all_items`
at `blocks/base_item.py:234` itself walks the entire BaseBlock registry,
including tiles and other blocks. Field movement at `abjuration.py:3519–3537`
also refreshes all areas and scans all entities. Local entry/exit can repeat
item work during the same move.

The measured remote-object move is fully outside the field: 1/25/100 registered
items produce two registry passes and 10/202/802 presentation snapshots. A
one-cell field move produces two item passes, one all-area refresh and one
all-entity pass, with 8/200/800 item snapshots. Current condition suppression
also snapshots every condition before/after each individual condition change
(`3360–3379`), an **O(C²) local pattern inferred from source**, not a separately
measured scaling result. Global light refreshes add further repeated work.

At `3311–3321`, the refresh installs global creation-return callbacks on magical
creations that have never been suppressed. Actual Goodberries far outside the
field produce four/16 `no_effect` callbacks per unrelated move, continuing after
the field ends. These callbacks are creation-owned, so this is persistent
unnecessary fanout rather than an unowned-handler memory-leak claim.

**Correction to the early lead:** plain native item-state publication did not
invoke Antimagic's global EFFECT listener in these probes. The demonstrated
registry amplification is from spatial object changes and field movement.
Existing exact-item refresh at `blocks/base_item.py:196`, indexed footprint
occupants and the field's already tracked suppressed owners are useful repair
references. Preserve overlapping fields and blocked creation-return retry rules.

### SC-P3: an indexed history can still have an unbounded tail

`conditions.py:2069–2085`, `Concentrating.publish_owner_state`, retrieves all
events targeting the owner and searches backward for its own latest condition
publication. This is **actor-target history, not the complete global event
history**. With an unchanged existing Haste concentration, adding 0/1,000/10,000
unrelated completed target records adds corresponding linear search work.

Discuss retaining the last committed publication or adding an exact existing
event-index lookup. Preserve native publication semantics rather than adding a
generic cache/manager. Haste is the measured representative; this shared-owner
cost applies to other callers of concentration publication as well.

### SC-P4: Antilife Shell starts from the world instead of its footprint

`abjuration.py:4333–4349` builds swept footprints, then enumerates every entity
and queries its antimagic state before testing spatial relevance. Remote living
actors therefore add work to a local one-cell shell movement. An additional
source-only concern is rebuilding the complete live footprint inside each
crossing query at `4329`.

Reference: the indexed footprint occupancy query in
`spatial/area_conditions.py:1510` can gather a deduplicated candidate set from
old/swept cells. Preserve the authored distinction between walking a shell into
living creatures and portal transfer, plus undead/construct exemptions.

### SC-P2: cheap callbacks still scale with unrelated actors

Older repeat-save handlers for Hold Person, Hold Monster, Power Word Stun,
Blindness/Deafness, Fear, Sunburst blindness and Bestow Curse subscribe to every
turn and filter a known recipient UUID in the processor. Sleep/Hypnotic Pattern
wake/break handlers similarly receive unrelated damage. Exact sites:
`enchantment.py:323,543,900,1181`; `illusion.py:284,508`;
`necromancy.py:625,2296,2328`; `evocation.py:2130`.

The measured Hold Person fanout is real but cheap; this is not a demonstrated
latency blocker. Native `Trigger.event_source_entity_uuid` and
`event_target_entity_uuid` buckets (`core/events.py:2346–2359`) already avoid
unrelated dispatch. No new dispatcher is needed. Area occupancy handlers and
source-gone fallback expiry handlers have different requirements and should not
be converted blindly to exact-recipient subscriptions.

## Work that was inspected and not classified as a bug

- Composing a spell's own damage, cure, condition, summon or retained technique
  is legitimate. A modifier or a neutral capability is not a foreign-spell
  branch merely because it affects another mechanic.
- Native area ENTER/LEAVE handlers are installed against indexed footprint
  cells even when their `Trigger` text lacks a UUID. Raw trigger counts alone
  do not prove global dispatch.
- Fireball's `get_event_history(effect_event.uuid)` is lineage-indexed. Its
  staged destruction cursor scans only newly emitted events; it is not a scan
  of all combat history.
- Guardian of Faith scans the new delivery interval after a cursor to count
  actual committed damage. A factual resolved-damage callback might simplify
  it later, but this bounded scan is not equivalent to SC-P3.
- Holy Aura's entity count, Charm Monster's combat-advantage lookup, Revivify's
  candidate discovery and wall/Forcecage construction displacement enumeration
  are casting/discovery work. They were not ranked as hot recurring handlers.
  Revivify also intentionally considers dead companion remains.
- Freedom of Movement and restoration spells selecting their own authored
  restraint/condition/tag cure targets are not violations of handler ownership.
  Their SC-09 failures concern canceled cast effects committing those cures.
- Previous 58-spell ownership repairs are present in this dirty worktree. The
  earlier report's historical fixed issues were not re-filed as current bugs.

## Tests, diagnostics and remaining discussion

| Artifact | Desired boundary or diagnostic |
| --- | --- |
| `tests/engine/test_spell_catalog_audit_gameplay_regressions.py` | Native overlap, charm, immunity, reaction, self-target, size/action admission and suppression. |
| `tests/engine/test_spell_catalog_audit_damage_regressions.py` | Bestow Curse real weapon hit/miss/critical outcomes, native result packets and rejected damage. |
| `tests/engine/test_spell_catalog_audit_admission_regressions.py` | 39 witnessed real spell refusals: 34 defects and five passing controls. |
| `tests/engine/test_spell_catalog_audit_duration_regressions.py` | Seven missing one-minute deadlines and two passing controls through native duration progression. |
| `tests/manual/spell_catalog_audit_performance.py` | Repeatable JSON/cProfile diagnostics for 22 operations, passive native handler-dispatch evidence and optional profiles. |

Tests assert desired behavior rather than freezing today's broken results.
Strict xfail prevents hiding an unexpected fix as a silent pass. Performance
work uses diagnostics rather than monkey-patched private methods, exact
implementation call-order assertions or timing thresholds. There are no new
production APIs, condition managers, handlers, client changes or engine fixes in
this audit/test batch.

Executed qualification: normal run **10 passed, 61 strict xfailed in 10.47s**;
`--runxfail` **61 failed, 10 passed in 10.56s**, with every failure at an intended
gameplay/state assertion and no setup/collection errors. Ruff passes on all five
new Python files; `git diff --check` passes. The complete existing suite was not
rerun for a batch that changes only audit documents and test/diagnostic files.

Raw measured operation records are preserved in
[the benchmark JSONL](SPELL_CATALOG_AUDIT_BENCHMARK_2026-10-16.jsonl).
The optional binary profiles were kept outside the repository under `/tmp`.

Run the new gameplay suites with the README's configured uv environment:

```bash
uv run --no-sync python -m pytest tests/engine/test_spell_catalog_audit_*regressions.py -q
uv run --no-sync python -m pytest tests/engine/test_spell_catalog_audit_*regressions.py --runxfail -q --tb=short
uv run --no-sync python -m tests.manual.spell_catalog_audit_performance --case all
```

Execution here used Linux source under `/home/tommaso/.codex/worktrees`, the
existing Linux venv `/home/tommaso/.cache/dnd-engine/venv/bin/python`, Python
3.13.12 and WSL2. The benchmark records source/environment locations and excludes
imports/setup from each instrumented operation. Its full 22-operation run took
31.45 seconds including imports/setup; profiled operation milliseconds are
diagnostic observations, not uninstrumented production performance claims.

Before fixes, discuss a bounded repair order: native cancellation/reaction
admission and the Bestow Curse rider; independent child/required-child ownership;
size/action contribution ownership and finite deadlines; then the measured
spatial/history costs. Charm Person's exact finite duration remains a BG3/SRD
policy choice; the regression deliberately avoids choosing it. The other tests
capture already-authored engine contracts and reproduced behavior, without
inventing special-case exceptions. Every confirmed correctness finding has a
regression; the four performance families have maintained diagnostic scenarios.

Shared-owner findings are mapped to representative tested roots in the CSV.
“No spell-specific finding” does not declare a root immune to SC-02, SC-09 or
SC-P3 merely because that root was not independently exercised. Source review
is not exhaustive damage-type, upcast, multiclass, transport, AI or rules
qualification. Full redesign, fixes and wider post-fix qualification are the
next discussion, not work silently included here.

## Exact SC-09 affected roots

Every row below has its own native failed regression in the admission matrix.
The CSV retains the root declaration source; this table points to its authored
`_apply` entry. The test observes the refused cast and the mutation that follows.

| Spell | Level | Authored apply site |
| --- | --- | --- |
| Guidance | 0 | `dnd/spells/divination.py:367` |
| Light | 0 | `dnd/spells/evocation.py:4350` |
| Poison Spray | 0 | `dnd/spells/conjuration.py:330` |
| Sacred Flame | 0 | `dnd/spells/evocation.py:493` |
| Cure Wounds | 1 | `dnd/spells/evocation.py:4541` |
| Expeditious Retreat | 1 | `dnd/spells/transmutation.py:1278` |
| False Life | 1 | `dnd/spells/necromancy.py:104` |
| Healing Word | 1 | `dnd/spells/evocation.py:4611` |
| Jump | 1 | `dnd/spells/transmutation.py:1159` |
| Sanctuary | 1 | `dnd/spells/abjuration.py:3017` |
| Shield of Faith | 1 | `dnd/spells/abjuration.py:2667` |
| Blur | 2 | `dnd/spells/illusion.py:154` |
| Darkvision | 2 | `dnd/spells/transmutation.py:929` |
| Enhance Ability | 2 | `dnd/spells/transmutation.py:1413` |
| Enlarge/Reduce | 2 | `dnd/spells/transmutation.py:1587` |
| Invisibility | 2 | `dnd/spells/illusion.py:901` |
| Lesser Restoration | 2 | `dnd/spells/abjuration.py:1657` |
| Mirror Image | 2 | `dnd/spells/illusion.py:1208` |
| Protection from Poison | 2 | `dnd/spells/abjuration.py:1980` |
| See Invisibility | 2 | `dnd/spells/divination.py:115` |
| Bestow Curse | 3 | `dnd/spells/necromancy.py:2533` |
| Haste | 3 | `dnd/spells/transmutation.py:813` |
| Protection from Energy | 3 | `dnd/spells/abjuration.py:757` |
| Remove Curse | 3 | `dnd/spells/abjuration.py:1815` |
| Death Ward | 4 | `dnd/spells/abjuration.py:2139` |
| Freedom of Movement | 4 | `dnd/spells/abjuration.py:2431` |
| Greater Invisibility | 4 | `dnd/spells/illusion.py:991` |
| Stoneskin | 4 | `dnd/spells/abjuration.py:895` |
| Greater Restoration | 5 | `dnd/spells/abjuration.py:1727` |
| Globe of Invulnerability | 6 | `dnd/spells/abjuration.py:1340` |
| Heal | 6 | `dnd/spells/evocation.py:4923` |
| True Seeing | 6 | `dnd/spells/divination.py:230` |
| Regenerate | 7 | `dnd/spells/transmutation.py:1974` |
| Power Word Stun | 8 | `dnd/spells/enchantment.py:1228` |

## Catalog coverage totals

| Spell level | Installed identities |
| --- | --- |
| 0 | 20 |
| 1 | 41 |
| 2 | 35 |
| 3 | 25 |
| 4 | 16 |
| 5 | 14 |
| 6 | 18 |
| 7 | 7 |
| 8 | 6 |
| 9 | 5 |
| **Total** | **187** |

| Root implementation module | Root count |
| --- | --- |
| `dnd/classes/paladin.py` | 1 |
| `dnd/spells/abjuration.py` | 26 |
| `dnd/spells/conjuration.py` | 20 |
| `dnd/spells/divination.py` | 5 |
| `dnd/spells/enchantment.py` | 19 |
| `dnd/spells/evocation.py` | 52 |
| `dnd/spells/ice_knife.py` | 1 |
| `dnd/spells/illusion.py` | 11 |
| `dnd/spells/infernal.py` | 2 |
| `dnd/spells/necromancy.py` | 14 |
| `dnd/spells/summoning.py` | 8 |
| `dnd/spells/transmutation.py` | 21 |
| `dnd/spells/wall_constructions.py` | 4 |
| `dnd/spells/wall_fields.py` | 2 |
| `dnd/spells/walls.py` | 1 |

Supporting module review also included catalog/content metadata, reaction costs,
shared hit effects and utilities, surfaces and wall helpers. Literal scan-call
counts and literal `EventHandler` construction counts were used as navigation,
not as counts of defects or a complete count of dynamically composed handlers.
