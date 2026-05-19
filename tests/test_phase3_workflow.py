from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents"))

from safetrip_agent.orchestrator import SafeTripOrchestrator
from safetrip_agent.subagents.completeness_agent import update_case_completeness
from safetrip_agent.subagents.evidence_agent import update_case_evidence
from safetrip_agent.subagents.intake_agent import classify_message, update_case_from_message
from safetrip_agent.schemas import (
    CaseState,
    DraftingResult,
    OrchestratorPlan,
    PerceptionExtraction,
    SafetyAssessment,
    SynthesisResult,
)


class FakeExtractionModel:
    def __init__(self, responses: dict[type, list[object]], name: str = "shared") -> None:
        self.responses = responses
        self.name = name
        self.calls: list[type] = []
        self.schema: type | None = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, _messages):
        assert self.schema is not None
        self.calls.append(self.schema)
        return self.responses[self.schema].pop(0)


class Phase3WorkflowTests(unittest.TestCase):
    def test_fake_police_priority_beats_generic_bank_transfer(self) -> None:
        result = classify_message(
            "Immigration police called me and asked for OTP and a bank transfer"
        )

        self.assertEqual(result.scam_type, "fake_police_or_government")
        self.assertGreater(result.confidence, 0.7)

    def test_intake_classifies_theft_and_physical_assault(self) -> None:
        theft = classify_message("My phone was stolen by a pickpocket near the market")
        assault = classify_message("I was attacked and punched outside a bar")

        self.assertEqual(theft.scam_type, "theft")
        self.assertEqual(assault.scam_type, "physical_assault")

    def test_case_state_collects_facts_and_evidence(self) -> None:
        state = CaseState()
        message = (
            "I booked a villa in Phuket today and transferred 12000 THB. "
            "I have the Facebook page, payment slip, booking reference, and chat screenshots."
        )

        state = update_case_from_message(state, message)
        state = update_case_evidence(state, message)
        state = update_case_completeness(state)

        self.assertEqual(state.scam_type, "fake_accommodation")
        self.assertEqual(state.location, "Phuket")
        self.assertEqual(state.incident_time, "today")
        self.assertEqual(state.amount_lost, "12000 THB")
        self.assertTrue(state.report_ready)
        self.assertEqual(state.missing_items, [])

    def test_orchestrator_runs_without_model_api_key(self) -> None:
        orchestrator = SafeTripOrchestrator(use_model=False)

        result = orchestrator.process(
            "Taxi driver overcharged me in Bangkok today."
        )

        self.assertEqual(result.case_state.scam_type, "taxi_overcharge")
        self.assertIn("Next question:", result.final_text)
        self.assertIn("pickup_and_dropoff", result.final_text)

    def test_structured_model_location_advances_followup(self) -> None:
        orchestrator = SafeTripOrchestrator(use_model=False)
        orchestrator.model = FakeExtractionModel(
            {
                OrchestratorPlan: [
                    OrchestratorPlan(intent="provide_info", carries_case_data=True),
                    OrchestratorPlan(intent="provide_info", carries_case_data=True),
                ],
                PerceptionExtraction: [
                    PerceptionExtraction(
                        scam_type="taxi_overcharge",
                        scam_type_confidence=0.89,
                        rationale="Ride and driver terms matched.",
                        amount_lost="2500 THB",
                        evidence_names=["fare_requested_and_paid"],
                    ),
                    PerceptionExtraction(
                        location="chatuchak in jj mall in front of that mall",
                    ),
                ],
                SynthesisResult: [
                    SynthesisResult(
                        response_text="Thanks for the details. Where in Thailand did this happen?"
                    ),
                    SynthesisResult(
                        response_text="Got it. When did this happen? An approximate date and time is okay."
                    ),
                ],
            }
        )

        first = orchestrator.process(
            "A taxi driver charged me 2500 THB and refused the meter."
        )
        self.assertIn("incident_location", first.case_state.missing_items)

        second = orchestrator.process(
            "it in nearly chatuchak in jj mall in front of that mall"
        )

        self.assertEqual(
            second.case_state.location,
            "chatuchak in jj mall in front of that mall",
        )
        self.assertNotIn("incident_location", second.case_state.missing_items)
        self.assertIn("incident_time", second.case_state.missing_items)
        self.assertIn("When did this happen?", second.final_text)

    def test_drafting_only_runs_when_report_ready(self) -> None:
        orchestrator = SafeTripOrchestrator(use_model=False)

        result = orchestrator.process(
            "I booked a villa in Phuket today and transferred 12000 THB. "
            "I have the Facebook page, payment slip, booking reference, and chat screenshots."
        )

        self.assertTrue(result.case_state.report_ready)
        self.assertIn("Case draft for tourist confirmation", result.final_text)
        self.assertIn("Please confirm whether this draft is accurate", result.final_text)

    def test_theft_and_physical_assault_can_reach_drafting(self) -> None:
        theft_orchestrator = SafeTripOrchestrator(use_model=False)
        theft_result = theft_orchestrator.process(
            "My phone was stolen in Bangkok today. I have the item value, theft "
            "location time, witness details, receipt, and tracking info."
        )

        self.assertEqual(theft_result.case_state.scam_type, "theft")
        self.assertTrue(theft_result.case_state.report_ready)
        self.assertEqual(theft_result.case_state.workflow_stage, "awaiting_user_confirmation")

        assault_orchestrator = SafeTripOrchestrator(use_model=False)
        assault_result = assault_orchestrator.process(
            "I was attacked in Pattaya today. I have the assault location time, "
            "injury medical record, attacker description, witness video, and CCTV."
        )

        self.assertEqual(assault_result.case_state.scam_type, "physical_assault")
        self.assertTrue(assault_result.case_state.report_ready)
        self.assertEqual(assault_result.case_state.workflow_stage, "awaiting_user_confirmation")

    def test_complete_case_drafts_then_confirmation_writes_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            posts = []

            def fake_post(endpoint: str, payload: dict) -> dict:
                posts.append({"endpoint": endpoint, "payload": payload})
                return {
                    "reply": "case created",
                    "incident_type": payload["incident_type"],
                    "severity": payload["severity"],
                    "should_create_case": True,
                    "required_info": payload["required_info"],
                }

            orchestrator = SafeTripOrchestrator(
                use_model=False,
                submission_output_root=Path(tmpdir) / "police_packets",
                police_submission_endpoint="https://example.test/api/mockchat",
                police_http_post=fake_post,
            )
            orchestrator.model = FakeExtractionModel(
                {
                    OrchestratorPlan: [
                        OrchestratorPlan(
                            intent="provide_info", carries_case_data=True
                        ),
                        OrchestratorPlan(
                            intent="confirm_submission", carries_case_data=False
                        ),
                    ],
                    PerceptionExtraction: [
                        PerceptionExtraction(
                            scam_type="fake_accommodation",
                            scam_type_confidence=0.9,
                            rationale="Accommodation scam facts are present.",
                            location="Phuket",
                            incident_time="today",
                            amount_lost="12000 THB",
                            evidence_names=[
                                "property_listing_url",
                                "payment_record",
                                "booking_reference",
                            ],
                        ),
                    ],
                    DraftingResult: [
                        DraftingResult(
                            response_text=(
                                "Case draft for tourist confirmation\n\n"
                                "The tourist reports a fake accommodation case in Phuket today.\n\n"
                                "Please confirm whether this draft is accurate."
                            )
                        ),
                    ],
                }
            )

            draft_result = orchestrator.process(
                "I booked a villa in Phuket today and transferred 12000 THB. "
                "I have the listing, payment record, and booking reference."
            )

            self.assertEqual(
                draft_result.raw_result["workflow_steps"],
                [
                    "Orchestrator",
                    "Perception Agent",
                    "Completeness Agent",
                    "Drafting Agent",
                    "Guidance Agent",
                    "Safety Agent",
                ],
            )
            self.assertEqual(
                draft_result.case_state.workflow_stage,
                "awaiting_user_confirmation",
            )
            self.assertIn("Please confirm", draft_result.final_text)
            self.assertIn("Recommendation:", draft_result.final_text)
            self.assertIn("Tourist Police", draft_result.final_text)
            self.assertTrue(draft_result.raw_result["agent_traces"])

            confirmation_result = orchestrator.process("confirm")

            packet_path = Path(confirmation_result.case_state.submission_packet_path)
            self.assertTrue(packet_path.exists())
            packet_text = packet_path.read_text(encoding="utf-8")
            self.assertIn("# SafeTrip Police Submission Packet", packet_text)
            self.assertIn("## Confirmed Draft", packet_text)
            self.assertIn("SafeTrip mock police handoff endpoint", packet_text)
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0]["endpoint"], "https://example.test/api/mockchat")
            self.assertEqual(
                set(posts[0]["payload"]),
                {
                    "reply",
                    "incident_type",
                    "severity",
                    "should_create_case",
                    "required_info",
                },
            )
            self.assertEqual(posts[0]["payload"]["incident_type"], "fake_accommodation")
            self.assertEqual(posts[0]["payload"]["severity"], "medium")
            self.assertTrue(posts[0]["payload"]["should_create_case"])
            self.assertEqual(
                posts[0]["payload"]["required_info"],
                ["location", "contact", "time", "evidence"],
            )
            self.assertEqual(
                confirmation_result.case_state.submission_api_response["reply"],
                "case created",
            )
            self.assertEqual(
                confirmation_result.case_state.workflow_stage,
                "submission_packet_written",
            )
            self.assertEqual(
                confirmation_result.raw_result["workflow_steps"],
                [
                    "Orchestrator",
                    "Submission Packet Agent",
                    "Safety Agent",
                ],
            )

    def test_submission_endpoint_error_is_non_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            def failing_post(_endpoint: str, _payload: dict) -> dict:
                raise RuntimeError("mock endpoint rejected payload")

            orchestrator = SafeTripOrchestrator(
                use_model=False,
                submission_output_root=Path(tmpdir) / "police_packets",
                police_submission_endpoint="https://example.test/api/mockchat",
                police_http_post=failing_post,
            )
            orchestrator.case_state.workflow_stage = "awaiting_user_confirmation"
            orchestrator.case_state.draft_text = "Confirmed draft."
            orchestrator.case_state.scam_type = "restaurant_or_venue_overcharge"

            result = orchestrator.process("yes")

            self.assertEqual(result.case_state.workflow_stage, "submission_packet_written")
            self.assertTrue(Path(result.case_state.submission_packet_path).exists())
            self.assertIn("error", result.case_state.submission_api_response)
            self.assertIn("packet is saved locally", result.final_text.lower())

    def test_orchestrator_uses_agent_specific_models(self) -> None:
        agent_models = {
            "orchestrator": FakeExtractionModel(
                {
                    OrchestratorPlan: [
                        OrchestratorPlan(
                            intent="provide_info", carries_case_data=True
                        )
                    ]
                },
                name="orchestrator",
            ),
            "perception": FakeExtractionModel(
                {
                    PerceptionExtraction: [
                        PerceptionExtraction(
                            scam_type="fake_accommodation",
                            scam_type_confidence=0.9,
                            rationale="Accommodation scam facts are present.",
                            location="Phuket",
                            incident_time="today",
                            amount_lost="12000 THB",
                            evidence_names=[
                                "property_listing_url",
                                "payment_record",
                                "booking_reference",
                            ],
                        )
                    ]
                },
                name="perception",
            ),
            "drafting": FakeExtractionModel(
                {
                    DraftingResult: [
                        DraftingResult(
                            response_text="Case draft for tourist confirmation\n\nPlease confirm."
                        )
                    ]
                },
                name="drafting",
            ),
            "safety": FakeExtractionModel({}, name="safety"),
        }
        orchestrator = SafeTripOrchestrator(use_model=False)
        orchestrator.agent_models = agent_models

        result = orchestrator.process(
            "I booked a villa in Phuket today and transferred 12000 THB. "
            "I have the listing, payment record, and booking reference."
        )

        self.assertEqual(result.case_state.workflow_stage, "awaiting_user_confirmation")
        self.assertEqual(agent_models["orchestrator"].calls, [OrchestratorPlan])
        self.assertEqual(agent_models["perception"].calls, [PerceptionExtraction])
        self.assertEqual(agent_models["drafting"].calls, [DraftingResult])
        self.assertEqual(agent_models["safety"].calls, [])


if __name__ == "__main__":
    unittest.main()
