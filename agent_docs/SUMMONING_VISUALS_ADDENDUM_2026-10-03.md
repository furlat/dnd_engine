# Summoning batch — visual gaps and action-mapping addendum

Date: 2026-10-03. Companion evidence/acceptance ledger to the
[sole implementation plan](SUMMONING_BACKEND_PLAN_2026-10-03.md), especially
section 10.2. No production or artwork changes are made by this document.

**The human delivers any later VFX brief personally. No message, handoff or
production request to the VFX thread is authorized.** The list below is scoped
to the selected 24 creatures and three summoning spells. It does not reopen the
rest of the roster, deferred abilities or the withdrawn arena request.

## Status vocabulary

- **Existing binding:** registered source/recipe data exists. This is not a new
  visual acceptance claim for all 24 body sizes or animation contexts.
- **Source available / binding pending:** an inspected strip or archive inventory
  exists; final semantic assignment, registration and timing still need work.
- **Current integration work:** belongs to the unified implementation plan;
  requires authored data or the bounded shared renderer extension, not new art.
- **Later VFX:** no selected production binding for this new summoning use was
  found in the current game/data catalogue. Existing artist exports may be
  reusable; this is not a claim that no original artwork exists anywhere.

## A. Later VFX list for the human to deliver

Prefer a small shared family of effects with explicit material/palette variants,
not 24 creature-specific programs. Final visual design and production approval
remain with the human and artist. These are presentation requirements, not new
native mechanics or gameplay conditions.

| ID | Missing or deferred visualization | Scope and source fact | Later deliverable / constraints |
| --- | --- | --- | --- |
| V1 | Summoning cast cue | Three cast identities: Animals, Fey, authored Fiend. Ordinary caster body gesture and a conjuration accent. | Inspect/reuse existing casting art first; bind the chosen cue to the actual SpellFact/cast lineage and existing cast-release marker. Do not give summoned beasts spellcasting because their source pack has a gesture. |
| V2 | Creature arrival / manifestation | One actual EntityCreatedEvent with recorded SummonOrigin; the destination actor is a normal creature. | A shared arrival effect with animal/spirit/fiend material variants where warranted, supporting the actual body bounds and ground pivot. Author the body-reveal milestone, front/back layers and duration. A failed cast has no birth effect. |
| V3 | Despawn / dissolution | Actual terminal departure after dismissal, expiry, required existence-sustain loss or defeat. | Reusable finite departure effect. A disappearance is not automatically a death animation or corpse. Preserve the departure's observed last body/position and typed cause; optional defeat accent can reuse damage media. Visibility/contact loss and application shutdown/reset must not replay it as a magical exit. |
| V4 | Optional Fey halo | All 18 spirit bodies; the current batch already requires palette replacement plus alpha. | Optional shared subtle halo layered around existing bodies. Blue/translucent body material is current integration work, not blocked on this effect. No new blue sprite exports, multiply tint or creature-specific halo renderer. |
| V5 | Optional Fey control-break cue | Exact control loss -> recorded faction change while the same Summoned creature survives. | One brief reusable release/bond-break accent. Keep body, spirit appearance, HP and lifetime; do not despawn/recreate it or invent a permanent “hostile aura” condition. Ordinary faction feedback remains sufficient until this accent is delivered. |

V1–V3 are the core later summon presentation coverage. V4–V5 are optional polish,
not prerequisites to making the batch usable. The list is not permission to start
production, contact another thread or replace existing accepted artwork.

Future binding must consume the same retained typed facts as live/history playback.
Arrival/despawn media adds no duplicate SummonCreated/Despawned state events.
Causal milestones must order reveal, first action, damage feedback and departure;
no matching by creature name/time proximity and no VFX timer controlling backend
existence. Hidden births/departures stay hidden. Seeking and reacquiring an already
present creature must not replay its original summon effect. A silent engine
reset remains silent; lifecycle cleanup alone is not permission for visible VFX.

A later handoff needs, for each accepted asset: source manifest/provenance, exact
frames/FPS/phase lengths, pivot/crop registration, body-reveal/contact/release
markers, four-camera or documented billboard orientation policy, supported body
sizes, alpha/material behavior, shadow/depth/front-back policy and whether any
effect is baked into the source. No coordinate or ownership companion is discarded
if the selected rendering path needs it. Use existing atlas/media registration;
originals remain separate from installed production assets.

## B. Conditions, traits and effects that must not become duplicate VFX projects

| Gameplay state/effect | Current evidence | Work for this batch |
| --- | --- | --- |
| Summoned existence | New backend condition in the plan; no current summoned recipe binding found. | Current: actor presence plus retained origin. Later: V2/V3. Do not add a perpetual aura merely because this is a condition. |
| Fey spirit manifestation | Shared condition/material renderer already supports palette ramps and alpha; this manifestation assignment is new. | Current: typed retained manifestation -> shared body material; unchanged on hostility. Optional V4 later. |
| SummonControl | New untimed Fey-only authority condition. | No mandatory persistent visual. Current recorded allegiance; optional V5 on actual loss. |
| Concentration | Existing concentration/effect ownership. | Reuse existing feedback. No caster-to-summon rope or second timer visualization is needed. |
| Prone from bite/claw/gore/ram/trunk | condition.prone already has fall/hold/reverse-stand presentation using Die. | Current: per-rig adequacy check and body-context mapping. A death strip with explosion, gore/disappearance or no living rest pose is not automatically usable for Prone. No “wolf prone”, “gore prone” etc. conditions or effects. |
| Frightened from Dread blood | condition.frightened has control.frightened front/back application/hold media. | Reuse the existing condition recipe and forced-movement presentation where the actual result requests movement; fit around small/large bodies and preserve causal timing. No new fear spell or per-demon condition. |
| Corrosive and Dread blood | Existing native body responses, residue bindings and world/media recipes. | Reuse existing blood/acid/dread release and affected-ground presentation; verify actual wounds and terrain contacts, not a new aura attached to the summon. Residues survive or expire by their own native rules. |
| Bite/claw/tail/gore damage | Existing AttackFact, TakeDamage, damage feedback/body-response presentation. | Current: correct natural-attack profile/contact and source layers. Baked claw graphics must not receive duplicate human sword slashes. New standalone hit accents are not required unless inspection finds a specific unavoidable gap. |
| Pack Tactics, senses, natural armor, Devil's Sight, Magic Resistance, magical body attacks | Existing passive mechanics / normal attack or save results. | No automatic custom looping effect. Use ordinary outcomes; magical damage capability does not require glowing claws. |
| Ground-to-ground flight for Fellwing/Huntsman | Native movement facts carry movement_mode; no Fly-named clip in the inspected Demon Beast 4/5 inventories. | Current mapping blocker: inspect wing poses/travel strips and author an adequate existing motion or explicitly report missing body art. Generic magical-flight particles do not fix an inadequate wing/body animation. This is not a commission for new body sheets. |
| Other received conditions (e.g. poison, paralysis, invisibility) | Existing shared condition system. | Validate applicable shared body/material/context behavior for these rigs; do not duplicate the conditions per species. Catalogue coverage is not evidence that every body pose is already compatible. |

## C. What action mapping exists now

The existing renderer separates:

`recorded action/condition + retained actor content identity -> authored recipe
and rig -> semantic clip/timing -> existing sheets/layers -> shared sampler`.

Production currently binds Grey Wolf and Demon Beast 1/2/3. It does **not** have
production bindings for the other twenty selected bodies. Previous artwork work
inspected primary strips and inventoried other clips; it did not complete every
attack/condition/movement mapping. This addendum does not relabel that evidence
as finished integration. Intrinsic body weapons use the ordinary item-backed
Attack route and currently retain source kind equipped plus their item UUID/ID;
this differs from the separate NaturalAttack representation's natural source
kind. The presentation matches actual recorded facts, never reclassifies them
to fit a clip selector.

Existing Grey Wolf has Idle/Run/TakeDamage/Die, Attack1, Attack2 and the semantic
Attack6 alias to source Attack1. Existing demons have equivalent rest/travel/hit/
death plus Rolling -> Roll 1, Attack1 -> Attack 1, Attack2 -> Attack 2,
Attack5 -> Attack 3 and Attack6 -> Attack 1. Human-derived profile selection and
contact anchors still require the deliberate body-attack mapping specified
in main-plan section 10.2.1; merely loading those aliases does not establish it.

### All 24 attack rows and remaining work

“Inspected primary” means the previous source study chose and viewed that strip,
not that all contact frames or secondary motions have been calibrated. Every
row still requires the final miss/hit/critical, primary/secondary, opportunity
attack and Multiattack-child checks. A critical need not use a different motion;
it must never choose an unrelated movement because of an automatic human profile.

| Creature | Native body attacks to map | Existing source evidence | Remaining binding work |
| --- | --- | --- | --- |
| Wolf | Bite | Installed Attack1 bite and Attack2 variant; source study also chose Attack2 | Reconcile deliberate hit/critical choices and contact timing; retain exact Wolf identity |
| Hound | Bite | Shepherd Dog, inspected Attack2; four attack strips in inventory | New rig, explicit Bite profile and markers |
| Boar | Tusk | Boar, inspected Attack2 | New rig/profile/markers |
| Stag | Ram | Stag, inspected Attack1 | New rig/profile/markers |
| Jaguar | Claw, Bite | Jaguar, inspected Attack2; Attack1–3 available | Inspect/select the second anatomical action, then both profiles |
| Bison | Ram | Bison, inspected Attack3 | New rig/profile/markers |
| Ostrich | Beak | Ostrich, inspected Attack1 | New rig/profile/markers |
| Brown Bear | Claws, Bite; Multiattack children | Brown Bear, inspected Attack2; Attack1–3 available | Select/calibrate both body attacks and their child ordering |
| Lion | Claws, Bite | Lion, inspected Attack2; Attack1–3 available | Select/calibrate both body attacks |
| Tiger | Claws, Bite | Tiger, inspected Attack2; Attack1–3 available | Select/calibrate both body attacks |
| Polar Bear | Claws, Bite; Multiattack children | Polar Bear, inspected Attack2; Attack1–3 available | Select/calibrate both attacks and child ordering |
| Rhinoceros | Gore | Rhino, inspected Attack2 | New rig/profile/markers |
| Blue Raptor | Claws, Bite | Raptor Attack1 inspected; Raptor Attack1–4 available | Select/calibrate both actions; preserve prefixed source names |
| Stegosaurus | Tail, twice through Multiattack | Attack3 inspected | New rig, one Tail profile reused for both actual child attacks |
| Elephant | Trunk Sweep | Attack1 inspected | New rig/profile; no invented tusk attack instead of depicted trunk motion |
| Triceratops | Gore | Attack1 inspected | New rig/profile/markers |
| Mammoth | Gore | Attack2 inspected | New rig/profile/markers |
| Tyrannosaurus | Bite OR Tail | Attack1 inspected; Attack1–4 available | Select/calibrate Tail separately; no visual grapple or implied extra attack |
| Dretch | Bite, Claws; existing Multiattack | Installed Demon Beast 1 Attack 1/2/3 mappings | Revalidate under explicit body usage; secondary Claws is not a human off-hand swing |
| Corrosive Demon | Same native attacks as Dretch | Installed Demon Beast 2; current body-response/residue data | Same mapping checks; keep independent actual corrosive feedback |
| Dread Demon | Same native attacks as Dretch | Installed Demon Beast 3; current dread/fear data | Same mapping checks; keep actual residue/fear outcomes |
| Claw Mote Devil | Claws | Imp 5 Attack 1–4 in source inventory | Select/inspect primary strip; new rig/profile/markers |
| Huntsman Wing Devil | Claws twice; grounded flight | Demon Beast 5 Attack 1–4, Jump and travel strips inventoried | Select/inspect Claws and flying body treatment; no Fly clip claimed |
| Fellwing Devil | Claws twice, Gore; grounded flight | Demon Beast 4 Attack 1–4 and travel strips inventoried | Select/inspect both attacks and flying body treatment; no Fly clip claimed |

### Shared non-attack mapping obligations

| Existing semantic context | Source/data route | Completion obligation |
| --- | --- | --- |
| Idle / ground movement / TakeDamage / ordinary death | Animals: Idle/Run/TakeDamage/Die. Ordinary dinosaurs likewise. Blue Raptor: Raptor Idle / Raptor run / Raptor TakeDamage / Raptor Die. Selected demons: Idle/Run/TakeDamage 1/Die 1 candidates. | Validate the actual frames, pivots, facing order and separate shadow policy for each row; candidate name is not proof of a valid living rest pose. Ordinary death remains distinct from summoned departure. |
| Prone entry / hold / stand-up | Existing condition recipe plus rig body-context binding; adequate existing fall/rest/reverse sequence. | No exploding corpse as a living Prone body, no per-species condition. |
| Forced movement / actual fear retreat | Existing recorded movement and TakeDamage/travel body contexts. | Preserve authoritative route and reactions; bind only the body presentation. |
| Ordinary jump / flying travel / connector traversal | Recorded context/trajectory/movement mode plus explicit body binding. | Do not treat all three as a human Rolling clip. Inspect actual source support; disclosed motion reuse needs evidence. Missing required motion is unresolved current integration, not implicit new-art authorization. |
| Dash / Dodge / Disengage / Hide / other reachable standard actions | Existing normal recipes and condition facts plus the same rig/body-context data. | Enumerate actual available native actions for each recipe. Validate their body/pose requirements, or use an explicitly authored legitimate body-disabled gesture. Never remove a legal action because media is missing, or map all actions to Attack1. |
| Equipment / healing gestures when reachable | Existing shared context; actual equipped/intrinsic item facts. | No fake hand grip on a quadruped, no invented held weapon; preserve state change and feedback with an adequate authored pose or explicit neutral no-gesture disposition. |
| Summon / dismiss caster gesture | Caster's own existing rig/recipe, not the summoned body's attack clips. | Current shared recipe/data work; V1's decorative accent is later delivery. |

## D. Clean component, validation and ownership

The **implementation design is in main-plan section 10.2.1**, not another plan:
retain the existing BodyRig registry, extend existing AttackProfileMatch with
rig-scoped selectors, and add one typed passive body-context table to each rig
where global body assumptions do not fit. Exact selectors use recorded movement
mode **plus trajectory and connector identity**, or an existing action/condition
reference, with one role-default and no overlapping wildcard rules. The body
binding carries the validated clip/marker/playback data for both timing and
sampling, including recovery, reversal and held poses. One pure body-binding
helper feeds the existing samplers. There is no alternative creature renderer, duplicated event
consumer, new attack runner or native creature -> Python visual subclass path.

Data contains content references, rig/clip IDs, exact source bindings, clocks,
markers and layer policy. It contains no executable handlers or spell/monster
name matching. The same canonical ordinary creature and summoned instance use
the same action/body binding; Fey contributes retained material only. Backends
never select a PNG, source frame or shader.

Acceptance must reject duplicate/ambiguous mappings, unknown rig/clip/resource
IDs, unreachable markers, missing required poses and eight-direction/shadow
registration gaps. Exercise ordinary and summoned copies, main/secondary body
attacks, misses/criticals, OA, native Multiattack children, Prone/stand-up,
movement modes, material composition and history/reacquisition. Include the
modular default path and existing four fixed rigs in regression coverage.
Required body mappings stay in the current batch's unfinished ledger; optional
VFX tracks stay explicitly optional. Do not turn missing essential body work
into an “artist pending” reason to call the batch complete.

## E. Evidence inspected for this addendum

- game/animation_types.py: BodyRig, BodyClip, AttackProfileMatch/AttackVariant and
  existing actor/anchor schemas.
- game/animation_data.py: _additional_rigs and shared profile loading;
  game/animation.py: body_rig/body_clip and equipment-body contexts.
- game/attack.py: select_attack_profile, native source/item facts and body/contact
  binding; game/player_facts.py: AttackFact and recorded movement_mode.
- game/condition_animation.py; game/data/condition-recipes.json;
  game/data/condition-media.json; game/data/world_bindings.json: existing Prone,
  Frightened and blood/residue bindings.
- game/data/rigs/greywolf.json and demonbeast01/02/03.json: literal installed
  aliases, source provenance and declared clocks/shadows.
- .runtime/pack-study-20260930/animals-humanoids/inventory.json;
  animal-dinosaur-completion/dinosaurs/contacts/inventory.json and chosen-attack
  provenance; orcs-demons/demons_inventory.json: available source names/frames.
- Prior inspected-strip findings in
  [the animal/dinosaur study](audits/PACK_ROSTER_ANIMAL_DINOSAUR_COMPLETION_2026-09-30.md).

This update reads existing code/data/studies; it does not claim a new visual
inspection of every source strip, a media import, test run or VFX-agent delivery.
