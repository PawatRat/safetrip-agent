# SafeTrip Test Report

Date: 2026-05-18  
Environment: local workspace, Python virtual environment `.venv`  
Mode: offline tests with fake LLM and fake HTTP adapters where external services are involved

## Summary

| Check | Result | Details |
|---|---:|---|
| Unit and workflow tests | PASS | 23 tests passed |
| Python compile check | PASS | `agents` and `tests` compiled successfully |
| CLI smoke test | PASS | Offline verbose workflow returned expected pipeline and next question |
| External network calls in tests | Not used | Azure `/api/mockchat` is tested with fake POST adapter |

## Commands Run

| Command | Result |
|---|---:|
| `.venv/bin/python -m unittest discover -s tests -v` | PASS |
| `.venv/bin/python -m compileall agents tests` | PASS |
| `.venv/bin/python agents/safetrip_langchain_workflow.py --message "Taxi driver overcharged me in Bangkok today." --verbose --offline` | PASS |

## Test Suite Result

```text
Ran 23 tests in 0.021s

OK
```

## Tested Areas

| Area | Coverage |
|---|---|
| Intake/classification | Classifies fake police/government priority and collects basic facts |
| Case coverage | Covers theft and physical assault case classification and draft readiness |
| Legal knowledge base | Verifies Guidance Agent retrieves case-specific tourist legal/source information |
| Guidance in final response | Verifies final user-facing replies keep recommendations alongside questions or drafts |
| Submission error handling | Verifies endpoint failures do not crash the chat after confirmation |
| Evidence collection | Collects allowed evidence and filters invalid evidence names |
| Completeness | Blocks drafting when required evidence or facts are missing |
| Loop prevention | Structured model path accepts messy location answers and moves to next missing item |
| Orchestrator routing | Incomplete cases route to `Guidance Agent (intake_help)`; complete cases route to `Guidance Agent (report_route)` and `Drafting Agent` |
| Per-agent models | Verifies each subagent uses its own configured model object |
| Draft confirmation | Non-confirmation does not submit; confirmation triggers packet/submission flow |
| Submission packet | Writes markdown packet with core sections and transcript |
| Azure mock submission payload | Verifies `reply`, `incident_type`, `severity`, `should_create_case`, and `required_info` fields |
| Submission response state | Stores endpoint and API response on `CaseState` |
| Safety | Flags immediate danger, unsupported submission claims, and unsupported legal certainty |
| CLI smoke | Offline verbose CLI displays detailed agent pipeline and returns a focused next question |

## CLI Smoke Output Summary

Input:

```text
Taxi driver overcharged me in Bangkok today.
```

Observed workflow:

```text
Intake Agent
Evidence Agent
Completeness Agent
Orchestrator Decision
Guidance Agent
Drafting Agent skipped
Safety Agent
```

Final response asks for the next missing required evidence:

```text
How much did the driver ask for, and how much did you pay?
```

## Current Known Limits

| Limit | Impact |
|---|---|
| Tests use fake LLM outputs | They verify orchestration contracts, not live Gemini quality |
| Tests use fake Azure POST | They verify payload and state handling, not live Azure Function availability |
| Local packet folder is untracked | Generated `police_submission_packets/` is runtime output and should not be committed |
| No load or concurrency tests yet | Production deployment should add session persistence and concurrent case tests |

## Recommendation Before Production

| Task | Reason |
|---|---|
| Add integration test against a staging Azure Function | Confirms `/api/mockchat` accepts the production payload |
| Add live-model smoke test behind an opt-in flag | Confirms Gemini structured outputs match schemas |
| Persist `CaseState` outside memory | Required for Azure deployment and multi-session users |
| Store generated packets in Blob Storage | Local disk is not reliable for production App Service/Container Apps |
