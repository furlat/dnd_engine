# Fixed-pack study: animals and humanoids (2026-09-30)

**SRD-first revision authority (30 September 2026):** this report preserves
archive/visual evidence and earlier proposals. Proposed mechanics below,
including sections labelled “selected design”, are superseded by the
[full-SRD rematch](PACK_ROSTER_SRD_FIRST_ANIMAL_DINOSAUR_2026-09-30.md) and
[reconciled synthesis](../ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md).
Use SRD 5.1 first, 5.2 secondary adapted to 5.1, with explicit changes for
actual visible equipment. Earlier custom action/spell/gear choices are not
competing current selections. Later named visual reinspections in the rematch
also take precedence over the corresponding earlier observation.

**Final roster authority:** use the [focused completion](PACK_ROSTER_ANIMAL_DINOSAUR_COMPLETION_2026-09-30.md)
and [full synthesis](../ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md). The completion
repairs the failed animal contact-sheet review, opens and inventories all 21
dinosaur variants, and distinguishes implemented foundations from the initial
SRD/species suggestions below. Those initial suggestions are not implemented
creature declarations. The source study remains retained as earlier evidence.

Read-only study of the four requested owned source archives under
`/mnt/c/Users/tommaso/Documents/assets/smallscale`; no source archive, runtime,
backend, asset manifest, or production art was changed. Selected frame evidence
and the generated inventory are in
`.runtime/pack-study-20260930/animals-humanoids/` in the checkout. The inventory
records archive member names, action names as authored, direction folders,
PNG frame count per direction, and sheet dimensions; it does not convert source
clip numbers into game content identities.

## Findings at a glance

| Archive | Family / visual groups | Source frame images | Sprite sheets | Authored directions and usual cells | Shadow evidence |
| --- | ---: | ---: | ---: | --- | --- |
| `2D Animals mega Pack 1 V2.zip` | 55 named animal variants | 66,840 | 1,114 | 8 named facings; 64×64; usually 15 frames per clip and facing | 557 matching 960×512 `Shadowless` / `With shadow` sheet pairs |
| `2D HD Barbarian pack 1.zip` | 9 named humanoid variants | 33,736 | 556 | 8 named facings; 192×192; usually 15 frames per clip and facing | 278 matching 2880×1536 paired sheets |
| `2D HD Character pack 1 V1.2.zip` | 9 named humanoid variants | 32,768 | 534 | 8 named facings; 128×128; usually 15 frames per clip and facing | 267 matching 1920×1024 paired sheets |
| `2D Dinosaurs Pack 1.rar` | Not established | Unavailable | Unavailable | Unavailable | Unavailable |

Counts above distinguish individual numbered-frame PNGs from packed animation
PNG sheets. Source ZIPs contain no explicit FPS, physical origin/support
registration, loop flags, or gameplay meaning. Eight-way facings are explicit
directory names (`E`, `SE`, `S`, `SW`, `W`, `NW`, `N`, `NE`); sheet dimensions
and representative cells agree with those directions and the pack-specific
15-column layout. The numbered PNG files are sparsely numbered in some
archives, so their filename suffix is not a trustworthy playback frame rate
or gameplay event.

### Animals

The 55 top-level family names are: Alpacha; antilope; Arabian horse; Bison;
Boar; Brown Bear; Brown Horse; Bull; Camel; Cat Black; Cat Large; Cat Orange;
Cat White; Chicken; Chimp; Cow; Cow brown; Crocodile; Deer; Donkey; Elephant;
Elephant female; ELITE Wolf; Giraffe; Golden Retriever; Grey Wolf; Grizzly;
Hayena; Hippo; Husky; Jaguar; Jak; Lama; Lion; Lioness; Mammoth; Monkey; Oryx;
Ostrich; Pig; Pinguin; Polar Bear; Ram; Rhino; Rhino Female; Sheep; Shepherd
Dog; Stag; Tiger; Toirtois; Turtle; Water buffalo; White Tiger; Work Horse;
Zebra. Spellings and capitalization preserve archive folder names.

Most animals author `Attack1`, `Attack2`, `Attack3`, `Die`, `Idle`, `Idle2`,
`Run`, `TakeDamage`, `Taunt`, and `Walk`. The archive also contains the
family-specific clips `Attack4`, `Fly`, `Idle3`, `IdleSit`, `Jump`, `Roar`,
`Howl`, `Sneak`, and `Idle`/`Run`/`resting`/`sleep`/`eating`/`drinking water`/
`fast walk`/`jump`/`jump attack`/`attacking`/`howling`/`sneaking`/`TakeDamage`/
`Die` variants under the `Hayena` (hyena) folder. The machine inventory is the
authoritative per-family list and retains actual filenames. These are authored
presentations: a clip named `Attack3`, `Roar`, or `Howl` is not evidence for an
engine action or a D&D ability.

Idle and locomotion are visibly quadruped, with distinct coat/species silhouettes
and some extra idle variants; the felids add jumps/roars, several canids add
howls/sitting/sneaking, and poultry add flight. Attack/TakeDamage/Die names
describe authored animation roles, not target, damage, movement, or rules. The
animal individual frames are small 64 px cells; the pack also supplies matching
shadowless and with-shadow full atlases. No effect layer is established in this
archive.

### Barbarian pack

Families: `1Ogre`, `2Golem`, `3Nomad`, `4Berserker`, `5BarbArcher`,
`6Barbarian`, `7BowMan`, `8Witchdoctor`, `9Shaman`. The shared authored action
vocabulary is `180Turn`, `Attack1`, `Attack2`, `Attack3`, `AttackRun`,
`BlockMid`, `BlockStart`, `CastSpell`, `CrouchIdle`, `CrouchRun`, `Die`,
`FrontFlip`, `Idle`, `Idle2`, `Pummel`, `QuickShot`, `QuickSlide`, `Rolling`,
`Run`, `RunBackwards`, `SittingChair`, `Slide`, `SlideEnd`, `SlideStart`,
`Special1`, `Special2`, `StrafeLeft`, `StrafeRight`, `TakeDamage`, `UnSheath`,
and `Walk`; family-specific files add `Kick`, and some families omit certain
slides. The JSON inventory records those omissions and source frame counts.

Visible equipment is baked into each named character family (for example,
large ogre/go-lem bodies, bows, staves, blades and shields); it is not a modular
gear pack. Melee, bow/cast/block/turn/mobility labels describe available clips,
not rules. Frames are 192×192, typically 15 columns by eight facing rows.

### Character pack

Families: `1Knight`, `2Archer`, `3Wizard`, `4Paladin`, `5CamoArcher`, `6Mage`,
`7DeathKnight`, `8DarkLord`, `9Longbow`. Shared clip vocabulary includes
`180Turn`, three `Attack` clips, `AttackRun`, `BlockStart`/`BlockMid`,
`CastSpell`, `CrouchIdle`/`CrouchRun`, `Die`, `FrontFlip`, `Idle`/`Idle2`,
`Kick`, `QuickShot`, `Rolling`, `Run`, `RunBackwards`, `SittingChair`,
`Slide`/`SlideStart`/`SlideEnd`, `Special1`/`Special2`, `StrafeLeft`/
`StrafeRight`, `TakeDamage`, `UnSheath`, and `Walk`. Knight, Paladin and
DeathKnight instead expose `Melee`, `Melee2`, `MeleeRun`, `MeleeSpin`,
`Pummel`, `ShieldBlockStart`/`ShieldBlockMid`, `UnSheathSword`, and a 16-frame
`CastSpell`; the archers/wizard/mage variants have the bow-oriented shared
attack set. The inventory records each family’s exact set and frame counts.

These are individual baked appearances, not a stand-alone equipment compositing
system. Bows, robes, armor, shields and weapons remain part of the chosen body
art. `Special1`, `Special2`, `QuickShot`, and `CastSpell` have no guaranteed
backend/gameplay interpretation. Frames are 128×128, typically 15 columns by
eight facings.

## Layer and shadow study

All three ZIPs visibly offer corresponding complete `Spritesheets/Shadowless/`
and `Spritesheets/With shadow/` PNGs. They are two variants of a clip sheet,
not separate body/shadow layers, and no independent shadow PNG folder is
present. Their paths pair on family and clip, cell layout and dimensions. This
means there is positive source evidence for the same pose without the baked
shadow, and for its appearance with the shadow. It is materially better than
trying to key black or a guessed shade out of the combined pixels.

For a separate ground layer, the source pair supports a precise per-frame matte
candidate: keep the shadowless image as the unchanged body; derive a shadow
mask from pixels transparent in Shadowless and covered in With shadow; place
that shadow under the body. It recovers the visible exterior of the baked
shadow without filtering the creature’s palette. Portions occluded by the body
are not uniquely recoverable, but the shadow belongs under that body and those
pixels are covered during composition. Before production use, verify pixel
registration and a representative crop across all eight facing rows, check
transparent-edge handling, and inspect a contact/attack pose for limbs or
equipment that move into the ground-shadow region. The evidence collected here
establishes paired source authority and matching grid/dimensions; it does not
include an exported alpha mask or claim pixel equality of the two complete
images.

The existing client already models an independent `shadow` layer and applies
its configured alpha in `NeuroClient/app/src/render/AnimatedEntity.ts`; the
existing default appearance creates a shadow layer in
`NeuroClient/app/src/render/equipmentVisuals.ts`. No suitable renderer shader
was found that selects a narrow source shadow color range. The pack-specific
paired shadowless references make such a color-key approach unnecessary for
these archives. Do not apply the default generated shadow on top of a
with-shadow atlas, since that double-darkens the ground. Conversely, the
installed wolf body comes from the shadowless atlas and can be drawn with the
existing distinct shadow slot if a matched shadow layer is supplied.

`game/data/rigs/greywolf.json` is installed and binds the exact native SRD wolf
identity to a 64×64, eight-row, 15-frame `GreyWolf` body rig. It maps locomotion,
damage, death and bite variants to authored clips and binds six body sheets
under `game/assets/rigs/greywolf/body/`. Its rig `slot_order` contains only
`body`; it does not declare/bind a vendor shadow sheet. The existing adaptation
text says the body is shadowless and notes no separate shadow media was
supplied; that is true of a standalone supplied shadow file, but the paired
`With shadow` atlas is present in the source ZIP and enables recovery as above.
The installation is partial source coverage, not evidence that all animals or
humanoids are installed.

## Unavailable and comparison packages

The dinosaur archive is a RAR v5 source (archive header begins `Rar!\x1a\x07`),
but this host has no `7z`, `7zz`, `unrar`, `unar`, or `bsdtar` executable and
no installed Python `rarfile`/`libarchive` module. No files from the RAR were
extracted or inventoried. Dinosaur family names, clips, dimensions, directions,
layers and FPS are therefore unknown here; no RAR tool was installed.

Light comparison only: `Downloads/Stand-alone Character creator - 2D Fantasy
V1.3.zip` contains an executable Unity character creator and
`Created Spritesheets/`, which indicates generated/composable character output
rather than fixed named NPC variants. `Downloads/x256 Spritesheets.zip` includes
separate named `Body` and `Shadow25%`/`Shadow50%`/`Shadow75%` sheets for
15-angle action sets such as `Attack1`, an example of explicit baked-source
separation but a different direction/action layout. Neither comparison pack
was deeply inventoried or changed.

## Inspection evidence

I extracted only selected numbered frames and Grey Wolf paired Idle sheets to
`.runtime/pack-study-20260930/animals-humanoids/`. The extracted Grey Wolf
examples, Ogre attack, and Knight idle were opened visually. A 55-family animal
sample set and both 9-family humanoid sets were generated for visual comparison;
the humanoid contact sheets show all nine representatives. Contact-sheet
rendering of the animal samples collapsed to a single visible tile in this
environment, so the names/count are confirmed from archive entries while a
visual review of every animal sample is not claimed. The Grey Wolf paired
shadow sheets were also opened; they support pose/layout comparison, but subtle
shadow pixels against the transparent black viewer were not assessed as a
final extraction.

Compact exhaustive inventories are in
`.runtime/pack-study-20260930/animals-humanoids/inventory.json` and
`.runtime/pack-study-20260930/animals-humanoids/README.txt` (source archive
paths, exact family/action groups, per-direction frame-file counts, dimensions,
and caveats). No asset hashes were computed.

## NPC-roster proposals (art is one-to-one; mechanics remain authored content)

Design proposal, not implementation: give every fixed art variant its own
stable flavour-NPC identity and presentation selection. Point its mechanics at
an appropriate reusable native/SRD foundation where that fits, or explicitly
author a custom stat block. The frontend resolves stable presentation identity
to its rig/art. Keep frame numbers, archive clip names, row order, tint, and
shadow handling out of backend creature/equipment/custom-ability identities.
“Visible art” below records what the source depicts; plausible attacks inferred
from anatomy remain uncertain. `AttackN`, `Roar`, `Howl`, and `CastSpell` never
by themselves authorize an extra attack, spell, flight, mount rule, movement
mode, or other game capability. Signatures are optional flavour ideas: reuse
existing mechanics only when they already fit, and author any new rule
separately. Color variants are presentation siblings by default.

### Animals (55 variant identities)

Foundation suggestions are starting points, not claims about the current
registry or implemented content. Use a custom animal when no close SRD/native
foundation fits rather than implying a false species identity.

| Source variant | Proposed flavour NPC | Visible gear / uncertain combat read | Foundation candidate | Optional signature flavour / elite palette |
| --- | --- | --- | --- | --- |
| Alpacha | Puna-pack Alpaca | Alpaca-like quadruped; no carried gear; bite/kick uncertain | Mule | Pack beast; copper coat |
| antilope | Sunstep Antelope | Antelope-like; no gear; horn rush uncertain | Elk | Dash look; pale-gold coat |
| Arabian horse | Saffron Courser | Horse; no rider/tack established; hoof strike uncertain | Riding Horse | Swift mount identity is flavour only; bright bay coat |
| Bison | Redgrass Bison | Horned bison; no gear; gore/trample uncertain | Ox or custom bison | Heavy-charge flavour; russet hide |
| Boar | Briarback Boar | Tusked boar; no gear; tusk attack plausible | Boar | Use a charge rule only if separately supported; ash tusks |
| Brown Bear | Honeyclaw Bear | Brown bear; no gear; bite/claw plausible from anatomy | Brown Bear | Maul flavour; scarred dark coat |
| Brown Horse | Chestnut Roadhorse | Horse; no equipment evidenced; hoof strike uncertain | Riding Horse | Courier role; chestnut coat |
| Bull | Ironhorn Bull | Horned bovine; no gear; gore/trample uncertain | Ox | Herd guardian; black/gold hide |
| Camel | Saltwind Camel | Camel; no gear; bite/kick uncertain | Camel | Desert survivor; pale-sand coat |
| Cat Black | Candle-Sneak Cat | Small black cat; no gear; scratch/bite plausible | Cat | Familiar flavour; silver eyes |
| Cat Large | Moonfang Panther | Large feline; no gear; claw/bite plausible | Tiger | Pounce as flavour; moon-grey coat |
| Cat Orange | Ember-Paw Cat | Small orange cat; no gear; scratch/bite plausible | Cat | Familiar flavour; cream-gold coat |
| Cat White | Frost-Paw Cat | Small white cat; no gear; scratch/bite plausible | Cat | Familiar flavour; blue-grey marks |
| Chicken | Hearthyard Hen | Chicken; no gear; peck plausible | Custom animal | `Fly` is visual only; red comb |
| Chimp | Vine-thief Chimp | Chimp; no gear; bite/swat plausible | Ape | Scavenger story does not grant item-use; russet face |
| Cow | Meadowbell Cow | Cow; no gear; kick/headbutt uncertain | Ox | Herd animal; cream patches |
| Cow brown | Bracken Cow | Brown cow; no gear; kick/headbutt uncertain | Ox | Herd animal; brindle coat |
| Crocodile | Mudgullet Crocodile | Crocodilian; no gear; bite plausible | Crocodile | River ambush narrative; moss scales |
| Deer | Fernrunner Deer | Deer; no gear; hoof/antler strike uncertain | Elk | Skittish narrative; dusk coat |
| Donkey | Stonepath Donkey | Donkey; no gear/tack established; bite/kick uncertain | Mule | Pack-beast flavour; dark ear tips |
| Elephant | Thunderstep Elephant | Elephant; no rider/gear established; stomp/trunk attack uncertain | Elephant | Heavy beast; warm-grey hide |
| Elephant female | Matriarch of Reedplain | Female-coded elephant art; no gear; stomp/trunk attack uncertain | Elephant | Matriarch relationship flavour; rose-grey marks |
| ELITE Wolf | Ashfang Alpha | Wolf palette variant; no gear; bite/claw plausible | Wolf | Pack leader flavour; silver/dark coat |
| Giraffe | Canopy Sentinel | Giraffe; no gear; kick/head strike uncertain | Custom animal | Silhouette does not grant reach; amber spots |
| Golden Retriever | Hearthward Retriever | Domestic dog; no gear; bite uncertain | Mastiff or Wolf | Loyal companion flavour; golden coat |
| Grey Wolf | Greyfang Tracker | Grey wolf; no gear; bite/claw plausible | Wolf | Tracking narrative; charcoal coat |
| Grizzly | Redclaw Grizzly | Brown bear variant; no gear; bite/claw plausible | Brown Bear | Durable beast flavour; russet muzzle |
| Hayena | Dustlaugh Hyena | Hyena; no gear; bite plausible | Hyena | Pack-call narrative; sandy mane |
| Hippo | Rivergate Hippo | Hippopotamus; no gear; bite/body charge uncertain | Custom animal | River beast; dark-grey hide |
| Husky | Blue-Eye Husky | Husky dog; no gear; bite uncertain | Wolf or Mastiff | Cold-weather companion; blue-grey coat |
| Jaguar | Greenveil Jaguar | Spotted big cat; no gear; claw/bite plausible | Tiger | Stalking narrative; deep jungle rosettes |
| Jak | Highpass Yak | Yak-like bovine; no gear; horn/head strike uncertain | Ox | Pack animal flavour; ice-grey coat |
| Lama | Cloudridge Llama | Llama; no gear; bite/kick uncertain | Mule | Pack animal; dark wool |
| Lion | Sun-Crowned Lion | Lion; no gear; bite/claw plausible | Lion | `Roar` is not an automatic fear effect; bronze mane |
| Lioness | Dusk-Hunt Lioness | Lioness; no gear; bite/claw plausible | Lion | Hunt narrative; smoke-grey coat |
| Mammoth | Old-Ice Mammoth | Mammoth; no rider/tack established; tusk/stomp uncertain | Mammoth | Ancient-beast story; frost-pale fur |
| Monkey | Lantern-Raid Monkey | Monkey; no carried gear; bite/swat plausible | Ape | Mischief does not grant climbing/item rules; copper face |
| Oryx | White-Dune Oryx | Long-horned antelope; no gear; horn strike uncertain | Elk | Horned guardian; ivory tips |
| Ostrich | Redgrass Strider | Ostrich; no gear; kick plausible but unverified | Custom animal | Strider story grants no speed rule; cobalt feathers |
| Pig | Orchard Pig | Pig; no gear; bite/headbutt uncertain | Boar | Farm animal; spotted coat |
| Pinguin | Blacktide Penguin | Penguin; no gear; peck/flipper strike uncertain | Custom animal | No automatic swim/flight; white crest |
| Polar Bear | White-Fang Bear | Polar bear; no gear; bite/claw plausible | Polar Bear | Ice hunter; blue-white coat |
| Ram | Craghead Ram | Ram; no gear; horn charge uncertain | Sheep | Headbutt flavour; dark horns |
| Rhino | Ironhide Rhino | Rhino; no gear; horn charge plausible | Rhino | Use only supported native charge rules; red-brown hide |
| Rhino Female | Redplain Cow-Rhino | Female-coded rhino art; no gear; horn charge uncertain | Rhino | Herd guardian story; pale horn |
| Sheep | Mossbell Sheep | Sheep; no gear; headbutt uncertain | Sheep | Flock role; charcoal fleece |
| Shepherd Dog | Flockward Hound | Shepherd dog; no gear; bite uncertain | Mastiff or Wolf | Guardian narrative; tan markings |
| Stag | Crownbranch Stag | Antlered deer; no gear; antler strike uncertain | Elk | Antler display; dusk antlers |
| Tiger | Emberstripe Tiger | Tiger; no gear; bite/claw plausible | Tiger | `Roar` is presentation; amber stripes |
| Toirtois | Moss-shell Tortoise | Tortoise; no gear; bite uncertain | Giant Tortoise if scale fits, else custom animal | Resilience is narrative; moss shell |
| Turtle | Bluewake Turtle | Turtle; no gear; bite uncertain | Giant Tortoise if scale fits, else custom animal | No automatic swimming; blue shell |
| Water buffalo | Reedbank Buffalo | Water buffalo; no gear; horn charge uncertain | Ox | Working-herd narrative; slate horns |
| White Tiger | Moonstripe Tiger | White tiger; no gear; bite/claw plausible | Tiger | White coat; silver stripes |
| Work Horse | Millroad Draft Horse | Work horse; no gear/tack established; hoof strike uncertain | Draft Horse or Riding Horse | Hauler story; black socks |
| Zebra | Thornplain Zebra | Zebra; no gear; hoof strike uncertain | Riding Horse | Herd identity; muted ochre stripes |

### Barbarian characters (9 variant identities)

| Source variant | Proposed flavour NPC | Visible equipment / uncertainty | Foundation candidate | Optional signature / elite palette |
| --- | --- | --- | --- | --- |
| 1Ogre | Gravelmaw Ogre | Ogre-like oversized body and heavy hand weapon; precise weapon varies by clip | Ogre | Reuse chosen melee foundation; iron-grey skin |
| 2Golem | Cairnheart Sentinel | Golem-like plated body and heavy weapon; construct nature needs rules authoring | Stone Golem or custom construct | Reuse construct traits only if selected; moss/bronze stone |
| 3Nomad | Saffron Road-Warden | Travel cloth/armour and carried weapon; details vary | Scout or Bandit | Desert-warden story; deep-red sash |
| 4Berserker | Red-Rage Breaker | Heavy melee silhouette; weapon baked into art | Berserker | Reuse rage only if foundation supplies it; ash warpaint |
| 5BarbArcher | Farshot Pathfinder | Bow-carrying archer art | Scout or Bandit | Existing ranged foundation; forest-green wraps |
| 6Barbarian | Stonejaw Reaver | Heavy melee equipment baked into appearance | Berserker | Chosen melee foundation; cobalt warpaint |
| 7BowMan | Windmark Bowman | Bow gear baked into appearance | Scout or Bandit | Veteran archer narrative; amber cloth |
| 8Witchdoctor | Bone-Censer Seer | Robed caster/tool silhouette; clip `CastSpell` establishes no spell list | Cultist or Priest | Chosen spells authored separately; violet face paint |
| 9Shaman | Storm-Reed Speaker | Robe/staff-like silhouette; elemental powers remain undecided | Priest or Cultist | Existing chosen support/caster content only; teal wraps |

### Fantasy characters (9 variant identities)

| Source variant | Proposed flavour NPC | Visible equipment / uncertainty | Foundation candidate | Optional signature / elite palette |
| --- | --- | --- | --- | --- |
| 1Knight | Ironwatch Knight | Armoured body, sword/shield-like gear; weapons baked into art | Knight or Guard | Selected martial foundation; gold trim |
| 2Archer | Briarline Archer | Bow-carrying archer | Scout | Existing ranged foundation; leaf-green cloak |
| 3Wizard | Starwell Wizard | Robe/staff-like caster; clip name does not specify spells | Mage or Cultist | Selected spells authored separately; indigo robe |
| 4Paladin | Dawnwall Paladin | Heavy armour and sword/shield silhouette | Knight or Guard | Selected defensive foundation; ivory/gold trim |
| 5CamoArcher | Fenveil Ranger | Camouflage clothing and bow appearance | Scout | Cosmetic camouflage; olive palette |
| 6Mage | Emberglass Mage | Robe/caster appearance; no particular spell guaranteed | Mage or Cultist | Spell identity stays separate; copper/amber robe |
| 7DeathKnight | Gloam Oathblade | Dark heavy armour and blade/shield silhouette; undead status unknown | Knight or Veteran | Martial foundation; bone trim only; no assumed undead rules |
| 8DarkLord | Blackthorn Magus | Dark caster/armour silhouette; powers unknown | Mage or Knight after rules review | No assumed necromancy; crimson-black cloth |
| 9Longbow | Far-Eye Longbowman | Longbow-carrying archer | Scout | Existing ranged foundation; silver/blue cloak |

Cosmetic elite variants keep the same mechanics unless content authors choose
otherwise explicitly. There are no dinosaur rows yet: the RAR is unreadable in
this environment. Add one identity per discovered dinosaur variant after
inventory; use a suitable SRD/native dinosaur foundation or separately authored
custom creature, and do not infer flight, swimming, mounting, or combat rules
from art alone.
