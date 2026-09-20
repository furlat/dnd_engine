# Graphics architecture review: timeline, reduction and ECS ownership

Date: 2026-09-20. Independent read-only ECS/anti-OOP review for the user's
graphics/data-portability audit. No runtime changes, tests or captures were made.
Read `RECOVERY_PLAN.md` and `HOW_TO_TEST.md`; followed the bug-fix reflection
guidance. Scope is event reduction, choreography, body/movement/attack/condition
timelines and equipment/rig binding. Scene masks, raster media, detailed anchor
schemas and importers have separate reviewers.

References below use current checkout paths and one-based source lines. `NC/`
means `/home/tommaso/Dev/NeuroClient/app/src/render/`. The original client is
evidence of intended timing and authored features, not an instruction to restore
its old queue classes, SDK integration or defensive machinery.

## Assessment

The core is a data-oriented presentation implementation: retained player facts
and authored records enter pure binding/sampling functions; Pygame drawing is a
separate consumer. Complete lineages and independently advancing latest/history
remain present. There is no spell-name executor in the reviewed choreography,
movement, attack or condition owners.

It is **not** accurate to say that all animation/reduction behavior lives in
NeuroStudio JSON, or that copying these JSON files into the old TypeScript client
would reproduce current playback. JSON supplies content, parameters and selected
semantic choices. Python supplies the event reducer, child scheduling, joins,
movement interruption semantics and body composition. The old client also had
procedural owners for those responsibilities. Its timeline editor did not remove
the need for `AttackClip`, `CastClip`, `TakeDamageClip`, `MoveClip` and the
subjective mapper.

The principal concrete shortfall is **partial execution of the retained schema**:
some records load successfully while their optional tracks are unimplemented.
Several are explicitly reported; voluntary movement's media/recovery fields are
silently unused. This needs an honest support boundary, not a new universal rule
interpreter or a campaign to move every constant into JSON.

## 1. Ownership that should be preserved

| Responsibility | Current source evidence | Meaning for portability/design |
| --- | --- | --- |
| Capture a complete native lineage | `game/presentation.py:782`: traverses terminal parent/children, retains their lineage and version identities, and captures admissions. | Transport units are complete causal roots, not independently queued damage/condition leaves. |
| Project native facts to player facts | `game/player_projection.py:445`, `:497`, `:535`: keeps parent/child topology even when `fact` is absent; returns permitted observations/world updates separately from private aggregates. | Presentation must keep opaque causal structure without acquiring undisclosed mechanics or foreign state. Do not replace this with renderer visibility guesses. |
| Portable input boundary | `game/player_facts.py:329`, `:389`, `:402`, `:413`; `game/player_reduction.py:204`: passive nodes, initialization, lineages and JSON serialization. | A future TS consumer can receive these recorded packets. UUIDs, enum values and the fact schema remain a transport contract. No live Entity is required by the reviewed samplers. |
| Latest state versus historical state | `game/encounter_play.py:142`, `:223`, `:236`, `:265`: receipt reduces `latest` immediately and appends the root; later the head binds from `historical` and receives its own elapsed time. | Engine/controller progression can advance while an earlier root animates or playback is paused. Human input currently waits for the visible boundary (`:162`), which is an application UX choice, not a backend timing requirement. |
| One reduction meaning | `game/player_reduction.py:66`, `:143`, `:175`: folds received after-values, senses, condition membership, gear and life state. | Event-type dispatch is ordinary reduction semantics. It does not need a JSON expression language. Visual timing determines *when* received values appear, not what the game outcome is. |
| Child choreography and joins | `game/choreography.py:188`, `:443`, `:476`, `:509`: visits the retained tree; chooses action contact/damage callbacks; joins child completion before authored recovery. | Nested attacks/spells/effects remain inside one root. A child's animation is not another pending root. The scheduling algorithm must accompany the authored data in any port. |
| Absolute-time playback | `game/choreography.py:549`, `:578`; `game/choreography.py:1084`: compiles state samples once, then selects time-dependent samples. | Seeking/rendering does not consume events or replay native handlers. Runtime timeline records contain data/state references and are not themselves a standalone exported wire format. |

The equivalent original leaf contracts are concrete: `NC/clips/AttackClip.ts:34`
dispatches children at hit/release and waits for delivery; `NC/clips/CastClip.ts:74`
starts delivery at the authored release and joins before recovery;
`NC/clips/TakeDamageClip.ts:34`, `:53`, `:68` schedule flash, HP/number and
conditions at separate body-frame callbacks. `NC/clipQueue.ts:491` executes
ordered groups and `:528` dispatches children within the current transaction.
Those are code semantics already present in NeuroClient, not newly invented
Python spell scripts.

## 2. What is actually reusable authoring data

| Area | Authored input and consumer | Boundary |
| --- | --- | --- |
| Weapon attack selection | `game/data/neuroclient/attack-profiles.json:2`; `game/attack.py:93` | Declared weapon identity, damage type, slot and result select highest-precedence variants. Dagger-critical overhead (`JSON:5`) and morningstar swing (`:14`) are explicit data. The shared selector does not test weapon names in Python. `sourceItemIds` is a small local extension; TS must accept it. |
| Attack body and contact | `game/attack.py:255`, `:260`, `:294` | Body clip/rate and frame anchors are authored; native damage/life after-values supply results. The runtime assigns semantic meaning to `release` versus `impact/contact/effect`. Arbitrary named markers are not arbitrary executable callbacks. |
| Walk/jump appearance and shape | `game/animation_types.py:755`; `game/choreography.py:811`, `:989` | Clips, step duration, jump duration formula parameters and arc-size parameters come from the imported context. Distance/height and whether steps committed come from retained facts. |
| Forced movement | `game/forced_movement.py:95`; `game/animation_types.py:733`, `:745` | Context authors easing/facing/scales; separate passive profile authors brace clip/frame/duration. Geometry and reached-cell facts remain native. The brace/slide/resume algorithm is shared code. |
| Equipment gesture | `game/animation_types.py:561`; `game/animation.py:278`; `game/combat.py:191` | The context authors body/rate/commit frame. Recorded gear and active set determine the loadout; unchanged visible layers add no gesture. |
| Fixed versus modular rigs | `game/animation_types.py:482`, `:491`; `game/combat.py:72`; `game/animation_data.py:65` | Identity-to-rig maps, sheet categories, row order, frame count, FPS and anchors are passive records. A packaged creature's gear is baked into its body. A modular actor composes real item layers from its received loadout. |
| Condition appearance | `game/condition_types.py:128`, `:143`; `game/condition_animation.py:53`, `:96` | Native membership UUIDs select recipes. Priority/exclusive groups, alpha/body color, feedback and transition duration are data; no renderer applies or removes gameplay conditions. |
| Actor-only actions and interaction contact | `game/body_action.py:42`, `:96`; `game/animation_data.py:287` | Original content-action schema, a shared local object-interaction recipe and passive action aliases select body, hidden slots, effect frame and feedback. Actor contact triggers received state presentation; it does not issue a second interaction command. |
| World transition timing | `game/world_animation.py:43`, `:64`, `:80` | Frame sequences, FPS and end-state frames are data. Runtime recognizes the existing `is_open`, `is_engaged`, `trap_state` fields; this is not a generic arbitrary-property animation interpreter. Lighting's state change is not presently a finite prop-transition channel here. |

The loader retains original context/condition/action documents and materialized
spell recipes (`game/animation_data.py:247`, `:256`, `:264`, `:377`). Local attack
and interaction revisions deliberately override their selected rows (`:284`,
`:290`); they do not replace native attack or interaction behavior.

One further portability boundary is easy to overlook: modular item visuals use
`AUTHORED_ITEM_VARIANT_CATEGORIES` from `dnd/items/authored_variant_inventory`
(`game/animation_data.py:17`, `:51`, `:108`). This is authored passive content,
not a live registry lookup or hidden inventory read, but it currently lives in
Python declarations rather than solely in the copied Studio bundle. A TS port
needs that resolved ledger exported or supplied by its existing equivalent.

## 3. Code-owned policies: distinguish intentional semantics from patches

### Preserved source semantics

- The OA lead fraction clamp `0.12..0.35`
  (`game/choreography.py:1001`) exactly follows `NC/clips/MoveClip.ts:55`.
  The authored `movementLeadInMs` and `walkStepDurationMs` remain inputs. Merely
  finding the clamp in Python does not establish a design defect.
- Postorder body/delivery/condition joins (`game/choreography.py:509`) implement
  the original child promises and recovery boundary, without copying the old
  async class infrastructure.
- Condition alpha easing and the immediate completion when alpha does not change
  (`game/condition_animation.py:129`, `:155`) follow
  `NC/clips/ConditionClip.ts:100`. A nonzero transition duration is not a generic
  pause to inject into every condition application.
- Gear's frame commit versus completed item identity
  (`game/choreography.py:615`) is an explicit timing policy. The original set
  marker is in `NC/clips/SwitchWeaponClip.ts:9`, `:38`; it does not mean that all
  equipment membership is authored by an animation.

### Recovery-specific semantics that a future port must carry explicitly

- Jump reactions now finish at launch, then one arc traverses the committed
  jump (`game/choreography.py:737`, `:749`, `:801`, `:814`). This is the user's
  correction to the old mid-air stop behavior, visible in
  `NC/clips/JumpClip.ts:95`, `:125`. Do not restore old behavior for parity.
- One jump body cycle is fitted to actual air time using the selected rig's
  frame count (`game/choreography.py:1145`). Old TS derives speed from
  `jumpBodyFrames/jumpSourceFps` (`NC/actionContextPresentation.ts:333`). Python
  still parses those two fields but deliberately does not use them for the new
  per-rig cycle. This semantic difference should be stated when exporting.
- An interrupted walk retains its presented sub-tile contact
  (`game/choreography.py:1055`) rather than snapping to the legal cell center.
  Original `NC/clips/MoveClip.ts:41`, `:75` restored that origin. Preserving the
  corrected rendering position is distinct from modifying native coordinates.
- Hidden transitions receive an authored single-step dwell without reconstructing
  hidden distance (`game/choreography.py:869`, `:955`, `:975`). That is a specific
  subjective-playback policy, not inferred travel and not a change to visibility.
- A missing fixed-rig ranged body uses Idle at the root rig's authored clock and
  reports missing media (`game/attack.py:245`). This is a disclosed coverage
  fallback; it is not evidence that the creature has a real ranged animation.
- Condition/HP/body overlays have explicit precedence in the sampler
  (`game/choreography.py:588`, `:607`, `:633`, `:639`, `:648`, `:657`). These loops
  are part of composition semantics. Data alone does not describe overlapping
  ownership. No regression was demonstrated here, so this is a porting note,
  not grounds to invent a new scheduler.

## 4. Concrete incomplete authored capabilities

### A. Loaded condition layers are not fully executed

`game/condition_animation.py:88` reports persistent strips, equipment modifiers
and rig appearance layers as unsupported; `:134` does the same for transition
effects. Alpha, body filtering, membership and badges do work.

This is more than a hypothetical schema feature. The shipped 141-row condition
document contains four nonempty weapon-coating equipment modifiers (concentration
fire, fire, lightning, timed fire at
`game/data/neuroclient/source/src/render/data/animation/conditionPresentation.json:74`,
`:152`, `:230`, `:308`) and Dragon Wings' appearance layer (`:1302`). Current
retained persistent-strip and transition-effect arrays are empty, so do not claim
those missing executors are presently dropping populated strips.

Original `NC/conditionPresentation.ts:354`, `:368` resolves equipment/appearance
layers; `NC/clips/ConditionClip.ts:35`, `:85` handles transition/persistent media.
Minimal next step, if selected: connect one existing weapon-coat modifier through
the same modular-layer composition using recorded membership, then retain its
generic slot/priority behavior. Do not add a switch for each coating or a new
condition framework.

### B. Voluntary-movement media/recovery are accepted but silently unused

`walkMedia`, `walkRecovery`, `jumpMedia`, `jumpRecovery` are typed at
`game/animation_types.py:759`, `:771`; a search of production Python finds no
consumer beyond their definitions. Walk/jump binding only builds travel and
reaction sequences (`game/choreography.py:795`, `:898`, `:1074`). In contrast,
NeuroClient maps those fields (`NC/subjectivePresentationMapper.ts:1093`) and
runs movement recovery (`NC/clips/MoveClip.ts:129`, `NC/clips/JumpClip.ts:72`).

Current imported values are empty media and disabled recovery. Therefore this is
an authoring-support gap, not evidence of a current lost animation. The smallest
immediate improvement would be to disclose unsupported nonempty/enabled values
at binding, consistent with the existing gap reporting, until this shared
capability is selected for implementation. Do not invent movement effects now.

### C. Actor-only delivery does not share the full casting/media path

`game/body_action.py:85` reports enabled caster VFX layers as unbound;
`:108` reports content-action strip media as unbound. The body/effect/recovery
and hidden-slot timing still play. The five current materialized actor-only
spell recipes do not enable caster overlays, so that limitation is currently
dormant for those spells. However, the shipped Greater Invisibility, Haste and
Healing potion action rows each do contain one actor media track
(`.../contentActionPresentationRecipes.json:546`, `:614`, `:682`).

Original `NC/clips/ActorActionClip.ts:31` preloads and attaches the action's VFX
while dispatching child effects at its frame. Minimal implementation when chosen:
reuse existing body/strip sampling in this owner, not a potion-specific effect
executor or a new recipe format. This is the relevant limitation for a claim
that every spell/action casting aura is already supported.

### D. Attack content support is narrower than its record shape

`game/attack.py:226` rejects an enabled profile with hidden slots or actor media;
`:230` accepts only enabled geometric `bolt` projectiles. `_attack_layers`
supports the slash slot only (`:148`). Original `NC/clips/AttackClip.ts:21`,
`:80` executes hidden slots and VFX. Current shared attack overrides have empty
hidden/media fields, and explicitly author a geometric bolt for ranged attacks
(`game/data/neuroclient/attack-profiles.json:68`), so the present bolt is authored
content, not a secretly substituted sprite.

The offhand row is explicitly one `Attack5` choice (`attack-profiles.json:23`);
damage-type/weapon-specific choices currently specialize main-hand only. That
is a coverage choice in data. It needs appropriate offhand source sheets and
authored rows if the user requests that detail, not Python weapon branches.

### E. Damage binding has a fixed cardinality limit

An attack can bind at most one directly owned applied-damage packet and one
life transition (`game/attack.py:284`). A spell application has the same shape
(`game/combat.py:153`). Independent spell applications and nested actions are
already kept separate; these checks must not be confused with missing volley
support.

The existing limit is a concrete expansion boundary: a future received
application with several direct damage packets will report/unbind presentation
rather than become fully represented by changing a recipe. This review did not
generate such a native example and does not claim that current galleries hit
the limit. If a selected game mechanic does, preserve each existing packet and
its ancestry at a shared contact; do not collapse gameplay data or introduce a
per-spell workaround.

### F. Healing and some context media remain bounded implementations

`game/choreography.py:389` reports healing body/media and nested HP-at-entry
timing as unbound. Equipment media raises at `game/animation.py:282`; reaction
body/media/recovery are rejected at `game/choreography.py:757`, `:999`; forced
movement media is rejected at `game/forced_movement.py:102`. These are explicitly
different from the silently ignored voluntary-movement fields. Their imported
context media are presently empty and optional reaction/recovery bodies disabled.
They should be listed as capability limits instead of silently counting all
loaded context data as implemented.

Other projectile restrictions remain plainly stated in `game/animation.py:791`
through `:820` (duplicate-slot semantics, tangent direction, palette swap,
equipment selection and death media). The schema/importer reviewer owns their
detailed comparison; this report does not imply all these modes are selected
or that every guard merits removal.

## 5. Minimal next steps from this review

1. Describe portability as **shared passive content plus shared execution
   semantics**, with the actual support subset above. A new TypeScript adapter
   needs the packet reducer and scheduling semantics, updated local fields and
   the resolved item visual ledger. Copying JSON alone is insufficient.
2. Prefer the already-authored, populated gaps for the next selected feature:
   weapon-coat appearance and potion/action strips. Each can extend an existing
   owner. Keep empty dormant features deferred rather than demanding a full
   schema implementation before gameplay continues.
3. Make the unsupported voluntary-movement fields visible to authoring/review
   instead of accepting edits that do nothing. This can use existing binding-gap
   reporting; it does not need startup filesystem audits or asset hashing.
4. When implementing a selected gap, prove the observable contract from recorded
   player inputs: effect/contact timing, body/equipment appearance before and
   after, complete nested lineage playback, unchanged latest state while seeking,
   and relevant rigs/camera views. No new tests or captures were run for this
   read-only audit.
5. Keep the user-corrected jump/OA/sub-tile behavior when porting. Reuse the old
   authored vocabulary and semantics that still fit; do not undo explicit
   corrections merely to resemble old source code.

No additional engine handler, polymorphic animation manager, generic rule
interpreter or transaction framework is indicated by these findings. The
existing data/functions split is suitable for completing the missing shared
capabilities, provided loaded records are not mistaken for implemented ones.
