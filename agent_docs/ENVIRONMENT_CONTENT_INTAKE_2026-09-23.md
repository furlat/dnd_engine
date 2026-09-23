# Environment content reconciliation — September 23

The user asked for direct discussion with environment-art task
`01a0b501-8a27-7413-ba24-4a36e5b140d2`: identify work that can be integrated as
new content using existing backend rules while the Fireball spatial-rendering
experiment continues separately. This record is the discussion result, not a
completed integration or a replacement for the broader interiors plan.

## Agreed scope

The artist confirmed the following **21 freestanding subjects** are faithful to
the delivered artwork as single composite props with baked decorative contents.
All have reviewed intact-entry, finite break and settled imagery in four views.

| Family | Exact source subjects |
| --- | --- |
| Household furniture | `generated-wardrobe`, `generated-bookshelf`, `generated-writing-desk`, `generated-bedside-stand`, `generated-work-stool`, `generated-storage-shelving`, `generated-ingredient-shelves`, `generated-preparation-counter`, `generated-sack-bundles` |
| Wooden seating | `misc-b53` chair, `misc-b26` bench |
| Pottery | `misc-a2` jar, `misc-a3` jar group, `misc-a4` pottery cluster |
| Storage props | `misc-a9` barrel cluster, `misc-b2` crate stack, `misc-b3` large crate stack |
| Stone props | `misc-c5` animal statue, `misc-c6` winged statue, `misc-c7` pedestal, `misc-c9` stone bench |

Three optional subjects are also indexed: `misc-a7` lidded vessel, `misc-c2`
anvil, and `generated-candlesticks` as an unlit prop. The complete 24-subject
handoff has 28 banks because some subjects have alternative impact animations;
it does not imply 28 gameplay species.

Fresh source handoff:
[/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/content-intake-2026-09-23/HANDOFF.md](/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/content-intake-2026-09-23/HANDOFF.md).
Adjacent `freestanding-candidates.json` supplies exact metadata/sheet/review
paths, state conventions, frame counts, pivots and preview footprint hints.
Preview dimensions are not final native collision profiles.

## Existing owners verified in this checkout

- `dnd/content/items/world_prop_builders.py`: one ordinary `WorldItem`, Health,
  oriented multi-cell footprint, same-identity destruction and optional owned
  difficult-terrain debris. Bed and table already use this path.
- `dnd/content/items/authored_item_definitions.py`: `StaticBlockerDefinition`
  already exposes explicit placement, height and movement/optics/propagation
  settings. Native placement and query mechanisms already support these facts.
- `dnd/content/items/authored_item_builders.py`: the existing direct item table
  composes both content families. No new runtime registry is required.
- `dnd/core/item_types.py` and `dnd/blocks/base_item.py`: the destruction profile
  and native transition retain identity and cascade physical consequences.
- `game/environment_art.py`, `game/data/environment_art.json` and
  `devtools/import_environment_props.py`: existing passive bindings, source
  packaging, finite playback and settled frame selection.

The current furniture profile exposes footprint, material, HP and debris choice,
but its builder fixes height to one step, movement blocking to true and optical/
propagation blocking to false. Those defaults are not suitable for every shelf
or statue. Exposing existing placement/channel facts as passive profile fields
is content-authoring support, not a new visibility or movement rule. Exact
physical values still need authoring; copying table defaults would be wrong.

Each new subject can therefore be a real targetable object with native HP,
collision/visibility policy, destruction event and persistent aftermath. There
is no need for an individual Python behavior class per chair, jar or statue.

## Agreed interpretation and limits

- Freestanding shelves and desks are one object. Their animated books, bottles
  and papers are baked decorative components, not separate inventory or supported
  child entities. The artist explicitly confirmed this interpretation.
- This new batch has **no authored use/open animation**. Wardrobes do not gain
  chest actions merely because their art depicts doors. No sitting, crafting,
  rest, trade or new container rule is implied by a prop name.
- No required gameplay liquid spill is specified for these selected subjects.
  Ordinary pottery/barrels are not silently oil or poison sources.
- Preserve each bank's source registration and finite timing; many use 384-pixel
  cells. The installed prop path already uses the 127-to-128 tile registration.
  Do not resize all subjects to an arbitrary common canvas or replay the break
  on discovering an already destroyed object.
- Source alternatives must remain stable through replay and late observation;
  installing one explicit alternative is sufficient for an initial content row.
- The artist's handoff includes its own file-identity evidence. No hashing,
  source audits or directory discovery is added to production by this intake.

## Separate from this content-only batch

Wash-basin artwork visibly spills water. It needs an explicit liquid behavior
choice and is excluded from a dry-prop interpretation. Candlesticks have no
accepted lit/unlit/flame socket contract in this batch. Mounted banners, signs,
wall shelves, and separate tabletop objects need their actual support/aftermath
handling; floor-baked banks must not be lifted onto a wall.

Window sill/header/jamb behavior, full house assembly, stacked floors and
structural collapse remain distinct work. The artist's native window experiment
tested whole-edge sight/light passage with movement blocked, not a completed
aperture system. Building style art is not proof of those rules.

The newer fixture-destruction package remains explicitly candidate artwork,
including its corrected active spikes. Its independent review is not new user
acceptance. Do not silently combine it with this reviewed decor collection.

Already installed, confirmed in current data: 16 authored door families plus
the generic alias; 12 blade/crusher profiles; bed, table, crate, three chest
styles, and the shared barrel body for six liquids. The old consolidated
handoff predates parts of that integration and must not restart them.

Only source/code inspection and task coordination were performed for this
request. No art imported, runtime behavior changed, or new test result claimed.
