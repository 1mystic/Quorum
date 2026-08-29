"""
Stream 5: `signal`. docs/DATA_SPINE.md section 5.

Free text and ordinal ratings.

Two shapes here are deliberately crippled, and the crippling is the mechanism
rather than a policy:

- `TextDoc` has no identity field. `text.near_duplicate_candidates` cannot leak
  an author because it was never handed one. The service layer keeps the
  doc_ref -> member_ref map and re-attaches names after the statistics are done,
  under its own k-anonymity check.
- `OrdinalResponse.value` is an `int` on a declared scale. There is nowhere in
  the spine to put the mean of a Likert item (spine rule S7).

Embeddings arrive precomputed. app/stats/ never calls an embedding model: that
would be network I/O and would break purity. The vector is an input.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

SignalSource = Literal[
    "request_body", "request_comment", "survey_free_text", "feedback", "minutes"
]


@dataclass(frozen=True)
class SignalRecord:
    """
    Atom. Lives inside the tenant boundary only, and never reaches a text
    service or an LLM with `member_ref` attached.
    """

    signal_ref: str
    at: datetime
    source: SignalSource
    text: str
    object_ref: str | None = None      # the request / survey this belongs to
    member_ref: str | None = None      # pseudonymous. STRIPPED before any text service.
    language: str | None = None
    redaction: Literal["raw", "pii_redacted", "unredacted_forbidden"] = "raw"
    category_hint: str | None = None
    strata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TextDoc:
    """
    Unit. What text services actually receive. No identity field exists, and
    none may be added: that absence is the privacy guarantee.
    """

    doc_ref: str
    at: datetime
    text: str
    tokens: tuple[str, ...]
    embedding: tuple[float, ...] | None = None   # computed upstream; stats never calls a model
    category_hint: str | None = None


@dataclass(frozen=True)
class OrdinalResponse:
    """
    Unit. One answer on a declared ordinal scale.

    `value` is NOT a float. The levels are ordered but not equally spaced: the
    gap between "poor" and "fair" is not the gap between "good" and "excellent",
    which is why a mean of a 1 to 5 Likert item is meaningless and why
    `survey.likert_distribution` returns a structure with no `mean` key.
    """

    response_ref: str
    at: datetime
    item_id: str                   # the survey question
    scale_min: int                 # inclusive
    scale_max: int                 # inclusive
    value: int
    respondent_ref: str
    strata: Mapping[str, str] = field(default_factory=dict)
    covariates: Mapping[str, float | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError(
                "OrdinalResponse.value must be an int on the declared scale (spine rule S7); "
                "response " + self.response_ref
            )
        if self.scale_min >= self.scale_max:
            raise ValueError("OrdinalResponse " + self.response_ref + " has an empty scale")
        if not self.scale_min <= self.value <= self.scale_max:
            raise ValueError(
                "OrdinalResponse " + self.response_ref + " value " + str(self.value)
                + " is outside its declared scale"
            )


__all__ = ["OrdinalResponse", "SignalRecord", "SignalSource", "TextDoc"]
