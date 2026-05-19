from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents"))

from safetrip_agent.model_provider import DEFAULT_AGENT_MODELS, resolve_agent_model_name
from safetrip_agent.orchestrator import SafeTripOrchestrator
from safetrip_agent.web_demo import result_to_payload
from safetrip_agent.legal_knowledge_base import build_guidance_from_knowledge
from safetrip_agent.schemas import (
    CaseState,
    EvidenceExtraction,
    OrchestratorPlan,
    PerceptionExtraction,
)
from safetrip_agent.subagents.evidence_agent import update_case_evidence_with_model
from safetrip_agent.subagents.guidance_agent import update_case_guidance
from safetrip_agent.subagents.perception_agent import update_case_perception_with_model
from safetrip_agent.subagents.safety_agent import review_case_safety
from safetrip_agent.subagents.submission_packet_agent import (
    build_police_submission_payload,
    build_submission_packet_markdown,
    severity_for_case,
    submit_case_to_police_endpoint,
)


class StaticStructuredModel:
    def __init__(self, response) -> None:
        self.response = response
        self.schema = None
        self.messages = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, messages):
        self.messages = messages
        return self.response


class DetailedBehaviorTests(unittest.TestCase):
    def test_agent_model_defaults_and_env_override(self) -> None:
        self.assertEqual(
            resolve_agent_model_name("intake"),
            DEFAULT_AGENT_MODELS["intake"],
        )
        self.assertEqual(
            resolve_agent_model_name("completeness"),
            "gemini-2.5-pro",
        )

        with patch.dict(os.environ, {"SAFETRIP_COMPLETENESS_MODEL": "custom-pro"}):
            self.assertEqual(resolve_agent_model_name("completeness"), "custom-pro")

    def test_offline_incomplete_branch_routes_to_intake_help_guidance(self) -> None:
        orchestrator = SafeTripOrchestrator(use_model=False)

        result = orchestrator.process("Taxi driver overcharged me in Bangkok today.")

        self.assertEqual(
            result.raw_result["workflow_steps"],
            [
                "Orchestrator",
                "Perception Agent",
                "Completeness Agent",
                "Guidance Agent",
                "Synthesis Agent",
                "Safety Agent",
            ],
        )
        self.assertEqual(result.case_state.workflow_stage, "collecting_info")
        self.assertNotIn("Drafting Agent", result.raw_result["workflow_steps"])
        self.assertIn("Next, collect:", result.case_state.reporting_guidance.route)
        self.assertIn("Next question:", result.final_text)

    def test_non_confirmation_does_not_submit_packet(self) -> None:
        posts = []
        orchestrator = SafeTripOrchestrator(
            use_model=False,
            police_http_post=lambda endpoint, payload: posts.append(payload) or {},
        )
        orchestrator.case_state.workflow_stage = "awaiting_user_confirmation"
        orchestrator.case_state.draft_text = "Draft waiting for confirmation."

        result = orchestrator.process("wait, I need to correct the location")

        self.assertEqual(posts, [])
        self.assertIsNone(result.case_state.submission_packet_path)
        self.assertNotIn("Submission Packet Agent", result.raw_result["workflow_steps"])

    def test_submission_payload_uses_required_mockchat_fields(self) -> None:
        state = CaseState(
            scam_type="online_transfer_scam",
            location="Bangkok",
            incident_time="today",
            amount_lost="5000 THB",
            draft_text="Confirmed police-ready draft.",
        )

        payload = build_police_submission_payload(state)

        self.assertEqual(
            set(payload),
            {
                "reply",
                "incident_type",
                "severity",
                "should_create_case",
                "required_info",
            },
        )
        self.assertEqual(payload["reply"], "Confirmed police-ready draft.")
        self.assertEqual(payload["incident_type"], "online_transfer_scam")
        self.assertEqual(payload["severity"], "high")
        self.assertTrue(payload["should_create_case"])
        self.assertEqual(payload["required_info"], ["location", "contact", "time", "evidence"])

    def test_submission_endpoint_stores_endpoint_and_response(self) -> None:
        state = CaseState(
            scam_type="taxi_overcharge",
            draft_text="Confirmed taxi report.",
        )
        calls = []

        def fake_post(endpoint: str, payload: dict) -> dict:
            calls.append((endpoint, payload))
            return {"reply": "created", "should_create_case": True}

        updated, response = submit_case_to_police_endpoint(
            state,
            "https://example.test/api/mockchat",
            fake_post,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "https://example.test/api/mockchat")
        self.assertEqual(response["reply"], "created")
        self.assertEqual(updated.submission_api_endpoint, "https://example.test/api/mockchat")
        self.assertEqual(updated.submission_api_response, response)

    def test_severity_mapping_prioritizes_high_risk_cases(self) -> None:
        self.assertEqual(severity_for_case(CaseState(scam_type="fake_police_or_government")), "high")
        self.assertEqual(severity_for_case(CaseState(scam_type="online_transfer_scam")), "high")
        self.assertEqual(severity_for_case(CaseState(scam_type="physical_assault")), "high")
        self.assertEqual(severity_for_case(CaseState(scam_type="taxi_overcharge")), "medium")

    def test_model_evidence_agent_filters_unknown_evidence_names(self) -> None:
        state = CaseState(scam_type="taxi_overcharge")
        model = StaticStructuredModel(
            EvidenceExtraction(
                evidence_names=[
                    "fare_requested_and_paid",
                    "not_a_real_evidence_name",
                ]
            )
        )

        updated = update_case_evidence_with_model(
            model,
            state,
            "The driver charged me 2500 THB.",
        )

        self.assertEqual(updated.known_evidence_names, ["fare_requested_and_paid"])
        self.assertEqual(model.schema, EvidenceExtraction)

    def test_guidance_intake_mode_adds_collection_instruction(self) -> None:
        state = CaseState(
            scam_type="taxi_overcharge",
            next_question="Where did the ride start and end?",
        )

        intake_guidance = update_case_guidance(state, "intake_help")
        report_guidance = update_case_guidance(state, "report_route")

        self.assertIn("Next, collect:", intake_guidance.reporting_guidance.route)
        self.assertNotIn("Next, collect:", report_guidance.reporting_guidance.route)
        self.assertTrue(intake_guidance.reporting_guidance.sources)
        self.assertIn("tourist-police-main", intake_guidance.reporting_guidance.source_ids)

    def test_legal_knowledge_base_returns_case_specific_sources(self) -> None:
        accommodation = build_guidance_from_knowledge("fake_accommodation")
        assault = build_guidance_from_knowledge("physical_assault")
        cyber = build_guidance_from_knowledge("online_transfer_scam")

        self.assertIn("tourist-police-trust", accommodation["source_ids"])
        self.assertIn("thailand-emergency-numbers", assault["source_ids"])
        self.assertIn("thai-police-online-reporting", cyber["source_ids"])
        self.assertTrue(accommodation["recommended_actions"])
        self.assertTrue(assault["sources"])

    def test_offline_safety_flags_danger_and_unsupported_claims(self) -> None:
        state = CaseState(messages=["The driver followed me and had a weapon."])
        response_text = "The criminal is caught and police report has been submitted."

        updated, safe_text = review_case_safety(state, response_text)

        self.assertIn("possible_immediate_danger", updated.safety_review.flags)
        self.assertIn("unsupported_submission_claim", updated.safety_review.flags)
        self.assertIn("unsupported_legal_certainty", updated.safety_review.flags)
        self.assertIn("Tourist Police 1155", safe_text)
        self.assertIn("reported person", safe_text)

    def test_submission_markdown_contains_core_sections_and_transcript(self) -> None:
        state = CaseState(
            scam_type="fake_accommodation",
            location="Phuket",
            incident_time="today",
            amount_lost="12000 THB",
            draft_text="Confirmed accommodation draft.",
            messages=["I booked a villa and paid 12000 THB."],
            user_confirmed_submission=True,
        )

        markdown = build_submission_packet_markdown(state)

        self.assertIn("# SafeTrip Police Submission Packet", markdown)
        self.assertIn("## Case Metadata", markdown)
        self.assertIn("## Confirmed Draft", markdown)
        self.assertIn("Confirmed accommodation draft.", markdown)
        self.assertIn("Tourist: I booked a villa and paid 12000 THB.", markdown)
        self.assertIn("SafeTrip mock police handoff endpoint", markdown)

    def test_confirmation_flow_writes_markdown_and_posts_once(self) -> None:
        posts = []

        def fake_post(endpoint: str, payload: dict) -> dict:
            posts.append({"endpoint": endpoint, "payload": payload})
            return {"reply": "created"}

        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = SafeTripOrchestrator(
                use_model=False,
                submission_output_root=Path(tmpdir) / "packets",
                police_submission_endpoint="https://example.test/api/mockchat",
                police_http_post=fake_post,
            )
            orchestrator.case_state.workflow_stage = "awaiting_user_confirmation"
            orchestrator.case_state.draft_text = "Confirmed draft."
            orchestrator.case_state.scam_type = "taxi_overcharge"
            orchestrator.case_state.location = "Bangkok"
            orchestrator.case_state.incident_time = "today"

            result = orchestrator.process("yes confirm")

            self.assertEqual(len(posts), 1)
            packet_path = Path(result.case_state.submission_packet_path)
            self.assertTrue(packet_path.exists())
            self.assertEqual(result.case_state.submission_api_response, {"reply": "created"})
            self.assertEqual(result.case_state.workflow_stage, "submission_packet_written")
            self.assertEqual(
                result.raw_result["workflow_steps"],
                [
                    "Orchestrator",
                    "Submission Packet Agent",
                    "Synthesis Agent",
                    "Safety Agent",
                ],
            )

    def test_web_demo_payload_contains_chat_and_pipeline_fields(self) -> None:
        orchestrator = SafeTripOrchestrator(use_model=False)
        result = orchestrator.process("Taxi driver overcharged me in Bangkok today.")

        payload = result_to_payload(result)

        self.assertIn("final_text", payload)
        self.assertIn("workflow_steps", payload)
        self.assertIn("agent_traces", payload)
        self.assertIn("case_state", payload)
        self.assertIn("Perception Agent", payload["workflow_steps"])
        self.assertTrue(payload["agent_traces"])

    def test_model_completeness_branch_does_not_repeat_answered_location(self) -> None:
        responses = {
            "orchestrator": StaticStructuredModel(
                response=OrchestratorPlan(
                    intent="provide_info", carries_case_data=True
                )
            ),
            "perception": StaticStructuredModel(
                response=PerceptionExtraction(
                    scam_type="taxi_overcharge",
                    scam_type_confidence=0.9,
                    rationale="Taxi overcharge detected.",
                    location="near Chatuchak JJ Mall",
                    amount_lost="2500 THB",
                    evidence_names=["fare_requested_and_paid"],
                )
            ),
        }
        orchestrator = SafeTripOrchestrator(use_model=False)
        orchestrator.agent_models = responses

        result = orchestrator.process(
            "it in nearly chatuchak in jj mall and driver charged 2500 THB"
        )

        self.assertEqual(result.case_state.location, "near Chatuchak JJ Mall")
        self.assertNotIn("incident_location", result.case_state.missing_items)
        self.assertIn("incident_time", result.case_state.missing_items)
        self.assertIn("When did this happen?", result.final_text)
        self.assertIn("Reporting guidance:", result.final_text)

    def test_advice_only_followup_skips_perception_agent(self) -> None:
        orchestrator = SafeTripOrchestrator(use_model=False)
        first = orchestrator.process(
            "Taxi driver overcharged me in Bangkok today and charged 2500 THB."
        )

        self.assertEqual(first.case_state.scam_type, "taxi_overcharge")

        second = orchestrator.process("what should i do")

        self.assertEqual(
            second.raw_result["workflow_steps"],
            [
                "Orchestrator",
                "Completeness Agent",
                "Guidance Agent",
                "Synthesis Agent",
                "Safety Agent",
            ],
        )
        self.assertEqual(second.case_state.messages.count("what should i do"), 1)
        self.assertIn("Reporting guidance:", second.final_text)
        self.assertIn("Tourist Police 1155", second.final_text)

    def test_model_confirmation_is_ignored_without_pending_draft(self) -> None:
        responses = {
            "orchestrator": StaticStructuredModel(
                response=OrchestratorPlan(
                    intent="confirm_submission",
                    carries_case_data=False,
                    rationale="Model incorrectly treated this as confirmation.",
                )
            ),
            "perception": StaticStructuredModel(
                response=PerceptionExtraction(
                    scam_type="taxi_overcharge",
                    scam_type_confidence=0.85,
                    location="Bangkok",
                    incident_time="today",
                    amount_lost="2500 THB",
                    evidence_names=["fare_requested_and_paid"],
                )
            ),
        }
        orchestrator = SafeTripOrchestrator(use_model=False)
        orchestrator.agent_models = responses

        result = orchestrator.process("confirm")

        self.assertNotIn("Submission Packet Agent", result.raw_result["workflow_steps"])
        self.assertIn("Perception Agent", result.raw_result["workflow_steps"])
        self.assertEqual(result.case_state.workflow_stage, "collecting_info")
        self.assertIsNone(result.case_state.submission_packet_path)

    def test_model_perception_filters_unknown_evidence_names(self) -> None:
        model = StaticStructuredModel(
            response=PerceptionExtraction(
                scam_type="fake_accommodation",
                scam_type_confidence=0.9,
                location="Phuket",
                incident_time="today",
                amount_lost="12000 THB",
                evidence_names=[
                    "payment_record",
                    "seller_chat_or_email",
                    "not_a_real_evidence_name",
                ],
            )
        )
        state = CaseState(messages=["I booked a villa and paid 12000 THB."])

        updated = update_case_perception_with_model(
            model,
            state,
            "I have the payment record and seller chat.",
        )

        self.assertEqual(model.schema, PerceptionExtraction)
        self.assertEqual(updated.scam_type, "fake_accommodation")
        self.assertEqual(
            updated.known_evidence_names,
            ["payment_record", "seller_chat_or_email"],
        )

    def test_orchestrator_appends_latest_message_once(self) -> None:
        orchestrator = SafeTripOrchestrator(use_model=False)
        message = "I booked a Phuket villa today and paid 12000 THB."

        result = orchestrator.process(message)

        self.assertEqual(result.case_state.messages.count(message), 1)
        self.assertEqual(result.case_state.messages[-1], message)


if __name__ == "__main__":
    unittest.main()
