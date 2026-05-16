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
    CaseFactExtraction,
    CaseState,
    CompletenessAssessment,
    DraftingResult,
    EvidenceExtraction,
    GuidanceSelection,
    SafetyAssessment,
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
                CaseFactExtraction: [
                    CaseFactExtraction(
                        scam_type="taxi_overcharge",
                        scam_type_confidence=0.89,
                        rationale="Ride and driver terms matched.",
                        amount_lost="2500 THB",
                    ),
                    CaseFactExtraction(
                        location="chatuchak in jj mall in front of that mall",
                    ),
                ],
                EvidenceExtraction: [
                    EvidenceExtraction(evidence_names=["fare_requested_and_paid"]),
                    EvidenceExtraction(evidence_names=[]),
                ],
                GuidanceSelection: [
                    GuidanceSelection(
                        route="Use Tourist Police 1155/app for immediate tourist help.",
                        source_ids=["seed:tourist-police-1155-app"],
                    ),
                    GuidanceSelection(
                        route="Use Tourist Police 1155/app for immediate tourist help.",
                        source_ids=["seed:tourist-police-1155-app"],
                    ),
                ],
                CompletenessAssessment: [
                    CompletenessAssessment(
                        report_ready=False,
                        missing_items=[
                            "incident_location",
                            "incident_time",
                            "pickup_and_dropoff",
                        ],
                        next_question="Where in Thailand did this happen?",
                    ),
                    CompletenessAssessment(
                        report_ready=False,
                        missing_items=["incident_time", "pickup_and_dropoff"],
                        next_question="When did this happen? An approximate date and time is okay.",
                    ),
                ],
                SafetyAssessment: [
                    SafetyAssessment(
                        response_text="Where in Thailand did this happen?",
                    ),
                    SafetyAssessment(
                        response_text="When did this happen? An approximate date and time is okay.",
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

    def test_complete_case_drafts_then_confirmation_writes_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = SafeTripOrchestrator(
                use_model=False,
                submission_output_root=Path(tmpdir) / "police_packets",
            )
            orchestrator.model = FakeExtractionModel(
                {
                    CaseFactExtraction: [
                        CaseFactExtraction(
                            scam_type="fake_accommodation",
                            scam_type_confidence=0.9,
                            rationale="Accommodation scam facts are present.",
                            location="Phuket",
                            incident_time="today",
                            amount_lost="12000 THB",
                        ),
                    ],
                    EvidenceExtraction: [
                        EvidenceExtraction(
                            evidence_names=[
                                "property_listing_url",
                                "payment_record",
                                "booking_reference",
                            ]
                        ),
                    ],
                    CompletenessAssessment: [
                        CompletenessAssessment(
                            report_ready=True,
                            missing_items=[],
                            next_question=None,
                        ),
                    ],
                    GuidanceSelection: [
                        GuidanceSelection(
                            route="Use Tourist Police support with accommodation evidence.",
                            source_ids=["seed:tourist-police-trust-portal"],
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
                    SafetyAssessment: [
                        SafetyAssessment(
                            response_text=(
                                "Case draft for tourist confirmation\n\n"
                                "The tourist reports a fake accommodation case in Phuket today.\n\n"
                                "Please confirm whether this draft is accurate."
                            )
                        ),
                        SafetyAssessment(
                            response_text="Police submission packet prepared.",
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
                    "Intake Agent",
                    "Evidence Agent",
                    "Completeness Agent",
                    "Orchestrator Decision",
                    "Guidance Agent",
                    "Drafting Agent",
                    "Safety Agent",
                ],
            )
            self.assertEqual(
                draft_result.case_state.workflow_stage,
                "awaiting_user_confirmation",
            )
            self.assertIn("Please confirm", draft_result.final_text)
            self.assertTrue(draft_result.raw_result["agent_traces"])

            confirmation_result = orchestrator.process("confirm")

            packet_path = Path(confirmation_result.case_state.submission_packet_path)
            self.assertTrue(packet_path.exists())
            packet_text = packet_path.read_text(encoding="utf-8")
            self.assertIn("# SafeTrip Police Submission Packet", packet_text)
            self.assertIn("## Confirmed Draft", packet_text)
            self.assertIn("not proof that a formal police report was submitted", packet_text)
            self.assertEqual(
                confirmation_result.case_state.workflow_stage,
                "submission_packet_written",
            )
            self.assertEqual(
                confirmation_result.raw_result["workflow_steps"],
                [
                    "Orchestrator Decision",
                    "Submission Packet Agent",
                    "Safety Agent",
                ],
            )

    def test_orchestrator_uses_agent_specific_models(self) -> None:
        agent_models = {
            "intake": FakeExtractionModel(
                {
                    CaseFactExtraction: [
                        CaseFactExtraction(
                            scam_type="fake_accommodation",
                            scam_type_confidence=0.9,
                            rationale="Accommodation scam facts are present.",
                            location="Phuket",
                            incident_time="today",
                            amount_lost="12000 THB",
                        )
                    ]
                },
                name="intake",
            ),
            "evidence": FakeExtractionModel(
                {
                    EvidenceExtraction: [
                        EvidenceExtraction(
                            evidence_names=[
                                "property_listing_url",
                                "payment_record",
                                "booking_reference",
                            ]
                        )
                    ]
                },
                name="evidence",
            ),
            "completeness": FakeExtractionModel(
                {
                    CompletenessAssessment: [
                        CompletenessAssessment(report_ready=True, missing_items=[])
                    ]
                },
                name="completeness",
            ),
            "guidance": FakeExtractionModel(
                {
                    GuidanceSelection: [
                        GuidanceSelection(
                            route="Use Tourist Police support with accommodation evidence.",
                            source_ids=["seed:tourist-police-trust-portal"],
                        )
                    ]
                },
                name="guidance",
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
            "safety": FakeExtractionModel(
                {
                    SafetyAssessment: [
                        SafetyAssessment(
                            response_text="Case draft for tourist confirmation\n\nPlease confirm."
                        )
                    ]
                },
                name="safety",
            ),
        }
        orchestrator = SafeTripOrchestrator(use_model=False)
        orchestrator.agent_models = agent_models

        result = orchestrator.process(
            "I booked a villa in Phuket today and transferred 12000 THB. "
            "I have the listing, payment record, and booking reference."
        )

        self.assertEqual(result.case_state.workflow_stage, "awaiting_user_confirmation")
        self.assertEqual(agent_models["intake"].calls, [CaseFactExtraction])
        self.assertEqual(agent_models["evidence"].calls, [EvidenceExtraction])
        self.assertEqual(agent_models["completeness"].calls, [CompletenessAssessment])
        self.assertEqual(agent_models["guidance"].calls, [GuidanceSelection])
        self.assertEqual(agent_models["drafting"].calls, [DraftingResult])
        self.assertEqual(agent_models["safety"].calls, [SafetyAssessment])


if __name__ == "__main__":
    unittest.main()
