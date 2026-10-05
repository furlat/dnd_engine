# Concrete schema-fit review: actions, attacks, movement and combat

2026-10-05. Independent anti-slop prerequisite review of the approved full-presentation plan. Source base HEAD `092e9daedaa7e0c65a54632b7085ab60ade642ca`; working files may contain subsequent parent implementation. No production edits and no new visual acceptance claimed.

## Disposition

**Approve adding evidence instrumentation and typed annotations to the existing owners. Do not approve replacing these owners with a generic cue execution engine.** The concrete examples below fit the plan's family-preserving direction. They expose specific requirements for provenance and timing which must be in the actual implementation; merely naming `start/contact/end` does not satisfy them.

Six exact historical bound-record excerpts are retained in [schema-fit-antislop-examples.json](schema-fit-antislop-examples.json). Each includes the original trace path, SHA256, recorded source revision, head index and UUID. These are concrete schema-fit witnesses, **not current runtime or pixel acceptance**. Older equipment and attack recordings predate later artwork/scale changes. Full original traces remain unchanged. Excerpts omit bulky recipes, particles and descendant lists; they must not be treated as a new serialization format.

## 1. Ranged attack: declaration, release, contact and consequence differ

Witness: `ranged-hit`, recorded at `f04f84906845d7d2d67e2eb5de615dab0224dc22`, head `ab729cbc-4b05-465d-b853-a8d13412f3ac`.

Actual values:

- `AttackFact.behavior_id=action.attack`, `weapon_slot=RANGED_MAIN`, `source_item_id=weapon.shortbow`, `source_item_uuid=4142c269-a619-441f-a0cf-d23e7d5de7c7`, `target_kind=creature`, `attack_source_kind=equipped`.
- `AttackTimeline.profile_id=ranged`, `clip=Attack3`, `release_ms=833.3333333333334`, `contact_ms=1100.9209593551657`, `body_end_ms=1166.6666666666667`, `complete_ms=2267.5876260218324`.
- Applied packet `428c271c-200c-4a50-b4e3-1269c89342fa` records 4 Piercing damage, resulting HP 6, and a resolution reference to attack lineage `0309249d-df52-4924-af93-6a24a63e5ffd`.
- `DamageTiming.hp_ms` equals contact here; this is a resolved value, not permission to collapse all damage timing fields globally.

Existing owners: `game/player_facts.py:96`, `game/attack.py:93`, `game/attack.py:310`, `game/animation.py:1088`.

Concrete representation: retain the attack's root event identity, declared item/slot/source kind and selected profile. Reference release/contact/body completion and the exact applied result packet separately. Graphic sampling uses the existing projectile sampler; narration of “hits for 4” is attached to applied outcome, not the attack's release or a roll request. A miss still has release/travel but no positive result. Object targets use `ObjectContact`, not an actor contact with fabricated HP/body fields.

The current timeline stores `results`, but does not copy every declaration selector. A presentation export must either retain a reference to the exact public node or explicitly project those selected fields. It must not consult the actor's later active loadout. `select_attack_profile` already owns profile precedence; no second semantic/profile registry is needed.

## 2. Body action: a meaningful action can have zero duration

Witness: `pending-retreat-dash`, head 8, UUID `9d785229-30a2-4234-91d0-de52cc4cf9c1`.

Actual cue: `recipe_id=action.spell.expeditious_retreat.dash`, `clip=Idle`, `enabled=false`, all six dates (`start/effect/body_end/join/complete`, with start) 0, empty cast layers, disabled recovery. Composition still has a state commit at 0 and a condition cue.

Existing owners: `game/body_action.py:33`, `game/body_action.py:99`, `game/body_action.py:239`.

Concrete representation: action evidence plus a disabled graphical body payload and instantaneous semantic/state milestone. Do not drop an action because `duration==0`, `enabled==false`, or the body sampler returns `None`. A head-start occurrence must be admitted once when the head enters playback, including an all-zero-duration head. Cursor `(previous,current]` alone cannot discover it if previous and current are both 0; admission/initial-boundary policy must explicitly handle this.

The related Fly witness (head `733a7aee-f185-4875-9ccb-45a7fdaa45b7`) has `effect_ms=916.6666666666666`, `body_end_ms=1166.6666666666667`, `join_ms=1816.6666666666665`. This proves body end and joining children are not synonyms. Hidden-slot restoration follows `join_ms`; active cast layers follow body duration. Keep the existing selected `body_context`, `recovery_body`, and `cast_layers`; do not create a second body-action runtime program.

Effective-handler and condition-triggered action selection is already represented by `BodyActionSubject` and `PlayerNode.content_attributions`. A semantic record must retain attribution evidence for these paths rather than infer a new action from the chosen animation.

## 3. Equipment: stance commit is not membership completion

Witness: `item-dagger-transfer-melee-main`, head 12, UUID `d9971f2a-2771-4bc6-aba9-bdf874a6bbd0`.

Actual values: `EquipmentTimeline.commit_ms=111.11111111111111`, `complete_ms=388.8888888888889`; original recipe Taunt, speed 3, commit frame 4. Replacement layers retain item `b6916386-1fd9-4f91-9be8-38d900e141f0` and coating effect `e3d5f3e5-5889-4ceb-94d8-99f177389cbb`, contribution `799327de-8de5-4b5b-9104-fed2f5d94f52`, applied source cursor 33.

Existing owners: `game/animation.py:277`, `game/combat.py:83`, `game/choreography.py` equipment branch and sample composition.

Concrete representation: exact equipment event, existing timeline anchors, replacement appearance reference and item-owned modifier identities. Keep appearance commit and authoritative equipment/membership completion distinct. Narration must distinguish switching stance, taking an item and equipping it using the original action/equipment facts; a changed sprite layer does not prove a pickup. The coating follows the same item UUID across owner changes; it is not recreated on the recipient or given a new elapsed age.

The raw bound record includes `AnimationData` through runtime objects. That object is not a portable payload. Export selected logical content references and existing typed values, not serialized caches or the entire animation catalog per cue.

## 4. Movement with nested consequences has several clocks

Witness: `damage-resolution-walk`, head `4fd133a7-e6bc-4adc-97e9-ecbcbc352448`.

Actual legs:

1. `[4,3]→[5,3]`, start 0, end 416.6666666666667, body start 0.
2. `[5,3]→[6,3]`, start 1583.3333333333335, end 2000.0000000000002, body start 1166.6666666666667.

Between these, a `MotionReaction` holds `[5,3]` at 416.6666666666667 through 1583.3333333333335. Its nested choreography has local duration 1166.6666666666667. Total motion completion is 3166.666666666667 after the second nested consequence.

Existing owners: `MotionLeg`, `MotionReaction`, `MotionTimeline` at `game/choreography.py:1972`; `walk_bound_timelines` at 2060; `bind_motion` at 2296.

Concrete representation: keep each leg's received geometry, independent body age, and the nested choreography owner with its absolute offset. For the first nested damage, its local HP time 0 corresponds to motion time 416.6666666666667, plus the enclosing presentation start. Do not flatten a hold into a zero-speed “path segment” or make a second displacement from the nested group's state change. `group.movements` explicitly prevents that duplicate travel already.

Flight/connector fields (`lift_phase_edges`, `passage_socket`, `passage_scale`, `support_riser`, curve fractions) remain passive parameters of the existing motion sampler. A hidden interval has no invented geometry; state-only observation and reacquisition need independent representation. `TimelineVisit.offset_ms` composes nested coordinates, but the root event/version reference must travel with it because `MotionTimeline` itself has no root UUID field.

## 5. Damage: native result owns outcome, not its visual parent

In the movement witness, the first `DamageCue.event_uuid` is `fd9a76dd-8c7b-44bb-bf66-8d4667b0a452`; its retained result UUID is `c09d5e93-227d-4e4b-952b-beede69a6a63`. The result records 2 Piercing damage and normal HP 18. Local timing is start/HP/number/flash 0 and end 1166.6666666666667.

Existing owners: `game/damage.py:19`, `game/damage.py:39`, `game/player_reduction.py` causal indices.

Concrete representation: request evidence, exact applied packets and life edges remain distinct. `bind_damage` deliberately filters direct results by native parent lineage and resolution membership, excluding nested hits. A global `(target,time)` matching rule would wrongly merge nested damage or duplicate narration when an attack/cast already owns that packet. Life edges are tracked in `owned_life_events`; preserve one presentation owner without losing the underlying factual edge.

When no source is disclosed, semantic text can say the target takes damage. It cannot invent an attacker from animation proximity. Zero outcomes and unsuccessful/blocked effects must have a factual disposition even if `bind_damage` returns no graphic cue. `DamageRequestFact` is not proof that damage occurred.

## 6. Spell A/B/A: application identity cannot be target identity

Witness: `missile-repeated`, head `cfa6b015-4e41-4fd0-b78e-bdc729266f4f`.

The three application IDs and travel/contact dates are:

| Application | Travel ms | Contact/effect/vitals ms |
|---|---:|---:|
| `25215c61-e12f-5cdb-ad92-fde160ebb726` | 583.3333333333334 | 733.3333333333334 |
| `a2250015-541e-5253-b95d-9701acd4774f` | 663.3333333333334 | 813.3333333333334 |
| `f376277c-1665-5ffb-a41c-a8ec1117ff83` | 743.3333333333334 | 893.3333333333334 |

First application resolution reference: kind `application`, lineage `34e62167-7ec6-489b-ad5c-6d45e46bb617`, first application UUID above. The first resulting packet deals 5 Force damage and leaves 75 HP. The third application targets the first recipient again; this is a separate contact/outcome. Cast release is 583.3333333333334, body end 1166.6666666666667 and complete/recovery start 2060.

Existing owners: `CastApplication`, `ApplicationTimeline`, `CastTimeline` at `game/animation.py:98`; `game/combat.py:166` binding; `game/player_facts.py:124` membership.

Concrete representation: occurrence identity includes exact native application membership and phase; sequence order is retained. Each target contact preserves its received elevation and scale. Geometry/curvature stays in the established sampler. Neither target UUID nor spell ID is sufficient as a milestone owner. The second cast in this recording has a separate native root; do not merge matching recipes/participants across casts.

Area delivery needs a separate ground contact, and `resolved_area_positions=None` differs from `()`. It is disclosure evidence, not a physical clipping mask. This remains a family distinction inside the existing cast representation rather than a new area executor.

## Required instrumentation and acceptance checks

1. Every emitted bound-family row needs its native evidence identity and **time coordinate owner**. Head/root UUID alone cannot identify nested applications or movement consequences.
2. Trace state commits with their producing native edge/version and owning milestone, not just `state_times_ms`. Atomic state updates stay atomic.
3. Export all body-action, equipment, movement, damage, cast/result records even when graphical duration is zero; distinguish absent graphics from absent facts.
4. Preserve native edge/application dedup identity independent of the group through which the edge is reached. Do not globally dedup repeated actual applications.
5. Select references to existing authored profiles/body contexts; keep family samplers. Shared annotations may expose timing relations without duplicating playback state.
6. Current rebinds must verify before/at/after release, contact, commit, completion and join for these witnesses. Historical numbers above are provenance, not permanently expected constants after a deliberate authoring change.
7. Portable serialization must omit runtime `AnimationData`, cached surfaces and Pygame resources. Fresh-process headless import proof remains required separately.

No new gameplay handler, spell-specific runtime branch or parallel event queue is needed for these examples. The chief design risk is introducing such a system to flatten differences that the existing passive records already represent correctly. The chief evidence gap is incomplete provenance for commits and nested bound records; the parent's instrumentation lane is the appropriate first repair.
