# Devices sustaining spells

The user chose device-owned concentration for cannon Web. The operator fires the
spell and pays its action cost; the device maintains the resulting magic. A device
has HP, can be attacked, and may maintain several spells up to an authored capacity.
Destroying it removes the linked effects. A visible tether must communicate this
real relationship and disappear when the relationship ends.

Ordinary mage concentration stays unchanged. Sleep remains its existing finite,
non-concentration spell: neither a tether nor dependence on the cannon is invented
for it. A device-sustained Sleep variant would be a separate rules decision.

## Existing mechanisms to reuse

- `BaseItem` already composes health, object damage, destruction, conditions and
  passive item presentation. Cannons should configure those capabilities.
- `Concentrating` already owns `ConcentrationSlot` records and linked-condition
  cleanup. It currently assumes its owner is an entity.
- Web already creates one native zone, with terrain, saving throws, restraint,
  escape, burning and concentration cleanup. Its observed footprint now travels
  through the existing subjective spatial-effect observations.
- Spell origin and concentration owner are different concepts. The operator stays
  the causal source; the item can be the physical emitter and the sustainer.

## Bounded implementation

1. Give spell devices authored HP and a concentration capacity (initial bodies:
   two slots). A zero item capacity preserves existing scroll/wand behavior.
2. Reuse the existing concentration condition and slots for item owners. Creature
   damage saves remain a creature rule; devices sustain until the effect ends or
   their condition/device is destroyed. Do not create a second lifecycle registry.
3. Full devices refuse another sustained cast before spending charges/actions or
   creating effects. Two independent casts of Web consume two independent slots.
4. Keep the existing linked-condition tree and per-slot entries synchronized when
   a linked effect ends. Free an emptied slot through the actual removal path,
   without polling. Preserve destruction's damage lineage during removal.
5. Retain public capacity and sustained-slot facts in the existing observed item
   state. Their identities describe gameplay ownership, not rendering instructions.
   The renderer may connect only known device placements to disclosed effects;
   private targets/locations must not appear through a tether.
6. Author the Web tether in presentation data using the delivered asset. Its
   endpoints follow those observed links. Departure/cast is not a substitute for
   a sustained link; removal/destruction must clear it during historical playback.

## Validation

Native tests cover two same-spell zones, refusal at capacity without cost,
independence from the operator's own concentration and damage, ordinary mage rules,
partial removal freeing a slot, and actual attacks destroying the device and
clearing both zones, restrictions and links. Replay tests consume serialized
observer events with no live native registry. Review clips show mage and device
casting, multiple sustained effects, and destruction from both observer views,
with four camera angles each.

Sleep proceeds independently: one directional shot, floor-aligned mist, native
HP-pool recipients, condition-owned lying pose/Zzz, and a real damage wake.

## Approved follow-up: device breakdown and persistent wreck

The user paused all Web artwork and body-wrap work and explicitly requested
working Sleep and breaking cannons. The separate approved fractured-body v2
artwork is now the presentation target for both device bodies.

- Existing item destruction owns cleanup at the hit/contact event. An optional
  frozen remnant component authors the replacement item ID and name; it creates
  an ordinary inert, nonblocking, nonpickable, nontargetable ground item at the
  exact original placement. No grants, charges, health or sustaining slots survive.
- The existing DESTROYED event records the explicit replacement UUID. Public
  projection requires a witnessed old contact and filters the new identity by
  actual observation. No inference from ordinary removal or coincident positions.
- The existing finite world transition samples the eight-frame / 12-fps break
  at contact. It temporarily supplies the observed replacement's body, then
  yields to the matching static wreck. Native effects end at contact, independently
  of the visual settling. A newly arriving observer sees the event-backed wreck.
- Transition data stays small: item ID, position/height, facing/pitch and exact
  replacement UUID. Artwork tables do not get copied into per-frame traces.
- Both bodies cast actual Sleep, then take separate nonlethal and lethal real
  longsword attacks. Paired four-camera clips show that destroying the launcher
  does not remove non-concentration Sleep. Native tests separately retain the
  already implemented device-sustaining cleanup contract.

Independent anti-slop and ECS review approved this reuse. The only added data
components describe real item replacement and authored media; there is no new
lifecycle registry or device subclass.

## Reviews and status

The native implementation agent supplied the reuse plan after reading item damage,
concentration slots and removal paths. The independent anti-slop and anti-OOP/ECS review approved this bounded reuse.
It required preserving operator identity/DC/costs, separate slots for independent
same-spell casts, rejection before costs/zone creation, atomic removal vetoes,
DAG-safe leaf DTOs, and a spatial state update after linking the zone. Item slot
summaries contain no remote targets; observed zones disclose their link only when
the device is also disclosed. Core sustaining and the approved breakdown follow-up
are implemented and independently reviewed. Existing actor-owned
follow-up actions such as Call Lightning are outside the validated device scope;
the shared owner change is not proof that those grants work unchanged.

The [completed result](SLEEP_WEB_DEVICE_RESULT_2026-09-20.md) records native and
presentation validation. The [10-clip Sleep/breakdown gallery](http://127.0.0.1:8767/runs/20260920T163754Z-bf4705/index.html)
replays saved real events from paired observers in four cameras, with no reported
media gaps. Wrecks are currently inert, nonblocking and not lootable. Web artwork
and body wraps remain paused by the user; they are not prerequisites for this work.
