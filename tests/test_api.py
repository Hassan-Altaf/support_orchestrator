"""HTTP-level tests via FastAPI TestClient.

Covers happy paths, validation errors, request-id middleware, error
envelope consistency, and recovered-error surfacing.
"""

from __future__ import annotations

import pytest


@pytest.mark.api
class TestMetaEndpoints:
    def test_health_returns_ok(self, client) -> None:
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["version"]

    def test_version_returns_version(self, client) -> None:
        r = client.get("/api/v1/version")
        assert r.status_code == 200
        assert "version" in r.json()

    def test_openapi_docs_mounted(self, client) -> None:
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200


@pytest.mark.api
class TestProcessValidation:
    def test_empty_message_returns_422(self, client) -> None:
        r = client.post("/api/v1/support/process", json={"message": ""})
        assert r.status_code == 422
        assert r.json()["error"] == "validation_error"

    def test_too_short_message_returns_422(self, client) -> None:
        r = client.post("/api/v1/support/process", json={"message": "hi"})
        assert r.status_code == 422

    def test_too_long_message_returns_422(self, client) -> None:
        r = client.post("/api/v1/support/process", json={"message": "x" * 15_000})
        assert r.status_code == 422

    def test_missing_message_returns_422(self, client) -> None:
        r = client.post("/api/v1/support/process", json={})
        assert r.status_code == 422

    def test_extra_field_returns_422(self, client) -> None:
        r = client.post(
            "/api/v1/support/process",
            json={"message": "Help with the system please", "rogue": "x"},
        )
        assert r.status_code == 422


@pytest.mark.api
class TestProcessHappyPath:
    def test_returns_full_processing_result(
        self,
        client,
        mock_provider,
        good_classification,
        good_extracted_info,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        mock_provider.queue_for("Classification", good_classification())
        mock_provider.queue_for("ExtractedInfo", good_extracted_info())
        mock_provider.queue_for("CustomerResponseDraft", good_customer_response())
        mock_provider.queue_for("InternalSummary", good_internal_summary())

        r = client.post(
            "/api/v1/support/process",
            json={"message": "Our outbound dialer is dropping calls every few seconds."},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["classification"]["category"]
        assert body["extracted_info"]
        assert body["escalation_context"] is None
        assert "VoiceSpin team" in body["customer_response"]
        assert body["internal_summary"]
        assert len(body["processing_trace"]) == 4
        assert body["recovered_errors"] == []
        assert body["request_id"]


@pytest.mark.api
class TestRequestIdMiddleware:
    def test_generated_request_id_in_response(
        self,
        client,
        mock_provider,
        good_classification,
        good_extracted_info,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        mock_provider.queue_for("Classification", good_classification())
        mock_provider.queue_for("ExtractedInfo", good_extracted_info())
        mock_provider.queue_for("CustomerResponseDraft", good_customer_response())
        mock_provider.queue_for("InternalSummary", good_internal_summary())

        r = client.post(
            "/api/v1/support/process",
            json={"message": "Need help with the outbound dialer please."},
        )
        rid = r.headers["x-request-id"]
        assert rid
        assert r.json()["request_id"] == rid

    def test_client_supplied_request_id_preserved(
        self,
        client,
        mock_provider,
        good_classification,
        good_extracted_info,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        mock_provider.queue_for("Classification", good_classification())
        mock_provider.queue_for("ExtractedInfo", good_extracted_info())
        mock_provider.queue_for("CustomerResponseDraft", good_customer_response())
        mock_provider.queue_for("InternalSummary", good_internal_summary())

        r = client.post(
            "/api/v1/support/process",
            json={"message": "Need help with the outbound dialer please."},
            headers={"X-Request-ID": "test-supplied-rid"},
        )
        assert r.headers["x-request-id"] == "test-supplied-rid"
        assert r.json()["request_id"] == "test-supplied-rid"


@pytest.mark.api
class TestRecoveredErrors:
    def test_classifier_failure_returns_200_with_recovered_errors(
        self,
        client,
        mock_provider,
        good_extracted_info,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        mock_provider.queue_for("Classification", RuntimeError("simulate outage"))
        mock_provider.queue_for("ExtractedInfo", good_extracted_info())
        mock_provider.queue_for("CustomerResponseDraft", good_customer_response())
        mock_provider.queue_for("InternalSummary", good_internal_summary())

        r = client.post(
            "/api/v1/support/process",
            json={"message": "Something seems off with our service today."},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["classification"]["category"] == "other"  # fallback signature
        assert len(body["recovered_errors"]) >= 1
        classify_entry = next(t for t in body["processing_trace"] if t["node"] == "classify")
        assert classify_entry["outcome"] == "fallback"
