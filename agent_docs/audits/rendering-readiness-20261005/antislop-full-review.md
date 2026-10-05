# Independent anti-slop review: full presentation coverage

2026-10-05. Reviewer: independent source audit of the provisional plan and readiness audit. No production changes, tests, or new visual certification. This report covers the non-spell owners inspected below; parent coverage inventories establish the catalog denominator.

## Verdict

The earlier provisional plan is not yet sufficient as an implementation specification. Its family table names many owners, but several non-spell decisions need explicit mappings and evidence. A generic track schema must not replace these distinctions with action-ID special cases. The following are design obligations, not claims that current gameplay is broken.

## Source-backed non-spell matrix

| Family | Current ownership and behavior | Contract/repair obligation | Acceptance case |
|---|---|---|---|
| Attack profile selection | `game/attack.py:146`: highest-precedence authored variant selected using declaration-time source kind, weapon slot, rig, outcome, damage types and item reference; ties fail | Export selection predicate/precedence and selected variant identity. Text must not choose weapon from the actor's later loadout | Melee/ranged/off-hand/natural; change equipped item after declaration; equal-precedence rejection |
| Creature/object attacks | `attack.py:310`: shared attack root branches to ActorContact or ObjectContact; actual damage result owns response | Preserve common attack ownership, typed target contact and object-specific destruction; no duplicate object-attack semantic pipeline | Same weapon hits creature, prop and wall section; blocked/missed attack |
| Attack delivery capability | `attack.py:332–364`: disabled body, hidden slots, actor media, non-bolt geometry and absent clips have explicit rejection/fallback paths | Coverage must distinguish selected authored variant from actually bound delivery. Existing Idle fallback is a disclosed limitation, not evidence of full animation support | Fixed-rig missing ranged clip; supported modular bolt; rejected configured media |
| Attack attribution and life | `attack.py:386–405`, `damage.py:39–83`: results resolved by native resolution ownership; life state may normalize intermediate negative HP | Every packet/life transition needs exact ownership, not target-based matching; do not merge nested secondary hits | Multi-hit same victim, nested retaliatory damage, zero HP then DYING |
| Attack timing and ornaments | `attack.py:367–468`: release/contact, body end, damage end, weapon flash and critical scale are distinct; child attack can hide body | Mark mechanical impact separately from flash/tail end; retain accepted critical emphasis as authored policy if migrated | Crit versus normal; child attack; long trail does not delay next movement |
| Content actions | `body_action.py:95–235`: draft, recipe alias, actual effective-handler attribution, condition reaction binding and action facts can select actor tracks | Inventory aliases, handler-derived actions and condition-owned actions as separate admissions into shared selection; no synthetic gameplay action needed for narration | Potion, device use, successful/failed handler, no disclosed source |
| Body-action joins | `body_action.py:237–266`: body may finish before children; hidden slots survive to join; recovery starts afterward | Distinguish body phase, slot restoration, child join, recovery and complete. Do not use one generic end date | Action with a long-running child; canceled action with a surviving child |
| Equipment change | `combat.py:368–410`, `choreography.py:1831–1848`: unchanged appearance/NONE produces no gesture; stance commits at authored frame, item membership/AC at completion | Two observed commits are not equivalent to one costume swap; state-only changes still have semantics | Bow-to-melee, unequip without new stance, unchanged visible layers, transfer/drop/pickup |
| Ordinary/hidden movement | `choreography.py:2296–2420`: admitted Step endpoints own path; loss/reacquisition inserts dwell but never invents hidden edges; other actors' steps remain separate | Explicit visible segment, hold/dwell and observation boundary records; no root-position interpolation through unknown travel | Visible→hidden→visible, isolated observed contact, blocked attempt with visible child damage |
| Movement reactions | `choreography.py:2460–2568`, `2609+`: lead-in/held pose/reaction/resume; reaction subtree may already own movement | Movement sequence must reference existing child timeline and exact held contact. No duplicate traveled segment or reaction narration | Opportunity attack stops movement, reaction displaces walker, walker dies before continuation |
| Jump/fly/window traversal | `choreography.py:2088–2248`, `2031`, `2327`: direct arc differs from flight path and connector profile; jump preflight and landing reactions differ | Finite movement-mode/trajectory/connector roles, measured body policy and geometry; no generic 'walk' fallback hiding flight | Native-wing flyer, Fly recipient, window crawl, jump interrupted before/after landing |
| Forced displacement and shove | `forced_movement.py:73–99`, `109–207`: resisted/prone/blocked/push outcomes; actual path/elevation, brace, effect formation, travel, recovery and arrival commits | Attempt semantic distinct from actual displacement; source-facing policy retained. Controlled/impact finite transfer uses straight segment, clearance cells are not waypoints | Resisted shove, blocked successful shove, partial push, cliff impact, safe ally placement |
| Damage-only presentation | `damage.py:39–106`: hidden cause can remain absent; direct request owns results; resulting life chooses body | Damage occurrence does not require rendered attack. Preserve life after decorative completion | Unseen damage source, periodic tile damage, temp HP absorption, prone-to-death |
| Explicit reactions | `choreography.py:415–442`, `1729–1737`; `interruption.py:34–181`: native roots remain distinct, attempts truncate, actual completed descendants survive | Cross-root dependencies and frozen incoming sample are data references; failed reaction is not cancellation | Counterspell success/failure/automatic result, intercepted projectile, child already completed |
| Condition interception | `condition_reaction.py:25–88`: initial Shield application anticipates contact, maintained Shield contact replays no cast | Persistent contact versus new application must be distinct roles. Do not replay a gesture for each blocked hit | First Shield block and next block under same condition UUID |
| Effective handler feedback | `body_action.py:72–84`: actual content attribution drives Indomitable/Relentless-Rage-style intervention | Audit handler evidence beyond fact kind; text must retain result even if body unavailable | Reroll success/failure, unknown handler source, damage interrupted by survival effect |
| Summon presence/control | `entity_lifecycle.py:31–61`: creation→arrival, terminal causes→departure, control-lost→bond; FEY_SPIRIT restricts bond art | Presence, disappearance and control loss are distinct semantic transitions. Lack of matching art must not erase factual meaning | Expiry, dismissed, defeated, sustain loss, hostile surviving Fey |
| Tile effects/residue | `app.py:1326–1488`, `deposit_media.py:25–47`: physical deposits can suppress duplicate residue drawing; spatial owner, per-tile residue and remembered ground differ | Denominator includes tile surface/residue/deposit state, not only spatial-media recipes; one physical contribution should not double render/narrate | Deposited material becomes residue, persistent ground after airborne phase, tile effect triggers damage |
| Device/world transitions | `app.py:1420–1495`: activation/pressed/trap/creation states, footprint placement, mechanism projectiles are independent of cast roots | Enumerate mechanism state transitions and their actual projectile/commit owners; world update can carry meaning without action cue | Door, trap activation, object destruction and wreck, multi-cell footprint |

## Concrete color-treatment defect in the proposed authoring contract

`game/attack.py:188–215` creates slash layers with `LayerColors(source='override', mode='tint')`. `game/animation_draw.py:211–240` does not dispatch on `colors.mode`. Its override path calls `_colored(image, primary, vfx_source_hues.get(category))`; `_colored` at 184–201 uses hue rotation when a category hue exists and RGBA multiplication otherwise. A supplied `sourceSheet` bypasses that path. Therefore the mode label is not authoritative; the visible treatment depends on additional source/category state. This is a source-confirmed authoring/implementation mismatch, not a freshly demonstrated pixel regression.

Required repair in the plan: materialize one explicit actual color treatment, including source-image treatment and palette parameters, and use it consistently in loading/cache identity/export. Do not merely change `mode='tint'` to `paletteSwap`: the current loader ignores that switch. Preserve accepted baseline art while making user-required palette replacement corrections explicit and visually reviewed. The existing cast-row cache key also omits declared mode and other treatment distinctions, reinforcing the need for a fully effective treatment identity.

## Other coverage traps

1. Five attack recipes are not five cases: variants, actor/object contacts, interception, absent bodies and declaration-time equipment substantially expand the behavioral denominator.
2. Eighty-five action recipes do not include every visible handler: `content_attributions` and condition responses admit additional behavior without new action facts.
3. A graphical binder returning None is not proof that a public action has no narrative meaning.
4. Summon control loss, dropped item ownership and newly observed world state need semantic output even if no body track plays.
5. Reaction/movement nesting must be assessed at each retained child boundary, not only final position equality.
6. Surface work remains presentation coverage of existing mechanics. It must not silently authorize additional chemical/elemental interactions.

## Anti-slop requirements for rewritten plan

- Carry one explicit denominator across authored collections, public inputs, bound outputs, retained lifetimes, sampled operators and final composition. Do not call the spell matrix full coverage.
- Each migration step names the old decision/owner it deletes or changes, the existing passive record it extends, the fact/owner it consumes and the evidence preserving behavior.
- Retain specialized functional geometry/sampling operators; remove duplicated selection/timing ownership instead of flattening algorithms into a universal renderer or JSON language.
- Treat source inspection, mapping completeness, fixture presence and visual/timing acceptance as separate statuses.
- Do not propose a new registry merely because several dictionaries exist. Identify the shared selection problem and extend existing typed owners only where necessary.
- Independent approval must explicitly state whether it covers the inventory, plan or actual production acceptance. None are interchangeable.

The rewritten plan may proceed to review once these obligations appear concretely in its coverage and implementation gates. This report does not certify any fresh visual render or authorize production edits.

## Second-pass review of rewritten plan

Read `SHARED_PRESENTATION_AND_TEXT_RENDERER_PLAN_2026-10-05.md` and `FULL_PRESENTATION_COVERAGE_2026-10-05.md` after the rewrite. The full-scope source denominator and family matrix now include the non-spell paths identified above, without presenting inventory counts as runtime acceptance. The ordered lanes retain existing families and lifetimes rather than introducing duplicate spell/action executors. The color-treatment issue is accurately scoped. Those aspects pass anti-slop review.

Two concrete obligations must be restored before final plan approval:

1. **Actual headless dependency repair:** `combat.py:30` imports passive `AreaSolid` from `area_media.py`, which imports Pygame/NumPy. Move only the shared passive geometry value into a suitable passive owner and import it from both consumers; prove the text compilation path does not import/init Pygame or load textures. SDL dummy mode is not proof. Avoid splitting already-passive metadata modules merely because their names contain “art”.
2. **Portable/validated contract:** explicit schema round-trip and content-relative resource identity checks, no absolute machine paths/callables, deterministic schedule tie ordering, cycle detection and rejection of unresolved required references/multiple producers. An import-DAG check does not validate the schedule graph.

These corrections do not require any production change in this planning pass. Once incorporated, the plan and full-scope source denominator can be approved. Such approval does **not** assert that the eventual schema has already passed concrete encoding gates or that runtime/visual acceptance is complete.

### Final second-pass disposition

Re-read the corrected plan: section 3 now names the actual `AreaSolid` extraction and fresh-process Pygame import rejection check; sections 4 and 8 now require schedule cycle/reference/producer validation, causal floors/native ordering, portable resource IDs and schema round trips. Both findings are resolved in the plan.

**APPROVED: full-scope source coverage denominator and rewritten implementation plan, from the anti-slop perspective.** The plan makes all presentation domains explicit and requires concrete mapping before schema freeze. No further blocking design omission was found in the reviewed non-spell paths. This is not schema-fit completion, runtime validation, visual approval, or authorization to bypass the user's implementation decision.
