# Final portal and Shield of Faith regressions

Bounded independent source review, 2026-10-05.

Accepted. Portal arrival_snapshots keys the exception by exact received observation event and actor. It retains the existing explicit endpoint arrival date, deduplicates that same snapshot, preserves its received HP and leaves unrelated generic observation floors intact. The exception neither invents an unseen healthy state nor grants the other endpoint. Evidence references the actual portal event arrival anchor. This is an existing owner precedence repair, not a new visibility rule.

Shield of Faith changes only existing authoring fields: both target-ground media tracks use contact clock; contact delay is 83.33333333333326 ms and condition delay remains zero. The condition already inherits the contact clock; another condition delay would apply it twice. With release at 583.3333333333334 ms and the existing -666.6666666666666 ms media lead, formation starts at zero and contact/condition occurs at 666.6666666666666 ms. Existing source animation frame 21 is preserved there. No parser, timing guard, clip or spell mechanic added. Native regression assertions explicitly check media start, formation frame and condition alignment, including observer perspectives.

No additional source blocker found. Test execution counts belong to the implementing lane/root; this reviewer checked assertions and source rather than claiming a duplicate runtime run.

Correction to the initial review: I had accepted the proposed nonzero condition delay without tracing the already-contact-based child input adequately. The strengthened native regression caught that duplication. Current final diff restores condition.delayMs to zero; the review above now describes the actual final recipe. The regression explicitly requires a nonempty matching Shield condition cue set before checking its timing.
