# Player UI repair — setup/material checkpoint

The previous UI was rejected by the user. This report does not convert test results
into visual acceptance. The current checkpoint is the actual playable layout,
proportions and materials; artwork regeneration and a final pixel-density standard
are deferred until that composition is accepted.

## Delivered in the existing owners

- Normal `python -m game` launch enters the Lantern Crypt with Fighter and Sorcerer.
  No character-creation screen. Existing explicit demo encounters remain available.
- Smaller left party portraits and separate top initiative. The active portrait
  has one highlighted border, with no redundant vertical bar. Party names/health
  are detached owned-party HUD facts, not a union of map visibility.
- A lean bottom action strip, explicit equipped melee/ranged controls, per-character
  preference, native spell rank/form choices and the on-demand ability library.
  Requested weapon slots never fall back to another slot. Accepted icon colors
  remain unchanged. Routine round/history paragraphs are removed.
- Quiet charcoal panel surfaces, consistent thin borders and restrained selection
  accents. Existing art at integer scales is provisional. Text remains antialiased.
- The log docks flush right. Native compact entries are the default; movement
  steps and damage aftermath fold under their native parents. Expansion/Math show
  original recorded detail, including dice. Fitting words no longer split because
  of per-glyph kerning estimates. Native turn headings no longer contain wrapping
  decorative dashes.
- Copy log copies admitted visible rows; Ctrl+C copies selected native text or a
  selected entry. Unrevealed outcomes are excluded. Actual SDL/X11 clipboard
  round-trip was checked separately from the deterministic headless input cases.
- Tile residue application wording uses the authored residue description instead
  of an anonymous creature-condition sentence. Native per-tile events remain
  intact under damage ancestry; this is not a new aggregate event or log generator.
- Each controlled observer uses an independent existing projection/reducer head
  and complete retained history. Turn handoff waits for visible playback to drain,
  clears old input/target state and selects the new command owner's permitted view.
  Frame traces carry observer identity; the summary returns that observer's complete
  history rather than a mixture of player streams.

## Dungeon content and exercised route

The 22×14 authored dungeon uses real floor, directional walls and doors, torches,
furniture, two loot chests, an optional trapped vault and a skeleton encounter.
No new trap, AI, campaign or rules subsystem was added. Review caught and corrected
north/south boundary placement, including the vault entrance. The lever is inside
the entry room, clear of the vault boundary, to make its approach unambiguous.

The native walkthrough completed: open/loot expedition supplies; open the vault;
enter its spike cell (HP 37→29 in the seeded run); open/loot its cache; return and
pull the trap lever; open both corridor doors; enter the burial hall; cast Magic
Missile at an enemy. It uses discovered commands, with native turn progression.
The game still uses the existing turn system throughout this map.

Evidence is kept outside version control in `.runtime/ui-repair-20261006/`:

- `dungeon-walkthrough.json` / `.log`: actual executed route, inventory and HP.
- `dungeon-1280x720`, `dungeon-1920x1080`, `dungeon-2560x1440`: Pygame framebuffer
  captures of play, player handoff, log and ability library.
- `combat-1280x720`: actual recorded-dice log capture using native Magic Missile.
- `index.html`: review viewer for those unmodified game images; not a game UI mockup.

## Verification and independent reviews

- 112 passed: affected encounter loop, per-observer HUD boundary, session and native
  body-residue cases. Added cases cover sealed dungeon routes/open doors and
  separated party visibility without sharing inventories.
- 22 passed: combat-log and physical SDL input cases, with explicit dummy display
  and audio drivers. The added wrapping case checks text that fits as a whole line.
- Earlier broader UI run: 38 passed and one incorrect new assertion counted enemy
  movement as player movement; corrected to require both player observers' movement
  in the complete final-observer stream, and its entire file passed in the 112 run.
- An interactive-display input rerun was nondeterministic; the complete 22-case
  input/log rerun above passed under explicit dummy SDL, without weakening the test.
- Anti-slop source review: no remaining blocking source finding after complete
  observer retention and native turn-heading fixes. Visual/design acceptance is
  explicitly not granted by this review.
- ECS/import-boundary source review: approved after the observer retention,
  north/south wall and recorded-senses fallback corrections. Reviewers did not
  claim to rerun the tests or approve final pixel density.
- Session, detached player facts and all changed UI modules pass static typing
  with zero errors and warnings. Broad player-loop static typing did not finish
  in bounded attempts; no clean result is claimed for that file. This limitation
  is separate from the completed tests.

The later human requests below authorize the bounded inventory layout repair.
Whole-world save/load, final artwork/material acceptance, resolution-specific
pixel production and a new exploration/campaign mode remain outside this
checkpoint. No artwork was imported or regenerated.

## Later October 6 corrections — grouped controls and shared glass

These supersede the single action strip and opaque-panel screenshots above.

- Four independently paged two-row blocks: Actions, Spells, Class abilities and
  carried usable Items. The headings are icons with hover names. Weapon modes
  stay explicit. Keys use the same painted controls as pointer clicks.
- Opening the combat log does not move, wrap or repage the bar. The flush-right
  log ends above controls and uses a narrow text gutter. Inventory, character,
  abilities, choices, context menu and tooltips share its translucent material.
  Panels clear the party rail and resource readout. The pause menu paints alone
  over the world and keeps every control inside smaller/scaled viewports.
- Hovering a multi-choice ability opens a compact strip above its source button.
  Every choice uses the bar's icon size. All spell levels and Sorcerer conversions
  use the same level symbols; actual summon/form/element variants use their
  existing art. There is no large rank panel, repeated spell image, cost footer or
  extra Select button. Final choices select the exact native action; dependent
  facets update the available choices first. Pointer travel into the strip,
  padding, wheel input and log overlap retain the strip's input priority.
- Sorcerer conversions publish their existing `slot_level` through the existing
  typed variant-facet DTO (`rank`). This is discovery metadata only: no conversion
  cost, grant, action economy or execution rule changed.
- Inventory uses native equipment slots around the portrait, a carried-item grid
  and a detail column. Hovering a slot lists compatible owned replacements;
  clicking performs native equip. Item details keep native use/unequip actions.
  The torch now points to the already registered torch icon, not a potion.
- Context cursors follow admitted interaction/target/inspection state. Hover
  outlines disappear on attack commitment and stay absent during playback.
- Log tree expansion and recorded-dice expansion are independent. Repeated hits,
  deaths, creature conditions, saves and reactions remain visible; blood tile
  aftermath stays under damage. Filtered-out selections cannot leak into copy.
  Glyph wrapping, native characters and exact recorded modifiers stay intact.

Current evidence under `.runtime/ui-repair-20261006/`:

- `details-{1280x720,1920x1080,2560x1440}`: ten real game frames per resolution,
  including hover spell levels, conversion, native equipment replacement,
  inventory/item/sheet and Fighter handoff. Each capture executes two native
  commands and reports zero presentation gaps.
- `combat-{1280x720,1920x1080,2560x1440}`: real repeated-hit log and ability library.
  Each executes one native command and reports zero presentation gaps.
- `index.html` now uses these refreshed images, including separate Spell levels
  and Conversion tabs. Earlier dungeon captures remain historical evidence.
- `final-hover-tests.log`: 34 passing native-choice, physical-input and log cases.
  Includes hover-to-level selection, native Sorcerer conversion, hover-to-equip,
  modal/keyboard capture, attack-highlight lifetime and filtered log copying.
- `final-ui-tests.log`: preceding 36-case run including detached HUD ownership.
- `final-equipment-log-tests.log`: 31 passing complete equipment/input/log/media
  cases. These runs overlap; their counts must not be summed as unique tests.
- `final-encounter-tests.log`: two passing complete encounter-loop cases.
- `overlay-input-tests.log`: four passing final cases after popup/log priority
  correction, including hover choices, native conversion, log text selection and
  viewport/menu bounds. All 37 files linked by the refreshed viewer return HTTP 200.
- Scoped UI, Sorcerer and variant-DTO typing passes. Encounter loop syntax is
  checked; the earlier broad typing runtime limitation remains as documented.

Independent anti-slop review inspected the compact strips and panel layering at
1280/1920/2560 and closed the menu-bounds defect. Independent ECS/DAG review
approved native metadata ownership and closed the popup/log input-priority
finding. These are bounded implementation/source reviews and sampled visual
checks; the human's design acceptance remains separate.


## Later correction — entrance wall joins

The human identified discontinuous wall joins in the entrance screenshot. Two
partitions used the opposite incident owner from the adjoining outer wall. The
Crypt now mounts the passage partition at x=7/EAST and vault partition at
y=8/NORTH. Physical blocked edges and door routes are unchanged. Four actual
camera captures report zero gaps, and the complete session file passes 4 tests.
No sprite pivots, floor pixels, shared render paths or collision rules changed.

The broader library/visual-thickness audit is handed to the human in
[the wall/floor handoff](../WALL_FLOOR_ASSET_ALIGNMENT_HANDOFF_2026-10-06.md).
That includes the separate floor/base overlap concern, legacy versus fixed-window
registrations, and prior measured cap/occluder mismatch. The local correction is
not an approval of every wall asset. Updated review evidence is under
`.runtime/ui-repair-20261006/wall-check/`; the existing UI captures are refreshed.

## Later correction — boundary lighting and desk clearance

The human's next screenshots exposed mismatched stone brightness beside doors.
Legacy walls discarded observed light and always used `world.authored` (0.62 RGB),
whereas environment doors sampled room lighting. Both now use the existing
disclosure/light treatment from observed incident supports. No unobserved light
value is used. Joined corners retain their source composite geometry and sample
its observed incident supports together; remembered and unobserved geometry retain
their respective existing treatments. This is the existing discrete light model,
not newly added continuous point-light shading or material recoloring.

The entrance writing desk moved from (1,3) to (2,4), clear of the wall's base.
All four current native captures were visually checked. Door blocking, route,
loot/trap/lever use and arrival at the enemy encounter were reverified with the
native walkthrough, ending in Magic Missile and recording HP 37→29 at the trap.

- `wall-check/light-before-tests.log`: all five light-level regressions failed
  before the repair, proving constant wall brightness.
- `wall-check/lighting-tests.log`: 122 passed; one water/wall overlap assertion
  still expected the old constant wall brightness. Its painter-order requirement
  was preserved and its reference wall updated to that scene's actual dim light.
- `wall-check/lighting-final-tests.log`: complete boundary file, 98 passed,
  including actual wall/door pixel changes, either-side lighting, hidden-light
  exclusion and all camera quarters. The 33 environment/app/session cases from
  the preceding run passed without changes.
- `wall-check/lighting-capture.log`: four native captures, zero presentation gaps.

The current screenshots supersede the previous lighting in the wall-check viewer.
The broader UI screenshots remain evidence for UI layout, not this lighting repair.

The follow-up plain-wall destruction audit found a real gap: the Crypt uses
non-targetable `environment.directional_wall`; all seven imported solid siblings
also register only intact media, with empty destruction mappings. Window parents,
their inserts and doors have separate working destruction banks. This is recorded
in the wall/floor handoff; do not call every wall animated or treat window-parent
break art as a compatible plain-wall replacement.
