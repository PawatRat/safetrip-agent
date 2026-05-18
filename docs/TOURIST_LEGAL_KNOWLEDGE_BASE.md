# Tourist Legal Knowledge Base

This knowledge base is connected to the `Guidance Agent` through `agents/safetrip_agent/legal_knowledge_base.py`. The Guidance Agent retrieves entries by case type and mode before producing tourist-facing recommendations.

## Sources

| Source ID | Publisher | URL | Used for |
|---|---|---|---|
| `tourist-police-main` | Tourist Police Bureau | https://www.touristpolice.go.th/main | Tourist Police 1155 and tourist assistance channel |
| `tourist-police-i-lert-u` | Thailand.go.th | https://www.thailand.go.th/public/visit-thailand-detail/001_02_085 | Tourist Police app, GPS/photo assistance request, Emergency Notification Center 1155 |
| `thailand-emergency-numbers` | Thailand.go.th | https://www.thailand.go.th/issue-focus-detail/009-017?hl=en | Emergency contacts including 191 police, 1155 Tourist Police, and 1669 emergency medical services |
| `tourist-police-trust` | Tourist Police Trust Portal | https://trust.touristpolice.go.th/en | Accommodation provider checks, suspicious URL checks, scam reports, emergency 1155 |
| `thai-police-online-reporting` | Royal Thai Police | https://thaipoliceonline.go.th/ | Online reporting channel for cyber/online incidents |

## Case Mapping

| Case type | Knowledge entry | Guidance focus | Sources |
|---|---|---|---|
| `taxi_overcharge` | Tourist Police assistance for tourist-related incidents | Tourist Police 1155/app, local incident packet, emergency 191 if urgent | `tourist-police-main`, `tourist-police-i-lert-u`, `thailand-emergency-numbers` |
| `rental_damage_claim` | Tourist Police assistance for tourist-related incidents | Tourist Police 1155/app and local incident packet | `tourist-police-main`, `tourist-police-i-lert-u`, `thailand-emergency-numbers` |
| `tour_package_or_illegal_guide` | Tourist Police assistance for tourist-related incidents | Tourist Police 1155/app and local incident packet | `tourist-police-main`, `tourist-police-i-lert-u`, `thailand-emergency-numbers` |
| `restaurant_or_venue_overcharge` | Tourist Police assistance for tourist-related incidents | Tourist Police 1155/app and local incident packet | `tourist-police-main`, `tourist-police-i-lert-u`, `thailand-emergency-numbers` |
| `theft` | Tourist Police assistance for tourist-related incidents | Tourist Police 1155/app, local theft report packet, emergency 191 if urgent | `tourist-police-main`, `tourist-police-i-lert-u`, `thailand-emergency-numbers` |
| `fake_accommodation` | Accommodation scam and suspicious booking guidance | Tourist Police Trust Portal and Tourist Police support | `tourist-police-trust`, `tourist-police-main` |
| `online_transfer_scam` | Online transfer scam and cybercrime reporting guidance | Contact bank/payment provider, preserve transfer evidence, prepare online/cyber report | `thai-police-online-reporting`, `thailand-emergency-numbers` |
| `fake_police_or_government` | Online transfer scam and cybercrime reporting guidance | Contact bank/payment provider if money/OTP/account access involved, preserve caller/chat/fake document evidence | `thai-police-online-reporting`, `thailand-emergency-numbers` |
| `physical_assault` | Physical assault and immediate safety guidance | Immediate safety, police 191, Tourist Police 1155, emergency medical 1669, assault evidence packet | `thailand-emergency-numbers`, `tourist-police-main`, `tourist-police-i-lert-u` |

## Retrieval Behavior

| Guidance mode | Behavior |
|---|---|
| `intake_help` | Retrieve legal/tourist assistance information and combine it with the next missing evidence question. |
| `report_route` | Retrieve legal/tourist assistance information and use the full case state to recommend the report route before drafting. |

## Production Note

The current knowledge base is local and deterministic. For production, this can be moved to Azure AI Search or another vector/search service while keeping the same Guidance Agent contract.
