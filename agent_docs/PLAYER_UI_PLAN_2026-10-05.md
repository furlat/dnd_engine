# Player UI implementation plan — second source pass, 2026-10-05

## Active grouped-bar / log repair — October 6, later user correction

This supersedes the single mixed shortcut row and the previous visual checkpoint.
The target is a coherent playable interface; source/test approval is not human
visual acceptance. Keep the current accepted icon/portrait artwork and materials.

| Requested behavior | Boundary and input | Observable acceptance |
| --- | --- | --- |
| Four distinct action blocks | Native discovery for Fighter/Sorcerer, owned items, resize, turn change | Base actions (including explicit melee/ranged), Spells, Class abilities, Items. Empty optional blocks disappear; world interactions stay in the world. Item-granted spells belong to Items. |
| Multiple compact rows | Two rows per block, constrained viewport and open log | Each block wraps independently; overflowing blocks have their own pages. No global page that replaces one category with another. Native rank/form variants remain one family. Hotkeys follow the visible positions. |
| Honest defaults | Initial discovery and inventory change | Include discovered usable families, even when temporarily unavailable. Owned-item membership follows current discovery; no dropped-item ghost controls. No duplicate ordinary/Extra Attack buttons. Existing pin preference applies to non-item families. |
| Designed combat history | Open log after movement, repeated hits, damage, reactions | Flush-right dock, aligned text gutter, quiet turn dividers, compact action/outcome lines, bounded child indentation and expandable math/detail. No repeated full tree dump by default. Native identities, ancestry and clocks remain authoritative. |
| Exact math and copy | Expand one row or turn on Dice, select/drag/copy, scroll | Native detailed wording and recorded dice/modifiers unchanged; canonical text selection and copied content agree with the visible text. Outcomes never recomputed; no second narrative formatter. |
| Surrounding UI consistency | Open inventory, item details, spell variants and tooltips | Measured readable type, matching margins/materials, no clipped content or overlapping controls at 1280×720, 1920×1080, 2560×1440. Repair concrete layout defects only; no new inventory mechanics or asset generation. |
| Fixed controls and glass panels | Toggle combat log; open inventory/choices/sheet | Bar position, wrapping and keys never change when the log opens. Log ends above the controls with a narrow text gutter. All open views share the same translucent surface; other HUD widgets must not show through beneath their controls. |
| Minimal permanent text | Idle HUD and action blocks | Category headers are icons with hover names. Persistent text is limited to useful state and necessary controls; explanations stay in descriptions/tooltips. |
| Hover choices, not a large selector | Hover any multi-choice spell/class ability; move into its options | A compact strip above the source button, with icons the same size as the bar. Shared level symbols for all spell levels and Sorcerer conversions; specific existing artwork for summon/form/element choices. No repeated spell art for rank, no title/cost/footer/Select panel. Clicking the final choice selects the exact native row. Earlier dependent facets update the remaining choices. |

Implementation: passive block membership in existing `action_bar.py`, shared
block geometry in `layout.py`, four page indices in existing focus, and the same
rendered hit records for pointer and keyboard activation. Existing HUD and native
command selection remain the only executor route. Existing `combat_log.py` keeps
its retained rows and timing gate; refine its fold policy and draw hierarchy,
without changing native producers. Verify real SDL input plus actual captured
framebuffers, including both party members and owned consumables. Read-only
anti-slop and anti-OOP/ECS reviewers examine this contract and the final source,
input evidence and screenshots. No other-chat communication.

Latest inventory extension: show equipped gear in a compact paper-doll slot layout
and carried gear as icons. Hover/click an equipped slot opens compatible carried
alternatives in the detail column, using `compatible_item_slots` exclusively;
clicking one uses existing EquipItem. No cross-character transfers or invented
slot rules. Use already accepted item/portrait icons. Category headings on the
bar become icons with hover labels; no persistent nonessential category text.
BG3 reference: https://bg3.wiki/wiki/Equipment and
https://www.reddit.com/r/BaldursGate3/comments/16ccd5x . PoE2 reference:
https://s3.amazonaws.com/obsidian-media/deadfire/deadfire-game-manual.pdf .

Additional user steering: the log is a translucent overlay, with a stronger
backing on hover and readable glyph shadows, not an opaque side block.
Contextual cursors follow existing admitted world actions
and selection previews; clear targeting/hover outlines during execution, including
the command-commit frame. Use platform arrow/hand/crosshair/unavailable/text states
without producing new cursor artwork. BG3 context references:
https://forums.larian.com/ubbthreads.php?Number=731397&ubb=showflat and
https://www.reddit.com/r/BaldursGate3/comments/1gzuf20 . These confirm contextual
feedback; this is not a claim of exact BG3 cursor artwork reproduction.

## Player-facing repair acceptance — 2026-10-06

The earlier UI implementation is not accepted. This repair follows the user's
play-session feedback and supersedes the character-creation entry flow below.

| Requested behavior | Observable boundary / input | Required result |
| --- | --- | --- |
| Play immediately with Fighter and Sorcerer | Normal `python -m game` launch | Two premades in an authored dungeon; no creation screen. Existing explicit demo encounters remain available. |
| Readable minimal HUD | Actual framebuffer at 1280×720 through 2560×1440 | Left party portraits, separate top initiative, compact bottom actions, no persistent debug/instruction paragraphs. Accepted icons retain their authored colors. |
| Deliberate weapon choice | Choose melee/ranged, then click a creature/object | Exact native attack slot; no automatic fallback. Preference retained per player. |
| Usable combat log | Open, scroll, expand, select, copy | Right-docked panel, consistent measured text and indentation, native compact summaries, inspectable original dice/modifiers. Copy works without selecting a row and excludes unrevealed entries. |
| Causal movement and blood | Move a path; take damage producing residue | One native movement parent with expandable steps/reactions; blood tile aftermath belongs under damage, not anonymous creature-condition spam. |
| Party understanding and visibility | Turn passes to the other human | Current command owner clear; no hidden-map disclosure through the inspection sidebar. |
| Worth playing | Follow dungeon route, inspect/loot, trigger trap, fight | Existing authored floor/walls/lights/props, native loot/trap/door actions, exploration leading to combat. No new campaign or AI subsystem. |

Implementation remains in the existing session, native log/projector, HUD and
encounter authoring owners. The later approved equipment-slot/item-grid and
hover-replacement view supersedes the earlier inventory-layout exclusion; native
inventory mechanics stay unchanged. New artwork, narrative rendering and generic
event/rules expansion remain outside this repair.

Verification: reproduce the reported input failures, run the relevant UI/native
contract tests, then inspect actual Pygame frames and exercise the real controls.
Anti-slop and anti-OOP/ECS reviewers independently review the final diff and
evidence; repair their actionable findings before declaring completion.

### Design checkpoint before pixel-density work

The user requires agreement on layout, proportions and materials before regenerating artwork. Use BG3-like small party/initiative portraits, with a lean WoW Classic PvP action strip instead of BG3’s hotbar. Keep current authored art colors; use quiet charcoal panel surfaces, thin neutral borders and restrained warm selection accents consistently. No new asset production in this checkpoint. One active-character highlight only: the portrait border; no duplicate vertical bar. Existing integer artwork scaling is provisional, not a final density standard: once the composition is accepted, audit pixel density across icon, portrait and chrome roles and consider dedicated resolution variants through 2560×1440. Text stays antialiased at display resolution.

### Historical implementation baseline

Historical status before the user’s rejection: implemented and independently reviewed. The [implementation and acceptance report](audits/PLAYER_UI_IMPLEMENTATION_2026-10-06.md) records actual module ownership, the native feature trace, the five persistent gameplay recordings, resolution samples and full regression reconciliation. Both final anti-slop and ECS/import-DAG receipts approve the delivered scope with its explicit limits. This document replaces the thin first plan and its appended amendments; the technical decisions below are retained as the approved contract.

## 1. Scope and fixed decisions

Deliver a coherent local tactical game interface in Pygame-ce: compact action bar, initiative portraits, rich combat log, direct world interaction, shared hover/selection/Alt highlights, inventory/equipment, character creation and supported progression. Use the current engine and retained player presentation. Environmental actions are NEVER placed in the action bar: opening/closing doors or chests, pulling levers, looting, lighting fixtures and crawling through windows are world click/context actions. Ctrl prepares an ordinary attack against a legal creature or destructible object.

The combat log is a principal feature, not a debugging panel. It has one source of wording and outcomes: existing observer-projected native combat logs. No narrative renderer, alternative outcome generation, second event executor, replay clock, rules in widgets, recreated Attack Object, ammo mechanics, new spells/classes or new artwork. Do not transplant NeuroClient's old network/state-machine runtime. The requested feasibility check found no easy whole-map/character restore path: gameplay save/load is deferred, with no substitute character-only save project. Existing passive recordings remain recordings.

### Source studies that form part of this plan

- [Combat log identity, nesting and timing](UI_COMBAT_LOG_CONTRACT_2026-10-05.md).
- [Targeting, world interactions and native command contracts](UI_TARGETING_CONTRACT_2026-10-05.md).
- [Character creation, progression, inventory and persistence feasibility](UI_CHARACTER_FLOW_CONTRACT_2026-10-05.md).
- [Complete registered icon matrix, direct features and grant-provider audit](UI_ICON_COVERAGE_2026-10-05.md).

These documents supply exact source functions and cases. The decisions below are the integrated implementation direction, not invitations to repeat discovery. Any later code change that invalidates evidence is a bounded new finding to record.

## 2. Baseline gaps and approved changes

This table records the pre-implementation gaps. Their delivered state and evidence
are in the implementation report; it is not a current outstanding-work list.

| Area | Existing owner | Concrete change required |
|---|---|---|
| Live encounter | game/session.py, game/encounter_play.py | Replace hardcoded left menu with HUD; keep native operation/capture/queue/reduction path |
| Action discovery | AvailableActionsResult / AvailableActionInfo | Preserve engine instances inside Session adapter; expose detached serializable values plus generation to views |
| Action selection | game/controls.py | Refactor existing selection reducer for explicit confirmation and context intent; do not retain a second menu selector |
| Multi-target | allow_same_target, num_projectiles, secondary_targets | Add selected_only/fill_primary policy and exact complete-prefix preview; preserve native repeat permission |
| Variant/disabled discovery | native spell/use variant generation | Publish typed variant facets, existing unexposed modes and known depleted spell ranks as non-executable choices with native reasons |
| Key conflict | encounter_play intercepts Space before controls | Live Space = End Turn only in neutral state; Enter = Confirm. Review playback pause remains review-only |
| Window traversal | TraverseConnector exists and has native tests | Register for standard live discovery and expose connector identity/landing choices; world-only interaction |
| Object use | source_item_uuid + SELF rows, OBJECT rows | Build object affordances from BOTH source-item and target-object relationships; no target-only matching |
| Picking | environment_selection_command/pick_environment_target, pick_support | One general interaction-frame hit map and highlight selection; account for actor pixels, object masks, depth and label hit regions |
| Initiative | Encounter.initiative_order; PlayerState current actor/round only | Add detached observer-authorized initiative rows; never hand live Encounter to widgets |
| Resources/sheet | native action economy and character state; limited PlayerActor | Project authorized own-character resources/sheet data once per native revision, rather than derive pools from action costs |
| Log | PlayerNode.combat_log; CombatLogEntry compact/verbose/detailed | Remove string stripping/text dedup/20-entry display; use canonical node rows, existing timing, rich text |
| Inventory | controlled_items, item presentation and native transfers | Add gated equip/unequip application wrappers, status/slot views; retain discovered drop/pickup/use |
| Creation | CharacterBuild, resolve_character_build, prepare/create_character | Add draft UI and selected builds to Session composition; explicitly expand native starting loadout plans once |
| Level-up | add_class_level and pure resolvers | Draft next level, validate then commit once; no invented XP awards/free respec |
| Persistence | legacy durable formats/server flow do not match direct character path | See feasibility conclusion; do not claim in-memory hydration is disk persistence |

## 3. Visual layout and interaction specification

### Geometry and styling

**Strict October 6 constraints:** maximize battlefield visibility. No patterned
backgrounds behind text, large empty live-game panels or persistent instructions
such as “Choose target.” Explanations belong in descriptions and hover tooltips.
Use readable native names, descriptions and content descriptor labels throughout;
never show UUIDs, hashes or implementation keys as player content. Image-generated
suggestions are styling references only: they may neither override these rules nor
invent equipment, descriptions or mechanics. Small flat cards, fine borders,
accepted pixel icons/portraits and antialiased text are the current direction.
Recorded native dice and modifiers are visible in the combat log by default
using native detailed wording. Child rows are open by default; collapsing them is an explicit user preference; the separate
detail control changes wording verbosity, with no regenerated maths or outcomes.
The new 41-creature portrait bank uses exact current content/rig associations
and its 36×48, 48×64 and 96×128 role files, alongside the original portrait bank.

Use a 1280×720 logical design canvas, transformed with one UI scale independent of world zoom. Layout computes rectangles from viewport dimensions; glyphs render at device-pixel size rather than scaling a low-resolution HUD screenshot. User UI scale 100/125/150%; resize invalidates layout/text wrapping, not engine state or targeting. Minimum supported logical viewport 960×540; below it show a resize prompt instead of clipped controls.

October 6 implementation steering supersedes the initial grid draft below.
The human rejected the bulky framed Pygame HUD. The default is now one compact
row of at most ten chosen shortcuts (eight on narrow layouts), not an automatic
catalog of every discovered action. The library supplies the full action list
and pin/unpin controls; native family/rank/form choices stay grouped behind a
shortcut. Icons touch without outer padding or gaps. Use the accepted CIE28
28-pixel artwork, integer nearest-neighbour scaling and its separate thin
pixel slot overlay. No large empty backplate, permanent panel-button strip or
boxed vitals. Show readable compact vitals/resources above the row; inventory,
sheet, reactions and the log open on demand. Preserve portrait turn order and
native world-click targeting. The earlier private Blender skin experiments
are rejected HUD directions, not accepted final artwork.

The delivered UI_ICONS_CIE28_PRODUCTION_HANDOFF_2026-10-06.md supplies the
accepted base bank and explicit mappings for 48 missing subjects; new choice
illustrations and the delivered Blender skin are review candidates. Preserve
originals and hashes in private source/production storage. Current native owners
replace stale handoff ContentRef hashes; no name-based alias or gameplay branch
comes from an artist manifest. Existing overhead condition VFX are untouched.
For straight Wall of Fire, discovery offers one directed line: its left side
burns, and reversing the ordered endpoints reverses that side. Omit an extra
left/right picker. Ring inside/outside remains a real distinct choice.

Text and damage remain antialiased at display resolution. Test 960×540,
1280×720, 1920×1080, 1920×1200 and the current primary monitor's 2560×1440.
Do not test/claim 4K or larger-than-monitor acceptance in this phase.


### Interaction priority, from first to last

Text input/modal focus → open context/variant popup → targeted selection → neutral UI controls → world intent → camera keyboard input. A handled event is consumed once. Mousewheel over a panel scrolls that panel; elsewhere zooms anchored at cursor. Camera WASD does not fire while typing/filtering. Pointer-down/up are captured by the same widget; a button release outside cannot click the map.

| Input | Neutral battlefield | During targeting / panel focus |
|---|---|---|
| Left click ground | Move to the native legal destination | Select required position/recipient instead |
| Left click hostile | Native main attack for selected melee/ranged preference | Allocate/select that admitted target |
| Left click own/allied actor | Inspect/focus; no attack | Select only if action admits it |
| Left click object | Native default world interaction | Select as target only if current action permits |
| Ctrl + pointer/click | Prepare main attack; choose admitted object/creature, including ally | Does not overwrite explicit spell targeting; cancel first |
| Right click | Context actions for clicked disclosed identity | Cancel targeting first; context only after cancellation on a later click |
| Alt held | Show disclosed interactive item labels and outlines | Keep current target highlighting; Alt does not cancel or commit |
| Escape | Open menu | Cancel targeting, close popup/modal in focus order |
| Enter | No action | Confirm valid allocation/choice; text input keeps Enter locally |
| Space | End Turn (only active human, latest playback, neutral state) | Never confirm targets or end turn behind a modal |
| Backspace | No action | Undo one allocation/point; text edit keeps its own Backspace |
| 1…0,-,= | Select first action row slot | Switch action cancels old uncommitted allocation |
| Shift + those keys | Select second action row slot | Same selection/cancellation semantics |
| Q/E, WASD, wheel | Existing camera rotation/pan/zoom | Camera allowed unless typing; does not mutate selection |
| Home / double-click portrait | Focus permitted actor | No command ownership change |
| I / N / K / L | Inventory / sheet / spellbook / reaction preferences | Toggle panel; do not submit an action |
| T | Pin hovered inspection tooltip | Same, without entering world-target mode |
| F1…F4 | Inspect/focus own roster slot | Cannot change whose combat turn it is |
| F12 | Existing developer diagnostic overlay | Replaces gameplay F3 conflict; F3 becomes roster slot3 |

BG3 is the interaction reference, not a wholesale binding promise: https://bg3.wiki/wiki/Options#Keybinds. This specification intentionally chooses Enter for target confirmation and keeps playback controls out of the player UI.

## 4. One world picking and highlight pipeline

### Inputs and ownership

Reuse `environment_selection_command` and item selection geometry for objects, `pick_support` for ground, current sampled actor pose/layers for creatures. Selection must follow displayed positions, elevation, camera quadrant, zoom and partial occlusion. Never identify from a sprite filename or diagnostic evidence tuple.

Add a passive `InteractionRegion` (kind actor/object/support, stable identity, placement/support, painter order, screen bounds and local coverage mask). Raster masks stay in the Pygame adapter; semantic `WorldHit` contains only identity/kind/support. Labels also map to WorldHit. The same region is used by ordinary hover, Ctrl attack, active targeting and Alt labels.

Extend existing DrawCommand with optional explicit selection identity/mask metadata, populated by actor/object command builders. Actor coverage uses physical body/equipment layers and excludes shadows, spell auras, overhead markers, trails and blood. Object coverage uses its registered selection mask. Window frame/insert and connector aperture are distinct identities/regions: solid pixels pick their foreground component, visible actor pixels through the aperture pick that actor, and an otherwise empty admitted aperture offers traversal. The window's Alt label/context still offers traversal when another actor fills its opening; the aperture is never an enlarged attack hitbox. Ground is a last-priority support hit, not a substitute for object pixels.

`game/app.py:draw_frame` already applies clip_actor_boundaries, split_actor_fixtures, terrain splitting and split_world_depth. Carry selection coverage through those same cuts and painter ordering; do not implement a second depth resolver. Return a small `SceneFrameResult` containing existing FrameEvidence (optional) and interaction regions (optional). Update its call sites explicitly; diagnostics continue using .evidence, never encode hit regions in debug output. Reuse emitted masks/regions for the frame. No need to redraw the whole scene when Alt is pressed.

### Selection/outline behavior

- Ordinary picking chooses the foremost eligible visible surface at the pointer. An ineligible opaque foreground object still obstructs normal picking; do not click through a wall just because a creature behind is a legal engine target.
- Inspectable disclosed items may be labelled even when currently out of reach; cursor/tooltip states Out of reach. Hidden items/traps, stale remembered object locations and undisclosed occupants never become Alt entries.
- Alt outlines all disclosed world-use/loot objects and destructibles with an appropriate available role. It does not enumerate every decorative floor pixel. Labels include name and default verb, remain clickable, and use existing label-placement helpers; cluster dense overlapping labels into a small selectable list, with stable object IDs.
- Hover adds a 2-pixel outline at 100% scale; selected target adds a stronger outline and allocation badge. Invalid current target uses blocked cursor plus reason, not only red. Precedence: current selection > hover > Alt background. One object never gets stacked competing outlines.
- No breathing/wiggle animation. No filled tile mask, whole-sprite colour multiplication, screen-space outline through foreground occluders, changes to cloud clipping or wall visibility logic.
- Raster work is limited to current visible regions and selected silhouettes; cache untransformed masks by exact bank/pose/frame/layers, invalidate pose/frame/equipment/integrity changes. A frame-local interaction set is dropped each frame. No unlimited full-screen per-entity buffers.

### World affordances and defaults

World use is authored as presentation disposition of existing action identities, not a second engine action. Each native row exposes/reuses an exact subject object UUID and verb kind; source-item SELF rows and object-target rows normalize at the application boundary. Current object state and admitted native rows determine which verb exists. No matching names like 'Open' or 'Jump'.

| World subject | Normal click | Context menu / Ctrl |
|---|---|---|
| Closed/open usable door | Open/Close if native row admits it | Inspect; attack via ordinary Attack if targetable |
| Intact breakable window | Inspect / indicate blocked traversal; do not auto-break | Attack ordinary window target; context shows native failure reason |
| Traversable broken/open window | Traverse through to permitted landing; if both sides/landings ambiguous show choices | Inspect; attack remaining frame if admitted |
| Lever | Toggle native device | Inspect; attack if admitted |
| Closed chest | Open | Inspect/attack; no loot-through-closed-container shortcut |
| Open nonempty chest | Loot native contents | Close/Inspect; report actual partial transfer |
| Ground item | Pick up | Inspect, native applicable item use if permitted |
| Usable environmental device | Execute selected native use; multiple equal defaults show small context chooser | Inspect, other native actions |
| Actor corpse | Native loot action only when supported/disclosed | Inspect; never fabricate corpse inventory from artwork |

Distant actions use one pending object intent with ordinary native Move then fresh action admission, not a macro bypass. Exact native contact/approach behavior is specified in the targeting study. Movement may trigger reactions/traps; interruption, death, turn end, object disappearance or loss of admission cancels remaining intent. Escape cancels pending future use, never rewinds completed movement. Never auto-Dash, spend a bonus action or walk through a hazard solely to satisfy a click without showing that cost/path.

## 5. Action bar, variants, tooltips and resources

Source rows remain AvailableActionInfo, not new spell/action UI classes. The Session adapter retains original live discovery and strips private execution templates before views consume a serialized/validated copy. Discovery generation is attached once to the detached result; command selections carry generation + exact row/target indices. Before execution verify actor, generation and current native admission. Persisted hotbar preferences use stable behavior/configuration/source-item/weapon-slot/variant identity, never transient discovery indices.

- Bar includes attacks, ordinary self/movement actions, spells, inventory consumables/item powers and a reaction-preferences shortcut. Exclude every environmental-use, pickup/loot object row and connector traversal from bar and its search; those remain accessible through the world context path. Ordinary Jump still belongs in common actions; window crawl does not.
- Family button chooses a concrete row through a small variant popover: cast rank, known native spell form, chosen weapon hand, metamagic or source item. Do not merge different physical items/charge pools. Item-source badge distinguishes a wand cast from a class spell; variants retain source UUID.
- Default order common combat actions → attacks by melee/ranged and hand → cantrips/spells by level/name → owned usable items. A custom slot remains in place when unavailable and shows why. No rearrangement every time targets/resources change. Newly acquired actions appear in the appropriate library section with a badge, not displacing pinned slots.
- Disabled icon: desaturated art, small lock/empty-resource cue; tooltip uses native availability_status. Source-affordable but no valid target differs from no charges/actions. Empty target list is not itself a reason string.
- Tooltip after 350ms: name/source, costs, range, concentration/duration where supplied, native description, variant choice and native failure reason. T pins; Escape closes; pinned tooltip does not capture world commands outside its bounds. Never calculate a missing hit chance client-side.
- Resource strip shows actions/bonus/reaction, remaining movement, spell slots and finite item charges from one authorized detached snapshot. Reuse public snapshot types identified in character study; add missing passive facts only. Do not sum costs from action rows to guess remaining pools. Restricted Haste/Action Surge/Slow budgets remain separately labelled when native owner distinguishes them.
- Melee/ranged selection is a UI default for next attack, not a fake equipment mutation. Execute exact discovered slot; native attack determines actual visual loadout. Two-handed and off-hand restrictions remain native.
- Reaction preferences use existing AvailableHandlerInfo and native toggle admission. They are explicitly labelled **automatic when enabled**. Add a narrow `_current_player`-gated Session command using existing `set_handler_enabled_by_uuid`; preserve current defaults. There is no current suspending human-reaction continuation, so this plan includes no ask-every-time dialog or nested event loop. A later reaction-choice system would need its own scope.

## 6. Targeting: final interaction contract

Extend the existing selector in controls.py; view draws its state, Session executes it. States: neutral, choosing_variant, choosing_targets, choosing_positions, confirming, pending_world_approach, waiting_for_native/playback. One discriminated state prevents simultaneous action and context selection. No second state machine executor for the engine.

The native discovery contract reuses `num_projectiles` for maximum and `allow_same_target` for repeat permission. Add only `allocation_completion: selected_only | fill_primary`, supplied by native owners. One primary is required by the current entity-target actions; do not add speculative minimum/exact-count rules. A native complete-prefix preview supplies confirmation validity and actual effective allocation/geometry. Derive these from native selection/execution owners, not a client spell-name list. No expansion from 'single selected' to 'all projectiles' without showing the resulting allocation before commit.

| Family | UI selection / confirm behavior |
|---|---|
| Ordinary single target/point | One click executes a fully configured admitted row; self action executes on button click |
| Projectile fill (Magic Missile, Scorching Ray, Eldritch Blast) | Keep ordered clicks and per-recipient counts. Confirm preview shows unallocated projectiles going to primary, matching native expansion. 'All here' fills explicitly; A/B/A stays exact. Enter/Confirm commits; max count alone does not silently fire |
| Up-to-N recipients | Confirm 1…N admitted targets; obey the exact row's repeat flag (Aid/Longstrider/Fly currently allow repeats). Unselected capacity remains unused |
| Chained secondary targets | First click fixes primary; secondary options come from its secondary_targets. Undo primary clears dependent choices. Confirm respects native maximum/uniqueness |
| Wall/path points | Show segments, count/length and native next-point options. Backspace removes last point; one-point caster-direction rule remains native. Shape selection is a native variant, not an angle inferred from number of clicks |
| Summons | Choose exact native form and slot, then one destination for one creature. Preview that creature at that destination; no group count/scatter/multiple-placement interface |
| Entity plus destination | Select entity then native admitted destination. Preserve Dimension Door's legal unseen destination semantics without revealing unseen map contents; native destination geometry can render a neutral cursor without requiring a visible tile |

While selecting: a small native ability name and allocation count, selected world markers, Backspace undo and explicit Confirm/Cancel. Explain remainder allocation and native costs in descriptions/tooltips; do not add a persistent instruction paragraph. Never spend resources before final native execution. Reject stale generations cleanly and show why. If a target becomes invalid, clear affected dependent selections and require reconfirmation; do not substitute a different target. Camera rotation/pan/zoom preserves UUIDs/world positions and updates markers.

### Bounded discovery work included in this proposal

These are explicit native API/content repairs needed for the requested UI, not hidden widget rules:

| Change | Owner and exact limit |
|---|---|
| Complete selection preview | One application entry `preview_available_selection` over the original retained row and ordered prefix. Return `can_confirm`, disclosed reason, effective ordered targets/positions and admitted next choices. Delegate to existing entity/position selection owners. Reuse only proven pure validation; extract a shared pure predicate where current validation is eventful. No costs, registered events, RNG or hypothetical live-actor mutation during hover |
| Variant facets | Extend existing `ActionDiscoveryDescription` / `AvailableActionInfo` with typed form/side/radius/summon-form/damage-or-ability-choice facts. Spell rank, weapon slot and source item already exist. A popover selects the actual variant; it never reconstructs one from labels/private templates |
| Known but depleted spell ranks | Extend existing variant generation to describe known ordinarily available ranks even when slots are exhausted, retaining the same native availability reason and a non-executable state. Do not invent higher ranks, missing spells or item copies. Revalidate through ordinary discovery at submission; UI cache does not confer availability |
| Existing unexposed choices | Publish Enhance Ability's six existing ability values and Enlarge/Reduce's two existing modes as native variants. Preserve their current recipient semantics. Hold Person/Invisibility upcasting changes are outside this UI proposal |
| Existing count-hook defect | Connect Beacon of Hope and Divine Word's authored six-recipient cap to `get_multi_target_count` used by discovery. Test native admission/execution and costs. This explicitly changes their currently erroneous discovered cap of one; no other spell count or balance change is bundled |
| World affordances and approach | Publish exact world disposition, clicked-identity binding and context/default verb. Extract observed world-item use descriptors before the current hand-contact gate; they are non-executable until ordinary rediscovery at contact. Filter existing exact Move targets through native contact with an explicit origin; preserve safe-path preference, costs/hazards. Window approach uses actual connector endpoints and Ctrl attack its own native reach/access |
| Connector/reaction exposure | Register existing TraverseConnector with a real behavior identity and expose existing ConnectorTraversalDiscovery. Add the handler-toggle application command above. Neither adds a new movement/reaction rule |

The native preview does not claim an arbitrary action's full `_validate` is harmless. Tests must establish no mutation for repeated hover/prefix queries, including invalid prefixes. Detailed source functions, wall budgets/forms and exact world IDs are in the targeting contract. The human approved this scope; implementation and acceptance are recorded separately.

## 7. Combat log implementation specification

Detailed producer audit and timing table: linked log contract. Canonical visible rows come from PlayerNode.combat_log, one record per exact node identity within generation. Existing central sub_entries contain descendants; do not recursively render them alongside the node list. Group by nearest logged native ancestor; reaction roots attach using triggered_lineage_uuid and presentation_group ancestry. Missing parent stays a visible standalone entry, not discarded.

The new panel replaces `_log_lines` and its rendered three lines. Native logs remain untouched as wording authority. Store selected verbosity and expansion per entry, not newly generated sentences. Native detailed wording is default so recorded dice/modifiers are visible. A separate detail control selects verbose wording; causal child rows are open by default and individually collapsible. Standalone queue-only immunity results require the small projected capture repair named in the log study; do not silently omit them.

### Rendering and history

- Parse only the existing documented bold/colour/dim tag vocabulary and `**bold**` into TextSpan(text, style). Unknown/malformed/unsupported nesting stays readable literal text; no HTML renderer/eval/regex-driven outcome generation. Measure line wrapping after tokenization. Fix the one documented doubled-brace producer typo at its source instead of adding generic repair heuristics.
- 18px body, line-height 22; 10px horizontal padding, 6px between root groups, 4px child indent step capped at 3 visual depths then show breadcrumb. Numeric roll details use a monospaced secondary face/columns when supported; normal prose remains proportional.
- The expansion control collapses/reopens causal children; row clicks select recorded text; actor/target chips use projected UUID fields. Do not make participant links by searching equal names in text. Hover chips focuses no hidden entity; click inspection uses permitted current/recorded data with a historical label.
- Turn headings ('Round 2 — Sorcerer') use existing turn facts, not wallclock time. A cast parent never includes a final child damage total before impacts reveal it; reveal gating uses exact causal descendants as described in study.
- Use existing presentation milestones and completion boundaries. Keep one local clock and group offsets; native execution being complete is not permission to display its future damage. Animation skip uses the same final visible cursor. Cancelled/interrupted events show their actual outcome once **only when a native combat_log entry exists**; a silently cancelled cast gets no invented sentence.
- Filters: All, Attacks, Spells, Damage/healing, Conditions, World/items; optional exact actor focus. Filters never delete records or change native grouping. Keep child context when filtering; no misleading empty root row.
- Scroll is pixel-based with variable row heights and a first-visible-entry anchor+offset. New rows auto-follow only when at bottom. Otherwise badge '+N new'; jump-to-latest clears it. Resize/expand/filter preserves anchor when possible.
- Retain 10,000 canonical rows per encounter; evict oldest complete groups if necessary, display 'Earlier entries omitted' and keep native replay independently. Only rasterize visible rows plus one screen of overscan. Cache at most 512 text-layout/surface entries keyed text/style/width/UI scale; never retain a full Surface per historical entry indefinitely.
- Text selection/copy within log; Ctrl+C copies visible-selected plain text, not secret structured payload. Ctrl while log focused never becomes forced world attack.

Acceptance must include identical damage hits, A/B/A, multi-target batch, saves/no-damage, resistance/immunity, reaction interruption, concentration loss, object destruction/loot, summon/despawn, hidden actors, simultaneous same names, long rolls, cancellation, replay/skip, observer change if supported, resized/high-DPI scrollback. Each case checks both existing projected entries and intentional absence: `combat_log is None` never becomes a row, including state-only destruction/transfer/summon outcomes without a native producer. This UI does not add missing narration. Full existing log details must remain legible in actual recordings, not only assertions.

## 8. Portraits, initiative and character screens

### Initiative and ownership

Initiative order comes from the native Encounter, projected to the authorized observer/controller. PlayerState presently exposes current actor and round, not the whole order; add detached order rows with disclosed UUID/portrait/name and current state. Exclude unknown identities/order slots rather than leaking invisible roster length. Do not infer initiative from portrait ordering in an old scenario asset directory.

Use separate visual states: gold active-turn border, white selected-inspection border, red target reticle, dim/marked dead or removed. Health bars use presented HP at its commit time. Summons enter/leave native order; no UI re-sort by name or initiative estimate. Scrolling/focus preserves stable UUIDs. Portrait click inspects; double click centres. Actor command ownership remains the current native human turn. Do not merge observers' hidden map/log data to make party UI convenient.

### Creation and progression screen sequence

Roster/start → New character or premade → identity/species/variant/background → point buy → supported class/choices → starting equipment → appearance/portrait → review → Confirm/Start. Back/Cancel retains only an uncommitted draft. Use current cold choices and resolver; invalid choices are shown with native explanation. Selecting a starting equipment package expands CLASS_STARTING_LOADOUTS/BACKGROUND_ITEM_LOADOUTS into build.item_loadout ONCE. Reloaded existing possessions are never replaced with starting gear.

Supported today: Fighter/Champion, Barbarian/Berserker, Sorcerer/Draconic; nine species; four supported species variants; Acolyte/Adventurer. No legacy unavailable classes in disabled endless lists. Optional premades are regular CharacterBuild values. Respect native 27-point buy, total level 20 and multiclass prerequisites.

Character preview uses immutable appearance data and existing render layers, no live-runtime reset while an encounter exists. Portrait selected independently of mechanical build. Sheet displays class levels, ability scores/modifiers, defenses, movement, native resources, passives and equipment from authorized snapshots. Fields unavailable in current snapshot get explicit passive projection additions from the character study, not widget-side live entity queries.

Level-up modal shows before/after, automatic grants and required choices, validates a full candidate then calls add_class_level once. Cancel changes no native state. This UI phase exposes pre-encounter chosen build level; an earned in-session level button requires an actual native entitlement. It does not invent XP awards or free respec. Existing APIs alone are not proof of a campaign progression policy.

### Inventory and loot

Own inventory uses controlled_items/current item presentation; unknown inventory is not an empty list. Show stack/charges, equipped slot, coating/enchantment text and icon inherited from exact native item identity. Click Use invokes existing action; Equip asks native compatible slots; Drop enters native legal position selection. Equip/unequip gain narrow `_current_player`-gated Session operations with capture. Never mutate slots directly. If unequip would fall to ground because inventory is full, show that actual outcome before confirming.

World chest/loot panels open from clicking the world, not an actionbar inventory surrogate. Closed chest Open then re-query; Loot All reports actual transferred subset/capacity and leaves failed transfers in container. Item transfer refreshes both ground highlight and inventory, using one native ownership source. Missing ground items cannot remain as stale selectable labels.

## 9. Assets and icon coverage — no future inventory prerequisite

Recovered 528 WebP icons plus 56 portraits; originals preserved. 515 indexed icon files verified byte-for-byte against the existing authenticated index; 13 extra recovered files are unindexed and must not become implicitly trusted. Asset receipt and audit scripts are in ignored `.runtime/ui-study-20261005/`; installed copies are ignored `game/assets/ui_recovered/`. Public Git receives compact bindings, not PNG/WebP/previews/full catalogs.

The linked inventory now enumerates all configured registered behavior rows, all 95 default creature factories (1,631 action occurrences), all 374 direct item builders (36 stored action templates), and 49 distinct feature/feat IDs from current class tables. Zero materialization failures. Dynamic world providers were inspected separately; all their declared action identities are in the registered matrix. Fixture content is labelled and excluded from production artwork requests. Registered conditional/temporary actions remain included even when no default monster currently grants them.

### Concrete mapping decisions

- ContentRef definitions reuse `dnd/content_system/icon_bindings.py`, existing authenticated asset index/ledger and descriptor presentation. No legacy display-name lookup or runtime fuzzy matching.
- Direct class feature IDs intentionally lack registered ContentRefs after cleanup. All 49 have existing art candidates in the old ledger. Add explicit presentation records keyed by those current semantic IDs using existing ContentPresentation fields; DO NOT resurrect retired class factories or fabricate ContentRef hashes. This is presentation data in `game/data/ui_presentation.json`, validated against native current feature IDs and the same asset index. It is not a second mechanical feature registry.
- Registered creature/item presentation, including `portrait_key`, stays on its existing descriptor/ledger even when the field needs filling. The UI document owns only direct feature/item semantic IDs that genuinely have no ContentRef descriptor, player portrait choices and common UI keys. It contains no duplicated ContentRef rows or new mechanical creature definitions.
- One explicit resolver dispatches on `content_ref`, `direct_feature`, `direct_item` or `portrait_choice`. `content_ref` uses only the current authenticated descriptor/index; direct kinds use only their exact validated UI record; `portrait_choice` uses its authored portrait asset. A controlled player's explicit portrait preference overrides its default portrait only. Missing keys return a labelled placeholder; there is no search across names, fallback ledgers or reconstructed ContentRef hashes. The author selects the correct reference kind once rather than runtime-probing for whichever works.
- Attack uses selected weapon/unarmed icon; spell-granting item uses spell icon with source-item/charge badge. Shared icon is explicit coverage, not a missing-art waiver. Multiattack uses its authored configuration/creature attribution; absence stays a gap.
- Existing broad class-icon substitutions (Dragon Wings using Haste, ancestry elemental spells, generic sorcery-points emblem) remain disclosed provisional choices. User permitted the old icons for now; no new weapon/icon art generation.
- Truly missing spell/action files are listed in the inventory. First search recovered unindexed icons and authored prior key aliases offline; if no semantically valid accepted image exists use a labelled neutral placeholder until user-provided artwork. Placeholder never counts as final icon coverage. Condition HUD icons are separate from overhead Godot markers; no changes to those VFX.
- Register selected images through current ImageResourceSource/AssetSpec media registration and private production installer. Recoverable originals already exist; do not overwrite public behavior files with importer output. No new packer or art production needed.

## 10. Data flow and module ownership

One-way flow: native Session command/discovery → detached permitted UI facts + retained lineages → existing reducer/binder/presentation timing → passive UI selection/layout → Pygame raster/input. UI commands return to Session; widgets never execute domain methods themselves. Rendering facts and command affordances have separate revisions; do not overwrite historical display with live HP/conditions.

The required passive additions are bounded:

- **Controlled sheet:** reuse `AppliedOriginState`, `AppliedClassLevel`, AbilityName/skill/save values and evaluated proficiency data in an optional authorized snapshot. Existing PlayerActor HP/AC/conditions/visual_loadout/controlled_items remain the sole owners of those fields. Capture evaluated changes through the existing observation/projection/reduction route, not from build formulas in widgets.
- **Resources:** native evaluated current/capacity/spent values with stable resource names, plus existing movement/handler information. Item charges remain in ItemPresentationState. Snapshot carries generation, observer, actor and native revision; gate display to the corresponding existing committed presentation boundary, or conservatively operation completion when no earlier exact boundary exists. Never refresh a historical panel from live entities.
- **Initiative:** projected tuple of disclosed actor identities in native relative order with existing current-actor/round state. Omit undisclosed counts/order gaps. Update on membership/turn changes and newly admitted observations. Party inspection requires a Session membership check and only returns controlled sheet data; it does not change the map observer or combine fog histories.
- **Log:** optional copied `PlayerNode.turn_execution_id` for real turn headings; expose existing lifecycle cue starts from `presentation_timing`. Ordinary log identities remain node UUIDs. The one unregistered immunity producer uses the existing Encounter listener and an observer-projected append with encounter-log index and operation-end gate. Carry it as a defaulted optional field on existing recorded/player sequences and Operation; no parallel transcript, synthetic event or second wording source.

Every replay-visible addition uses the existing packet serialization/version-compatibility policy and is checked with round trips and old packets. Current command affordances are intentionally separate from recorded display facts; generation validation prevents submitting an option from a previous intake revision.

| File/module | Implementation responsibility | Forbidden responsibility |
|---|---|---|
| game/session.py | Gate active human; discovery-generation association; equip/unequip and selected-build composition adapters | Pygame drawing, UI layout, new rules |
| game/controls.py | Sole target-selection reducer; commands/cancel/undo/confirm on exact native options | Backend mutation; separate per-spell targeting branches |
| game/ui/types.py | Small passive HUD state/intent/rect records; references reuse existing contracts | Live Entity/Session, registries, executable callbacks in persisted data |
| game/ui/layout.py | Theme, scaling, panel geometry, focus rectangles | Spell or action semantics |
| game/ui/rich_text.py | Existing safe tag parser, spans, measured wrap, hit/copy ranges | New combat narration, outcome math |
| game/ui/combat_log.py | Canonical projected row view, grouping/timing indices, expansion/filter/scroll | Duplicated native log storage/executor, objective entries |
| game/ui/action_bar.py | Slot/family/variant views and tooltip; world-action exclusion | Weapon/slot/attack economy rules |
| game/ui/hud.py | Authorized order/portrait/vitals view; consolidated here instead of a separate initiative.py | Initiative calculation or actor control mutation |
| game/ui/world_interaction.py | WorldHit → exact native option/pending intent, context rows | Shadow/object-name heuristics, native pathfinding duplication |
| game/interaction_frame.py | General hit-region composition and outline sampling | Domain actions, secret world lookup |
| game/ui/character.py | Creator/sheet/level draft view and intents | New progression/persistence model |
| game/ui/panels.py | Item/slot/loot view + command intents; consolidated here instead of a separate inventory.py | Ownership mutation or item-effect regeneration |
| game/encounter_play.py | Existing loop; input precedence, command dispatch, playback and UI assembly | Per-widget rules or new monolithic parallel UI |

Small helper functions remain in their owner until real reuse justifies splitting. No widget inheritance framework, service locator, generic callback bus, late imports or cycle workarounds. Existing private execution templates remain at Session boundary; passive serialized copies go to views. A module import contract test verifies dnd never imports game/UI and UI view modules never import live engine owners. No type-check/getattr dispatch to hide missing authored fields.

## 11. Save/load scope boundary

The user prefers saving the WHOLE encounter (map and characters), accepts replay only if needed, and explicitly rejects a large diversion. In-memory class hydration is not whole-world restoration; a passive observer replay cannot regenerate undisclosed rules or mutable owners. Do not implement character-only persistence as an unrequested compromise. The character feasibility study records the actual existing hooks and conclusion; if full save is not a small supported integration, this UI delivery has no working Save/Load claim or pretend buttons. Keep creation/deployment/current-encounter inventory functional and issue a separately scoped full-save design later. No changes to death/rest/elapsed-time settlement policies implied.

**Feasibility result: defer gameplay persistence.** `decode_sequence` produces a passive presentation target, not a playable Session. Map snapshots do not restore conditions, controllers, item contents and native handler owners; the legacy durable character format is incompatible with the current direct class composition. Re-executing event outcomes is not a deterministic command journal with initial world/RNG/identity reconstruction. There is no small existing inverse to wire. Do not start a new snapshot framework, replay-driven mechanics loader or character-only durable format in this UI phase. No further persistence decision blocks UI implementation.

## 12. Implementation sequence with concrete exit checks

Each step receives anti-slop and ECS review before building the dependent step. Fix findings within the approved slice; do not broaden into AI/renderer/rules refactors.

1. **Native exposure repairs.** Add only the contract fields/registration proven missing by targeting and character studies and explicitly listed in section 6: partial-allocation disposition, complete-prefix preview, typed facets/depleted choices, named mode/count exposure fixes, connector discovery, world affordances/approach, reaction toggle, detached initiative/resource/sheet facts, queue-only log capture. Preserve rule execution except the two explicitly named erroneous target caps. Exit: native command tests prove partial/max/repeat targeting; preview purity; unavailable/mode/facet coverage; window discover/execute; own/unknown projection; no private templates in UI payload. No widgets needed to prove this.
2. **Media binding + interaction geometry.** Validate current feature/icon references, register copied art, emit post-cut interaction regions and bounded mask cache. Exit: all 4 camera quadrants, window hole/body behind, overlapping ground loot, destroyed/open state, small/large/prone/flying actors, cliffs and hidden objects. No art regeneration or VFX timing edits.
3. **UI shell + world clicks.** Introduce layout/focus; remove old menu event handling as new selector takes over. Neutral click/context/Ctrl/Alt and pending approach use native commands. Exit: one physical click causes at most one intended command; panel clicks cannot reach world; window/lever/chest actions absent from hotbar; Space/Enter regression covered in actual encounter loop.
4. **Combat log.** Replace old text display and deque; integrate exact release indices with existing playback. Exit: all log cases in study, 20-minute synthetic scroll history bounds, repeated row preservation, same final rows after skip/replay, hidden identities safe. Visual acceptance at supported widths and scales.
5. **Action bar + initiative.** Family/variant choice, resource strip, disabled reasons, stable slots, portrait selection/focus. Exit: full multi-target UI/native execution matrix, variant/sourceitem identity, turn gate, summon initiative changes, no premature HP/resource reveal.
6. **Creation/sheet/inventory.** Wire supported build choices, explicit loadout, draft validation, selected party composition, inventory operations, pre-encounter level selection and permitted native level-up path. Exit: create→deploy→equip→drop→pickup→use→end encounter; cancellation leaves state unchanged; second party member inspect cannot mutate out of turn. No unsupported Save/Load claim.
7. **Final acceptance.** Remove superseded controls/log rendering, inspect imports and bounded caches. Run all affected game/progression/architecture tests; record exact commands/results. Capture approved native gameplay sessions in existing persistent gallery, with scenario manifest identifying each acceptance row. Both independent reviewers inspect integrated behavior and source, not only this plan.

## 13. Acceptance gallery and reproducible test grid

| Recording/case | Required visible proof |
|---|---|
| HUD overview at 1280×720, 1920×1080, high-DPI | Readable log/bar/portraits; no overlaps; stable selection on resize |
| Door/window/lever/chest lane | Hover/Alt/context; open/close; attack same object via Ctrl; window crawl via click; no world buttons on bar |
| Occlusion/selection lane | Window aperture, actor behind wall, near/far objects, overlapping loot; no shadows/aura picked, no hidden labels |
| Move→interact lane | Preview approach/cost, native movement, final use; interrupt/cancel/dead actor/removed object prevents follow-up |
| Projectile allocation | All-on-one, A/B/A, partial fill preview, undo, max-count explicit confirm; original native costs/outcomes |
| Multi-target/position lane | Under-max buff, native repeat policy, chain dependent targets, successive one-creature summons with different forms, wall points/ring variant, telekinesis, unseen teleport destination |
| Combat-log lane | Repeated equal damage, save/immunity, reaction, concentration, destruction/loot; expanded roll details legible and synchronized |
| Item/turn economy lane | Main/off/ranged sources; class vs item spell; charges depleted; Haste/Slow/Action Surge resources from native state |
| Character lane | Nine-species supported options; representative three-class builds, required choices, starting equipment once, cancel, two-party deploy |
| Inventory lane | Equipped effects, drop/pickup transfer, partial loot/capacity, unequip ground-fallback warning |
| Stress/accessibility | 10k row history with bounded surfaces; keyboard operation; clipped tooltip/scroll handling; colour-independent meaning |

Use existing tests/game/test_controls.py and test_encounter_play.py for input semantics, test_session.py for gated native integration, test_item_pickup_playback.py for ownership/visual synchronization, tests/progression for creation/progression. Add only externally meaningful behavior assertions; no tests mirroring widget implementation. Source inspection receipts and audit scripts are small; screenshots/videos/generated inventories stay under ignored runtime output. Final completion means reviewed native behavior plus inspected actual screenshots/recordings, not 'tests passed' alone.

## 14. Review receipts

Both fresh independent reviews approved the revised technical contract after corrections:

- [Anti-slop review and recheck](UI_PLAN_ANTISLOP_REVIEW_2026-10-05.md): approved; no unresolved design blockers. Corrections covered target allocation, one-creature summoning, disabled/variant discovery, exact icon ownership, input precedence and intentional absence of native log entries.
- [Anti-OOP/ECS/import-DAG review and recheck](UI_PLAN_ECS_REVIEW_2026-10-05.md): approved. Verified passive snapshots, exact native execution ownership, shared selection geometry, disclosure, pure selection preview and the deferred persistence boundary.

The anti-slop receipt records hashes of the technical plan and four studies at
design review. Those are historical design approvals. Implementation source and
sampled visual receipts are now [anti-slop](audits/UI_IMPLEMENTATION_ANTISLOP_2026-10-05.md)
and [ECS/import-DAG](audits/UI_IMPLEMENTATION_ECS_2026-10-05.md); the
[implementation report](audits/PLAYER_UI_IMPLEMENTATION_2026-10-06.md) supplies
the completed test partitions, failure closures, physical input evidence and
explicit remaining native/content limits. No save/load or whole-game perfect
content claim follows from these UI approvals.
