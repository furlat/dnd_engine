# Player UI implementation and acceptance — 6 October 2026

Status: implementation, full regression reconciliation and both independent
acceptance reviews complete. This report describes the
approved [player UI plan](../PLAYER_UI_PLAN_2026-10-05.md), rather than a new lane.

## Delivered behavior and ownership

The default game opens party creation, then the existing Goblin encounter.
Fighter and Sorcerer premades provide a direct playable route; native character
drafts can replace them. `--quick-start` skips creation. No campaign, new spell,
new ammunition system or alternative event executor is included.

| Feature | Delivered behavior | Actual owner |
|---|---|---|
| Minimal HUD | One touching row of at most ten pinned shortcuts, eight on narrow layouts; unboxed vitals; initiative portraits; small panels on demand | `game/ui/action_bar.py`, `hud.py`, `layout.py`, `skin.py` |
| Native action library | Search and pin exact behavior/configuration/weapon/item identities; stable positions when unavailable; native rank/form/ability choices | `game/ui/action_bar.py`, `variants.py`, `panels.py` |
| World controls | Click ground to move, enemy to attack, object for its native default; Ctrl attack; right-click context; Alt usable-object highlights | `game/ui/world_interaction.py`, existing `game/controls.py`, `encounter_play.py` |
| Window/approach | Existing connector traversal discovered as a world action; ordinary native movement followed by fresh admission of the same interaction | `dnd/actions_functional.py`, `dnd/entity.py`, `game/session.py` |
| Ordered targeting | Native partial/repeated allocation, dependent recipients and points; undo and explicit confirmation; exact admitted preview | `game/controls.py`, native selection hooks and `preview_available_selection` |
| Picking/highlights | Shared post-cut painted actor, object, wall aperture and ground coverage; shadows and spell overlays are not physical actor targets | `game/interaction_frame.py`, `interaction_types.py`, existing draw-command/compositor owners |
| Initiative and resources | Authorized order, presented HP and party sheets; native evaluated current/capacity values and reaction preferences | `game/session.py`, `player_facts.py`, existing projection/reduction |
| Combat log | Original detailed native wording by default, recorded dice/modifiers, causal children, filters, follow/scroll, expansion and text copy | `game/ui/combat_log.py`, `rich_text.py`; native log remains sole wording source |
| Inventory | Native compatible equip/unequip, item use, charges, effect descriptions, legal-position Drop; world chest/loot and real ground Pick Up | `game/ui/panels.py`, gated Session adapters and existing item actions |
| Creation and levels | Cold native choices, point buy, starting loadout, appearance/portrait and level draft; Fighter, Barbarian and Sorcerer supported paths | `game/character_select.py`, `ui/character.py`, existing character resolvers |
| Rendering/media | Delivered pixel icons and role portraits at integer nearest scale; antialiased text at display resolution | `game/ui/media.py`, `primitives.py`, `ui_composition.py`, private asset importer |
| Recording | Existing schema-2 player sequence with initialization, lineages, native log appends and authorized HUD snapshots | Existing `game/replay.py`, `player_projection.py`, `player_reduction.py` |

Inventory and initiative remain small functions in `panels.py` and `hud.py`.
The plan's prospective `ui/inventory.py` and `ui/initiative.py` were not created:
no extra module owner is needed. Views receive passive facts; startup composition
and Session are the boundaries that may read native content/live state. Domain
imports never depend on the game UI. The existing encounter loop consumes intents
and performs command dispatch; there is no widget class hierarchy or callback bus.

## Exact native changes

These changes support the requested controls; they are not a broad rules refactor.

1. Existing discovery rows expose generation, typed variant facets, allocation
   disposition, world affordance and connector facts. Session retains the exact
   executable row privately and returns detached values. Stale, foreign-session,
   wrong-actor and wrong-target handles cannot spend resources.
2. The native ordered-prefix preview shares pure selection checks with execution.
   It exposes effective allocation and next admitted choices without registering
   events, rolling dice or paying costs. Native safe-path preference is shared by
   disclosed preview and actual movement, instead of duplicated in the UI.
3. Magic Missile, Scorching Ray and Eldritch Blast declare their existing
   fill-primary behavior. Other up-to-N actions leave unselected capacity unused.
   Beacon of Hope and Divine Word now expose their existing six-recipient cap
   through the discovery count hook. These two cap corrections were explicit in
   the approved plan; damage, save and action-economy formulas are unchanged.
4. Existing Enhance Ability choices and Enlarge/Reduce modes become native
   discoverable variants. Existing wall, summoning, energy and movement variants
   publish passive facets. Straight Wall of Fire has one ordered-endpoint form;
   reversing its points reverses its hot side. Ring inside/outside stays a choice.
5. Known exhausted spell ranks remain visible with their native unavailable
   reason. They are not executable. Item variants preserve their exact source and
   retained template; SELF item use binds its owner, while ordinary source-only
   SELF actions retain their original native declarations.
6. Existing TraverseConnector is registered for standard discovery. World uses
   can expose a non-executable observed verb before reaching contact; a click may
   request ordinary movement, then rediscover the same action. Native contact,
   hazards, costs and reactions still decide whether it executes.
7. Session gains gated equip/unequip and reaction-toggle adapters. HUD snapshots
   carry authorized sheets, native resources and disclosed initiative at their
   committed operation boundary. Capacity evaluation omits native expenditure
   modifiers while retaining native grants/constraints; widgets do not infer it.
8. Existing cold origin/class requirements are shared with creation. Optional
   Sorcerer replacement choices have explicit data rather than a UI name test.
   Selected starting loadouts expand once before native materialization. Portrait
   preference is passive appearance data, independent of mechanics.
9. Existing packet types gain optional/defaulted HUD facts, turn association and
   observer-projected queue-only log appends. They remain on the same sequence,
   operation, projection and reduction path. Original logs are copied, not
   reconstructed; old passive packets remain readable. The movement-log producer
   uses a semicolon before its cost so coordinate redaction cannot corrupt it.
10. Native item-effect snapshots include their existing display name/description
    for inventory. Bonuses, coatings and Continual Flame keep their original
    mechanical owner. No presentation key is converted into invented prose.

## Rendering corrections found during acceptance

- Inverse-projected camera directions now subtract the inverse origin, removing
  translation from the volume-ray vector. Existing area/scene regressions verify
  the correction; no tile mask, new spell geometry or art was introduced.
- Floating damage text uses antialiased display-size glyphs. Camera/world zoom
  still transforms its world anchor and rise; it does not enlarge glyph bitmaps.
- New passive selection masks are propagated through existing render commands
  and cuts without changing their RGBA scene result. Tests now compare observable
  destination/blend/evidence and rendered pixels rather than invoking ambiguous
  Python tuple equality on NumPy mask arrays.
- Hidden log geometry no longer captures inventory scrolling. Layout/discovery
  freshness rejects old painted hits after focus, text or modal changes, including
  multiple SDL events in one frame. This does not add an engine scheduler.

## Persistent gameplay evidence

[Standard engine gallery](http://127.0.0.1:8768/player-ui-20261006/runs/20261006-player-ui-acceptance/index.html).
Private root: `.runtime/player-ui-20261006/`. Drivers, raw frames, proofs and all
five complete `physical/*-sequence.json` packets are retained there. Every packet
was encoded/decoded and reduced, comparing final actor HP/positions and cursor
with the actual captured client result. These recordings use real posted SDL
mouse/keyboard input through production dispatch. Drivers return no native action
commands. Some failed harness probes preceded the accepted recordings; the saved
accepted packets allow subsequent presentation replay without rerunning mechanics.

| Clip | Actual native proof | Published duration / gaps |
|---|---|---|
| Fighter | Main-hand Attack and Extra Attack from world clicks; inventory and native dice log; native AI turn | 650 frames, 20.3125s / 0 |
| Sorcerer | Library search, rank 2 Magic Missile; A/B/A, undo and confirmation; native effective recipients A/B/A/A | 820 frames, 25.625s / 0 |
| Environment | Alt highlights, world-click lever, inventory, native turn | 450 frames, 14.0625s / 0 |
| Storage | Open Chest → Loot All → inventory Drop → chosen floor cell → click real Handaxe pixels to Pick Up; same UUID transfers out and back | 900 frames, 28.125s / 0 |
| Completion | One clicked Move, native automatic opportunity attack killing Goblin 1, one clicked main-hand Attack killing Goblin 2; encounter ends | 384 published frames, 12s / 0 |

Completion uses ordinary RNG seeded 0, with no injected die faces or HP changes;
the final Fighter has 41 HP and both Goblins are DEAD at -4/-5 HP. Its full raw
capture has 1,200 frames; the published clip trims only post-completion idle time.
This is not two player attack clicks. The separate Fighter clip demonstrates
Extra Attack. Other targeted recordings use deterministic dice for clear roll
evidence, without bypassing native execution or ownership.

These are full live-HUD recordings from one camera, in the usual gallery format.
They are not four-camera render-only demonstrations. Four camera quadrants and
occlusion/picking cases are covered separately by the regression tests. Parent
visual inspection includes refreshed Fighter/Sorcerer logs and HUD, storage
inventory/log/ground transfer, completion, and minimum/maximum-resolution panels.
Reviewers identify their own sampled images in their receipts. Neither five
clips nor passing tests claims that every frame/ability was inspected by eye.

All 15 refreshed HUD/sheet/inventory captures exist for 960×540, 1280×720,
1920×1080, 1920×1200 and 2560×1440, with zero reported presentation gaps.
Creator/appearance samples also exist at those sizes. The automated lane uses SDL
dummy; this is not a claim of testing physical Windows fullscreen interaction or
a 4K display. Fonts are antialiased; supplied icon/portrait pixels remain nearest.

## Plan acceptance matrix

| Plan row | Boundary evidence | Physical/visual evidence |
|---|---|---|
| HUD/resolution | `test_ui_media`, `test_encounter_play`, UI layout/input tests | 15 refreshed resolution images; five live HUD clips |
| World interaction | `test_player_selection_contract`, `test_controls`, `test_ui_native_choices` | Lever and storage clips; window native-discovery/approach tests |
| Occlusion/picking | `test_interaction_frame`, boundary/map/XYZ tests | Sampled real scene captures; all four quadrants tested |
| Move then interact | Native approach/prefix freshness tests, `test_ui_input_acceptance` | Completion clicked movement; lever interaction |
| Projectile allocation | Pure preview, native partial/repeat/cost and controls tests | Sorcerer A/B/A/A rank-2 clip |
| Multi-target/points/forms | Entity-destination, chain, wall, summoning and native selection tests | UI family choices; this gallery does not claim an individual physical recording for every form |
| Combat log | `test_ui_combat_log`, subjective native replay, standalone immunity, feedback tests | Original dice/modifiers in Fighter/Sorcerer/storage clips |
| Items/economy | Source variants, equipment sequence, engine roster/spell tests, projected HUD tests | Fighter Extra Attack; source descriptions and charges in inventory |
| Character | `test_ui_character_creation`, all progression tests, native build validation | Creator/appearance screenshots at five sizes; actual SDL stale-click/cancel tests |
| Inventory/loot | Ownership/transfer, pickup/equipment playback, native UI selection | Complete same-Handaxe drop/pickup and Potion of Healing loot |
| Stress/input | Bounded log-history/layout, malformed tags, copy, modal and batch-input tests | Readable small/large samples; no claim of an exhaustive manual accessibility audit |

## Regression results

The full game suite is covered by a completed prefix plus a completed remainder,
and the newly added glyph-zoom test. Current collection is **3,695 game cases**.
Original collection was 3,694. The first run was interrupted after 1,610 completed
cases; the remainder restarted the whole boundary file, collecting 2,086 cases.
Their union covers the original 3,694 identities (two overlap), and the new
glyph-zoom case is in the final input/feedback rerun. This is partitioned coverage
with failure closure, not one uninterrupted all-green run against frozen source.

| Run / private log in `.runtime/ui-study-20261005/` | Result | Reconciliation |
|---|---|---|
| `ui-game-final.log` | 1,514 passed, 96 failed; 2,376.29s, then interrupted | 90 volume-ray failures and six ndarray comparisons closed below |
| `ui-game-remaining.log` | 2,050 passed, 36 failed; 2,710.38s | All 36 failures closed by the affected-file runs below |
| `ui-area-scene-repair.log` | 136 passed; 46.66s | Complete area/scene file closes the 90 ray failures |
| `ui-final-feedback-replay.log` | 29 passed; 58.66s | Complete equipment/forced-movement and feedback files close six command comparisons and test AA glyphs |
| `ui-movement-temp-fixed.log` | 41 passed; 38.25s | Complete movement/routes, pending-spell facts and placement files close eleven failures |
| `ui-support-regressions-fixed.log` | 60 passed, five failed; 127.16s | Full condition facts file's 29 cases pass; the rendering module loaded before its last choice-selector edit |
| `ui-support-rendering-final.log` | 36 passed; 113.18s | Full rendering file closes those five, plus the finite-cache baseline case; together the two files close 21 broad-run failures |
| `ui-self-source-final2.log` | 117 passed; 31.09s | Complete support media/replay and native roster/spellcasting files close timing plus two Thaumaturgy failures; backpack ownership still passes |
| `ui-media-final.log` | Five passed; 7.60s | Complete UI media file closes the incidental 612-vs-613 icon-count assertion, checks actual Fly pixels instead |
| `ui-engine-final.log` | 3,031 passed, seven failed; 547.46s | Full engine/AI/architecture/progression run; six item-owner failures plus one known-depleted-rank expectation |
| `ui-style-final.log` | 125 passed; 122.65s | Complete affected native roster/spellcasting plus UI files close all seven; final SELF refinement also passes in the 117-case run |
| `ui-progression.log` | 201 passed; 6.94s | Independent complete progression run |
| `ui-shell-acceptance.log` | 117 passed; 244.15s | UI shell/native input/creation/log/media acceptance |
| `ui-boundaries-final.log` | 116 passed; 144.94s | Native selection, packet/disclosure, interaction and projection boundaries |
| `ui-last-input-recheck.log` | 32 passed; 97.97s | Final SELF change rechecked through physical input, native choices/prefix selection, actual media and glyph zoom |

The 36 remainder failures are exactly: five movement route comparisons, five
placement comparisons, one temporary-HP fixture choosing the wrong ability,
15 condition-fact ability fixtures, five condition-render ability fixtures,
one finite cache warmup, one old Shield contact expectation, two SELF fact
regressions and one incidental resource count. No failure is dismissed merely
because it predates the UI or belongs to another module. Complete files were
rerun; assertions for native costs/outcomes, RGBA placement, selected ability,
finite cache behavior and measured contact remain intact.

All 132 failures in the two game runs, and all seven in the native broad run,
are closed by the recorded affected-file reruns. No unresolved tested failure
remains in these suites.

The final 32-case physical-input/selection/media/feedback rerun also passes.
`ui-types-last.log` finishes with **zero errors, warnings and informations** for
`pyright game dnd/actions_functional.py devtools/import_ui_icons.py`, including
the final SELF owner/source correction. The preceding game-wide and importer
runs are also clean.
`git diff --check` is clean. The suite uses Python 3.13.12, pygame-ce 2.5.8, the
Linux uv environment, SDL dummy and this `/mnt/c` checkout; timings include its
filesystem cost. Repeated subsets overlap, so their pass counts are not added to
claim an inflated total.

## Media and explicit limits

613 selected icon resources use accepted source pixels. The 56 player portraits
have three delivered role sizes; 41 exact creature associations have three role
sizes. Creature portrait ownership is on current content descriptors, not a second
UI creature catalog. Fly's accepted shared image is explicitly bound to its native
spell reference; no name heuristic or generated substitute is used.

[Artwork status/handoff](../PLAYER_UI_ARTWORK_HANDOFF_2026-10-06.md) records the
remaining eight declared binding gaps: world-only TraverseConnector, generic
runtime Multiattack, fixture Test Bless, Hit Save Rider, Keen Perception, Magic
Resistance, Innate Flight and Aegis Training. Ordinary spell icons resolve. Some
existing weapon/feature icon approximations remain disclosed in authored data.

Ground potions/other consumables do not have authored floor appearances. They can
be looted and used in inventory; dropping them does not magically create a world
sprite or clickable pixels. The storage recording deliberately uses an existing
Handaxe floor sprite. Completing those assignments is a separate content task.

The native log currently contains some repeated anonymous `Unknown gains
Bloodied` entries. The UI preserves those real entries and does not deduplicate
or invent their actor identity. This remains a native producer/projection issue;
the UI phase does not certify flawless wording for every existing producer.

Whole-map/character save/load remains deferred under the approved "only if easy"
decision. Passive recordings are not live-session restoration. No pretend Save
button or replacement narrative exists. Pre-encounter levels are supported;
earned in-session XP/level entitlement remains outside this phase.

No assets, full packets, videos or screenshots belong in public Git. They stay
in ignored private storage/runtime paths. The final status audit finds no new
public PNG/WebP/video/archive/media file and no modified/new public file over
1 MiB. No commit or push was performed.

## Independent review

- [Anti-slop implementation receipt](UI_IMPLEMENTATION_ANTISLOP_2026-10-05.md).
- [ECS/import-DAG implementation receipt](UI_IMPLEMENTATION_ECS_2026-10-05.md).

Both final local reviewers approve the implemented scope and source boundaries,
latest native SELF/item binding, sampled evidence and completed regression
reconciliation. Each independently checked the 3,695-identity coverage and
failure closures, the final 32-case rerun and typing result. The anti-slop
reviewer also independently round-tripped/reduced all five packets. Their
receipts preserve the distinction between partitioned regression coverage and
sampled visual inspection. The native log and ground-consumable limitations
above are not erased by test/source approval.
