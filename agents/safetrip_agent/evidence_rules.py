from __future__ import annotations

from .schemas import EvidenceRequirement, ScamType


SCAM_EVIDENCE_RULES: dict[ScamType, list[EvidenceRequirement]] = {
    "taxi_overcharge": [
        EvidenceRequirement(
            name="pickup_and_dropoff",
            required_level="required",
            reason="Shows route and jurisdiction.",
        ),
        EvidenceRequirement(
            name="fare_requested_and_paid",
            required_level="required",
            reason="Defines disputed loss.",
        ),
        EvidenceRequirement(
            name="vehicle_plate_or_taxi_id",
            required_level="strongly_recommended",
            reason="Identifies driver or vehicle.",
        ),
        EvidenceRequirement(
            name="receipt_payment_or_trip_record",
            required_level="strongly_recommended",
            reason="Supports amount and time.",
        ),
    ],
    "rental_damage_claim": [
        EvidenceRequirement(
            name="rental_shop_name_location",
            required_level="required",
            reason="Identifies involved business.",
        ),
        EvidenceRequirement(
            name="rental_agreement_or_deposit_record",
            required_level="required",
            reason="Shows terms and money held.",
        ),
        EvidenceRequirement(
            name="before_and_after_photos",
            required_level="strongly_recommended",
            reason="Counters pre-existing damage claims.",
        ),
        EvidenceRequirement(
            name="claimed_damage_and_amount",
            required_level="required",
            reason="Defines dispute.",
        ),
    ],
    "fake_accommodation": [
        EvidenceRequirement(
            name="property_listing_url",
            required_level="required",
            reason="Identifies fake listing or provider.",
        ),
        EvidenceRequirement(
            name="payment_record",
            required_level="required",
            reason="Shows transaction.",
        ),
        EvidenceRequirement(
            name="seller_chat_or_email",
            required_level="strongly_recommended",
            reason="Shows promises and identity.",
        ),
        EvidenceRequirement(
            name="booking_reference",
            required_level="required",
            reason="Links report to booking.",
        ),
    ],
    "tour_package_or_illegal_guide": [
        EvidenceRequirement(
            name="operator_or_guide_contact",
            required_level="required",
            reason="Identifies seller or guide.",
        ),
        EvidenceRequirement(
            name="receipt_itinerary_or_listing",
            required_level="required",
            reason="Shows promised service.",
        ),
        EvidenceRequirement(
            name="payment_record",
            required_level="required",
            reason="Shows loss.",
        ),
        EvidenceRequirement(
            name="photos_of_guide_vehicle_shop_or_badge",
            required_level="strongly_recommended",
            reason="Supports identification.",
        ),
    ],
    "online_transfer_scam": [
        EvidenceRequirement(
            name="transfer_slip_or_transaction_id",
            required_level="required",
            reason="Core financial evidence.",
        ),
        EvidenceRequirement(
            name="receiver_account_or_promptpay",
            required_level="required",
            reason="Needed for bank/police follow-up.",
        ),
        EvidenceRequirement(
            name="chat_logs",
            required_level="required",
            reason="Shows deception and agreement.",
        ),
        EvidenceRequirement(
            name="seller_profile_url_phone_or_page",
            required_level="strongly_recommended",
            reason="Identifies scammer channel.",
        ),
    ],
    "fake_police_or_government": [
        EvidenceRequirement(
            name="caller_or_chat_identifier",
            required_level="required",
            reason="Identifies impersonation channel.",
        ),
        EvidenceRequirement(
            name="fake_document_link_or_qr",
            required_level="strongly_recommended",
            reason="Shows impersonation artifact.",
        ),
        EvidenceRequirement(
            name="transfer_record",
            required_level="conditional",
            reason="Required if money was sent.",
        ),
        EvidenceRequirement(
            name="remote_app_or_otp_details",
            required_level="conditional",
            reason="Required if credentials/device access were compromised.",
        ),
    ],
    "restaurant_or_venue_overcharge": [
        EvidenceRequirement(
            name="venue_name_location",
            required_level="required",
            reason="Identifies incident area.",
        ),
        EvidenceRequirement(
            name="bill_menu_or_receipt_photo",
            required_level="required",
            reason="Shows disputed charge.",
        ),
        EvidenceRequirement(
            name="expected_vs_demanded_amount",
            required_level="required",
            reason="Defines overcharge.",
        ),
        EvidenceRequirement(
            name="payment_record",
            required_level="strongly_recommended",
            reason="Shows payment made.",
        ),
    ],
    "theft": [
        EvidenceRequirement(
            name="item_description_and_value",
            required_level="required",
            reason="Identifies what was stolen and approximate loss.",
        ),
        EvidenceRequirement(
            name="theft_location_and_time",
            required_level="required",
            reason="Establishes where and when the theft occurred.",
        ),
        EvidenceRequirement(
            name="suspect_or_witness_details",
            required_level="strongly_recommended",
            reason="Supports police follow-up if anyone saw or recorded the incident.",
        ),
        EvidenceRequirement(
            name="photos_receipts_or_tracking_info",
            required_level="strongly_recommended",
            reason="Helps identify the stolen item and ownership.",
        ),
    ],
    "physical_assault": [
        EvidenceRequirement(
            name="assault_location_and_time",
            required_level="required",
            reason="Establishes jurisdiction and incident timeline.",
        ),
        EvidenceRequirement(
            name="injury_description_or_medical_record",
            required_level="required",
            reason="Documents harm and supports urgency assessment.",
        ),
        EvidenceRequirement(
            name="suspect_description_or_identity",
            required_level="strongly_recommended",
            reason="Helps police identify the reported person.",
        ),
        EvidenceRequirement(
            name="witnesses_photos_or_video",
            required_level="strongly_recommended",
            reason="Supports the incident account with third-party or media evidence.",
        ),
    ],
    "unknown": [],
}
