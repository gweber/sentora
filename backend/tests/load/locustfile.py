"""Load tests for Sentora API.

Run with:
    locust -f tests/load/locustfile.py --host http://localhost:5002

Scenarios:
    - ReadOnlyUser: simulates dashboard/status polling (80% of traffic)
    - SyncUser: triggers syncs and monitors progress (10%)
    - PowerUser: fingerprint/classification/taxonomy CRUD (10%)

Prerequisites:
    pip install locust
    A running Sentora backend with seeded data (./start.sh or docker compose up).
"""

from __future__ import annotations

from locust import HttpUser, between, tag, task


class ReadOnlyUser(HttpUser):
    """Simulates a typical read-heavy dashboard user.

    Polls sync status, reads agent lists, checks health, and views
    classification results. Represents ~80% of real-world traffic.
    """

    weight = 8
    wait_time = between(1, 3)

    @tag("health")
    @task(5)
    def health(self) -> None:
        self.client.get("/health")

    @tag("health")
    @task(3)
    def health_ready(self) -> None:
        self.client.get("/health/ready")

    @tag("dashboard")
    @task(10)
    def dashboard_fleet(self) -> None:
        self.client.get("/api/v1/dashboard/fleet")

    @tag("dashboard")
    @task(5)
    def dashboard_apps(self) -> None:
        self.client.get("/api/v1/dashboard/apps")

    @tag("dashboard")
    @task(5)
    def dashboard_fingerprinting(self) -> None:
        self.client.get("/api/v1/dashboard/fingerprinting")

    @tag("sync")
    @task(8)
    def sync_status(self) -> None:
        self.client.get("/api/v1/sync/status")

    @tag("sync")
    @task(3)
    def sync_history(self) -> None:
        self.client.get("/api/v1/sync/history")

    @tag("agents")
    @task(6)
    def agents_list(self) -> None:
        self.client.get("/api/v1/agents/?limit=50")

    @tag("agents")
    @task(4)
    def groups_list(self) -> None:
        self.client.get("/api/v1/groups/")

    @tag("agents")
    @task(2)
    def sites_list(self) -> None:
        self.client.get("/api/v1/sites/")

    @tag("taxonomy")
    @task(3)
    def taxonomy_categories(self) -> None:
        self.client.get("/api/v1/taxonomy/categories")

    @tag("taxonomy")
    @task(2)
    def taxonomy_entries(self) -> None:
        self.client.get("/api/v1/taxonomy/entries")

    @tag("classification")
    @task(4)
    def classification_results(self) -> None:
        self.client.get("/api/v1/classification/results")

    @tag("fingerprints")
    @task(3)
    def fingerprints_list(self) -> None:
        self.client.get("/api/v1/fingerprints/")

    @tag("apps")
    @task(3)
    def apps_overview(self) -> None:
        self.client.get("/api/v1/agents/apps/overview?limit=50")

    @tag("tags")
    @task(2)
    def tags_list(self) -> None:
        self.client.get("/api/v1/sync/tags")

    @tag("metrics")
    @task(1)
    def prometheus_metrics(self) -> None:
        self.client.get("/metrics")


class SyncUser(HttpUser):
    """Simulates an operator triggering and monitoring syncs.

    Triggers manual syncs, polls status during the run, and checks
    history afterward. Represents ~10% of traffic.
    """

    weight = 1
    wait_time = between(5, 15)

    @tag("sync")
    @task(1)
    def trigger_sync(self) -> None:
        with self.client.post("/api/v1/sync/trigger", catch_response=True) as resp:
            if resp.status_code in (200, 409):
                resp.success()

    @tag("sync")
    @task(5)
    def poll_status(self) -> None:
        self.client.get("/api/v1/sync/status")

    @tag("sync")
    @task(2)
    def check_history(self) -> None:
        self.client.get("/api/v1/sync/history")

    @tag("sync")
    @task(1)
    def check_checkpoint(self) -> None:
        self.client.get("/api/v1/sync/checkpoint")


class PowerUser(HttpUser):
    """Simulates an analyst doing fingerprint/classification/taxonomy work.

    Creates and manages fingerprints, triggers classification runs,
    and edits taxonomy entries. Represents ~10% of traffic.
    """

    weight = 1
    wait_time = between(2, 5)

    @tag("fingerprints")
    @task(5)
    def list_fingerprints(self) -> None:
        self.client.get("/api/v1/fingerprints/")

    @tag("fingerprints")
    @task(3)
    def get_suggestions(self) -> None:
        self.client.get("/api/v1/suggestions/")

    @tag("classification")
    @task(1)
    def trigger_classification(self) -> None:
        with self.client.post("/api/v1/classification/trigger", catch_response=True) as resp:
            if resp.status_code in (200, 409):
                resp.success()

    @tag("classification")
    @task(4)
    def poll_classification(self) -> None:
        self.client.get("/api/v1/classification/results")

    @tag("classification")
    @task(2)
    def classification_overview(self) -> None:
        self.client.get("/api/v1/classification/overview")

    @tag("taxonomy")
    @task(3)
    def browse_taxonomy(self) -> None:
        self.client.get("/api/v1/taxonomy/entries")

    @tag("taxonomy")
    @task(2)
    def preview_pattern(self) -> None:
        self.client.post(
            "/api/v1/taxonomy/preview",
            json={"patterns": ["*chrome*", "*firefox*"]},
        )

    @tag("dashboard")
    @task(3)
    def dashboard_refresh(self) -> None:
        self.client.post("/api/v1/dashboard/refresh")

    @tag("audit")
    @task(2)
    def audit_log(self) -> None:
        self.client.get("/api/v1/audit/?limit=50")

    @tag("apps")
    @task(2)
    def apps_search(self) -> None:
        self.client.get("/api/v1/agents/apps/overview?q=chrome&limit=20")
