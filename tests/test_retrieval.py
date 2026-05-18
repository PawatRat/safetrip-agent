from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents"))

from safetrip_agent.evidence_rules import SCAM_EVIDENCE_RULES
from safetrip_agent.retrieval import (
    EVIDENCE_INDEX,
    LEGAL_INDEX,
    retrieve_evidence_requirements,
    retrieve_legal_doc_ids,
)


class RetrievalTests(unittest.TestCase):
    def test_indexes_are_populated(self) -> None:
        self.assertEqual(len(EVIDENCE_INDEX), len(SCAM_EVIDENCE_RULES))
        self.assertGreater(len(LEGAL_INDEX), 0)

    def test_evidence_retrieval_preserves_authoritative_requirements(self) -> None:
        # Behaviour must be unchanged: same exact requirements as the rule table.
        for scam_type in SCAM_EVIDENCE_RULES:
            requirements, docs = retrieve_evidence_requirements(scam_type)
            self.assertEqual(requirements, SCAM_EVIDENCE_RULES[scam_type])
            self.assertIn(scam_type, docs)

    def test_evidence_retrieval_is_deterministic(self) -> None:
        first = retrieve_evidence_requirements("taxi_overcharge", "driver fare")
        second = retrieve_evidence_requirements("taxi_overcharge", "driver fare")
        self.assertEqual(first[1], second[1])

    def test_legal_retrieval_returns_relevant_docs(self) -> None:
        accommodation = retrieve_legal_doc_ids("fake_accommodation", "report_route")
        assault = retrieve_legal_doc_ids("physical_assault", "intake_help")
        self.assertTrue(accommodation)
        self.assertTrue(assault)
        self.assertIn("accommodation-scam-trust-portal", accommodation)
        self.assertIn("physical-assault-emergency", assault)


if __name__ == "__main__":
    unittest.main()
