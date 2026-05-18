# SafeTrip Full-Cycle Conversation Test Report

Date: 2026-05-18  
Mode: offline orchestrator with fake Azure POST adapter  
Purpose: simulate complete conversations across supported scam cases, answer with prepared evidence-rich tourist messages, confirm the draft, and verify the workflow reaches final submission packet flow.

## Summary

| Check | Result |
|---|---:|
| Supported case types simulated | 9 |
| Cases reaching draft confirmation stage | 9 |
| Cases reaching final submission packet stage | 9 |
| Packets written | 9 |
| Mock POST calls sent | 9 |
| Full-cycle failures | 0 |

## Command Run

```bash
.venv/bin/python - <<'PY'
# Runs SafeTripOrchestrator with use_model=False and injected fake POST.
# For each case: process tourist message -> process "confirm" -> assert packet + POST.
PY
```

The run used a fake endpoint:

```text
https://example.test/api/mockchat
```

No live Azure endpoint was called.

## Full-Cycle Results

| Prepared case | Classified as | Draft ready after tourist message | Stage after draft | Stage after confirmation | Missing items | Mock POST count | Packet written | API incident type | Severity |
|---|---|---:|---|---|---|---:|---:|---|---|
| `taxi_overcharge` | `taxi_overcharge` | Yes | `awaiting_user_confirmation` | `submission_packet_written` | None | 1 | Yes | `taxi_overcharge` | `medium` |
| `fake_accommodation` | `fake_accommodation` | Yes | `awaiting_user_confirmation` | `submission_packet_written` | None | 1 | Yes | `fake_accommodation` | `medium` |
| `online_transfer_scam` | `online_transfer_scam` | Yes | `awaiting_user_confirmation` | `submission_packet_written` | None | 1 | Yes | `online_transfer_scam` | `high` |
| `fake_police_or_government` | `fake_police_or_government` | Yes | `awaiting_user_confirmation` | `submission_packet_written` | None | 1 | Yes | `fake_police_or_government` | `high` |
| `rental_damage_claim` | `rental_damage_claim` | Yes | `awaiting_user_confirmation` | `submission_packet_written` | None | 1 | Yes | `rental_damage_claim` | `medium` |
| `tour_package_or_illegal_guide` | `tour_package_or_illegal_guide` | Yes | `awaiting_user_confirmation` | `submission_packet_written` | None | 1 | Yes | `tour_package_or_illegal_guide` | `medium` |
| `restaurant_or_venue_overcharge` | `restaurant_or_venue_overcharge` | Yes | `awaiting_user_confirmation` | `submission_packet_written` | None | 1 | Yes | `restaurant_or_venue_overcharge` | `medium` |
| `theft` | `theft` | Yes | `awaiting_user_confirmation` | `submission_packet_written` | None | 1 | Yes | `theft` | `medium` |
| `physical_assault` | `physical_assault` | Yes | `awaiting_user_confirmation` | `submission_packet_written` | None | 1 | Yes | `physical_assault` | `high` |

## Prepared Tourist Messages

| Case | Message used |
|---|---|
| `taxi_overcharge` | Taxi driver charged me 2500 THB in Bangkok today. Pickup from JJ Mall to Siam. I have the fare paid receipt and taxi plate. |
| `fake_accommodation` | I booked a villa in Phuket today and transferred 12000 THB. I have the listing URL, payment slip, booking reference, and chat messages. |
| `online_transfer_scam` | An online seller on Facebook in Bangkok today made me transfer 5000 THB. I have the transfer slip, transaction ID, PromptPay QR, receiver account, and chat logs. |
| `fake_police_or_government` | Immigration police called me in Chiang Mai today and asked for OTP and a bank transfer. I have the caller phone number, Line profile, fake document QR, transfer record, and remote app details. |
| `rental_damage_claim` | A motorbike rental shop in Pattaya today kept my 3000 THB deposit and claimed damage. I have the rental shop name location, rental agreement, before and after photos, and claimed damage amount. |
| `tour_package_or_illegal_guide` | A tour guide in Bangkok today sold me a fake tour package for 4500 THB. I have the guide contact phone, receipt itinerary listing, payment record, and photos of the guide vehicle badge. |
| `restaurant_or_venue_overcharge` | A restaurant in Phuket today charged me 7000 THB more than the menu. I have the venue restaurant location, bill menu receipt photo, expected demanded amount, and payment record. |
| `theft` | My phone was stolen in Bangkok today. I have the item value, theft location time, witness details, receipt, and tracking info. |
| `physical_assault` | I was attacked in Pattaya today. I have the assault location time, injury medical record, attacker description, witness video, and CCTV. |

## Verified Final Flow

Each simulated case completed this path:

```text
Tourist message
-> Intake Agent
-> Evidence Agent
-> Completeness Agent
-> Orchestrator Decision
-> Guidance Agent (report_route)
-> Drafting Agent
-> Safety Agent
-> User confirmation
-> Submission Packet Agent
-> police_submission.md
-> mock POST /api/mockchat
-> Safety Agent
```

## Notes

| Item | Detail |
|---|---|
| External services | Not called; fake POST adapter was used |
| LLMs | Not called; offline deterministic path was used for this full-cycle run |
| Runtime packet files | Written inside a temporary directory and automatically removed after the run |
| What this proves | The workflow can reach final submission flow for all currently supported case types when enough information and evidence are provided |
| What this does not prove | Live Gemini extraction quality or live Azure Function availability |
