# NDClient interaction inventory: Pygame and NeuroClient

Source inspection on 8 October 2026; not browser acceptance. Companion to
[the implementation plan](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md).
Pygame paths are in this engine repository. NeuroClient paths are relative to
`/home/tommaso/Dev/NeuroClient/app/src/`.

The destination preserves current interaction semantics and selectively recovers
the older browser client's useful controls and panel behavior. Neither UI is an
approved whole-product design. Existing functions are evidence, not proof that the
user-reported bugs have all passed interactive acceptance.

| Interaction | Current Pygame owner / behavior | NeuroClient salvage or replacement | NDClient acceptance |
|---|---|---|---|
| Camera | `game/projection.py`, `encounter_play.py`: Q/E, WASD, cursor zoom, G grid, fullscreen | `ui/boardViewportController.ts`: drag, smooth zoom/inertia, focus handling; replace flat/store assumptions | Pan independent of world rebuild, four rotations retain focus; typing/scrolling panels cannot move camera |
| Grid | `app.py`: elevated retained supports, default off | `grid.ts`: mesh and hover uniforms useful; flat 64×32 inverse projection replaced | World 128×64 registration, slopes/raised floors; floor → grid → wall/body order |
| Picking | `interaction_frame.py`: final composition coverage, apertures, support height | `ui/visualEntitySelectors.ts` ground-diamond picking replaced | Final presented scene and pointwise physical masks agree with hover/click in every camera |
| Object highlight | Physical visible silhouette and owner identity | Reuse shader/DOM mechanics only | Local outline, no rectangular padded sprite bounds; disappears as spending gesture completes |
| Wall transparency | `boundary_occlusion.py`, `app.py`: faces covering received visible floor fade; bases/openings remain | Old seen-wall alpha is memory styling, not cutaway | Automatic cutaway; does not grant visibility or modify native blocking; click through faded upper face |
| Alt interactables | `encounter_play.py`: admitted names/coverage, clickable labels | No equivalent board-wide implementation found; distinguish old portrait Alt-click | Same eligible doors/items/props across cameras, no hidden labels, no stuck Alt on focus loss |
| World click | `ui/world_interaction.py`: exact affordance, unique default, right-click alternatives | Old contextual filtering can inform menu design | Open/close/loot/lever/window/trap via world, not extra action-bar rows |
| Approach then interact | Retain intent, native safe approach, move, rediscover exact action | Old client lacks this complete workflow | No implicit Dash/bonus spend; door reach from native result; actor/blockage changes invalidate stale preview |
| Melee/ranged | Explicit action families and X preference | Browser keybinding/layout patterns | Both available intentionally; no silent weapon substitution; correct ranged body/weapon animation |
| Action bar | `ui/action_bar.py`: base/spell/class/item families, unavailable state retained | `ui/actionBarModel.ts`, `actionBar.ts` layout/accessibility selectively | Four compact icon blocks, multi-row, useful tooltips, no fake or duplicate actions |
| Upcasts/variants | `ui/variants.py`: native dimensions/ranks resolved to actual choice | Old selection_parameter/catalog assumptions replaced | Same-sized hover level icons; real sub-icons for walls/summons/resistance/conversion; no bulky modal |
| Ordered targets | `controls.py`: native next_targets/next_positions/can_confirm | Old max-count client auto-submit and UUID maps replaced | A/B/A preserved, repeats only if allowed, fewer than max if admitted, one target repeated only when semantics allow |
| Aim/AoE/path | `ui/targeting.py`: native footprint/path/cost/hazards/OA exposure | Reuse browser path presentation/input only | Preview matches submitted prefix/choice; geometry on actual receiving supports; stale async replies discarded |
| Self actions | Native self-choice, availability | Browser button/focus patterns | Legal Action Surge executes once; unavailable action cannot enter a pointless targeting/confirmation flow |
| Party/initiative | `audience.py`, `scene_actors.py`, `ui/hud.py`: authorized union, retained contacts/HP, F1–F4 | `initiativeBar.ts`: SELF/TARGET/focus ideas | Split rooms do not hide allied witnessed action; no leaked enemy portrait; no command authority on dead slot |
| Inventory/equipment | `ui/panels.py`: controlled items, slots, quantities, native compatible choices | `equipmentPanel.ts`: filters/search/compact double-click behavior | Clear slots, hover compatible items, accurate effects/charges/coatings; native equip/use/drop/loot only |
| Abilities/reactions | `ui/panels.py`: actual costs, resources and automatic-reaction toggles | Selected character/action/reaction panel ergonomics | Received enabled choices only; no invented feature variants or hidden inventory |
| Combat log | `ui/combat_log.py`: typed rows, causal groups, native math, fold/filter/follow/copy, presentation reveal | `combatHistoryPanel.ts`: DOM resize/lock/follow; old formatter replaced | Aligned readable sidebar, actual clipboard copy, retained death/OA names, grouped movement/blood, no narrative duplicate |
| Tooltips/details | Delayed hover, T pinning, clipped scroll, UI scale | DOM tooltip/accessibility and pointer ownership | Human labels, descriptions carry help, panels don't cover whole screen, stable bar while log opens |
| Playback/input | Intake separated from displayed state, stale painted-control guard, pause | Old queue/FSM replaced; UI gestures reused selectively | One spending gesture, focus/cancel safe, asynchronous SDK consumption during animation; history inspection not authority |
| Studio history | No encounter backward scrubber found; review playback exists | Workspace/timeline/undo widgets can be adapted | New absolute seek uses same reducer/compiler/sampler; equipment/vitals/conditions all active |
| HUD text and icons | Current exact media resolution and accepted portraits | Existing Pixi HUD layout/antialiased text and DOM detail panes; replace old icon bindings | New BG3-style bank, readable antialiased text, no UUIDs/underscores/debug banners; optional diagnostics only |
| Status/error | Current rejection messages exist | Browser transient notices/accessibility | Errors expire/dismiss, give native reason; no permanent “safe approach” banner; no blanket try/catch hiding faults |

## Gesture ownership and async previews

Keep one transient selection record: acting entity, exact discovered choice/ref,
native discovery revision/cursor, ordered prefix and local request sequence. A
preview reply installs only if all still match. Pointer hover may issue a newer
request; an older reply cannot repaint the new target. A committed command clears
spending highlights. Cancel/actor change/reconnect/authority change clears stale
gestures, while ordinary inspected selection remains separately meaningful.

Do not freeze camera/hover while waiting for network or animation. Debounce by
changed intent, cache within the current admitted revision, and avoid fetching
the same unchanged choices on every frame. Actual target legality belongs to the
server; a local scene hit only identifies what the user pointed at.

## Original complaint coverage remains mandatory

The prior plan's P01–P31 mapping is retained. In particular: doors/ally corridors;
known-area movement; party sight; geometry-aware grid and cutaway; startup/panning;
generic projectile orientation/palettes/speed; full admitted area art; zero-HP
turns; no duplicate Haste Dash; exact dice and known log identities; real goblin
encounter; informative crash ownership. Backend defects discovered by the browser
are fixed in the existing native owner, not patched over with client rules.

UI layout acceptance uses play, not a contact sheet: fighter + sorcerer explore,
open doors, loot, trigger a trap, split rooms and fight authored goblins. Check
mouse/keyboard at the actual screen size, with log and inventory both independently
opened. Record remaining defects by feature and evidence rather than declaring
completion from the presence of a button.
