from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents"))

from safetrip_agent.orchestrator import SafeTripOrchestrator
from safetrip_agent.subagents.completeness_agent import update_case_completeness
from safetrip_agent.subagents.evidence_agent import update_case_evidence
from safetrip_agent.subagents.intake_agent import classify_message, update_case_from_message
from safetrip_agent.schemas import CaseState


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
        orchestrator = SafeTripOrchestrator()

        result = orchestrator.process(
            "Taxi driver overcharged me in Bangkok today."
        )

        self.assertEqual(result.case_state.scam_type, "taxi_overcharge")
        self.assertIn("Next question:", result.final_text)
        self.assertIn("pickup_and_dropoff", result.final_text)

    def test_drafting_only_runs_when_report_ready(self) -> None:
        orchestrator = SafeTripOrchestrator()

        result = orchestrator.process(
            "I booked a villa in Phuket today and transferred 12000 THB. "
            "I have the Facebook page, payment slip, booking reference, and chat screenshots."
        )

        self.assertTrue(result.case_state.report_ready)
        self.assertIn("Case draft for tourist confirmation", result.final_text)
        self.assertIn("Please confirm whether this draft is accurate", result.final_text)


if __name__ == "__main__":
    unittest.main()
