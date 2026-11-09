"""Registration onboarding and AI-RPA management."""

from tests.integration.test_uploads import UploadFixture, order_row, workbook_bytes


class OnboardingTests(UploadFixture):
    def register_new_user(self):
        self.client.post("/logout")
        response = self.client.post(
            "/signup",
            data={
                "name": "New Operator",
                "email": "new.operator@example.com",
                "password": "password123",
                "password_again": "password123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/onboarding?new=1"

    def finish_onboarding(self):
        return self.client.post(
            "/onboarding",
            data={
                "provider": "offline",
                "model": "grounded-rules-v1",
                "base_url": "",
                "api_key": "",
                "ai_enabled": "1",
                "rpa_enabled": "1",
                "max_records_per_task": "10000",
                "ai_daily_limit": "100",
                "rpa_daily_limit": "10",
                "connection_local_excel": "1",
                "connection_local_http": "1",
            },
            follow_redirects=False,
        )

    def test_new_registration_opens_ai_rpa_onboarding(self):
        self.register_new_user()
        page = self.client.get("/onboarding")
        assert page.status_code == 200
        assert "Set up your AI-RPA workspace" in page.text
        assert 'data-guide-section="onboarding-ai"' in page.text
        assert 'data-guide-section="onboarding-rpa"' in page.text

    def test_onboarding_completes_and_next_login_goes_to_dashboard(self):
        self.register_new_user()
        response = self.finish_onboarding()
        assert response.status_code == 303
        assert response.headers["location"] == "/?guide=start"
        settings = self.client.get("/settings")
        assert settings.status_code == 200
        assert "AI &amp; RPA control center" in settings.text
        assert "Local Excel Output" in settings.text
        assert "Local HTTP Target" in settings.text
        self.client.post("/logout")
        login = self.client.post(
            "/login",
            data={"email": "new.operator@example.com", "password": "password123"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert login.headers["location"] == "/"

    def test_disabled_ai_blocks_suggestion_generation(self):
        page = self.client.get("/settings")
        assert page.status_code == 200
        response = self.client.post(
            "/settings/automation",
            data={
                "rpa_enabled": "1",
                "max_records_per_task": "10000",
                "ai_daily_limit": "100",
                "rpa_daily_limit": "10",
                "connection_local_excel": "1",
                "connection_local_http": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = workbook_bytes(
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
                order_row("AI-OFF", amount=19),
            ]
        )
        path = self.upload(data=data).headers["location"]
        blocked = self.client.post(
            f"{path}/exceptions/ORD-001/suggestions",
            data={"request_id": "DISABLED-AI"},
            follow_redirects=False,
        )
        assert blocked.status_code == 400
        assert "AI suggestions are disabled" in blocked.text

    def test_settings_track_ai_and_rpa_usage(self):
        data = workbook_bytes(
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
                order_row("USAGE-1", amount=19),
            ]
        )
        path = self.upload(data=data).headers["location"]
        self.client.post(
            f"{path}/exceptions/ORD-001/suggestions",
            data={"request_id": "USAGE-AI"},
            follow_redirects=False,
        )
        self.client.post(
            f"{path}/exceptions/ORD-001/decisions",
            data={"action": "accept", "decision_id": "USAGE-ACCEPT"},
            follow_redirects=False,
        )
        self.client.post(f"{path}/proceed", follow_redirects=False)
        self.client.post(f"{path}/approval", follow_redirects=False)
        self.client.post(f"{path}/execution/step", follow_redirects=False)
        page = self.client.get("/settings")
        assert page.status_code == 200
        assert "1 / 100" in page.text
        assert "1 / 10" in page.text
