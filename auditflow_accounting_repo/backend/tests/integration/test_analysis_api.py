import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.anyio
async def test_analysis_report_endpoint_returns_stable_payload() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/analysis/reports",
            json={
                "analysis_id": "analysis-api-1",
                "process": {
                    "process_name": "Suspense process",
                    "summary": "The team posts a suspense account entry.",
                    "source_filename": "walkthrough.txt",
                },
                "risk_result": {
                    "inconsistencies": [
                        {
                            "id": "inc-1",
                            "type": "account_usage",
                            "title": "Suspense account needs rationale",
                            "description": "Suspense account lacks closure logic.",
                            "source": "heuristic",
                            "severity_hint": "medium",
                            "confidence_hint": 0.8,
                            "evidence": [
                                {
                                    "source": "process",
                                    "text": "suspense account entry",
                                    "section_index": 0,
                                    "chunk_index": 0,
                                }
                            ],
                        }
                    ],
                    "risks": [],
                    "follow_up_questions": [
                        {
                            "id": "q-1",
                            "question": "What is the closure logic?",
                            "rationale": "Suspense accounts need closure.",
                            "related_finding_ids": ["inc-1"],
                        }
                    ],
                },
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["analysis_id"] == "analysis-api-1"
    assert payload["status"] == "completed"
    assert payload["summary"]["total_findings"] == 1
    assert payload["summary"]["review_required_count"] == 1
    assert payload["findings"][0]["score"]["severity"] == "medium"
    assert payload["evidence"][0]["text"] == "suspense account entry"
    assert payload["follow_up_questions"][0]["id"] == "q-1"


@pytest.mark.anyio
async def test_analysis_report_example_payload_is_valid() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    example_path = PROJECT_ROOT / "docs/examples/analysis_report_request.json"
    example_payload = json.loads(example_path.read_text(encoding="utf-8"))

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/analysis/reports",
            json=example_payload,
            headers={"X-Request-ID": "analysis-example-test"},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["analysis_id"] == "analysis-example-1"
    assert payload["summary"]["total_findings"] == 1
