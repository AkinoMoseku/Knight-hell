"""Server-authoritative sync, revisions, offline operations and devices."""

from flowremote.control_plane.db import Database
from tests.integration.test_uploads import UploadFixture, order_row, workbook_bytes


class SyncTests(UploadFixture):
    def upload_flagged(self):
        return self.upload(
            data=workbook_bytes(
                [
                    (
                        "order_id",
                        "customer_name",
                        "customer_id",
                        "quantity",
                        "unit_price",
                        "amount",
                        "order_date",
                    ),
                    order_row("SYNC-1", amount=19),
                ]
            )
        ).headers["location"]

    def bootstrap(self):
        return self.client.get(
            "/api/sync/bootstrap",
            headers={"X-Device-Id": "DEVICE-TEST", "X-Device-Label": "Pytest browser"},
        )

    def test_bootstrap_returns_authoritative_state_and_registers_device(self):
        self.upload_flagged()
        response = self.bootstrap()
        assert response.status_code == 200
        payload = response.json()
        assert payload["cursor"] >= 1
        assert len(payload["tasks"]) == 1
        assert payload["tasks"][0]["exceptions"][0]["record_id"] == "ORD-001"
        assert payload["device_registered"] is True
        with Database(self.url) as db:
            device = db.query("SELECT * FROM devices WHERE id = 'DEVICE-TEST'")[0]
        assert device["label"] == "Pytest browser"
        assert device["user_id"] == "A"

    def test_anonymous_sync_is_rejected(self):
        self.client.post("/logout")
        assert self.client.get("/api/sync/bootstrap").status_code == 401
        assert self.client.post("/api/sync/operations", json={}).status_code == 401

    def test_pwa_shell_and_offline_page_are_served(self):
        worker = self.client.get("/sw.js")
        assert worker.status_code == 200
        assert worker.headers["service-worker-allowed"] == "/"
        assert "flowremote-shell" in worker.text
        manifest = self.client.get("/static/manifest.webmanifest")
        assert manifest.status_code == 200
        assert manifest.json()["start_url"] == "/"
        offline = self.client.get("/static/offline.html")
        assert offline.status_code == 200
        assert "Offline cache" in offline.text

    def test_offline_decision_is_idempotent_and_versioned(self):
        self.upload_flagged()
        payload = self.bootstrap().json()
        exception = payload["tasks"][0]["exceptions"][0]
        operation = {
            "type": "decision",
            "operation_id": "OFFLINE-OP-1",
            "task_id": payload["tasks"][0]["id"],
            "record_id": exception["record_id"],
            "action": "skip",
            "value": None,
            "base_revision": exception["revision"],
        }
        first = self.client.post("/api/sync/operations", json=operation)
        assert first.status_code == 200
        assert first.json()["result"]["status"] == "skipped"
        assert first.json()["result"]["replayed"] is False

        replay = self.client.post("/api/sync/operations", json=operation)
        assert replay.status_code == 200
        assert replay.json()["result"]["replayed"] is True
        with Database(self.url) as db:
            assert db.scalar("SELECT COUNT(*) FROM decisions") == 1
            assert db.scalar("SELECT status FROM exceptions") == "skipped"

        stale = dict(operation)
        stale["operation_id"] = "OFFLINE-OP-STALE"
        stale["action"] = "accept"
        conflict = self.client.post("/api/sync/operations", json=stale)
        assert conflict.status_code == 409
        assert conflict.json()["error"] == "revision_conflict"

    def test_pull_returns_only_new_changes(self):
        self.upload_flagged()
        payload = self.bootstrap().json()
        cursor = payload["cursor"]
        task = payload["tasks"][0]
        exception = task["exceptions"][0]
        result = self.client.post(
            "/api/sync/operations",
            json={
                "type": "decision",
                "operation_id": "PULL-OP",
                "task_id": task["id"],
                "record_id": exception["record_id"],
                "action": "skip",
                "base_revision": exception["revision"],
            },
        )
        assert result.status_code == 200
        pull = self.client.get(f"/api/sync/pull?cursor={cursor}")
        assert pull.status_code == 200
        changes = pull.json()["changes"]
        assert {change["entity_type"] for change in changes} == {"task", "exception"}
        next_cursor = pull.json()["cursor"]
        empty = self.client.get(f"/api/sync/pull?cursor={next_cursor}").json()
        assert empty["changes"] == []

    def test_multi_field_offline_edit_is_applied_atomically(self):
        self.upload(
            data=workbook_bytes(
                [
                    (
                        "order_id",
                        "customer_name",
                        "customer_id",
                        "quantity",
                        "unit_price",
                        "amount",
                        "order_date",
                    ),
                    order_row("SYNC-EDIT", customer_id=None, quantity=0),
                ]
            )
        ).headers["location"]
        payload = self.bootstrap().json()
        task = payload["tasks"][0]
        exception = task["exceptions"][0]
        response = self.client.post(
            "/api/sync/operations",
            json={
                "type": "decision",
                "operation_id": "OFFLINE-EDIT",
                "task_id": task["id"],
                "record_id": exception["record_id"],
                "action": "edit",
                "base_revision": exception["revision"],
                "correction": {"customer_id": "C-OFFLINE", "quantity": "2"},
            },
        )
        assert response.status_code == 200
        assert response.json()["result"]["status"] == "manual"
        with Database(self.url) as db:
            order = db.query(
                "SELECT customer_id, quantity FROM source_records WHERE task_id = ?",
                (task["id"],),
            )[0]
        assert order == {"customer_id": "C-OFFLINE", "quantity": 2}

    def test_bootstrap_includes_cached_ai_content(self):
        path = self.upload_flagged()
        self.client.post(
            f"{path}/exceptions/ORD-001/suggestions",
            data={"request_id": "SYNC-AI"},
            follow_redirects=False,
        )
        payload = self.bootstrap().json()
        exception = payload["tasks"][0]["exceptions"][0]
        assert exception["suggestion"] == "20.00"
        assert exception["ai_items"][0]["field"] == "amount"

    def test_another_user_cannot_read_or_push_to_the_task(self):
        self.upload_flagged()
        payload = self.bootstrap().json()
        task = payload["tasks"][0]
        self.login("B")
        assert self.client.get("/api/sync/bootstrap").json()["tasks"] == []
        denied = self.client.post(
            "/api/sync/operations",
            json={
                "type": "decision",
                "operation_id": "OTHER-OP",
                "task_id": task["id"],
                "record_id": "ORD-001",
                "action": "skip",
                "base_revision": 1,
            },
        )
        assert denied.status_code == 400
        assert "not found" in denied.json()["message"]
