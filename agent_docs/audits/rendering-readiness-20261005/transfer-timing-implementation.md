# Standalone transfer timing evidence

Implemented only passive producer evidence in portal_animation.py and forced_movement.py. Existing playback equations, contact selection, trajectory and sampling are unchanged. PortalTransferCue, ShoveCue and ForcedMovementCue expose timing_evidence tuples.

Evidence covers doorway stride/transit/settling; ground portal opening/fall/disappearance/exit/arrival; shove selected body contact; displacement brace/application floor/travel/body/recovery/removal floor and native spatial admissions. Source dates use the enclosing choreography clock. Dependency export must add visit.offset_ms only, never cue.start_ms a second time.

Unknown portal identity with a supplied opening date is represented as the bound event owner's opening input, not a claimed native admission or invented spatial identity.

Verification: tests/game/test_transfer_timing_evidence.py: 5 passed. Includes independently projected traveler/arrival/departure portals, native shove, and successful native Telekinesis displacement branch using the established catalog seed. Telekinesis production selects a BodyHop owner: its standalone binder test is explicitly not claiming this cue is the production owner. Evidence arithmetic and JSON round trips checked. Scoped production-module Pyright: 0 errors.

Independent review remains the parent's responsibility; this is an implementation receipt, not self-approval.
