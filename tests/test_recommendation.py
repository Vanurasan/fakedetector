"""Contract tests for the Recommendation domain model."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from fakedetector.domain import Recommendation

CANONICAL_ACTIONS = [
    "no_additional_action",
    "manual_review",
    "verify_source",
    "verify_source_via_independent_channel",
    "request_better_quality_source",
    "retry_analysis",
    "escalate_to_security",
    "send_to_incident_response",
]


def recommendation_data() -> dict[str, Any]:
    """Return a complete canonical recommendation."""
    return {
        "primary_action": "manual_review",
        "additional_actions": ["verify_source_via_independent_channel"],
        "text": "Выполните ручную проверку.",
        "requires_manual_review": True,
    }


@pytest.mark.parametrize("action", CANONICAL_ACTIONS)
def test_recommendation_accepts_every_canonical_primary_action(action: str) -> None:
    recommendation = Recommendation.model_validate(
        {**recommendation_data(), "primary_action": action}
    )

    assert recommendation.primary_action == action


def test_recommendation_accepts_all_canonical_additional_actions() -> None:
    recommendation = Recommendation.model_validate(
        {**recommendation_data(), "additional_actions": CANONICAL_ACTIONS}
    )

    assert recommendation.additional_actions == CANONICAL_ACTIONS


@pytest.mark.parametrize("field", ["primary_action", "additional_actions"])
def test_recommendation_rejects_unknown_action(field: str) -> None:
    value: str | list[str] = "delete_message" if field == "primary_action" else ["block_user"]
    with pytest.raises(ValidationError):
        Recommendation.model_validate({**recommendation_data(), field: value})


@pytest.mark.parametrize("missing_field", recommendation_data())
def test_recommendation_requires_every_field(missing_field: str) -> None:
    data = recommendation_data()
    del data[missing_field]

    with pytest.raises(ValidationError):
        Recommendation.model_validate(data)


def test_recommendation_json_dump_and_round_trip() -> None:
    recommendation = Recommendation.model_validate(recommendation_data())
    dumped = recommendation.model_dump(mode="json")
    restored = Recommendation.model_validate_json(recommendation.model_dump_json())

    assert json.loads(json.dumps(dumped)) == dumped
    assert restored == recommendation


def test_recommendation_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        Recommendation.model_validate({**recommendation_data(), "automatic": True})
