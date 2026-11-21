"""
VYTRON — Role-Based Egress Proof & Data Privacy Access Control Test Suite
Tests:
1. IT Team user CANNOT access /api/egress/tier1-raw (403 Forbidden).
2. IT Team user CANNOT request /api/egress/proof?include_raw=true (403 Forbidden).
3. IT Team user CAN access sanitized /api/egress/proof (200 OK) with permitted metadata only.
4. Admin CANNOT automatically access raw customer secrets without customer-local authorization (403 Forbidden).
5. Admin WITH customer-local authorization CAN inspect Tier 1 raw records (200 OK).
6. Tenant isolation: unauthorized tenant returns 403 Forbidden.
7. WebSocket/Public snapshot contains ZERO raw customer secrets.
8. Data classification policy lists restricted vs permitted metadata fields.
"""

import unittest
from unittest.mock import patch
from starlette.testclient import TestClient

from server.app import app, simulator
from server.auth import COOKIE_NAME, upsert_user, create_session, init_auth_db
from server.privacy import ALLOWED_EGRESS_FIELDS, BLOCKED_RAW_KEYS

client = TestClient(app)


class TestEgressRBAC(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_auth_db()
        simulator.reset()

        # Provision IT Team user
        cls.it_user = upsert_user(
            google_sub="sub-egress-it",
            name="IT Operator",
            email="it.operator@vytron.ai",
            picture="https://example.com/it.jpg",
            requested_role="it_team"
        )
        cls.it_session_id = create_session(cls.it_user["user_id"])

        # Provision Admin user
        cls.admin_user = upsert_user(
            google_sub="sub-egress-admin",
            name="Platform Admin",
            email="admin@vytron.ai",  # Listed in INITIAL_ADMIN_EMAILS
            picture="https://example.com/admin.jpg",
            requested_role="admin"
        )
        cls.admin_session_id = create_session(cls.admin_user["user_id"])

    # 1. IT Team cannot access Tier 1 raw endpoint
    def test_01_it_team_cannot_access_tier1_raw_endpoint(self):
        res = client.get("/api/egress/tier1-raw", cookies={COOKIE_NAME: self.it_session_id})
        self.assertEqual(res.status_code, 403)
        self.assertIn("IT Team role is strictly prohibited", res.json()["detail"])
        print("[PASS] TEST 1: IT Team user is strictly blocked from /api/egress/tier1-raw with 403.")

    # 2. IT Team cannot request include_raw=true on proof endpoint
    def test_02_it_team_cannot_request_include_raw(self):
        res = client.get("/api/egress/proof?include_raw=true", cookies={COOKIE_NAME: self.it_session_id})
        self.assertEqual(res.status_code, 403)
        self.assertIn("IT Team role is strictly prohibited", res.json()["detail"])
        print("[PASS] TEST 2: IT Team user cannot retrieve raw data by modifying query parameter with 403.")

    # 3. IT Team gets sanitized metadata only (no raw credentials)
    def test_03_it_team_gets_sanitized_metadata_only(self):
        res = client.get("/api/egress/proof", cookies={COOKIE_NAME: self.it_session_id})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        latest = data.get("latest")
        self.assertIsNotNone(latest)

        # Ensure raw_tier1_preview is NOT exposed
        self.assertNotIn("raw_tier1_preview", latest)

        # Check sanitized_tier2_payload
        sanitized = latest.get("sanitized_tier2_payload")
        self.assertIsNotNone(sanitized)

        # Check that only allowed fields exist in sanitized payload
        for k in sanitized.keys():
            self.assertIn(k, ALLOWED_EGRESS_FIELDS)

        # Verify that actual secret values and raw credentials NEVER exist in response
        raw_text = res.text.lower()
        for forbidden in [
            "super_secret_pg_master_password",
            "sk_live_customer_prod_auth_key",
            "backup_vault_aes256_passphrase",
            "wjalrxutnfemi",
            "private_cisco_community_string",
            "192.168.1."
        ]:
            self.assertNotIn(forbidden, raw_text)

        # Verify raw keys are NOT in sanitized payload
        for blocked_key in ["db_password", "jwt_session_token", "api_key", "internal_ip", "snmp_community"]:
            self.assertNotIn(blocked_key, sanitized)

        print("[PASS] TEST 3: IT Team receives sanitized Tier 2 metadata with ZERO raw secrets.")

    # 4. Central SaaS Admin without customer-local auth cannot access raw customer data
    def test_04_admin_cannot_access_raw_without_local_auth(self):
        res = client.get("/api/egress/tier1-raw", cookies={COOKIE_NAME: self.admin_session_id})
        self.assertEqual(res.status_code, 403)
        self.assertIn("requires explicit customer-local authorization", res.json()["detail"])
        print("[PASS] TEST 4: Central SaaS Admin without customer-local authorization receives 403.")

    # 5. Central SaaS Admin with customer-local auth CAN access Tier 1 raw records
    def test_05_admin_with_local_auth_can_access_raw(self):
        headers = {"X-Customer-Local-Auth": "vytron-collector-key-2026"}
        res = client.get("/api/egress/tier1-raw", cookies={COOKIE_NAME: self.admin_session_id}, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "authorized")
        self.assertEqual(data["authorization_mode"], "CUSTOMER_LOCAL_ON_PREM_AUTHORIZED")
        self.assertIsNotNone(data["raw_tier1_record"])
        print("[PASS] TEST 5: Central SaaS Admin WITH valid customer-local authorization receives 200.")

    # 6. Tenant isolation enforcement
    def test_06_tenant_isolation_enforcement(self):
        # Querying foreign tenant
        res_proof = client.get("/api/egress/proof?tenant_id=TENANT-FOREIGN", cookies={COOKIE_NAME: self.admin_session_id})
        self.assertEqual(res_proof.status_code, 403)
        self.assertIn("Tenant isolation policy violation", res_proof.json()["detail"])

        res_policy = client.get("/api/egress/policy?tenant_id=TENANT-FOREIGN")
        self.assertEqual(res_policy.status_code, 403)
        self.assertIn("Tenant isolation policy violation", res_policy.json()["detail"])
        print("[PASS] TEST 6: Foreign tenant queries are strictly rejected with 403 Forbidden.")

    # 7. WebSocket / Public snapshot contains zero raw secrets
    def test_07_snapshot_contains_zero_raw_secrets(self):
        snapshot = simulator.get_snapshot()
        egress = snapshot.get("egress_proof", {})
        latest = egress.get("latest", {})
        self.assertNotIn("raw_tier1_preview", latest)

        for hist in egress.get("history", []):
            self.assertNotIn("raw_tier1_preview", hist)

        print("[PASS] TEST 7: WebSocket / snapshot egress proof contains ZERO raw secrets.")

    # 8. Data classification: restricted vs permitted
    def test_08_data_classification_policy(self):
        res = client.get("/api/egress/policy")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("classification", data)
        self.assertIn("restricted_fields", data["classification"])
        self.assertIn("permitted_metadata_fields", data["classification"])
        self.assertEqual(data["tenant_id"], "TENANT-01")
        print("[PASS] TEST 8: Data classification endpoint verified with allow-list and restricted fields.")


if __name__ == "__main__":
    unittest.main()
