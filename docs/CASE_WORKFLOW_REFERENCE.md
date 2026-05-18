# SafeTrip Case Workflow Reference

This file summarizes the case types currently available in the SafeTrip agent workflow, the evidence each case requires, and the recommendation route used by the Guidance Agent.

## Case Availability And Requirements

| Case type | Available now | Required evidence | Strongly recommended evidence | Conditional evidence | Recommendation route |
|---|---:|---|---|---|---|
| `taxi_overcharge` | Yes | `pickup_and_dropoff` - Shows route and jurisdiction.<br>`fare_requested_and_paid` - Defines disputed loss. | `vehicle_plate_or_taxi_id` - Identifies driver or vehicle.<br>`receipt_payment_or_trip_record` - Supports amount and time. | None | Use Tourist Police 1155/app for immediate tourist help and prepare a local incident packet for the responsible area. |
| `rental_damage_claim` | Yes | `rental_shop_name_location` - Identifies involved business.<br>`rental_agreement_or_deposit_record` - Shows terms and money held.<br>`claimed_damage_and_amount` - Defines dispute. | `before_and_after_photos` - Counters pre-existing damage claims. | None | Use Tourist Police 1155/app for immediate tourist help and prepare a local incident packet for the responsible area. |
| `fake_accommodation` | Yes | `property_listing_url` - Identifies fake listing or provider.<br>`payment_record` - Shows transaction.<br>`booking_reference` - Links report to booking. | `seller_chat_or_email` - Shows promises and identity. | None | Check/report suspicious accommodation through Tourist Police trust/report flow; use Tourist Police support for tourist assistance. |
| `tour_package_or_illegal_guide` | Yes | `operator_or_guide_contact` - Identifies seller or guide.<br>`receipt_itinerary_or_listing` - Shows promised service.<br>`payment_record` - Shows loss. | `photos_of_guide_vehicle_shop_or_badge` - Supports identification. | None | Use Tourist Police 1155/app for immediate tourist help and prepare a local incident packet for the responsible area. |
| `online_transfer_scam` | Yes | `transfer_slip_or_transaction_id` - Core financial evidence.<br>`receiver_account_or_promptpay` - Needed for bank/police follow-up.<br>`chat_logs` - Shows deception and agreement. | `seller_profile_url_phone_or_page` - Identifies scammer channel. | None | Contact bank immediately if money/credentials are involved, then prepare cybercrime or police report evidence. |
| `fake_police_or_government` | Yes | `caller_or_chat_identifier` - Identifies impersonation channel. | `fake_document_link_or_qr` - Shows impersonation artifact. | `transfer_record` - Required if money was sent.<br>`remote_app_or_otp_details` - Required if credentials/device access were compromised. | Contact bank immediately if money/credentials are involved, then prepare cybercrime or police report evidence. |
| `restaurant_or_venue_overcharge` | Yes | `venue_name_location` - Identifies incident area.<br>`bill_menu_or_receipt_photo` - Shows disputed charge.<br>`expected_vs_demanded_amount` - Defines overcharge. | `payment_record` - Shows payment made. | None | Use Tourist Police 1155/app for immediate tourist help and prepare a local incident packet for the responsible area. |
| `theft` | Yes | `item_description_and_value` - Identifies what was stolen and approximate loss.<br>`theft_location_and_time` - Establishes where and when the theft occurred. | `suspect_or_witness_details` - Supports police follow-up if anyone saw or recorded the incident.<br>`photos_receipts_or_tracking_info` - Helps identify the stolen item and ownership. | None | Use Tourist Police 1155/app for tourist assistance and prepare a local theft report packet with item details, location, time, and ownership evidence. |
| `physical_assault` | Yes | `assault_location_and_time` - Establishes jurisdiction and incident timeline.<br>`injury_description_or_medical_record` - Documents harm and supports urgency assessment. | `suspect_description_or_identity` - Helps police identify the reported person.<br>`witnesses_photos_or_video` - Supports the incident account with third-party or media evidence. | None | If there is immediate danger or injury, move to safety and contact Tourist Police 1155 or emergency medical help, then prepare an assault incident packet for local police. |
| `unknown` | Fallback only | None | None | None | The Intake Agent should ask what happened and classify into an available case before drafting. |

## Workflow Notes

| Workflow point | Meaning |
|---|---|
| Case available now | The Intake Agent can classify the tourist message into this case type and the Evidence Agent has a configured evidence checklist for it. |
| Required evidence | The Completeness Agent should normally block report drafting until these items are collected or clearly answered. |
| Strongly recommended evidence | Useful for police handoff quality, but not always blocking for draft generation. |
| Conditional evidence | Required only when the related condition is present in the tourist's story. |
| Recommendation route | Seed route retrieved by the Guidance Agent. In live mode, the Guidance Agent can rewrite this into a concise tourist-facing recommendation using full case state. |

## Current Branching Behavior

| Condition | Orchestrator route |
|---|---|
| Evidence or core incident information incomplete | `Orchestrator -> Intake Agent -> Evidence Agent -> Completeness Agent -> Guidance Agent (intake_help) -> Safety Agent -> ask one next question` |
| Evidence and core incident information complete | `Orchestrator -> Intake Agent -> Evidence Agent -> Completeness Agent -> Guidance Agent (report_route) -> Drafting Agent -> Safety Agent -> ask user to confirm draft` |
| User confirms draft | `Orchestrator -> Submission Packet Agent -> POST /api/mockchat and write police_submission.md -> Safety Agent` |
