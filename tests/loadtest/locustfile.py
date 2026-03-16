"""Load test for Evidence-Bound API. NOT run in CI.

Usage:
    locust -f tests/loadtest/locustfile.py --host http://localhost:8000
"""

from locust import HttpUser, between, task


class DocQAUser(HttpUser):
    """Simulates a user querying the Evidence-Bound API."""

    wait_time = between(1, 3)

    @task(3)
    def ask_question(self) -> None:
        """POST /v1/ask with a sample question."""
        self.client.post(
            "/v1/ask",
            json={
                "question": "What are the key terms of the agreement?",
                "matter_id": "load-test-matter",
            },
            headers={
                "X-Tenant-Id": "load-test-tenant",
                "X-Matter-Id": "load-test-matter",
                "X-User-Role": "attorney",
            },
        )

    @task(1)
    def health_check(self) -> None:
        """GET /v1/health as a lightweight check."""
        self.client.get("/v1/health")
