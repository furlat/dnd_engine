# Chilled ground: proposal only

The art handoff asks for a BG3-inspired readable surface vocabulary. This is a
proposal for this engine, not a claim that BG3 rules or automatic freezing have
been implemented. Ray of Frost still slows a creature; Chill Touch is necrotic
and blocks healing; Ice Knife deals piercing and cold. Their delivery does not
silently add a ground hazard.

## What already exists

`dnd/spatial/environmental_conditions.py` owns WetSurface and IceSurface.
IceSurface is already difficult ground with a DC10 Dexterity slip save, and
uses the existing appearance/entry/turn-end spatial trigger system. Wet ground
already declares FREEZE -> IceSurface and VAPORIZE -> SteamCloud transitions;
ice declares VAPORIZE -> SteamCloud. These are existing authored mechanics,
not instructions to wire every cold damage event to FREEZE.

`dnd/residues.py` separately owns persistent tile residue memberships: blood,
bone fragments, Ashen and the two demonic-blood variants. Blood quantity and
footprints are recorded state. Rendering consumes those after-values; it does
not determine which tiles have been frozen or which creature should slip.

## Recommended next small unit

1. Keep a pale frost trace cosmetic until a spell explicitly supplies a native
   surface operation. If traces persist, represent them using the existing
   inert tile-residue membership and existing world updates; no cold-particle
   collision handler or renderer-owned tile state. Define a modest lifetime
   separately from spell condition duration; persistent membership must expire
   through native condition/state events, not a private renderer timer.
2. Demonstrate an explicit FREEZE operation against an existing small wet
   patch. Reuse WetSurface's replacement transition and IceSurface's actual
   movement/save handlers, including their existing first-per-turn gate for
   entry and turn-end saves. No second ice condition, universal temperature
   accumulator, or automatic sequence of Chilled -> Frozen creature states is
   needed to establish this behavior.
3. Make dangerous ice visually distinct from an inert frost trace: a continuous
   readable ground patch with a clear boundary, plus the existing description
   of difficult terrain/slip risk. A decorative snow particle is insufficient
   evidence of a hazard. Both viewers receive the native disclosed patch state.
4. Preserve blood/Ashen memberships underneath until a specific rule changes
   them. Freezing water does not imply deleting blood, bone, scorch or poison.
   Rendering order may show frost over stains while preserving their amount.
   If frozen blood becomes a mechanic later, author that material transition
   explicitly. Do not infer it from red pixels.
5. Choose spell footprint, duration and thaw behavior per authored rule. A
   low-level ray should not acquire a permanent five-foot slip trap merely
   because its impact contains ice meshes. Likewise Chill Touch should never
   create cold surfaces. Existing VAPORIZE is available when a rule explicitly
   calls for it; a visual fireball alone is not that decision.

Acceptance for that future unit: dry ground remains harmless; an explicit wet
freeze creates the recorded ice patch; walking onto it pays the existing cost
and rolls the real save; jumping over it skips ground contact and landing uses
the existing arrival rules; both subjective recordings replay identically;
blood/Ashen state survives unless the authored operation says otherwise.

The proposal received anti-slop (`gore_antislop`) and ECS (`gore_ecs_review`)
review; the latter clarified native expiration and first-per-turn ownership.
Implementation still needs its own concrete authored-rule choices and review.
No new surface state, handler or freeze rule was added during this integration.
