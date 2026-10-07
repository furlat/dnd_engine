# BG3 PC interface reference study — October 6, 2026

Collected for the human's request to research the rejected player UI. This is
a reference study, not an implementation plan or a new mechanics scope.
Inventory and character creation are excluded. The existing request is still
a fixed human Fighter/Sorcerer party, a minimal action bar, readable text and a
proper dungeon experience.

**Screenshot board:**
[14 sourced PC screenshots](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html).
Every image links to its original and its source page. The durable
[source catalog](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/BG3_UI_REFERENCE_SCREENSHOTS_2026-10-06.json)
retains the URLs, captions and inspection date. The board is private
under `.runtime/bg3-ui-reference-20261006/`; no BG3 pixels are game assets.
The visual references are release-era PC screenshots, mostly 2023, rather than
a claim that every screenshot depicts the latest patch. Current community
documentation and official patch notes verify the behavior described below.
Screenshots were loaded in a browser and visually inspected. Dynamic behavior
is sourced separately; no BG3 play session was recorded for this study.

## 1. Screen structure and party control

The [combat HUD screenshot](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#hud)
shows four distinct areas: party portraits on the left, initiative across the
top, the selected character's controls along the bottom, and a collapsible log
on the right below the minimap. Party portraits carry HP and adjacent condition
symbols. Initiative portraits identify combat order; they do not replace the
party controls. The
[dungeon targeting screenshot](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#path)
also shows smaller summon portraits attached to party members.

**Application to our complaints:** party selection and turn ownership need
distinct visible states. We do not need permanent names, round/status prose
and repeated instructions scattered around all four areas. The Fighter and
Sorcerer need a stable left-side party control even when an enemy is acting.
Inspecting a party member must not silently grant that member a turn.

BG3 normally explores in real time and switches to turns for combat; players
can also toggle turns outside combat. It permits interchangeable turns for
eligible adjacent allies. That is a gameplay difference to record, not a
reason to change our initiative or exploration engine during a UI repair.
[Turn-based mode](https://bg3.wiki/wiki/Turn-based_mode).

## 2. Action bar, artwork and weapon choice

Larian describes the hotbar as movable/hideable groups, with filters for
different action resources and class abilities. Its aim is to expose depth
while controlling clutter.
[Official HUD redesign description](https://baldursgate3.game/news/community-update-15-absolute-frenzy_49).
The release UI also allows changing row count and rearranging shortcuts.
[Hotbar guide](https://steamcommunity.com/sharedfiles/filedetails/?id=3142001611).

The visual evidence is more useful than copying the whole bar:

| What to inspect | What the screenshot shows | Relevance to our UI |
| --- | --- | --- |
| [Weapon controls](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#weapon) | Weapon buttons beside the selected portrait and a named ranged-attack tooltip. | The player needs an explicit, stable melee/ranged choice. A preference that silently substitutes another attack is not an adequate control. |
| [Icon close-up](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#icon-legibility) | Distinct bright symbols, dark slots and small variant badges. | Preserve the accepted icon artwork's contrast. Avoid blackening the entire bar merely because there is currently no valid target. |
| [Resources](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#availability) | Different shapes for actions, bonus actions and spell slots; visible filled/spent states. | Separate availability, selection, resource shortage and target validity. They are different facts. |
| [Spell tooltip](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#spell-tooltip) | Name, damage, description, save, range and cost are grouped in a temporary panel. | Explanations belong on demand, with readable type and deliberate spacing. They need not surround every icon permanently. |

BG3 does dim unavailable spells. The point is not “never dim”: an exhausted
casting resource and the absence of a target should not make the same
unexplained visual statement. BG3 exposes resource consumption and reasons
through the casting controls and descriptions.
[Casting UI guide](https://steamcommunity.com/sharedfiles/filedetails/?id=3122428771).

**Our design constraint remains stricter:** one compact shortcut row, with
additional choices opened when needed. BG3's multiple rows, ornate frames and
large selected portrait are references to inspect, not requirements to import.
Pygame can support the same hierarchy, anchoring, spacing and state distinctions;
the toolkit does not explain the current layout shortcomings.

## 3. Targeting, upcasting and multiple targets

The [upcast close-up](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#upcast-a)
shows a temporary rank selector, an available higher rank and spent ranks.
It does not require a permanent shortcut for every level. The plus on an icon
indicates additional spell choices, which can include a variant as well as
upcasting; it should not be described as simply “more damage.”
[Variant-badge discussion](https://steamcommunity.com/app/1086940/discussions/0/3808408328764078732/).

The [PC Magic Missile screenshot](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#multitarget)
shows allocated-projectile progress and the confirmation area. PC players can
repeat a creature selection for repeated projectiles. Partially allocated
spells have a confirmation step when that action permits fewer targets.
[Repeated selection and partial confirmation](https://www.reddit.com/r/BaldursGate3/comments/16ets89/).
Larian also explicitly fixed a bug preventing spell variants from casting with
fewer than their maximum targets.
[Official Patch 5 notes](https://baldursgate3.game/news/patch-5-now-live_99).

**For our interface:** rank, form/element and target allocation are separate
choices. The world preview must match the chosen native action. “One click
assigns every projectile” is not established as a general BG3 rule by these
sources; our own convenience behavior must be labelled and implemented from
our action's allocation rules. Straight Wall of Fire's hot side still follows
our approved endpoint order; this study does not add another side picker.

## 4. Movement, attack previews and reactions

The [Shacknews dungeon screenshot](https://shacknews-www.s3.amazonaws.com/assets/editorial/2023/08/baldurs-gate-3-combat-movement-and-attack.jpg)
shows a white approach path, a destination/attack ghost and hit chance beside
the target. A ranged or melee choice can change whether approaching is needed.
The useful feedback is attached to the route and target, not a permanently
visible “choose target” paragraph.
[Combat explainer](https://www.shacknews.com/article/136590/combat-explainer-baldurs-gate-3).

A [red opportunity-attack warning](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#opportunity)
marks a relevant threatening creature.
[Movement warning source](https://mobalytics.gg/blog/baldurs-gate-3/combat-tips-tricks/).
Larian later added a warning when a proposed approach for spellcasting would
enter a dangerous surface, and improved spent-resource legibility.
[Official Patch 6 notes](https://baldursgate3.game/news/patch-6-now-live_108).

The [reaction settings screenshot](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#reactions)
shows separate enable and Ask settings. BG3 can execute a reaction
automatically or pause for the player's choice; costs are shown in the reaction
configuration. This is separate from ordinary action selection.
[Reaction controls](https://bg3.wiki/wiki/Reactions).

**For us:** previews must expose the native route, cost and consequences.
They must not independently recompute combat rules or turn a queued reaction
into another normal action. A path is one player command even when native
substeps trigger traps or opportunity attacks.

## 5. World clicks, highlighting and dungeon readability

The [world-label screenshot](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#labels)
shows compact names anchored to loot and containers, including empty state.
The [object context menu](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#context)
offers object-specific alternatives, including attack and throw, beside the
object. The
[door screenshot](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#door)
shows a dungeon threshold in its architectural and lighting context.
Sources: [player world labels](https://www.reddit.com/r/BaldursGate3/comments/15j0hlp/has_anybody_found_the_matching_true_loves_caress/),
[world context menu](https://www.neoseeker.com/baldurs-gate-3/walkthrough/Get_Gortashs_Netherstone),
[door scene](https://clutchpoints.com/gaming/baldurs-gate-3-guide-open-locked-door-in-overgrown-ruins).

Alt is the default **item-label** control. Character highlighting and sneak
cones are separate controls. It is not accurate to claim that stock Alt labels
every door, lever or decorative prop.
[Default controls](https://bg3.wiki/wiki/Options).

**Our requested behavior:** world clicking supplies the primary interaction;
a small context menu supplies alternatives; Ctrl prepares an attack; Alt makes
our supported interactables discoverable. Including doors, levers and window
traversal in that discoverability is our requirement, even where it goes
beyond BG3's item-label convention. Environmental actions do not need to
occupy the shortcut bar.

The dungeon references also make the content problem concrete: thresholds,
corners, local light, sight-blocking architecture and props explain where the
player is and what can be touched. A flat demonstration floor does not provide
the experience requested after the environment work. This does not require
new artwork to establish those basic spatial relationships.

## 6. Combat log: concise rows, real arithmetic on inspection

The [calculation screenshot](http://127.0.0.1:8768/bg3-ui-reference-20261006/index.html#dice)
shows short log entries and a separate hover/pinned breakdown. The breakdown
contains the target's AC, the rolled die, named attack modifiers and separate
damage contributions. Names and results are readable as text; the main list
is not a dense table of permanent actor chips and calculation columns.
[Original forum screenshot](https://forums.larian.com/ubbthreads.php?Number=883795&ubb=showflat).

The panel occupies a consistent right-side location with its own scrollbar
and size controls. BG3 does leave a margin; the human's preference for our
flush, aligned sidebar is a project requirement, not a claim that BG3 is
literally attached to the screen edge.

The older full-HUD reference contains repeated XP entries. That is not the
behavior to copy: Patch 6 explicitly consolidated simultaneous party XP
awards from multiple kills into one total. Patch 5 corrected roll wording,
named weapon bonuses and improved links between losing stealth and its cause.
Patch 3 fixed hotbar reactions overlapping the log.
[Patch 6](https://baldursgate3.game/news/patch-6-now-live_108),
[Patch 5](https://baldursgate3.game/news/patch-5-now-live_99),
[Patch 3](https://baldursgate3.game/news/patch-3-mac-support-magic-mirror-more_93).

**Our additional requirements, not verified stock BG3 features:**

- Copy the visible log reliably, with deliberate selection behavior.
- Group a movement command while retaining its substeps and reactions for inspection.
- Present blood/residue as the spatial aftermath of damage, with known source
  and tile facts, rather than repeated anonymous condition gains.
- Use the recorded engine dice, modifiers, results and causal parents. Never
  regenerate arithmetic or infer hidden information in a widget.

The current native movement parent/substeps and damage ancestry are valuable
existing data. A polished presentation does not justify duplicating the event
system or replacing the projected combat log.

## 7. Relevant default PC controls

These are BG3 defaults, not a statement that our application implements all
of them. They are remappable.
[Keybind reference](https://bg3.wiki/wiki/Options).

| Input | BG3 function |
| --- | --- |
| Left click | World interaction / selected targeting action |
| Right click | Context menu; cancel a prepared action in its targeting context |
| Left Ctrl | Prepare main attack |
| F | Toggle melee/ranged weapon set |
| R | Toggle dual wielding |
| F1–F4 | Select party member |
| G | Toggle party grouping |
| WASD | Pan camera |
| Q / E | Rotate camera |
| Wheel | Zoom |
| Home | Center camera on character |
| O | Tactical camera |
| Alt | Show item labels |
| Shift | Show sneak cones |
| Backtick | Highlight characters |
| T | Examine / pin tooltip |
| Escape | Cancel / close |
| Space | End turn / cancel end-turn where allowed |
| Shift + Space | Toggle turn-based mode outside combat; context also includes fleeing |
| Z / V / X | Jump / shove / throw |
| K / L | Spellbook / reactions |

## 8. Evidence limits and next discussion

This collection answers the screen-layout and interaction questions with
actual game evidence. Screenshots do not establish BG3's internal event,
serialization, observer or rendering architecture. They also do not prove
log copying, hierarchical movement rows or every special targeting shortcut.
Those remain explicit requirements of our game.

The next design discussion can use the existing NeuroClient conventions and
this reference set to specify the repaired interface. The highest-value
differences are party selection versus turn ownership, explicit weapon choice,
readable icon states, contextual choices, spatial previews and a consistently
aligned log with details on demand. No production code was changed for this
research task.
