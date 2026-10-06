# Native targeting and world interaction contract — 2026-10-05

Status: source study and concrete implementation recommendations for the UI plan. No production code, gameplay rule, artwork, or test was changed. Source was read on the shared checkout on October 5; line references identify the reviewed owners, not a frozen commit. Existing tests cited below were read, not rerun. Read with `RECOVERY_PLAN.md` and `HOW_TO_TEST.MD`; later historical completion claims do not establish current UI coverage.

The human's latest correction is binding: environmental interactions are world clicks, never action-bar commands. Alt highlights items. Hover, targeting, and Alt share picking/highlight machinery. Ctrl chooses an attack on doors/windows; an ordinary click opens a door, operates a lever, or traverses an admitted window. The recommendations below implement that distinction with exact native identities and data, without parsing action names.

## 1. Owners and the boundary that must survive

| Owner | Current contract and evidence |
| --- | --- |
| `game/session.py:144` | `_current_player` admits only the actual human owning the current active turn. `discover_player_actions` calls native discovery. `execute_player_action` checks the primary belongs to the exact row, forwards ordered extra UUIDs and positions to `execute_available_action`, checks deaths, and returns actual terminal roots. No target rules belong in controls. |
| `game/encounter_play.py:193` | Human input opens only at `waiting_for_player and active is None and not pending and not paused`. Native decisions can advance independently of historical playback. After a submitted action, choices are discarded and rebuilt at the next displayed human boundary. |
| `dnd/actions_functional.py:252` | The functional `get_available_actions` wrapper exposes `legal_only`, default false. The underlying `Entity.get_available_actions` also has `target_filter` and `include_dead`. The game wrapper currently does not expose those. |
| `dnd/entity.py:7668` | Current discovery generates native variants, groups self/entity/position/object/item-use rows, then appends toggleable handlers. The UI must keep all discovered choices reachable, including new grants and item forms after a state change. |
| `dnd/core/base_actions.py:2578` | `AvailableTarget` supplies identity, kind, indexed position, shortest/safe paths and costs, hazards/opportunity exposures, AoE affected positions and recipients, and optional primary-dependent `secondary_targets`. |
| `dnd/core/base_actions.py:2614` | `AvailableActionInfo` supplies exact behavior/provider/root/configured-content identity, execution token, category, attack flag, costs/status, target type, position-selection data, cast level/concentration, multi count/repeat permission, and source item. Private `execution_template` preserves the exact discovered native variant. |
| `dnd/actions_functional.py:533` | `execute_available_action` preserves the exact discovered source and clones the target allocation. Item actions use the native item-use path; other rows use the bound template. Controls must not reconstruct spells/items from display strings. |
| `game/controls.py:19` | Current passive menu state holds one selected row, ordered target indices, ordered positions, and a cursor. The proposed UI can replace how that state is presented; it should still submit one native command through the same session boundary. |

The renderer continues consuming retained player facts. Engine queries occur at the admitted application boundary; drawing, hover, and hit tests must not query live entities to improve a historical picture.

## 2. Current selection behavior, including integrated limitations

`game/controls.py:68–103` implements all ordinary selection using row data. A single target executes immediately. `MULTI_ENTITY` appends target indices in order, permits repeats unless `allow_same_target is False`, and executes automatically on reaching `num_projectiles`. Before that, Space is intended to confirm the current prefix. Primary-dependent targets can execute early when the secondary pool is exhausted.

There are important differences between helper behavior and the actual application:

1. **Partial confirmation is not connected in the live loop.** `game/controls.py:151` accepts Space for a partial entity allocation, but `game/encounter_play.py:219` first toggles pause; dispatch then requires `not paused`. A Space press while ready pauses instead of confirming. The separate controls/Chain Lightning tests exercise the helper without this interception. The new plan needs an application-level input test.
2. **Escape exits the application.** `game/encounter_play.py:212` currently treats Escape as quit, not cancel selection. A targeting cancel interaction requires changing input precedence.
3. **Multi-target Backspace clears all entity picks.** Position Backspace removes one last vertex, but entity Backspace resets the whole tuple (`controls.py:135`). Ordered single-step undo is a proposed improvement.
4. **Generic distinct-target options still include selected entries.** Duplicate rejection happens at click time; only the dependent secondary list filters already selected indices (`controls.py:76`). Up-to-N selection does not auto-finish merely because every generic unique candidate has been selected.
5. **The UI does not validate a whole entity allocation before submission.** The native command validates allocation count, membership and repeat permission (`actions_functional.py:500`); the concrete action then validates combinations. Acid Splash, for example, can currently offer two individually valid creatures too far apart for one cast.
6. **Map picking needs a visible support for most targets.** Objects with explicit masks get the earlier mask pass. Creature/entity picks fall back to target-position equality against a picked visible support (`controls.py:172`). This does not cover overlapping creature silhouettes or all permitted nonvisual/touch selections.
7. **Current area preview is data-driven but limited.** It draws only disclosed `affected_positions` on visible supports. It does not recompute area geometry. Ordered wall preview shows chosen vertices/connecting lines, not the full native shell, heat side, or formation displacement.
8. **Unavailable preservation has native exceptions.** `legal_only=False` preserves many explanatory rows, but ordinary leveled-spell generation emits only levels with an available slot (`actions.py:5284`); object collection emits only affordable rows with targets (`entity.py:7188`); nearby world item use is omitted outside hand reach (`entity.py:7322`). A full spellbook or remote object affordance browser cannot be truthfully described as a cosmetic grouping of today's `all_actions` alone.

## 3. Target families and exact native semantics

### Single self, creature, object, and position

`TargetType` is declared at `dnd/core/base_actions.py:197`. Existing families are SELF, ENTITY, CREATURE_OR_OBJECT, OBJECT, POSITION, POSITION_PATH, POSITION_LOS, POSITION_AOE, MULTI_ENTITY. `actions_functional.py:403` binds each directly. A self item action can have a world `source_item_uuid`; SELF does not imply an action-bar self buff.

Single creature/object targets use their exact UUID. `CREATURE_OR_OBJECT` admits object contacts through native physical access; `Attack.object_target_policy="active"` permits striking invulnerable active objects as an attempted attack (`actions.py:1978`), so Ctrl must not silently restrict its targets to damageable objects. Costs, reach, LOS, weapon eligibility and object contact remain native validations.

POSITION_PATH identifies a movement route; it is not the same as `position_selection.kind="path"`, which describes extra selected vertices. Movement targets already carry shortest/safe routes, costs, hazards and opportunity-attack exposures. Native execution prefers an affordable safe path by default, otherwise the shortest disclosed path (`actions_functional.py:349`). The current menu displays the shortest `path_cost`; a replacement movement preview must show the route actually selected by this preference.

POSITION_AOE already exposes affected cells and permitted recipients. It does not authorize the UI to discover hidden recipients or predict authoritative hidden obstacles. SELF AoE and directional AoE remain native discovered rows; no new cone/circle rules are needed in the UI.

### Projectile allocation: single target expands, partial allocation fills with primary

| Native owner | Count | Resolution of submitted prefix |
| --- | --- | --- |
| Magic Missile, `dnd/spells/evocation.py:556`, `get_all_targets:601` | Native `get_num_projectiles`, base three and slot scaling/overrides | `[A]` becomes `[A,A,A]`; `[A,B]` becomes `[A,B,A]`; `[A,B,A]` stays ordered. Remaining darts always fill with the primary. |
| Scorching Ray, `evocation.py:697`, `get_all_targets:744` | Native ray count | Same primary-fill behavior. Every resolved ray remains an application. |
| Eldritch Blast, `evocation.py:2775`, `get_all_targets:2805` | Caster-level beams, explicit target-count override when present | Same primary-fill behavior; ordinary scales are 1/2/3/4 beams at levels 1/5/11/17. |

All three permit repeats. They do not have a separate discovered "single target spell" and "multi-target spell" alternative; one exact row accepts an ordered allocation. Do not invent a second spell variant, a separate executor, or a client rule registry keyed by these names. A UI "all on this target" gesture should submit `[A]` through this existing boundary after displaying the native effective allocation.

Preserve A/B/A as ordered data throughout input, command mapping, execution and presentation. Counts on target badges are useful, but a `Counter`, set, or per-target damage grouping cannot replace the allocation sequence. The engine convolution retains real application identities (`base_actions.py:2388`), as required by `RECOVERY_PLAN.md:2340`.

### Up to N recipients

These accept a shorter prefix without filling unused slots. `num_projectiles` currently doubles as maximum recipient count; it is not sufficient to label everything "projectiles" or infer primary fill.

| Native family | Current maximum and repeat behavior |
| --- | --- |
| Acid Splash (`conjuration.py:384`) | One or two distinct creatures; if two, their XY differences must each be at most one cell (`:449`). Does not publish `secondary_targets`; current second-target UI is overbroad until native validation. |
| Charm Person / Hold Monster (`enchantment.py:51`, `:530`) | Native slot-dependent maximum; unique selected targets retained in order. |
| Bless / Bane (`enchantment.py:1480`, `:1380`) | Three plus native upcast bonus; unique selected targets. |
| Blindness/Deafness (`necromancy.py:627`) | Slot-dependent count; no primary fill; repeats forbidden. |
| Banishment (`abjuration.py:1482`) | One plus upcast bonus; distinct recipients; rejects over-allocation. |
| Prayer of Healing / Mass Healing Word / Mass Heal (`evocation.py:4681`, `:4758`, `:4998`) | Six / six / twenty maximum; repeats forbidden. Mass Heal has native healing distribution, not a UI per-target HP-allocation input. |
| Aid (`abjuration.py:2742`) | Up to three, no primary fill. It currently inherits `allow_same_target=True`. Do not silently impose unique targets in the UI on the assumption that it must match other buffs. |
| Longstrider / Fly (`transmutation.py:1975`, `:2060`) | Native slot-dependent maxima, no primary fill. They also inherit repeat permission. Longstrider explicitly rejects too many recipients; the common discovered execution cap still applies to both. |
| TestBless / NecroticBless (`enchantment.py:733`, `necromancy.py:783`) | Existing additional native definitions with fixed cap/unique selection. Their presence in source is not a claim that a particular player knows them or that a spellbook should manufacture them. |

`BaseAction.get_all_targets` (`base_actions.py:1561`) otherwise preserves the supplied UUID sequence. Runtime action overrides can change effective target type/count; the UI must consume the resulting row rather than cache an ordinary spell assumption.

Two further MULTI_ENTITY definitions expose a current count-hook mismatch: Beacon of Hope (`abjuration.py:3134`) and Divine Word (`evocation.py:5221`) each declare `get_num_projectiles() -> 6`, but neither overrides `get_multi_target_count`; `SpellAction` does not bridge these methods. The actual discovered cap therefore follows `BaseAction.get_multi_target_count`'s default of one unless an explicit override is installed. Their prose/method name is not evidence of six-target live discovery. The proposed UI plan includes the bounded native repair: make these two existing definitions publish their already intended cap of six through the actual discovery hook, keeping their other targeting/effect mechanics unchanged. This is proposed plan scope, not implementation authorization.

Hold Person (`enchantment.py:322`) is currently a separate single-ENTITY spell, not a Hold Monster subclass or a multi-recipient upcast. Invisibility/Greater Invisibility (`illusion.py:837`, `:928`) and Enhance Ability (`transmutation.py:1335`) are also single ENTITY in current native definitions. Enhance Ability's six ability values and Enlarge/Reduce's two modes are native fields, but these classes do not override discovery to publish all alternatives. Their current exact templates may be configured to a value; a UI must not pretend the alternatives are already present as discovered choices. The proposed UI plan includes native discovery variants for Enhance Ability's existing strength/dexterity/constitution/intelligence/wisdom/charisma values and Enlarge/Reduce's existing enlarge/reduce values, using exact variant binding and typed choice facts. These are exposure repairs, not new spell effects. Hold Person and Invisibility keep their current target mechanics; no SRD multi-target expansion enters this lane. These changes remain proposed plan scope until implementation is authorized.

### Chain Lightning: one primary, dependent branches

`dnd/spells/evocation.py:3706` is explicit: one primary within native cast range, up to three branches plus upcast bonus, each distinct and visibly reachable within 30 feet of the primary. Objects can participate. Secondary reach is measured from the primary, not the caster or previously selected secondary. A secondary may be outside the primary cast range and still be valid. The caster can be a secondary if admitted.

`get_secondary_target_options` (`:3755`) returns permitted creatures/objects, excluding the primary. Discovery attaches it to each primary and assigns secondary indices starting after the primary target count (`entity.py:5489`). `selection_target_pool` maps a command's indices through `[primary, *primary.secondary_targets]`. A generic lookup only in `row.valid_targets` would lose legal branches.

`secondary_targets=None` means ordinary pool; `[]` means that particular primary has no branches. Selecting a different primary must discard all old branches. Primary-only confirmation is valid; no nearest-target auto-selection is authorized. Branches are not optional decorative VFX: only selected recipients take native applications. Tests: `tests/engine/test_chain_lightning_selection.py`, `tests/game/test_chain_lightning_selection.py`.

### Wall/path/ring selection

`dnd/core/action_types.py:16` defines the current position contract: `single`, `path(max_length_feet, max_segments, allow_origin_start, origin_start_offset_cells)`, or `entity_destination`.

For explicit paths, the first `AvailableTarget.position` is the first vertex and `extra_target_positions` are the remaining ordered vertices. Native `get_extra_position_options` delegates to `get_valid_extra_target_positions` using the exact row/template and prefix (`actions_functional.py:472`, `base_actions.py:1412`). Do not enumerate all possible walls or implement line-length/visibility/support tests in controls.

If a path has no explicit extra vertex and allows an origin start, native `get_selected_position_path` produces a ray from the casting origin with its authored start offset (`base_actions.py:1359`). Current wall owners use offset one cell. A one-click wall confirmation can therefore mean "origin-adjacent ray to this point," not a zero-length wall. Current Pygame requires two Enter presses for this shorthand. The preview must name and show that effective geometry before confirmation.

| Owner | Existing choices and budgets |
| --- | --- |
| Wall of Fire (`walls.py:180`, variants `:290`) | Four choices per slot: segment heat left/right, ring heat inside/outside. Segment: 60 ft, one segment. Ring: one center, radius fixed at 10 ft. |
| Wall of Thorns (`wall_fields.py:247`, variants `:303`) | Segment or ring per slot; segment 60 ft/one segment; native ring is one center. |
| Wind Wall (`wall_fields.py:311`) | One continuous path, 50 ft, up to ten segments. No discovered ring form. |
| Ice / Force / Stone through `ConstructWall` (`wall_constructions.py:564`, variants `:719`) | Panels with displacement left/right. Ice and Force also offer 5/10-ft dome radius and inside/outside displacement. Stone has 10/20-ft panel-width alternatives, up to ten segments and a 200-ft path budget; native full-panel validation still applies. Ice/Force have 100-ft/one-segment metadata. Stone does not offer a dome. |

The segment/ring/dome/hot-side choices already exist as separate exact discovery variants. The UI should group them as form/side controls selecting an existing row. No geometry choice should be inferred by parsing `__wall_...` or display labels. Typed facet metadata is currently missing from the public row; `position_selection` alone cannot distinguish a dome from a ring or a heat side from a displacement side.

The next-point query validates the actual path/placement. A first point may be admitted only because a legal continuation exists (`allow_partial_position` in `base_actions.py:2014`); this does not prove a one-point confirmation is valid. The proposed UI needs an engine-owned complete-selection preview/validation before enabling Confirm, not `len(points)>=1`.

### Summoning

`dnd/spells/summoning.py:15` already generates exact `(slot, form_id)` variants from `available_forms`. Each cast selects **one creature form and one destination**. Conjure Animals/Fey/Fiend currently do not offer "eight creatures," manually placed groups, or a radius scatter option. Higher slots unlock stronger forms. Do not invent a multi-position summon interface from tabletop alternatives absent here.

These are ordinary POSITION rows with subjective walkable/unoccupied requirements. Native admission calls the explicitly bound summoning owner, and resolves again on paid execution; the UI cannot replace this by testing a tile alone. Slot/form selection precedes the map destination. Costs/concentration and source-item adaptations remain properties of the exact selected row.

### Creature plus destination: Telekinesis and Dimension Door

Telekinesis and its concentration-granted `action.spell.telekinesis.move` both use ENTITY plus `EntityDestinationSelection` (`transmutation.py:1677`, `:1751`). Choose the creature first; query next positions; submit exactly one destination as `extra_target_positions=[destination]`. The adapter binds this as the action's `end_position`, not its extra-position list. Discovery offers a creature only if at least one destination is valid. Missing/excess destinations are rejected; execution revalidates after the creature moves.

Telekinesis is currently supported ground creature transfer, Huge or smaller; selected creature and destination must be visible, within 60 ft of caster, and displacement within 30 ft with admitted airborne route/landing (`transmutation.py:1586`). It does not offer object lifting, arbitrary XYZ height, sustained floating, or dragging a creature around without paying a repeat action. Initial cast includes a move; repeats spend another action while the exact concentration marker remains active. Hostile saving throws and landing damage are native outcomes, never previewed as guaranteed.

Dimension Door (`conjuration.py:4289`) uses the **same entity-destination input**, with self meaning travel alone and a nearby willing ally meaning take a companion. Its destination query intentionally includes unseen or obstructed coordinates within the authored map envelope. Obstructed arrival is a paid native mishap, not a discovery filter. Current mouse picking cannot reach an undisclosed support, although keyboard next-position selection can. The UI must expose admitted unknown coordinates without revealing terrain/occupancy. Add coordinate selection or a neutral map-envelope grid with "destination unknown" presentation; do not manufacture terrain.

## 4. Proposed exact interaction states and confirmation defaults

These are recommendations for the enclosing plan; they are not claims about today's UI. They are passive application selection states, not a second target-rule framework or gameplay queue.

| State | Input and next state | Confirm rule |
| --- | --- | --- |
| Ready | Select action/spell/item family; choose exact offered variant; world hover shows default action. | No command from mere selection. |
| Variant choice | Select exact slot/form/side/provider row. Preserve unrelated row choices visibly. | Self-only command uses its explicit action click; other actions enter target selection. |
| Targeting single/AoE | Hover obtains the existing disclosed target/area preview; click chosen target. | Direct click commits the selected single target; AoE/destination click commits the currently previewed admitted position. No extra modal by default. |
| Allocating projectile | Click appends one ordered application; same target can be clicked repeatedly if admitted. | Explicit Confirm, including at maximum. No auto-execution on final target. For a partial prefix show effective native primary-fill allocation and label "Cast N projectiles". Single-target shortcut is "All on target" within this same row, not a new spell mode. |
| Selecting up to N | Click appends recipient; selected entries indicate native duplicate permission. | Explicit Confirm after at least one admitted target; label "Cast on K targets (up to N)". Never imply unused capacity fills automatically. |
| Chain primary/branches | Choose primary, then only its actual secondary pool. Sequence retains primary and branches. | Explicit Confirm after primary alone or any legal branch prefix. Replacing primary clears branches. |
| Selecting path | Pick first vertex; native query provides next vertices. Hover can preview a candidate continuation. | Explicit Confirm only when native complete-selection preview says accepted. Show whether one-point shorthand or explicit path is selected. |
| Selecting creature/destination | Pick creature, query admitted positions, pick one destination. | Destination click enters a reviewable complete selection; explicit Confirm by default because target and landing are separate decisions. Backspace removes destination before creature. |
| World approach | Click a remote world interaction; display admitted movement route and final intended operation. | One click authorizes ordinary Move then rediscovery of the intended interaction. Reconfirm only if the intended operation changes; invalidated/blocked approach cancels with actual reason. |
| Submitted/waiting | Clear active input selection; receive and present actual operations. | Human actions stay gated until the displayed boundary. |

Use Enter for Confirm and an on-screen Confirm button for every explicit-confirm state. In live play, Space ends the turn only while neutral, on the active human turn, with playback settled and no modal; it is a no-op during targeting or a modal. Playback pause remains review-only. Backspace removes the last entity allocation/vertex/destination. Escape/right-click cancels selection and returns to Ready before any menu/exit binding; right-click opens world context only on a later click once neutral. Changing action/slot/form/provider clears incompatible targets. A disabled/unavailable selection exposes native status and costs; it does not silently choose a cheaper level, different source, different creature, or alternate world action.

The proposed complete-selection response should expose `can_confirm`, a disclosed reason, effective ordered allocation and/or selected geometry, and admitted next choices. It is a narrow native discovery extension over existing validation, not a universal client TargetingManager. It must be side-effect free: no registered events, costs, or live position mutation during hover.

## 5. World interaction, Ctrl attack and Alt highlighting

### Exact existing action identities

`dnd/content_system/action_definitions.py:169–185` authenticates these native behaviors. The following are all world-only in the proposed UI, even when the native row is SELF or appears in `all_actions`:

| World choice | Native behavior | Binding |
| --- | --- | --- |
| Open/close directional door | `action.environment.directional_door.open` / `.close` | `source_item_uuid` is the clicked door; native SELF target stays the actor. |
| Open/close ordinary door | `action.environment.door.open` / `.close` | Same binding. Available form follows actual open state. |
| Pull trap lever | `action.environment.trap_lever.pull` | Source item is the lever; native link selects the mechanism. |
| Toggle reusable control lever | `action.environment.control_lever.toggle` | Source item; native link requests the light/door state. |
| Chest open/close/loot | `action.environment.storage_chest.open`, `.close`, `.loot_all` | Source chest; opening and transferring contents are distinct native operations. |
| Wall torch | `action.environment.wall_torch.ignite` / `.extinguish` | Source wall torch. Carried `action.item.torch.*` remains inventory/item use. |
| Device / campfire / feast | `action.environment.arcane_device.activate`; `action.environment.campfire.cook` / `.rest`; `action.environment.heroes_feast.eat` | Source item and native prerequisites. Do not replace supplied alternatives with a fuzzy default. |
| Pick up floor item | `action.pick_up` (`actions.py:5543`) | OBJECT target UUID; use the clicked item, not its position as identity. |
| Attack door/window/item | `action.attack` (`actions.py:1957`) or an actually discovered authored attack row | CREATURE_OR_OBJECT UUID, precise weapon/source choice, native contact/range. Ctrl does not issue a door-use command. |

World clicks require exact matching of clicked identity to **source item** for use actions and **target UUID** for direct-object/attack actions. This is why grouping by `target_type`, `is_item_use`, or display-name substrings would be incorrect. Multiple available actions should open a compact world context chooser; the action bar does not become the fallback home for world interactions. Exact authored UI-affordance metadata should define a default operation and context alternatives. Until supplied, a visible context list is safer and truthful than guessing a default from names.

Do not automatically treat all `action.environment.*` as world item use either: escape-jaw actions are creature-affecting actions with their own current context. Classification belongs to exact content metadata, not namespace prefixes.

### Forced attacks: what exists and what is missing

Current Pygame controls have no Ctrl branch, no forced-attack state, and no session argument widening attack candidates. Ordinary attack rows already include admitted objects (`CREATURE_OR_OBJECT`); the Ctrl implementation can select the exact native attack row/target for doors and windows without introducing force-hit or bypass mechanics.

For ally attacks, `Entity.get_available_actions(target_filter="all")` broadens the outer pool and `Attack._validate` checks range/LOS/weapon eligibility without a faction rejection (`actions.py:2567`). This is an existing native route, but indiscriminately switching the entire discovery result to `all` would affect other actions too. Add a narrowly named attack-intent option to the session/native discovery wrapper and preserve only the chosen action's force-target candidates. Spells still enforce their own native recipient filter; Ctrl must not grant beneficial/harmful targeting exceptions. No Ctrl interaction may expose unseen objects, exceed reach, add unknown UUIDs, or turn an invulnerable strike into guaranteed damage.

Recommended held-modifier behavior: Ctrl+hover previews the selected eligible attack and its source/cost; Ctrl+click issues it. Release Ctrl restores ordinary world affordances. A friendly target click is deliberate under Ctrl and uses the same immediate attack confirmation default; the UI must visibly identify the target and attack before click. If several weapon attacks exist, use the player's selected attack mode or the world context chooser, never “first attack found” hidden precedence.

### Window passage is native but not registered in the live discovery composition

`dnd/content/items/window_builders.py:63` installs a `PASSAGE` connector with `presentation_key="window"`, frame UUID, size cap, endpoints, and source-exit provocation policy. The frame and insert are separate exact targets; fixed grilles/shutters are not an openable-door alternative. An intact blocked insert may be attacked; an admitted aperture may be traversed.

`TraverseConnector` (`actions.py:1256`) implements exact connector revision/digest/endpoint validation, costs and movement. It supplies `get_connector_traversal_discovery`; it is SELF because the selected variant already owns the transfer. **It is not included in `setup_standard_actions` (`actions_functional.py:88`), no authenticated content behavior identity for it was found in current action definitions, and `AvailableActionInfo` currently omits connector traversal metadata.** `tests/engine/test_windows.py:48` and `test_traversal_connectors.py:162` directly create this native action to demonstrate traversal. That test path does not prove it appears in the live UI.

The concrete integration is: register/authenticate this existing native action in standard composition; project its `ConnectorTraversalDiscovery` into the existing row; classify it world-only; link the disclosed connector/frame identity to the world hit region and exact row. A proposed new identity such as `action.traverse_connector` must be registered properly, not merely written in controls. Ordinary `action.jump` remains the Jump action; there is no separate current discovered "crawl window" or "jump window" alternative. If both must be independently selectable, that is a native content/rules decision, not a label the UI can fabricate. The window passage's current authored animation can still look like a vault/crawl while using the one existing native transfer.

### Move to interact

Native object use currently requires `GridMap.manual_object_contact` (five-foot HAND reach, `gridmap.py:2522`). Remote world uses are omitted before item action discovery (`entity.py:7322`). There is no current approach-and-interact command in controls/session.

A concrete extension should keep native contact/navigation owners:

1. Add an engine query for a disclosed object's **approach options**, returning ordinary admitted Move targets and the exact intended object/operation identity. `GridMap.attack_object_contact` already accepts `origin` (`gridmap.py:2532`); `manual_object_contact` is the thin wrapper missing it. Add the optional `origin` argument to that wrapper and forward it. The lower method already checks footprint/boundary-side surfaces, support elevation distance, subjectively known portions, and `can_reach_between(..., PhysicalAccess.HAND, subjective=True, terminal_provider_uuid=object_uuid)`. No contact algorithm needs copying. Do not approximate “adjacent tile” from sprite geometry or evaluate hypothetical entity mutations.
2. The application stores one pending world intent `(actor, object UUID, exact operation/provider, chosen approach)`, not an auto-play action list. Submit the ordinary Move; capture and display its complete native consequences.
3. At the next displayed human boundary, rediscover. If the actor reached admitted contact and the same operation is still available, execute its exact current row. A destroyed/disappeared object, failed approach, control loss, ended turn, interruption, changed operation, or player cancellation clears the pending intent and reports the actual result.
4. Do not spend a new turn, auto-Dash, use teleport, auto-attack a blocker, switch sides of a door, or operate another lever just to complete an old intent. Only movement within the current authorized turn and rediscovered operation is proposed here.

Approach presentation should show route cost/hazard/opportunity exposures and the final intended operation. A remote object's observed existence does not itself disclose its hidden contents, linked mechanism state, or future action availability.

The native approach query is concretely a filter over **the exact currently discovered movement row's `valid_targets`**: retain target `t` only when `t.position` exists and `manual_object_contact(actor.uuid, object_uuid, subjective=True, origin=t.position)` returns a contact. Preserve `t.path`, `t.safe_path`, their costs and opportunity exposures unchanged. Choose an affordable safe route using the same `_disclosed_movement_path` preference as execution; order equal approaches deterministically by that chosen route's cost and then position. If multiple locomotion rows are available, retain the player's exact selected locomotion row or expose that choice; walking and flying can share `behavior_id="action.move"`, so the ID alone must not select whichever row appears first. No new client or native BFS is required for this UI feature.

The missing remote operation label is a separate disclosure issue from approach geometry. Extract the current native world-item use-source enumeration in `Entity._collect_use_actions` (`entity.py:7300–7333`) into a helper that can return exact **observed contextual operation descriptors** before the final hand-contact executable-row gate. Its ordinary executable caller retains the existing contact test; the approach caller receives a non-executable operation descriptor and current approach options. Preserve item-specific `get_use_actions` state choices, authenticated behavior/provider identity and disclosure rules; do not expose chest contents to populate a remote menu. At contact, re-run ordinary full discovery and execute the matching real row. If this helper cannot establish the requested operation from disclosed state, display only a neutral approach/inspect affordance until it can; do not promise a fabricated future use.

An attack approach has different reach/access from HAND use. Ctrl attack must call the same existing `attack_object_contact` with the selected native attack's range/physical-access data, not reuse the manual-contact filter. Window approach candidates are the disclosed, correctly oriented connector source endpoints; arrival then rediscovers the existing connector action. Those distinctions belong to the native approach query's concrete action contract, not client branching on object names.

### One shared pick/highlight substrate

Current machinery is useful but partial. `environment_draw.py:87` uses authored prop selection masks at exact mount/pivot, and falls back to `item_selection_command` for ground equipment. `pick_environment_target` sorts by painter order and tests mask alpha (`:121`). Current target highlighting in `controls.py:236` tints that same mask. Aperture coverage is explicitly separate (`environment_aperture_image:113`). Doors are held in a separate art table and do not gain a complete mask merely from this prop function. Destroyed props return no selection command, which is inadequate as a blanket rule for lootable destroyed chests or admitted wreck targets.

Proposed passive record emitted from the existing scene/raster composition:

```text
PickRegion(identity, kind, screen_origin, selection_mask, visible_mask,
           painter_key, disclosed_world_position, related_connector_uuid?)
```

`kind` distinguishes creature, world item, and connector contact; it is not an action executor. Reuse the registered mask when present, the actual current ground-item silhouette otherwise, and the actual current door/body pose where no registered region exists. Associate a connector aperture with its disclosed frame/connector record. Preserve frame/insert independence. A window aperture mask is a passage region, not the grille's attack hitbox.

Build regions once for the composed frame. A single picker orders hit candidates by existing painter/depth semantics; mask intersection with the composited visibility/occlusion result prevents selecting a concealed object through foreground geometry. Existing environment picking has no general scene-occlusion intersection, so this needs real integration rather than a rename. For creatures, derive the selection silhouette from body/equipment geometry, excluding large decorative VFX and floating labels. Known but wholly hidden contacts can remain in an explicit permitted target list; they do not get invented visible pixels.

One `HighlightRequest(identity, reason, style)` input uses these regions for hover, currently selected targets, and held-Alt item highlighting. Reasons merge with precedence (selected target over hover over Alt) rather than three render passes with different geometry. Alt changes visible emphasis/labels only; it does not change native legal targets, grant visibility, select a command, or draw forgotten hidden items as current. Tooltip/Alt labels are clickable aliases of the same identity/region. No new imported artwork is required to establish this contract.

## 6. Minimal missing native/UI metadata

These additions belong to existing discovery/content values and owners. They must not be replaced by a parallel spell-name targeting table.

| Missing fact | Concrete proposed location/API | Why existing data is insufficient |
| --- | --- | --- |
| Prefix resolution semantics | Add `allocation_completion: "selected_only" | "fill_primary"` to the existing multi-entity discovery description/row, supplied by a `BaseAction` hook and overridden by the native fill owners. Keep `num_projectiles` as cap and `allow_same_target` as truth. | Count/repeat permission cannot distinguish Aid from Magic Missile. |
| Legal next recipient / full-prefix admission | Extend native discovery with `preview_available_selection` as specified below, using ordinary target membership, existing primary-dependent options, and pure concrete selection predicates shared with final validation. Do not call arbitrary `_validate` during hover. | Acid Splash's pair restriction is not represented; primary-dependent Chain already has most of this data. No general combination validator exists in the UI contract. |
| Complete point preview | Add sibling `preview_available_selection` alongside `get_extra_position_options`, returning completeness and disclosed geometry for the exact row/prefix. Reuse bounded native geometry predicates; route next-position feasibility through those predicates instead of an unrestricted action-validator callback. | First-point admission can be partial; path metadata alone cannot validate shell/support/hot-side effects. |
| Typed variant facets | Extend existing `ActionDiscoveryDescription`/`AvailableActionInfo` with native choice facts, such as form, side, radius, summon form reference, damage-kind option, held weapon/source. Slot level already exists. | These native variants currently differ mainly in token/display name and private template fields. |
| Presentation surface/default | Add exact authored affordance data to content description and project into each row: surface (`action_bar`, `world`, `inventory`, or contexts), operation label/default priority, clicked identity binding (`source_item`, `target`, `connector`). | SELF/OBJECT/category/is_item_use cannot classify door use, carried potions, weapon attacks and connector transfers. Preserve a visible contextual fallback for future rows. |
| Connector identity and endpoints | Project native `ConnectorTraversalDiscovery` onto existing action row; register existing TraverseConnector with authenticated behavior identity. | Command tokens cannot be parsed as authored metadata and the live standard composition does not currently register this rule. |
| Approach affordance | Native `get_object_approach_options` over current subjective navigation/contact, plus one session pending world intent. | Out-of-range object use is absent from current discovery. |
| Reaction toggle command | Add session function using `set_handler_enabled_by_uuid` with actual player ownership; return refreshed handler facts without inventing an action event. | Handler data already exists, but no current game command exposes it. |

Do not add a mandatory `minimum_targets` field speculatively: present selected-entity actions all need one primary; a future mechanic needing zero or a nontrivial minimum can extend the concrete selection contract then. Do not add generic client formulas for range, slots, spell geometry, group summon counts, or independent application timing.

### Concrete preview request/result and purity boundary

Proposed native signature, using the exact already-discovered row:

```text
preview_available_selection(entity, action_info, primary_target=None,
                            extra_target_uuids=(), extra_target_positions=())
    -> AvailableSelectionPreview

AvailableSelectionPreview:
    can_confirm: bool
    reason: str | None
    effective_target_uuids: tuple[UUID, ...]
    next_targets: tuple[AvailableTarget, ...]
    next_positions: tuple[tuple[int, int], ...]
    geometry: AoEPresentationGeometry | None
    affected_positions: tuple[tuple[int, int], ...]
```

The request is the same primary-plus-ordered-extras shape as `execute_available_action`; an omitted primary means an empty selection. The session resolves its current generation/row handle into `action_info` and projects the result into detached UI values. `can_confirm` is true only for a complete currently admitted selection. `reason` is a disclosed incompleteness/invalidity explanation, not an arbitrary action Event's status. `effective_target_uuids` preserves ordered repeated applications and applies the native `allocation_completion` policy; it is empty for positional/self selection without explicit recipient allocation. `next_targets` and `next_positions` are admitted continuations of this exact prefix, not a new exhaustive target universe. At a complete maximum allocation they are empty. `geometry` describes the intended selected native area/path when provided; `affected_positions` contains only preview positions allowed by current disclosure. Neither field promises final affected hidden occupants, saves, damage, displacement results, or summon success. This value contains no Event, entity/template reference, callback, or live owner.

Do not implement this function by invoking `action.apply`, `_create_declaration_event`, generic `action._validate`, or a fake execution rolled back afterward. Today's `validate_requirements_for_discovery` constructs a detached declaration and calls `_validate` (`base_actions.py:2014`); absence of event registration does not establish universal purity. Concrete `_validate` methods can mutate their action, such as Enhance Ability setting `self.target_entity_uuid` (`transmutation.py:1370`), and Event phase methods are lifecycle APIs. `EventQueue.preflight` has a distinct validation-only handler contract (`events.py:1983`), but it is not blanket authorization to call unrelated validation handlers on every hover.

For already discovered single/self/AoE/summon rows, preview consumes the admitted target and supplied preview facts; final execution performs ordinary revalidation. For added multi-prefix checks, extract only the concrete combination predicates needed here: Acid Splash's pair proximity and Chain Lightning's existing primary/secondary contact constraints, plus common membership/cap/repeat checks. Share those same native predicates with execution validation so rules are not duplicated. For path/entity-destination prefixes, reuse or narrowly extract the read-only checks already represented by `position_selection_error`, wall geometry/support/full-panel helpers, `_telekinesis_selection_error`, and Dimension Door's `_selection_error`. Modify the bounded next-position selection path to use these checks rather than calling a generic event-producing validator. No hover operation registers an Event, rolls dice, consumes resources, mutates a template, moves an entity, or creates a creature/item. Broadly refactoring every action validator is outside this plan.

Request preview only when the selected generation/row/prefix changes; pointer movement merely chooses among cached disclosed continuations and redraws. If a supported family still requires eventful work to establish a preview fact, expose its already-discovered target facts and defer that fact to execution rather than simulate it during hover. This limitation must not remove the action from discovery or invent a guaranteed outcome.

## 7. Current human reactions

Humans currently receive the same synchronous enabled native reactions as other actors. `HumanController` only provides a turn boundary (`controller.py:258`); it does not suspend EventQueue for a reaction prompt. Opportunity attacks resolve in the Step event handler (`reactions.py:18`). Shield checks affordability and whether +5 AC can turn a normal hit into a miss, or intercepts Magic Missile damage; it automatically spends the lowest qualifying slot (`spells/abjuration.py:283`). Counterspell chooses an automatic qualifying slot when available, otherwise a third-level-or-higher attempt (`:945`). Hellish Rebuke similarly selects a current casting source/resource (`spells/infernal.py:130`). Stone-enclosure escape directly rolls and picks an affordable exit reaction (`wall_constructions.py:516`), not a human destination prompt.

Player-toggleable handlers already expose exact UUID, enabled flag, behavior/provider identity and trigger event in `AvailableActionsResult.handler_details` (`entity.py:5498`, `base_actions.py:2782`). `BaseBlock.set_handler_enabled_by_uuid` already validates that a handler is player-toggleable (`base_block.py:1109`). Current Pygame never displays or changes these handlers.

Recommended bounded UI is a reactions panel showing **automatic when enabled** and toggle switches, retaining native initial enabled states. It must not claim “ask every time.” A blocking human reaction choice needs an explicit new engine continuation contract; pausing historical playback cannot interrupt a reaction already committed synchronously. No reaction scheduler/continuation redesign is smuggled into this UI plan.

## 8. Behavioral acceptance matrix

The first implementation should extend existing feature tests at their real boundary, with a small integrated Pygame input lane. Follow `HOW_TO_TEST.MD`: data cases, real native discovery/execution, no source-string assertions as behavioral proof, no private-state call-count tests, no guessed sleeps. A source study does not require a full suite run; none is claimed here.

| Case | Input/observable acceptance | Suggested existing boundary |
| --- | --- | --- |
| Single attack/self action | Select exact row and target; one native command, correct resources, no action on hover. | `test_controls.py`, `test_session.py` |
| Human/history gate | Click while native future differs from displayed history; no command until settled human boundary. | `test_encounter_play.py` / live frame-event harness |
| Space input precedence | Space ends one turn only from neutral/active-human/settled live input; targeting/modal/AI/history states do nothing. Enter/Confirm commits selection. No live playback-pause toggle. | Integrated `encounter_play` event loop, not only controls helper |
| Cancel/undo | Escape cancels selection without closing game; Backspace removes only last A/B/A application or vertex. | Pygame input helper plus one live wiring case |
| All projectiles one target | Native `[A]` resolves N application identities; UI previews all N. | Native Magic Missile/Scorching Ray/Eldritch Blast parameterized cases |
| Partial projectile prefix | `[A,B]` resolves `[A,B,A…]`, shown before Confirm. | Native command plus passive selection output |
| Repeated sequence | `[A,B,A]` preserves order through command and application facts; badge counts do not reorder it. | Existing Magic Missile history/play tests |
| Up-to-N subset | Bless/Aid one target resolves one, no auto-fill; explicit Confirm still available below cap. | Real discovery and resulting recipients |
| Distinct native rule | Duplicate Banishment/Chain rejected without costs; inherited Aid/Longstrider/Fly repeat semantics are not silently rewritten. | Native command/state |
| Pair restriction | Acid Splash second choices respect five-foot pair constraint; stale invalid pair rejected without spending. | Native next-target query and command |
| Chain outside caster range | Secondary admitted by primary reach, exact secondary index mapping preserved. | Existing chain selection tests |
| Chain primary change | Branches from old primary clear; empty secondary list still allows primary-only Confirm. | Controls/native chain scenario |
| Allocation max | Reaching cap stays reviewable until Confirm; no fourth selection for cap three. | Controls output and event cursor |
| Slot/form change | Changes exact row/cost/cap and clears incompatible allocation; never reuses stale token by label. | Discovered spell variant scenario |
| Bounded discovery repairs | Beacon of Hope/Divine Word expose native cap six; all six Enhance Ability and both Enlarge/Reduce modes bind their exact existing field/effect. Hold Person/Invisibility retain current target mechanics. | Native discovery/execution cases, only after plan approval |
| Preview purity | Empty/partial/full/repeated/path/destination requests return the declared cold result; repeated hover/prefix preview leaves event cursor, RNG state, resources, templates, positions, conditions and deployed membership unchanged. Final command still revalidates. | Native public preview plus command scenarios |
| Item spell | Same targeting UI reaches exact source UUID/charges/slotless override; source removal rejects naturally. | Item-use command tests |
| Directional/AoE | Preview only supplied affected cells/recipients; final hit set comes from native facts. | Existing shared spell-target/area tests |
| Explicit wall | Two endpoints are sent in order; Backspace undoes; first-point-only incomplete selection cannot confirm. | `test_wall_point_selection.py` |
| Origin shorthand | One-point shortcut explicitly previews native offset-origin segment; output matches native geometry. | Existing wall shorthand scenario |
| Wall choices | Ring center/hot side; Ice/Force dome radius/displacement; Stone segment budget; no nonexistent Stone dome. | Native discovery variants plus visible selector |
| Wind/Stone prefix | Next vertices follow native budget and support constraints; invalid/excess vertex never spends. | Existing wall/remaining-wall tests |
| Summon | Exact form+slot+one position creates one canonical native creature, not count/scatter alternatives. | Summoning lifecycle + controls |
| Telekinesis | Creature then one landing required; initial and repeat have correct costs; stale target destination rejected. | `test_entity_destination_selection.py`, `test_telekinesis_landing.py` |
| Dimension Door unknown | Admitted unseen coordinate selectable without revealed terrain; native paid obstruction mishap retained. | `test_banishment_dimension_door.py` plus input |
| World SELF item | Ordinary click door/lever uses source_item_uuid while retaining the row's self target; no environment bar button. | Environment control scenarios + UI |
| Context alternatives | Chest opening and loot remain separate; world chooser lists exact existing alternatives. | Environment loot/control tests |
| Ctrl object attack | Same door/window click under Ctrl chooses native attack, exact component UUID and weapon; release restores use. | Object attack tests + UI modifier cases |
| Ctrl ally attack | Permitted native attack discovery widens deliberately, no broad spell filter change or template mutation. | Native action discovery/execution |
| Window components | Insert/frame/passage use distinct registered masks/identities; blocked insert has no invented open/crawl command. | `test_windows.py`, window presentation |
| Window native discovery | Registered TraverseConnector appears world-only with exact revision/endpoints; stale revision rejected, costs/interruptions native. | Traversal connector tests plus session discovery |
| Approach/use | Remote click follows disclosed ordinary path, then refreshed exact use; interrupted/destroyed target cancels. | Native movement plus world interaction sequence |
| Approach limits | Insufficient movement does not auto-Dash/end turn; hazard/exposure matches executed route; no hidden path disclosure. | Native movement routes/subjectivity |
| Shared hover/target/Alt | All three highlight the same region at all four cameras/zoom/height; Alt adds no targetability. | Passive regions + bounded pixel/input cases |
| Mask overlap/occlusion | Front visible region wins, masked-out aperture does not hit frame, concealed object cannot be clicked through foreground. | Existing environment/window depth tests extended at picker boundary |
| Wreck loot | Destroyed lootable chest remains world-selectable when native actions permit; destroyed decoration is not automatically attackable. | Environment loot + shared region scenario |
| Reactions toggle | Exact handler UUID toggles before next native trigger; disabled handler spends no reaction; enabled resolves automatically. | Native handler toggle and session/UI |
| Future discovery | New concentration action, newly equipped item, summon dismissal, unfamiliar native variant remain reachable through their declared surface/context. | Existing native grant/discovery scenarios |

The anti-slop reviewer must check concrete player journeys, unavailable explanations, integrated input precedence, exact native variants, and that world actions never leak into the action bar. The anti-OOP reviewer must check passive UI data, ECS owner reuse, exact behavior identities, import DAG, no renderer live-entity queries, no duplicated geometry/rule registry, and no second mechanical action/reaction queue. Both reviews are required before the enclosing implementation plan is accepted; this study does not claim their approval.
