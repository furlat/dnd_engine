# Summon control handoff — schema 18

Implementation: `feature/rules-checking`, working tree based on `9ead58f825cc`.
The original ownership implementation and its agent match are complete; their
historical regression and timing limits are recorded in the
[implementation plan](plans/SUMMON_CONTROLLER_OWNERSHIP_PLAN_2026-10-22.md).
The schema-18 caster-defeat correction is implemented, with regressions and source
review passed and a separate live match completed. Direct live caster-defeat
dismissal was not exercised because all summons departed earlier; native and
real-worker tests prove that boundary with living bodies.

**Caster-defeat correction:** all eight summon families now depart when their
original caster becomes DYING/STABLE at zero HP or DEAD, regardless of
concentration. This includes a previously released hostile Fey. Another caster
sharing the same seat keeps its own summons. Healing does not restore retired
bodies. Positive-HP sleep, stun and paralysis add no new universal dismissal.
The [cleanup plan](plans/SUMMON_CASTER_DEFEAT_CLEANUP_PLAN_2026-10-22.md) records
the implementation and acceptance. Earlier recordings of a weapon surviving its
downed caster remain defect evidence; their ownership and transport evidence
remains historical.

## Client behavior

All eight summon families follow the caster's controller. Human and Codex summons
use the ordinary choices, preview, command and end-turn APIs. Native AI casters
retain independently owned native AI summons. The backend does not auto-play an
externally controlled summon while waiting for input.

Live acceptance also exposed a pre-existing Spiritual Weapon content error: its
20-foot flying Move had no usable speed grant. The backend now composes the
existing `InnateFlight` condition, as other flying summon bodies do. Human/Codex
worker tests prove normal Move choices, preview, five-foot debit and next-turn
reset, followed by caster-defeat cleanup. No new movement API or client workaround
is needed. The recorded live duel started before this correction.

Use the latest `boundary.input_actor_uuid` and current audience membership. Both
`waiting_for_human` and `waiting_for_codex` are external input boundaries; an
unowned turn has no input actor for that seat. Bootstrap/reattachment now returns
current membership, including living summons, rather than the startup roster.
Do not rebuild a separate encounter or attach a second player seat for a summon.

Natural combat completion is `outside_encounter` with an `encounter_end` fact;
`terminal` is the separate whole-game boundary. The live duel exposed an older
completion bug with a stable, zero-HP opponent. The human authorized ending combat
when a side has no conscious combatants, and that rule is now implemented. A
conscious surviving ally still keeps its side fighting. A defeated caster's own
summons now leave before that outcome is evaluated. Stunned and paralyzed
actors remain conscious for this check. Ending combat does not kill, stabilize
or heal downed actors; death saves continue while a conscious ally keeps the side
fighting. The first recorded match remains explicitly incomplete.

## Ordered membership

Player schema is **18**, protocol version remains **1**. Both generated SDKs and
schema files are updated. Schema digest:
`8eb07a2f102b0549f83fc6556b65359a3f061bcb5d71b1a1aa39973ba5c8867f`.

The existing `SpatialFact.terminal_cause` enum adds `caster_defeated`. A summon
already retired by concentration loss still reports its existing `sustain_lost`
cause. Update the schema/SDK identity and finite enum; the membership and sensory
message shapes remain unchanged. Consume the backend's departure and revocation
facts; do not implement a second client-side caster-HP dismissal rule.

A committed transition emits a normal player node with:

```json
{"kind":"audience","audience":{"controlled":["actor UUIDs"],"observers":["observer UUIDs"],"revision":1}}
```

`controlled` and `observers` are complete ordered after-values. Revision increases
once per real membership change. Apply this fact at its occurrence, before any
BodyRecord at that same occurrence and before later facts. Ordinary occurrences
retain their existing body-before-node ordering. The stable stream observer UUID
does not change. The backend reference reducer implements this order.

An AudienceFact may also contain `sensory`, using the existing SensoryFact fields
and the enclosing group's shared sensory rows. For that node: apply membership
and remap cached observer bits, apply the world update, then fold nested sensory
changes. Private body details at the same occurrence follow the membership node.
Do not apply an operation's final audience to its earlier facts.

On observer tuple changes, remap all retained object/contact/effect member bits by
UUID from the old tuple to the new tuple. Append new observers and remove departed
ones; no permanent tombstone slots. A shared table has explicit member columns
whenever any consuming segment has multiple observers, even if the final audience
contains only one observer. Interpret each row under membership at its consuming
fact. One→two→one within the same group is covered by recorded replay tests.

The owning seat gains a summon observer only if it already observes the actual
caster. A control-only caster remains control-only. Another seat observing that
caster does not acquire the summon. Mechanical targeting still uses each actor's
own native senses.

## Summon Dragon color choice

The human subsequently requested one color choice instead of independently
choosing Breath damage and caster resistance. Current choices now expose exactly
five rows using the ordinary `form` facet:

| `form` value | Public birth name | Breath and caster resistance |
| --- | --- | --- |
| `black` | Black Draconic Spirit | Acid |
| `blue` | Blue Draconic Spirit | Lightning |
| `green` | Green Draconic Spirit | Poison |
| `red` | Red Draconic Spirit | Fire |
| `white` | White Draconic Spirit | Cold |

Consume ordinary discovered rows; do not offer the old `damage_type` and
`resistance` selectors or the old `draconic_spirit` form value. That identifier
remains the one canonical creature content identity shared by every color. Native
creation recipes record `dragon_color`; public birth names identify the color,
and the existing cadence/resistance condition states publish the resulting damage
type to both entitled seats. Recipe parameters themselves are not a new public
field. The color change itself added no protocol fields. Existing body scaling, five
innate resistances, free Breath cadence and resistance removal with the summon
remain covered; this change adds no new creature artwork or renderer binding.

## Revocation and retained knowledge

Fey losing control while its caster remains alive changes allegiance and gets
native AI authority. Caster defeat instead retires it, without a transient hostile
handoff. A prevented death still completes the ordinary handoff if concentration
was actually lost.
A surviving released Fey retains its UUID, HP, items, turn identity and spent
resources. Revocation
arrives even if the former owner cannot see the body. Dismissal, defeat and expiry
also revoke control before sensory detachment. Borrowed player controllers are
never closed by a summon's teardown.

Remove revoked actors from active private sheets and inventory/control affordances;
preserve legitimately received historical facts and exploration memory. Loss of
control is not evidence of death. Stop consuming future private observations and
private field-clock ticks for the released actor. Other observers continue to
contribute their actual contacts and visibility.

## Reproducible transport evidence

[Receipt](audits/SUMMON_CONTROL_RECORDING_2026-10-22/receipt.json) and
[validation](audits/SUMMON_CONTROL_RECORDING_2026-10-22/validation.json) describe a
real Human cast → Wolf grant → movement → bite → end turn → concentration drop →
retirement journey. Both seats' initialization, 14 records each and detached
reference final states are saved beside the receipt. Python and TypeScript SDKs
validated all 28 records; backend decoded replay matches the saved final states.
Separate real HTTP tests cover both Human and Codex, unauthorized commands,
ordered SSE delivery, catch-up and current bootstrap/reattachment membership.

The SDKs remain transport/validation libraries. Consumer game-state folding belongs
to the client; the backend reducer is the reference. Monty's bounded consumer now
folds current membership and recognizes Codex input. No NDClientGodot files or
another chat were changed or messaged by this work.

The first [Monty duel audit](audits/MONTY_SUMMONERS_2026-10-22/validation.json)
preserves 228 exact records and 77 committed commands. Both SDKs decode them and
both seats independently reduce successfully. It proves summon commands, control
removal, a surviving weapon acting after its caster falls, and Amber's explicit
same-seat reconnect. It does **not** prove natural encounter completion: the
stable-opponent defect prevented that. Monty's reconnect helper now uses an
explicit matching attachment epoch through the existing server API; its ordinary
default still refuses takeover of an attached seat.

The [earlier schema-17 completed duel](audits/MONTY_SUMMONERS_2026-10-22_VERIFIED/README.md)
ended naturally with Blue winning. Each independent Sol agent controlled both a
Wolf and Spiritual Weapon. All 66 committed commands matched their public packets
and current authority; one invalid selection was rejected and corrected. Both
SDKs decoded all 192 exact records and both seats passed detached reference replay.
In that historical run, Amber's caster fell at sequence 86, its weapon still attacked at 92, and Blue
defeated that last conscious weapon at 95. Both seats then received
`encounter_end` and `outside_encounter`, with Amber's caster still dying.
No separate live PlayerState oracle was recorded, so this archive does not claim
live/replay equality. This duel exercises Wolves and Spiritual Weapons; dragon
colors and the final neutral-condition implementation are qualified by the
focused tests below. Its weapon-survival behavior is superseded by the schema-18
caster-defeat correction.

## Validation and measured cost

The [fresh schema-18 duel](audits/MONTY_SUMMONERS_2026-10-22_CASTER_DEFEAT/README.md)
ended naturally in round 16 with Amber at 28 HP and Blue DYING at zero HP. Both
seats received encounter end and `outside_encounter` at sequence 210. Both SDKs
decoded 422 exact packets; reference replay and all 145 committed-command checks
passed. Both agents cast and attacked with summons and reattached their own seats.
All Wolves and Weapons departed before the final blow, so this live run does
**not** directly demonstrate caster-defeat dismissal. Native/worker regressions
provide that proof. The archive also predates the final group-scope and flight
repairs, independently qualified below.

The combined engine, AI and player/server run before the color simplification
and final neutral-condition correction
passed **5,497 tests**, with
20 expected failures and one warning. Python SDK passed 110, TypeScript SDK 83,
and Monty 22. Scoped typing still has five diagnostics on unchanged lines in
`facts.py`/`projection.py`; it is not claimed clean.

The [timing report](audits/SUMMON_CONTROL_TIMINGS_2026-10-22.md) retains the
baseline, ownership implementation measurements and matched comparison. Crowded Fireball's
initial slowdown did not reproduce: current medians 38.18/39.55 ms versus the
last matched baseline's 39.73 ms, with identical work and packet size. Ordinary
movement remains uncertain by 0.60–0.90 ms against that last baseline amid host
drift; no blanket zero-overhead claim is made. Actual summon input handoff was
5.04–5.63 ms median in the earlier quiet run, and 7.10–9.07 ms under later host
load, with a maximum 14.06 ms including intervening collection. Fey release has
a real additional cost to create its hostile AI. These are worker measurements,
excluding transport, rendering and agent reasoning.

After the color simplification, the focused native summon, lifecycle, ownership,
regression, player transport and two-seat condition-publication batch passed
**276 tests with one expected failure**. All five colors, level-5-to-9 scaling,
actual Breath use and exact resistance cleanup remain covered. The existing
timing artifacts predate this last selector change; the harness now selects the
red form, and no new measured speedup is claimed. The human explicitly closed
further investigation of tiny timing differences on the busy host.

The final encounter/life-state/condition-transform, architecture, catalog and
protocol batch passed **111 tests**. It corrected two earlier architecture
failures: combat completion now reads a neutral condition flag instead of concrete
condition names, and the encounter source follows its comment policy. Renamed
conditions are covered. The retained initial failure log is separate from the
successful full gameplay run and corrected final batch.

For the caster-defeat follow-up, the [cleanup audit](audits/SUMMON_CASTER_DEFEAT_2026-10-22/README.md)
records **5,542 passing engine/AI/player tests**, 20 expected failures and one
existing warning. The subsequent simultaneous-caster settlement correction has
its own **176 passing** summon/encounter tests; grouped instant-death Fey also
passes an explicit regression. Python and TypeScript SDK suites passed 110 and
83 tests. Real worker/HTTP tests cover both Human and Codex, two casters sharing
a seat, stale-command refusal and current bootstrap/catch-up/reattachment.

The [defeat timing comparison](audits/SUMMON_CASTER_DEFEAT_2026-10-22/timings.md)
measured ordinary damage at **9.62 → 9.62 ms** median, caster defeat with Weapon
at **11.05 → 17.16 ms**, and Weapon+Wolf at **18.85 → 23.74 ms**. Added work is
required retirement and encounter end; the maximum measured command plus encoding
was **24.63 ms** across the three-sample cases. No transport/rendering or large
summon-population latency guarantee is claimed.

The final weapon-flight correction passed **322 native/player/content/architecture
tests** (one expected failure) and **3 worker/HTTP tests**. One timing capture on
the final group/flight code measured **10.15 ms** ordinary damage, **16.52 ms**
Weapon defeat and **25.00 ms** Weapon+Wolf defeat, maximum **25.55 ms**. This
includes the flight condition's cleanup; it does not measure casting or movement.
Raw results and method are retained in the same defeat timing report.
