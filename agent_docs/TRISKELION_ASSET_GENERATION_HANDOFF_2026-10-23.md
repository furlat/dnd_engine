# Triskelion Outer Ward: asset generation handoff (visual counterparts)

23 October 2026, branch `content_push_opus`. This lists every **distinct** environment
asset the Outer Ward ground floor needs, so each can be made once and reused.
**Room composition is a separate later pass**, so there are no placements or layouts
here. Rooms are listed only to show where an asset is used and how many copies the
book implies.

Source: the book transcription
(`/home/tommaso/.codex/worktrees/triskelion-backend/dnd_engine/agent_docs/triskelion-outerward-floor-00/SOURCE_TRANSCRIPTION.md`),
read in full. Cross-checked against the stopped worktree's `ASSETS_TO_AUTHOR.md` and
`PLACEMENT_REFERENCE.md` (its documentation is a brief; its code is not adopted). Engine
plan: [content push plan](plans/CONTENT_PUSH_OPUS_PLAN_2026-10-23.md).

## How to read this

- **Size:** the asset's own footprint in 5-ft cells (W×D), rounded to the grid. "Wall" means
  it sits on a wall boundary cell; "decal" means a flat floor or wall overlay with no
  collision. Book dimensions are quoted where given.
- **States:** the visual states the client must draw. Every breakable asset also needs a
  **destroyed** state: debris, rubble or wreck, matching how existing doors, walls and props
  break.
- **Breakable:** yes or no. The default is **yes** for anything physical and freestanding.
  "No" covers floors, decals, wall linings, masonry hearths built into walls, stairs and
  platform supports, water, and remains.
- **Source:**
  - `reuse <id>`: an existing engine item; its art may already exist, so check the
    environment library first.
  - `variant of <id>`: same mechanics, new look.
  - `new`: new asset.
- **Style and technique:** match the existing environment library (`fantasy-unified-catalog`)
  camera, scale, depth/normal companions and break banks; see [ASSETS.md](../ASSETS.md).
  The old brief rejected some techniques, and that still holds: no recolour or tint
  stand-ins for distinct materials, no resized wrong-form props, no generic banners for
  hunting tapestries.

## 1. Floors, surfaces and wall linings (not breakable; tileable)

| Asset | Used in | Notes |
| --- | --- | --- |
| Cobblestone ground, weathered, with litter overlay (leaves, pebbles, bones, trash) | R1 | Outdoor |
| Wooden bridge deck over a trench | R1 | Plank deck plus trench edge |
| Cobbled stone bridge deck, open edges | R68 | Steep drop to the south |
| Dressed stone, damp and mouldy (default walls/floor) | most rooms | Base shell |
| Red wood panelling, walls and floor | R3 | Pleasant wood; heavy cobwebs |
| Polished gray marble, walls and floor | R4 | |
| Gray tile floor with small drains | R5 | |
| Wooden plank floor (creaking) | R7, R38, R59 (hardwood), R66, R67 | |
| White plaster walls | R7, R17 | R17 bloodstained |
| Orange-yellow plaster, dirty | R8 | |
| Dull gray painted stone, walls and floor | R12 | |
| Yellow wood boards with metal channel inlays (the electric floor) | R15 | Must read clearly unlike the carpet |
| Yellow-tan pine floor | R18, R19 | |
| Carved stone faces (laughing, scowling, crying) on walls and floor | R20 | Same faces as the R4 statue |
| Slate floor | R21 | |
| Red-veined black marble, walls and floor | R24 | |
| Gray mould floor (two states: dormant, spores erupting) | R26 | Hazard visual |
| Wood wall panelling | R29, R38, R56 | |
| Earthen floor | R30 | |
| Green wallpaper with a pale rectangle where a painting was | R32 | |
| Red-and-black checker tile, cracked and worn | R37 | |
| Lemon-yellow walls | R40 | |
| White tile floor, chipped and filthy | R40 | |
| Red-and-white checker tile | R44 | |
| Dark wood panelling | R45, R66 | |
| Blue/green vertical-stripe wallpaper | R54 | |
| Pink/light-blue stripe decor | R56 | |
| Burned-out room: blackened exposed stone, singed beams | R57 | |
| Blue-and-white diamond wallpaper | R58, R59 | |
| Blue-and-white striped wallpaper | R60 | |
| Walls covered with crude charcoal drawings | R61 | |
| White tile, walls and floor | R62, R65 | |
| White tile with purple fungus in the cracks | R65 | Hazard visual |
| Red wallpaper | R63, R64 | |
| Stone floor, bloodstained, with dried gore | R17 | |
| Stone walls | R67 | |
| Wooden ceiling beams (optional, if ceilings are drawn) | general | R57 singed |
| Crown mouldings (optional wall-top trim): oak leaves, grape vines, black Triskelion shields, sailing ships | R2, R21, R40, R58 | Decorative |

**Carpets** (floor overlays, not breakable): red, lush, mud- and blood-stained (R15, about
4×8 cells, plus 3-ft strips to six arches); red runner (R46, 8×2); blue (R45); light blue
(R56); light gray with bloodstains (R58).

## 2. Openings, doors, windows, stairs (architecture)

| Asset | Used in | Size | States | Breakable | Source |
| --- | --- | --- | --- | --- | --- |
| Open arch, 5 ft and 10 ft | ~40 rooms; R15 six arches; R35/R43/R67 arcades | wall, 1 or 2 cells | — | no | new or existing wall family |
| Empty doorway with rusty hinges (outer doors torn off) | R1 | wall, 2 cells | — | no | new |
| Standard wooden door | most rooms | wall, 1 cell | open, closed, **locked**, destroyed | yes | reuse `environment.door.indoor_door_*` |
| Double door, 10 ft | R37/R42, R42/R43 | wall, 2 cells | open, closed, destroyed | yes | variant of indoor door |
| Large double door, 20 ft (to the bridge) | R43/R68 | wall, 4 cells | open, closed, destroyed | yes | new |
| Barred door, bar on one side | R14 | wall, 1 cell | barred, unbarred, open, destroyed | yes | variant of indoor door, plus bar |
| Door with an iron skull emblem | R42 | wall, 1 cell | open, closed, destroyed | yes | variant of indoor door |
| Door with its lower part chewed away (pre-damaged) | R51 | wall, 1 cell | open, closed, destroyed | yes | variant of indoor door |
| Badly burned door, still working | R57 | wall, 1 cell | open, closed, destroyed | yes | variant of indoor door |
| Window, plain glass, intact | R3 (dirt-streaked, 6), R39 (5), R44 (12) | wall, 1 cell | intact, broken | yes | reuse `environment.window.*` |
| Window, plain glass, **hinged** | R9 (2), R10 (2), R11 (2), R51 (3), R64 (4) | wall, 1 cell | closed, open, broken | yes | variant, open state new |
| Window, small, high-set thick glass | R5 (3), R6 (3), R47 (8) | wall, 1 cell | intact, broken | yes | variant |
| Window, plain glass smeared with foul resin | R19 (5) | wall, 1 cell | intact, broken | yes | variant |
| Window, large glass, broken, with floor shards | R34 (3) | wall, 1 cell | broken | yes | reuse, broken state |
| Stained-glass window, one per motif (all have intact and broken states) | see next six rows | wall, 1 cell | intact, broken | yes | new art per motif |
| — already broken, motif lost | R2 (6) | | broken | | |
| — feasting and fighting scenes | R35 (7) | | | | |
| — red and green | R52 (3) | | | | |
| — green nymphs | R60 (5) | | | | |
| — snowy mountain peaks | R61 (2) | | | | |
| — bathing blue nymphs | R62 (2); dirty stained glass, motif unspecified, R65 (3) | | | | |
| Skylight opening, 20×20 ft, with frame and light shaft | R37 | 4×4 ceiling opening | — | no | new |
| River arches in the north wall | R68 | wall | — | no | new |
| Stair going up (map exit) | R3, R33, R38, R67 | 2×2 | — | no | new (spiral where the book shows one) |
| Stair going down (map exit) | R3, R21, R44 | 2×2 | — | no | new |
| Auction block: raised wooden platform 20×20 ft, 10 ft high, fascia and supports | R7 | 4×4, +10 ft | — | no (support) | new |
| Wooden platform stairs | R7 | 2×3 each (two) | — | no | new |
| Trapdoor in the platform top | R7 | 1×1 | closed (opening not supported) | no | new |
| Secret false back in a wardrobe (R52) and a cabinet (R62) | R52, R62 | part of the furniture | closed, open | — | see §4 |

## 3. Furniture

| Asset | Used in (count) | Size | States | Breakable | Source |
| --- | --- | --- | --- | --- | --- |
| Table, plain wooden | R8 (rickety), R13, R25, R27, R28, R32, R33, R40, R51, R56, R58, R60, R63 | 1×1 to 1×2 | intact, destroyed | yes | reuse `table` / `small_wooden_table` |
| Long dining table with benches (feast hall) | R35 (enough for 70) | table 1×3 + 2 benches 1×3 | intact, destroyed | yes | new |
| Card table, green felt | R32, R45 | 1×1 | intact, destroyed | yes | new |
| Stack of green-felt card tables (pile of about 3) | R45 (~8 stacks) | 1×1 | intact, destroyed | yes | new |
| Coffee table / end table, short | R51, R54, R63 | 1×1 | intact, destroyed | yes | new |
| Worktable with oils and sharpening tools | R16 | 1×2 | intact, destroyed | yes | new |
| Woodworking bench | R19 | 1×2 | intact, destroyed | yes | variant of `preparation_counter` |
| Bar counter (tavern), continuous run | R38 | 1×1 modules (straight, end) | intact, destroyed | yes | new |
| Writing desk | R8, R9 (huge), R10, R11, R51, R60, R63 | 1×1 to 1×2 | intact, destroyed | yes | reuse `writing_desk`; huge-desk variant |
| Desk overturned, one leg torn off (pre-broken) | R8 | 1×1 | — | yes | variant |
| Chair, wooden | R8, R9 (massive), R10, R11, R13, R19, R25, R33, R51, R60, R63 | 1×1 | intact, destroyed | yes | reuse `wooden_chair`; massive-chair variant |
| Chair lying broken on its side | R13, R33 | 1×1 | — | yes | variant |
| Restraint chair (neck and wrist guards) | R11 (2) | 1×1 | intact, destroyed | yes | new |
| Padded chair | R50 (2), R63 (2) | 1×1 | intact, destroyed | yes | new |
| Couch, one per upholstery | see next five rows | 1×2 | intact, destroyed | yes | new art per colour |
| — black/white striped (slime-trailed) | R51 (2) | | | | |
| — dark green | R54 (3) | | | | |
| — pink/light-blue striped | R56 | | | | |
| — red/gray (two form the barricade) | R63 | | | | |
| — lounge couch | R32 | | | | |
| Bench, wooden | R35 | 1×3 | intact, destroyed | yes | reuse `wooden_bench` (long variant) |
| Bed, simple | R49 (green bedding), R50 (red/white striped), R53 (blue/white diamond), R55 | 1×2 | intact, destroyed | yes | reuse `bed`; bedding variants |
| Barracks bed (pre-ruined in R34) | R34, R48 | 1×2 | intact, wrecked | yes | reuse `bed` |
| Cot, foul and stained | R29 (10) | 1×2 | intact, destroyed | yes | new |
| Four-poster bed | R52 (red, neat, dusty), R61 (stained, ripped bedding) | 2×2 | intact, destroyed | yes | new |
| Large comfortable bed | R64 | 2×2 | intact, destroyed | yes | variant of four-poster |
| Dresser | R48, R55 | 1×1 | closed, open, destroyed | yes | variant of `bedside_stand` |
| Dresser with an attached mirror | R49, R50 | 1×1 | intact, mirror smashed, destroyed | yes | new |
| Large dresser with mirror (mirrors smashed) | R53 (4) | 1×1 | — | yes | same as above, smashed state |
| Wardrobe | R55, R60 (knife-slashed), R61 | 1×1 | closed, open, destroyed | yes | reuse `wardrobe` |
| Wardrobe, large, with false back and interior hook | R52 | 1×1 | closed, open, secret open, destroyed | yes | new |
| Armoire | R61 | 1×1 | closed, open, destroyed | yes | new |
| Cabinet | R27 (wooden, several) | 1×1 | closed, open, destroyed | yes | new |
| White cabinet with a carved mermaid holding a jug, false back | R62 | 1×1 | closed, open, secret open, destroyed | yes | new |
| White bath cabinet | R65 | 1×1 | closed, open, destroyed | yes | new |
| Bookcase | R9 (small), R10 (large), R63 | 1×1 | intact, destroyed | yes | reuse `bookshelf` |
| Shelf of bloodstained execution logs | R9 | 1×1 | intact, destroyed | yes | variant of `bookshelf` |
| Ornate hat rack | R39 | 1×1 | intact, destroyed | yes | new |
| Battered rich furniture pushed against walls | R58 | 1×1 to 1×2 | intact, destroyed | yes | variants above |
| Odd surplus furniture and musty rugs (storeroom clutter) | R22 | 1×1 | intact, destroyed | yes | new |

## 4. Containers

All containers are breakable; destruction spills their contents.

| Asset | Used in (count) | Size | States | Source |
| --- | --- | --- | --- | --- |
| Footlocker | R34 (battered), R48, R53 (8), R64 | 1×1 | closed, open, **locked**, destroyed | new |
| Small wooden chest | R49, R50 | 1×1 | closed, open, **locked**, destroyed | reuse `storage_chest` / fantasy chest |
| Iron-bound chest | R29 | 1×1 | closed, open, locked, destroyed | new |
| Huge padlocked iron chest | R52 | 1×2 | padlocked, open, destroyed | new |
| Small iron box with a lock | R61 | 1×1 | locked, open, destroyed | new |
| Long, shallow wooden box | R61 | 1×1 | closed, open, destroyed | new |
| Small chest under a loose floorboard | R38 | under a 1×1 floorboard | closed, open | reuse `loose_floorboards` plus a small chest |
| Keg | R2 (lighting oil, 2), R27 (sour wine) | 1×1 | intact, destroyed | variant of `oil_barrel` |
| Barrel, painted black X | R27 | 1×1 | closed, open, destroyed | variant of barrel |
| Barrels (salted meat, brackish water) | R31 (2) | 1×1 | intact, destroyed | reuse barrel family |
| Casks (salted pork, pickled fish) | R60 (5), R61 | 1×1 | intact, destroyed | variant of barrel |
| Sack, large (spilled sugar), small salt sacks | R27 | 1×1 | intact, spilled, destroyed | reuse `sack_bundles` plus a spilled state |
| Green drawstring sack embroidered "Old Jed" | R39 (hangs on the hat rack) | 1×1 | intact, destroyed | new |
| Bucket | R5 | 1×1 | intact, destroyed | new |
| Metal vat, large | R28 (3) | 1×1 | intact, destroyed | new |
| Glass canister, sealed | R65 (3, inside the cabinet) | item art | closed, open, broken | new |
| Teapot catching drips | R62 | 1×1 | — | new |
| Coffin, complete, with lid | R18 (6) | 1×2 | closed, open, destroyed | new |
| Coffin, partly assembled | R18 (4) | 1×2 | — | new |
| Pine planking pile | R18 | 1×1 | intact, destroyed | reuse `timber_pile` |

## 5. Fixtures, plumbing, workshop, hearths

| Asset | Used in (count) | Size | States | Breakable | Source |
| --- | --- | --- | --- | --- | --- |
| Wall pump, broken but dripping | R5 | wall | dripping | yes | new |
| Floor drain / grate | R5, R17 | decal | — | no | new |
| Pump faucets, blue (cold) and red (hot), dry | R27 (2) | wall | — | yes | new |
| Free-standing hand pump (working) | R28 | 1×1 | — | yes | new |
| Bathtub tap, dripping or dry | R62, R65 | part of the tub | dripping, dry | — | — |
| Primitive toilet: alcove with a board with a hole | R26 (6), R47 (6) | 1×1 against a wall | — | yes | new |
| Porcelain toilet, white and blue | R62, R65 | 1×1 | — | yes | new |
| Ornamental brass bathtub, large and huge | R62, R65 | 1×2 | — | yes | new |
| Fire pit, cold, gray ash | R28 | 1×1 | cold | no | reuse `cold_fire_pit` |
| Anvil | R28 | 1×1 | — | yes | reuse `anvil` |
| Metal tools pile (hammers, tongs, shovels, chains) | R28 | 1×1 | — | yes | variant of `workshop_apparatus` |
| Carpentry tools | R19 | 1×1 | — | yes | variant of `workshop_apparatus` |
| Grindstone (sharpening) | R16 | 1×1 | — | yes | reuse `grindstone` |
| Tool rack (wall) | R28 | wall | — | yes | new |
| Wall fireplace (masonry hearth with lintel and mantle), one style per size | see next four rows | wall, 2 cells | cold, lit | no (part of the wall) | new |
| — large, unnaturally cold | R2 | | cold | | |
| — huge | R35, R67 | | | | |
| — ornate | R48 | | | | |
| — ordinary | R52, R54, R56 (lit, burning furniture), R58, R60, R61 (lit), R63, R64; grand R66 | | | | |
| Nymph fountain: black-marble nymph pouring from a vase into a blood-red stone basin | R24 | 2×2 | trickling foul green water | yes | new |

## 6. Lights

Light only where the book says it's lit.

| Asset | Used in (count) | Size | States | Breakable | Source |
| --- | --- | --- | --- | --- | --- |
| Continual-light rod, wall-mounted (torch-sized metal rod) | R4 (2 lit), R37 (4 lit), R46 (4 lit) | wall | lit, plus an empty recess for missing rods | yes | new |
| Wrought-iron cresset (torch holder) | most rooms; R7 many | wall | empty, holding a torch | no | new |
| Wall torch | R7 (3, unlit), R38 (3, burning) | wall | lit, unlit | yes | reuse `wall_torch` |
| Large bronze chandelier | R40 | 2×2 ceiling | unlit | yes | new |
| Red crystal chandelier | R45 (2) | 2×2 ceiling | unlit | yes | new |
| Large candelabrum | R54 (3) | 1×1 | unlit | yes | variant of `unlit_candlesticks` |
| Black candles, many (shrine) | R64 | 1×1 | unlit | yes | variant of `unlit_candlesticks` |

## 7. Wall decor, textiles, displays, racks

| Asset | Used in (count) | Size | States | Breakable | Source |
| --- | --- | --- | --- | --- | --- |
| Hanging tapestry, hunting scene (valuable; can be taken down) | R23 (7) | wall | hanging, removed | yes | new |
| Rolled tapestry, bulky and mouldy | R22 (6) | 1×1 | — | yes | new |
| Curtains lining walls, one per colour | R37 (red, frayed), R49 (green, with a bulge and feet poking out), R50 (red/white striped) | wall | — | yes | new |
| Tavern sign: pale-yellow bear skull, side view, on blue | R37 | wall | — | yes | new |
| Kite shield with Triskelion insignia on the wall (takeable) | R39 (17) | wall | mounted, removed (pale mark) | yes | new |
| Tattered captured-enemy banners | R42 | wall | — | yes | variant of the `tall_red_banner` family (new art) |
| Gilded plate armour on a stand | R42 (4; one without its great helm) | 1×1 | with helm, without helm, empty stand | yes | new |
| Featureless wooden manikin | R49 | 1×1 | behind curtain, revealed | yes | new |
| Training dummy | R67 | 1×1 | — | yes | reuse `training_dummy` |
| Dartboard (wall) | R32 | wall | — | yes | new |
| Weapon rack with rusted bardiches | R16 | wall, 1×1 | full, partly empty, empty | yes | new |
| Polearm rack (spears, awl pikes, guisarmes) | R36 | wall, 1×1 | full, partly empty, empty | yes | new |
| Sword rack | R46 (empty) | wall | empty, full | yes | new |
| Weapon-and-armour rack | R48 | wall | full, empty | yes | new |
| Practice weapon and shield rack (wooden) | R67 | wall | full, empty | yes | new |
| Iron rings, chains and manacles set in walls | R6, R17 | wall decal | — | no | new |
| Antlers and mounted deer heads | R66 | wall | — | yes | new |
| Portrait, framed, one image per subject (all portraits, cropped or full) | see next five rows | wall | hanging, slashed | yes | new art per subject |
| — Santiago Triskelion (labeled) | R54 | | | | |
| — Alfonsina Triskelion holding a globe of tiny numbers | R56 | | | | |
| — Vittorino Triskelion, signed Patrizio | R63 | | | | |
| — Sergi Triskelion | R66, above the mantle | | | | |
| — Luciana (girl, ~10) and Salvatrice (girl, ~8) | R66, north wall | | | | |
| Painting "The Hunt": Sergi on horseback charging a hydra with rooster heads | R66 | wall | hanging, slashed | yes | new |
| Slashed, discarded paintings | R61 | 1×1 floor | — | yes | new |
| Hanging golden figure in manacles (Armand Triskelion; creature deferred, place as inert) | R1, above the inner arch | wall | — | no | new |

## 8. Statues, taxidermy, shrine

| Asset | Used in (count) | Size | States | Breakable | Source |
| --- | --- | --- | --- | --- | --- |
| Triskelion statue, marble: three faces (scowl, laugh, cry), three legs and arms holding staff, sword and nine-tailed whip, Phrygian caps | R4 | 2×2 | intact, destroyed | yes | new |
| Shrine: marble platform, many black candles, small malformed green-metal idol | R64 alcove | 1×2 platform; idol is item art | idol present, removed | platform yes | new |
| Stuffed bear (one partly eaten) | R66 (2) | 2×2 | intact, damaged, destroyed | yes | new |
| Stuffed elk | R66 | 2×2 | intact, destroyed | yes | new |
| Stuffed wolf | R66 (5) | 1×1 | intact, destroyed | yes | new |
| Stuffed lion | R66 | 1×2 | intact, destroyed | yes | new |
| Stuffed hippogriff | R66 | 2×2 | intact, destroyed | yes | new |
| Stuffed giant skunk | R66 | 1×1 | intact, destroyed | yes | new |
| Stuffed eagle on a branch perch | R66 (3) | 1×1 | intact, destroyed | yes | new |
| Small taxidermy cluster (waterfowl, weasels, cats, foxes, rabbits), many missing limbs | R66 (several) | 1×1 | intact, destroyed | yes | new |
| Dragon skeleton, 18 ft, hung on wire from the ceiling (inert, nonblocking) | R35 | ~4×2, raised | — | yes | new |

## 9. Remains, corpses, floor dressing (not breakable; searchable remains)

| Asset | Used in | Size | Notes |
| --- | --- | --- | --- |
| Skeleton seated in a chair, wearing leather armour | R8 | 1×1 | Pairs with a chair |
| Obese moldering corpse with a gold chain, crumpled under a desk | R9 | 1×1 | |
| Skeletal remains, crunched bones (scatter) | R14 (13), R1 | decal / 1×1 | Nonblocking |
| Hunched skeletal mage in blue-green robes with yellow silk lightning bolts, seated at a table | R33 | 1×1 | |
| Drained, savaged small creature corpses (dementings) | R40 (4) | 1×1 | |
| Small decayed human corpse | R47 | 1×1 | |
| Gore-smeared headsman's block | R17 (several) | 1×1 | Breakable yes |
| Rat nest (pillows, blankets, clothes, paper) | R12 | 1×1 | |
| Monster nest (furniture bits, rugs, clothes, garbage) | R41 (NW recess) | 2×2 | |
| Garbage, rags and dirt pile | R20 | 1×1 | |
| Dirty straw patch | R2, R33 | 1×1 | reuse `loose_straw_*` |
| Scattered metal plates, bowls, utensils | R13 | decal | |
| Scattered coins and wooden gaming tokens | R45 | decal | |
| Smashed glass shards | R34, R53 | decal | |
| Droppings / excrement | R12, R30 | decal | |
| Dog bowls, rawhides, brushes | R30 | 1×1 | |
| Wooden dog hutch | R31 (24) | 1×1 | Breakable yes |
| Slime trail | R51 | decal | |
| Burned furniture and ash patches | R57, R56 | 1×1 | |
| Cobwebs, corner and heavy | R3, R6, R8, R11, R36, R66 | wall/corner decal | |
| Blood stains, bloody handprints | R17, R58; dressing table | decal | |

**Random dungeon dressing** (book p.5, optional decals and props): small urine puddle, red wax
drippings, dagger hilt, clump of dirty straw, badly dented helmet, bloody handprints on a
wall, corpse of a small creature or goblin.

## 10. Water and terrain

| Asset | Used in | States | Notes |
| --- | --- | --- | --- |
| Rushing river, flowing north to south, ~10 ft deep (animated) | R68 | flowing | Swim terrain; no current simulation |
| Waterfall edge and drop to the south (backdrop) | R68 | — | Off-map scenery |
| Outer trench under the entrance bridge | R1 | — | |
| Dripping water and puddles | R5, R62 | dripping | Decal |
| Foul green water in the fountain basin | R24 | trickle | Part of the fountain |

## 11. Items needing ground/inventory art (new kinds only)

Weapons and armour:
- bardiche (rusted), spear, awl pike, guisarme (each functional and ruined);
- kite shield with the Triskelion insignia;
- gilded plate armour and great helm;
- studded black leather armour with a skull face;
- silver dagger;
- shield with a green griffon crest.

Treasure and trinkets:
- gold chain of office;
- ruby earring;
- silver ring with the Triskelion insignia;
- silver crane brooch;
- silver chalice, pewter cup;
- jade and cherrywood snuff boxes;
- ivory elephant carving;
- marble cockatrice statuette;
- chrysoberyl, agate, moonstone;
- jade-and-silver key; other keys;
- silver lock with key on a rusty chain.

Consumables and containers:
- brandy bottle;
- vinegar bottle labelled "potion of healing";
- orange potion (Super-Heroism);
- jar of grape jam;
- glass canisters;
- soaps, candles, towels;
- meerschaum pipes (old man's face, devil's face);
- pouch of blue-green leaf.

Magic and special items:
- mood ring (black, red, yellow and white states);
- red-bound book;
- Wand of Illumination;
- bull's-eye lantern set with bloodstones;
- gray Cloak of Protection with fish and bird embroidery;
- Boots of Elvenkind;
- the green-metal idol;
- thieves' tools (intact; broken on a failed pick);
- Trap Disarm Toolkit (consumed when a disarm fails).

Wealth and gaming:
- coin stacks (copper, silver spanners, gold crescents, dwarven mabans);
- wooden gaming tokens.

## 12. Interactions and state transitions (what to animate)

Beyond breaking, these are the state changes the game will drive. Each row is one transition.
Any asset marked breakable in §2–§8 also needs a **break** transition: the intact asset bursts
into the destroyed state, splinters, glass or stone by material, and contents spill for
containers. That isn't repeated per row below. "Loop" means an idle animation while in the
state.

### 12.1 Doors and openings

| Asset | Interaction | From → to | What visibly happens |
| --- | --- | --- | --- |
| Standard, double, skull, burned, chewed doors | Open / Close | closed ↔ open | Door leaf swings on its hinges; double doors swing both leaves |
| Any lockable door | Unlock or lock with a key | locked ↔ closed | Small lock action at the keyhole (click); leaf doesn't move |
| Any lockable door | Pick lock (success / failure) | locked → closed / stays locked | Lock jiggles; on success a click and slight give; on failure the thieves' tools snap (item-level) and nothing moves |
| Any lockable door | Force (Strength) | locked → open | Door slams open with a burst at the lock and latch |
| Barred door | Lift the bar off / put it back | barred ↔ unbarred | Wooden bar lifted out of its iron brackets and set aside, or placed back; only from the bar side |
| Wardrobe false back (R52) | Twist the interior hook | closed → secret open | Hook turns; the wardrobe's back panel swings away, revealing a passage |
| Mermaid cabinet false back (R62) | Twist the mermaid's jug | closed → secret open | Carved jug rotates; the shelves' back panel swings open |
| Hinged windows | Open / Close | closed ↔ open | Glass casement swings on side hinges |
| Any window | Break | intact → broken | Glass shatters outward/inward and shards fall to the floor (§9 shard decal remains) |

### 12.2 Containers

| Asset | Interaction | From → to | What visibly happens |
| --- | --- | --- | --- |
| Chests, footlockers, iron box, long box, coffin | Open / Close | closed ↔ open | Lid lifts on hinges; coffins: lid slides aside |
| Lockable containers | Unlock with a key / pick lock / force | locked → closed or open | As for doors; a **padlock** (R52 iron chest, R61 box) drops open |
| Small chest R49 (dart trap) | Open while trapped | closed → open + trap spent | Four darts shoot **inward** from the chest's sides; afterwards empty dart slots show |
| Footlocker R53 (needle trap) | Open while trapped | closed → open + trap spent | A needle flicks out of the lock plate, then retracts; trap now spent |
| Trapped container | Disarm with a Trap Disarm Toolkit (success / failure) | trapped → spent / triggered | Success: small jam or pin action at the mechanism. Failure: the toolkit snaps and the trap fires as if opened |
| Loose floorboard R38 | Lift / Replace | in place ↔ lifted | Board pried up and laid aside, showing the small chest below |
| Dresser, cabinet, wardrobe, armoire | Open / Search | closed ↔ open | Doors or drawers open; after a search, contents look disturbed |
| Barrel with X, sacks, kegs | Search / Open | closed → open | Lid off or sack mouth opened, rummaged contents (cotton wads for the X barrel) |
| Liquid barrels and kegs | Break | intact → destroyed | Staves burst and the liquid spills into a spreading puddle decal (water, brine, oil, wine) |
| Sugar sack R27 | (already spilled) | — | Spill decal with ants (ambient loop) |
| Glass canisters R65 | Open | sealed → open | Lid unscrewed (item-level) |

### 12.3 Searchable things (contents gated by a check)

| Asset | Interaction | From → to | What visibly happens |
| --- | --- | --- | --- |
| Desks, nests, straw, remains, garbage, bookcases, boots, pillow | Search (check succeeds / fails) | unsearched → searched | Rummage: items shuffled, straw/rags pushed aside, a pillow torn open; the asset keeps a "searched/disturbed" look. Failure: same rummage, no reveal |
| Corpses and skeletons | Search | unsearched → searched | Clothing/armour pulled at, pockets opened; remains shift slightly |
| Inspector desk R11 | Search under the desk | hidden → revealed | Lump of red wax with coins pried off the underside |
| Card-table pile R45 | Search | — | Tables shift (spider lair; creature deferred) |

### 12.4 Things that can be taken off walls, racks and stands

| Asset | Interaction | From → to | What visibly happens |
| --- | --- | --- | --- |
| Weapon racks (bardiche, polearm, sword, armour, practice) | Take a weapon | full → partly empty → empty | One weapon lifted from its pegs; rack shows gaps, then empty |
| Kite shields R39 | Take down | mounted → removed | Shield lifted off its wall hook; a pale outline remains |
| Gilded plate armour stands R42 | Take armour / helm | full → without helm → empty stand | Pieces lifted off the stand |
| Tapestries R23 | Take down | hanging → removed | Tapestry unhooked and drops/rolls up; wall bare |
| Hat rack and "Old Jed" sack R39 | Take the sack | sack on rack → empty rack | Sack lifted off its hook |
| Shrine idol R64 | Take / return the idol | on platform ↔ removed | Small idol lifted; empty spot among the candles |
| Continual-light rods | Take a rod | in socket (lit) → empty recess | Rod pulled from its socket; the light goes with the rod |
| Wall torch | Take from cresset / place | in cresset ↔ empty cresset | Torch lifted; cresset empty |

### 12.5 Curtains, coverings and reveals

| Asset | Interaction | From → to | What visibly happens |
| --- | --- | --- | --- |
| Green curtain with a bulge R49 | Pull aside | closed → open | Curtain drawn back, revealing the wooden manikin with brown feet |
| Curtains (all) | Pull aside / close | closed ↔ open | Fabric gathers to the side |

### 12.6 Pushing furniture (Shove Object)

| Asset | Interaction | From → to | What visibly happens |
| --- | --- | --- | --- |
| Couches, chairs, tables, chests, barrels (anything shoveable) | Shove one cell | cell A → adjacent cell B | Object slides/drags one cell with a scrape; heavy pieces tilt and scrape slowly. A blocked shove shows a short push that doesn't move |
| Barricade R63 (2 couches, 3 chairs) | Shove pieces away | barricaded → clear | Same as above, piece by piece |

### 12.7 Water and plumbing

| Asset | Interaction | From → to | What visibly happens |
| --- | --- | --- | --- |
| Hand pump R28 | Pump / fill a container | idle → pumping → idle | Handle cycles; clean water gushes from the spout |
| Broken wall pumps R5, dripping taps R62 | — | dripping (loop) | Drip loop; puddle decal below |
| Dry faucets R27, R65 | Turn | — | Handle turns, nothing comes out |
| Fountain R24 | — | trickle (loop) | Thin foul green trickle from the vase |
| River R68 | — | flowing (loop) | Rushing current, north to south |

### 12.8 Hazards (one-shot feedback when they trigger)

| Asset | Trigger | What visibly happens |
| --- | --- | --- |
| Gray mould floor R26 | Someone enters or disturbs it | Puff of gray spores erupts from the floor, then settles back to dormant |
| Purple fungus R65 | Exposure check fires | Faint drift of purple spores from the tile cracks |
| Electric floor R15 | Someone steps on an exposed (non-carpet) cell | Brief spark crawling along the metal channels around that cell |
| Darkness R14 | Present / dispelled by Daylight | Dense magical dark (loop); fades out when dispelled |

### 12.9 Lights and fire

| Asset | Interaction | From → to | What visibly happens |
| --- | --- | --- | --- |
| Fireplaces (lit ones) | — / extinguish | lit (loop) → cold | Flame loop; when put out, embers die to ash |
| Wall torch | Light / extinguish | unlit ↔ lit | Flame loop when lit |
| Chandeliers | Break | hanging → fallen | Chandelier drops and crashes, glass/bronze debris |
| Dragon skeleton R35 | Break | hanging → collapsed | Wires snap and the skeleton falls into a bone heap |

### 12.10 Actor animations needed (character rig, not props)

- **Search / rummage:** kneeling or standing hands-in.
- **Pick lock:** kneel with tools, small hand motions; success ending and a failure ending where the tools snap.
- **Disarm a trap:** careful two-hand work at the mechanism; success ending, and a failure ending that flinches as the trap fires.
- **Lift or place a bar.**
- **Pry up a floorboard.**
- **Twist a hidden mechanism** (hook, jug).
- **Take an item off a wall or rack, or put one back.**
- **Shove a heavy object:** lean and push, with a blocked-push variant.
- **Pump water and fill a container.**
- **Pull a curtain aside.**
- **Coughing fit:** loop while Coughing (R26 mould condition).
- **Startled / frightened reaction:** for Haunted "sounds", turning toward a random direction.

## 13. Not made in this pass

- **Creatures and what they carry:** Armand appears only as the inert hanging figure in §7.
- **Gallows** (R7): the book calls them occasional, and they aren't present.
- **Replacement outer doors** (R1).
- **New rods for the missing sockets** (R4, R37): those show as empty recesses.
- **Effects:** invented glows, electric VFX, and spore or hallucination VFX beyond the two
  hazard floor states.
- **Other floors:** the garden above the skylight, other levels and their scenes.
- **Room composition:** layouts, placements and counts per room come in the separate
  composition pass.

**Counts:** the book's counts are listed here as written, for example 36 beds in R48 and
27 in R55. The room-composition pass decides how many fit; this list only says each asset
must exist.
