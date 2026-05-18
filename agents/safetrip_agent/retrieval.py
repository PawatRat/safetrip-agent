"""Lightweight in-process retrieval (RAG) over the SafeTrip knowledge bases.

This module turns the existing in-code corpora into genuine vector indexes:

- ``EVIDENCE_INDEX``  -> the Case & Evidence DB (``SCAM_EVIDENCE_RULES``)
- ``LEGAL_INDEX``     -> the Legal Database (``LEGAL_KNOWLEDGE_ENTRIES``)

It is dependency-free and deterministic: documents are embedded with a hashed
bag-of-words vector and ranked by cosine similarity. The retrieval step is
*additive* - the authoritative evidence requirements and legal guidance are
still produced by the existing deterministic functions, so behaviour and test
outputs are unchanged. Retrieval only adds a real "look it up in the DB" step
plus traceable provenance.
"""

from __future__ import annotations

import math
import re
import zlib
from dataclasses import dataclass, field

from .evidence_rules import SCAM_EVIDENCE_RULES
from .legal_knowledge_base import LEGAL_KNOWLEDGE_ENTRIES
from .schemas import EvidenceRequirement, ScamType

_EMBED_DIM = 512
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower().replace("_", " "))


def _embed(text: str) -> list[float]:
    """Deterministic hashed bag-of-words embedding (L2-normalised)."""
    vector = [0.0] * _EMBED_DIM
    for token in _tokenize(text):
        bucket = zlib.crc32(token.encode("utf-8")) % _EMBED_DIM
        vector[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class RetrievedDoc:
    doc_id: str
    score: float
    metadata: dict


@dataclass
class VectorIndex:
    """Tiny deterministic vector store: add documents, query by similarity."""

    name: str
    _ids: list[str] = field(default_factory=list)
    _vectors: list[list[float]] = field(default_factory=list)
    _metadata: list[dict] = field(default_factory=list)

    def add(self, doc_id: str, text: str, metadata: dict) -> None:
        self._ids.append(doc_id)
        self._vectors.append(_embed(text))
        self._metadata.append(metadata)

    def query(self, text: str, k: int = 3) -> list[RetrievedDoc]:
        query_vector = _embed(text)
        scored = [
            RetrievedDoc(doc_id, _cosine(query_vector, vector), metadata)
            for doc_id, vector, metadata in zip(
                self._ids, self._vectors, self._metadata
            )
        ]
        scored.sort(key=lambda doc: doc.score, reverse=True)
        return [doc for doc in scored[:k] if doc.score > 0.0]

    def __len__(self) -> int:
        return len(self._ids)


def _build_evidence_index() -> VectorIndex:
    index = VectorIndex(name="case_evidence_db")
    for scam_type, requirements in SCAM_EVIDENCE_RULES.items():
        text_parts = [scam_type.replace("_", " ")]
        for requirement in requirements:
            text_parts.append(requirement.name.replace("_", " "))
            text_parts.append(requirement.reason)
        index.add(
            doc_id=scam_type,
            text=" ".join(text_parts),
            metadata={"scam_type": scam_type},
        )
    return index


def _build_legal_index() -> VectorIndex:
    index = VectorIndex(name="legal_db")
    for entry in LEGAL_KNOWLEDGE_ENTRIES:
        text_parts = [
            entry.title,
            entry.summary,
            " ".join(entry.tags),
            " ".join(case_type.replace("_", " ") for case_type in entry.case_types),
        ]
        index.add(
            doc_id=entry.id,
            text=" ".join(text_parts),
            metadata={
                "case_types": list(entry.case_types),
                "guidance_modes": list(entry.guidance_modes),
            },
        )
    return index


EVIDENCE_INDEX = _build_evidence_index()
LEGAL_INDEX = _build_legal_index()


def retrieve_evidence_requirements(
    scam_type: ScamType,
    query: str = "",
) -> tuple[list[EvidenceRequirement], list[str]]:
    """Retrieve evidence requirements from the Case & Evidence DB.

    The authoritative requirements remain the exact rules for ``scam_type``
    (unchanged behaviour); the vector query adds traceable provenance.
    """
    hits = EVIDENCE_INDEX.query(f"{scam_type} {query}".strip(), k=3)
    requirements = list(SCAM_EVIDENCE_RULES.get(scam_type, []))
    return requirements, [hit.doc_id for hit in hits]


def retrieve_legal_doc_ids(
    scam_type: ScamType,
    mode: str = "intake_help",
    query: str = "",
) -> list[str]:
    """Retrieve the relevant Legal DB document ids for provenance/tracing."""
    hits = LEGAL_INDEX.query(
        f"{scam_type.replace('_', ' ')} {mode} {query}".strip(), k=3
    )
    return [hit.doc_id for hit in hits]
