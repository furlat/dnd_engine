# Native roster effects: visual handoff

October 2, 2026. Native owners are implemented in
[the checkpoint](ROSTER_ABILITIES_IMPLEMENTATION_2026-10-02.md). Visual production
owner: `01a0fd33-69ff-7321-bada-ba124e477822`. Use existing registered media first;
request new shared effect art only after checking the queued handoffs. No new
weapon or backpack geometry. Preserve originals and install 32FPS production
media under [ASSETS.md](../ASSETS.md).

| Identity | Received native cause and presentation contract |
| --- | --- |
| `spell.produce_flame` / `condition.spell.produce_flame` | Casting on self installs a retained hand flame and real actor-anchored bright/dim 10ft light. A creature target is an immediate 30ft ranged spell attack. Later `action.spell.produce_flame.hurl` consumes the retained flame even on a miss; dismiss/recast/expiry removes it and its light. Shared hand/release/travel/contact treatment; no sustained flame after hurl. |
| `spell.shillelagh` / `condition.spell.shillelagh` | Apply a material treatment to the exact club/staff UUID and caster only. One-minute native effect ends on recast/release. Original palette replacement/bloom is allowed; never create new weapon shapes or leave the effect on a looted weapon. |
| `spell.longstrider` / `condition.spell.longstrider` | Touch recipient cue followed by an optional quiet movement cue. Actual effect lasts one hour without concentration; one native membership per recipient. Upcast recipients share the existing multi-target cast lifecycle. |
| `spell.barkskin` / `condition.spell.barkskin` | Touch application, quiet maintained material and removal following the actual concentration membership. One-hour maximum. It changes effective AC, not worn equipment. Reuse shared skin/material effects on modular and fixed bodies. |
| `spell.fly` / `condition.spell.fly` / `action.spell.fly.move` | Shared cast/application cue and received ordinary movement samples. Ten-minute concentration, supported ground-to-ground movement only; no hovering pose or invented wings. `trait.innate_flight` shares traversal with authored speed and no concentration. |
| `spell.fire_shield` / `condition.spell.fire_shield` | Warm/chill application and maintained treatment, native 10ft bright/dim light, removal on dismissal/expiry. Warm resists cold and retaliates with fire; chill reverses those types. Bind variant through received native facts; extend passive typed projection if needed, never read live conditions during replay. |
| Fire Shield retaliation | Automatic 2d8 packet follows a qualifying melee hit within5ft, including a melee spell hit or a hit whose incoming damage is zero. Use damage provenance from the actual shield effect. Retaliation contact must precede the damage response; no free attack gesture/reaction and no recursively triggered shield. |
| `action.monster.wight.life_drain` / `condition.wight.life_drain` | One intrinsic contact attack, optionally one Longsword replacement in melee Multiattack. Shared contact and maximum-HP reduction cue on failed DC13CON save. Further reductions update the same membership; it survives source death and ends at long rest. No zombie creation cue or transferable weapon enchantment. |
| `action.monster.innate_invisibility` | Reuse existing Invisible material/visibility and concentration presentation. Native ability is not a spell cast. Activation burst is optional; attack/concentration removal reveals the creature and equipment together. |
| `trait.magic_resistance` / Devil's Sight / magical natural source | No mandatory persistent aura or new gesture. Existing save/sense/attack facts drive feedback. Intrinsic effects do not transfer with a looted item. |

## Arrow and backpack ownership

`consumable.arrow.ember`, `.frost`, `.storm` and `.venom` are inventory stacks,
not equipment or a quiver ammunition pool. Discovery and AttackEvent expose
`selected_ammunition_uuid` and immutable `ammunition_payload`; weapon UUID remains
the actual bow/crossbow. Bind reusable arrow travel/contact, with native Fire,
Cold, Lightning or saved Poison damage. Venom adds no Poisoned condition.
Ground-stack appearance is an explicit registration gap; inspect existing arrow
donors before authoring a passive ground binding. Never use multiplication tint
or certify a spell bolt as an arrow without inspecting the donor geometry.

Consumption is native release, including a miss. Replay never consumes another
copy. Damage/body response waits for the selected arrow's contact. Multiple
attacks retain their own causes; do not merge successive turns into one volley.

`gear.ember_quiver`, `gear.wayfarer_pack` and `gear.warden_pack` use existing
BACKPACK geometry (`Quiver`, `Quiver`, `Back Canister`). Their charges stay with
the item after unequip/drop/loot; normal long rest recharges the owned possession.
Ember uses the accepted transferable fire-coating material on its declared bow;
Wayfarer uses shared Longstrider; Warden uses shared Resistance/concentration.
No bespoke backpack particles, compartments or new artwork are requested.

## Acceptance

Bind body gesture, release/contact, recipient effect, sustain and removal
separately. Fixed artwork may already bake a component: inspect selected layers
before adding shared FX. Rules and recipient effects remain reusable on modular
characters; only intrinsic anatomy or unavailable fixed gestures justify a rig
restriction. Do not duplicate item-owned elemental damage/material as an ability.

Use saved received events and normal engine four-camera galleries, real floor
tiles, original shadows and accepted wall/window occlusion. Verify missiles,
misses, expiry, concentration loss, item transfer and source removal. Never use
final-state masks, live world reads or a new preview format. These contracts are
a production handoff; they are not completed visual acceptance.
