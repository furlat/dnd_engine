# Cleanup repair evidence

The repair implementation and source re-reviews are complete; full-suite receipt
reconciliation is tracked in [the implementation report](../CLEANUP_REPAIR_IMPLEMENTATION_2026-10-03.md).
This file records verified corrections to the approved plan's diagnostic
assumptions and the additional defects caught during final review.

## Construction

The two expected failures did not prove self-blocked section targeting. A public
attack destroys the section, yielding negative HP, and retires its UUID. The
scenario required HP exactly zero and then attempted another attack on that
retired UUID. The scenario now accepts HP <= 0 and both strict xfails are removed.
Existing terminal-provider spatial rules remain unchanged. Formation publication
was a separate real defect: sections must be committed before CREATED is emitted.

## Content evidence

The extra structural owner is **Dretch Multiattack**, not Wight (the repair plan's
inventory label was wrong). Its declaration and owner are in
`dnd/monsters/multiattack_definitions.py`; the creature composition is
`dnd/monsters/srd_roster.py:_configure_dretch`. The SRD ledger already changed
Dretch from missing to playable, with its existing explicit gameplay limitations.
This repair records that existing admission; it implements no new creature rule.

The CR-0 manifest keeps the accepted `513dd97` sources, the original authority
record, reconciliation rows and historical proofs. Only three current artifact
pins changed, after inspecting their deltas:

- Authored item visuals: 283 to 404 evidence rows (85 categories / 318 variants,
  plus the existing source-ID collision row). Existing roster/modular material
  variants are additions to the earlier art census.
- Icon bindings: 874 to 876 rows. Added True Seeing potion use, Dretch and Dretch
  Multiattack; removed the retired Attack Object action binding.
- SRD coverage: still 925 rows. Dretch is the sole status change: 178 playable,
  5 partial, 742 missing. The corresponding proof and current creature owner,
  plus the Multiattack owner, are now recorded explicitly.

The direct item inventory includes the existing roster weapon/carried/gear
families, powered backpacks, 19 window components, Maul and basic poison coating.
The four retired `consumable.arrow.{ember,frost,storm,venom}` IDs must remain
absent. No runtime code reads these audit ledgers.

## Historical recording compatibility

Original compressed fixture bytes are unchanged. Named additive fields retain
absence through native round trip. Current explicit unknown causes remain
supported. Old creature-damage packets without ownership proof receive a precise
diagnostic instead of being assigned to their nearest attack parent.

The archived device example contains such an old Fire Bolt. Its complete native
state still reduces; timed presentation of that old operation is rejected. The
legacy destruction pixel checks settle its entire prefix as initialization and
review the actual final destruction, retaining every prefix event and observation.
Door and Web archives remain tested through their existing full replay paths.

## Final review corrections

Independent anti-slop review caught a second-order timing issue after independent
Spike Growth ownership was restored: an exposure could publish a later HP snapshot
before the preceding incoming result. The shared scheduler now waits for earlier
typed result commits for that recipient. This preserves native packet order;
it does not recalculate damage or match events by spell name.

Visual inspection and independent event review then caught a different error:
forced movement inherited the spell's earlier state milestone, exposing the final
cell before the push. Forced movement now owns its own placement and commits each
spatial child at its recorded arrival. The real two-cell push keeps (4,3) through
contact, then reaches (5,3) and (6,3); HP goes 20→18→16→14. Exact boundary, reverse
seek, altered number-frame timing and the unchanged saved-input replay are covered.

The ECS reviewer additionally exercised Warden pack use through Resistance and
cancelled self-casts. Resistance now uses the same paired child/concentration
admission boundary as the retained spells. A cancelled cast releases its provisional
effect tree before admission. Failed replacement preserves the old owner and
children; committed action costs and item releases are not ancestry-wide refunds.

All three implementation reviewers subsequently approved these fixes. Their final
reports retain exact hashes and reproduce the corrected public-boundary outcomes.

The complete game run exposed one interaction in that forced-movement fix: it
cleared the landing milestone already owned by an existing trap-avoidance hop.
The reset now applies only when no owned hop exists. The unchanged settled-landing
test reproduces the fault; all 34 tests in the jaw-hop, forced-movement and
resolution modules pass after the one-line correction. All three reviewers
approved this bounded change, and two new saved jaw-trap recordings exercise it.
The original full-run failure is retained separately from the affected rerun.
