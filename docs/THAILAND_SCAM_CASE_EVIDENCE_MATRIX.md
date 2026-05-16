# Thailand Scam Case Evidence Matrix

**Purpose:** Seed examples for SafeTrip AI's knowledge base and LangChain sub-agent workflow. This is not a complete legal manual. It is a practical first draft for tourist-facing intake, police-report preparation, and officer dashboard review.

**Scope:** Common tourist and online scam cases in Thailand, with evidence the system should ask for before drafting a police-ready report.

---

## Source Grounding

| Source | Use in the workflow |
|---|---|
| Tourist Police Bureau | Tourist assistance, translation, emergency support, 1155 hotline, Thailand Tourist Police app, tourist-area incident escalation. |
| Tourist Police Trust Portal | Accommodation scam checking and scam reporting for suspicious lodging providers or URLs. |
| Royal Thai Police online reporting / cybercrime channels | Online fraud, transfer scams, call-center scams, bank-account cases, transaction-led reports. |
| DSI public warning on fake online crime-report websites | Evidence examples for fraud reporting and warning that official government sites should be verified. |
| Consumer protection complaint channels | Consumer disputes such as services not provided, misleading advertising, defective service, or contract/receipt disputes. |

Important operational rule: SafeTrip AI should not tell users that a formal police report has been filed until the confirmed submission workflow returns a case/reference status.

Reference starting points:

- Tourist Police Bureau: https://www.touristpolice.go.th/en/main
- Tourist Police Trust Portal: https://trust.touristpolice.go.th/en
- Royal Thai Police online reporting entry point: https://www.thaipoliceonline.go.th/
- DSI fake online crime-report warning: https://www.dsi.go.th/en/Detail/a5b004706ede4a7d5a96d16c16ab5200
- LangChain sub-agent pattern: https://docs.langchain.com/oss/python/langchain/multi-agent/subagents

---

## Shared Required Fields

| Field | Why it matters |
|---|---|
| Tourist name or contact method | Needed for officer follow-up. For MVP, channel ID can be enough until formal submission. |
| Language | Needed for translation and bilingual report drafting. |
| Incident location | Determines responsible area and helps hotspot detection. |
| Date and approximate time | Supports timeline and CCTV/request follow-up. |
| What happened | Core narrative for report drafting. |
| Amount lost or disputed | Helps classify severity and restitution path. |
| Evidence attachment or reason unavailable | Prevents unsupported reports from looking complete. |
| Suspect/service details | Name, business, profile, phone, plate number, account, URL, or app handle. |
| User confirmation | Required before sending a formal report draft to a police queue. |

---

## Scam Case Examples

### 1. Taxi / Tuk-Tuk Overcharge

**Typical story:** Tourist is quoted a high fixed fare, meter is refused, route is extended, or the driver demands extra fees at the destination.

| Evidence | Required level |
|---|---|
| Pickup and drop-off locations | Required |
| Date/time of ride | Required |
| Fare requested and fare paid | Required |
| Vehicle plate, taxi ID, driver card, or vehicle photo | Strongly recommended |
| Receipt, payment slip, app trip record, or cash-payment note | Strongly recommended |
| Chat messages or booking record if arranged online | Conditional |
| Photo/video of fare meter or route map | Optional but useful |

**Follow-up examples:** "Where did the ride start and end?" "Do you have a photo of the license plate, taxi ID, receipt, or app trip record?" "How much did the driver ask for, and how much did you pay?"

**Suggested routing:** Tourist Police / local police station for the incident area. Use 1155 for immediate tourist assistance or mediation.

### 2. Rental Vehicle Damage Claim Scam

**Typical story:** Tourist rents a motorbike, jet ski, or car and is later blamed for pre-existing damage or charged an inflated repair amount.

| Evidence | Required level |
|---|---|
| Rental shop name and location | Required |
| Rental agreement, receipt, deposit record, or ID/passport deposit note | Required if available |
| Before-rental photos/videos with timestamp | Strongly recommended |
| After-rental photos/videos | Strongly recommended |
| Claimed damage photos and demanded repair amount | Required |
| Staff names, phone numbers, LINE/chat history | Strongly recommended |
| Witness names or nearby CCTV location | Optional |

**Follow-up examples:** "Did you take photos or video before using the vehicle?" "Did the shop keep your passport, ID, or deposit?" "What amount are they demanding, and are you currently being pressured to pay?"

**Suggested routing:** Tourist Police first if the tourist is being pressured, detained, or threatened. Otherwise prepare a local report packet.

### 3. Fake Accommodation / Booking Scam

**Typical story:** Tourist pays for hotel, villa, hostel, or condo booking through a fake website, fake social page, spoofed listing, or impersonated property.

| Evidence | Required level |
|---|---|
| Property name, address, listing URL, and booking platform | Required |
| Payment slip, card receipt, transfer record, or transaction ID | Required |
| Chat/email conversation with the seller or fake provider | Strongly recommended |
| Screenshots of listing, profile, website, QR code, or ad | Strongly recommended |
| Check-in date and booking reference | Required |
| Confirmation from real property that booking is invalid | Optional but useful |

**Follow-up examples:** "What site, app, page, or person did you book through?" "Do you have the payment confirmation and the listing URL?" "Have you contacted the real accommodation to verify the booking?"

**Suggested routing:** Tourist Police Trust Portal for suspicious accommodation/provider checking, Tourist Police for tourist assistance, cyber/online-fraud report if money was transferred online.

### 4. Tour Package / Illegal Guide / Shopping Kickback Scam

**Typical story:** Tourist is sold a fake or misleading tour, taken to commission shops, pressured to buy gems/suits/souvenirs, or guided by an unauthorized operator.

| Evidence | Required level |
|---|---|
| Tour operator/guide name and contact | Required |
| Booking receipt, itinerary, brochure, or web listing | Required if available |
| Payment evidence | Required |
| Photos of guide, vehicle, shop, license badge, or tour desk | Strongly recommended |
| What was promised versus delivered | Required |
| Names/locations of shops visited under pressure | Strongly recommended |
| Other affected tourists or witnesses | Optional |

**Follow-up examples:** "What exactly was promised in the tour description?" "Did the guide show a license badge or company ID?" "Were you pressured to buy something or taken somewhere not in the itinerary?"

**Suggested routing:** Tourist Police for illegal guide or tourist-service fraud; consumer protection route when it is primarily service-not-as-advertised.

### 5. Online Purchase / Bank Transfer Scam

**Typical story:** Victim transfers money for goods, tickets, services, investment, or a rental, then the seller disappears or blocks contact.

| Evidence | Required level |
|---|---|
| Bank transfer slip, e-slip, transaction ID, or card record | Required |
| Receiver account name, account number, PromptPay, wallet ID, or QR code | Required |
| Chat logs, DMs, email, SMS, or call logs | Required |
| Seller profile URL, phone number, page, ad, website, app handle | Strongly recommended |
| Product/service listing screenshots | Strongly recommended |
| Delivery/tracking details or proof no delivery occurred | Conditional |
| Bank case/reference ID if already contacted bank | Conditional |

**Follow-up examples:** "Have you contacted your bank yet to freeze or dispute the transaction?" "Please upload the transfer slip and screenshots of the chat with the seller." "What account or PromptPay number received the money?"

**Suggested routing:** Bank first for freezing/dispute where relevant, then Royal Thai Police online/cybercrime reporting or local police depending on channel and jurisdiction. Tourist Police can help foreign tourists navigate the process.

### 6. Fake Police / Government / Remote-Access Scam

**Typical story:** Scammer claims to be police, immigration, bank, courier, DSI, or another official agency, then asks for money, OTPs, remote app installation, or "verification" transfers.

| Evidence | Required level |
|---|---|
| Phone number, LINE ID, WhatsApp, email, website, or social profile | Required |
| Call logs, SMS, chat screenshots, voice notes, or video-call screenshots | Strongly recommended |
| Any fake warrant, ID card, official letter, QR code, or link received | Strongly recommended |
| Transfer slips or account details if money was sent | Required if applicable |
| Remote app name installed or permission granted | Required if applicable |
| Bank/device actions already taken | Required if applicable |

**Follow-up examples:** "Did they ask you to install an app, share an OTP, or transfer money for verification?" "Do you still have the phone number, chat, link, or fake document?" "If remote access was installed, disconnect from the internet and contact your bank immediately."

**Suggested routing:** Cybercrime/online-fraud report and bank contact if money or credentials are involved. Escalate to emergency guidance if the tourist is still under active coercion.

### 7. Restaurant / Bar / Venue Overcharging

**Typical story:** Tourist is presented with an inflated bill, hidden charges, forced minimum spend, or intimidation after ordering.

| Evidence | Required level |
|---|---|
| Venue name and location | Required |
| Menu, price list, receipt, or bill photo | Required if available |
| Amount expected versus amount demanded/paid | Required |
| Payment slip/card transaction/cash note | Required if available |
| Staff interaction details and witness names | Optional but useful |
| Photos of signs, menu, or disputed items | Strongly recommended |
| Whether tourist is currently being threatened or blocked from leaving | Required safety field |

**Follow-up examples:** "Are you safe and free to leave right now?" "Can you upload the bill, menu, or payment receipt?" "What price was shown before ordering, and what amount are they demanding now?"

**Suggested routing:** Tourist Police immediately if the tourist is being intimidated or prevented from leaving. Otherwise create an evidence packet for local tourist police/local police or consumer complaint handling.

---

## Workflow Notes for Agents

1. Ask one or two targeted questions at a time.
2. Prefer evidence uploads over long explanations where possible.
3. Separate "required to draft a useful report" from "nice to have."
4. If the tourist is in immediate physical danger, route to emergency guidance instead of normal evidence collection.
5. For online transfer fraud, prioritize bank contact and transaction evidence because speed can matter.
6. For official-procedure questions, retrieve from approved knowledge sources and log source IDs.
7. For allegations against named businesses or people, draft neutral language: "the tourist reports..." rather than asserting guilt.

---

## First MVP Case Types

| Priority | Case type | Reason |
|---|---|---|
| 1 | Online purchase / transfer scam | Clear evidence model and high repeatability. |
| 2 | Fake accommodation booking | Strong tourist relevance and portal alignment. |
| 3 | Taxi/tuk-tuk overcharge | Common tourist issue and good location-based alert candidate. |
| 4 | Rental vehicle damage claim | Evidence-heavy and benefits from guided collection. |
