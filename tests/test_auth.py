"""
VYTRON — Google Authentication & Role-Based Access Control Test Suite
Tests:
1. Unauthenticated user accessing /api/auth/me returns 401.
2. Configuration endpoint returns public config without leaking secrets.
3. Invalid/malformed Google token is rejected.
4. Google OAuth token verification flow with valid claims creates user in SQLite.
5. Critical Security: Ordinary user selecting 'admin' is denied Admin privileges and assigned 'it_team'.
6. Authorized Admin (email in INITIAL_ADMIN_EMAILS) receives 'admin' permissions.
7. Backend-enforced authorization: IT Team calling /api/admin/users receives 403 Forbidden.
8. Authorized Admin calling /api/admin/users receives 200 OK with full user list.
9. Admin can promote/assign user roles via /api/admin/assign-role.
10. Logout invalidates session and subsequent requests return 401.
11. Expired sessions are rejected and cleaned up.
12. Existing endpoints (servers, chat health, knowledge sources) continue working without regression.
"""

import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from server.app import app
from server.auth import (
    get_db_connection,
    init_auth_db,
    verify_google_id_token,
    resolve_authorized_role,
    upsert_user,
    create_session,
    get_user_from_session,
    invalidate_session,
    COOKIE_NAME,
    INITIAL_ADMIN_EMAILS
)

client = TestClient(app)


class TestGoogleAuthAndRoleAuthorization(unittest.TestCase):
    def setUp(self):
        """Ensure clean test environment in SQLite tables."""
        init_auth_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM users")
        conn.commit()
        conn.close()

    def tearDown(self):
        """Clean up test data."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM users")
        conn.commit()
        conn.close()

    # 1. Unauthenticated user
    def test_01_unauthenticated_user_access(self):
        res = client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json()["detail"])
        print("[PASS] TEST 1: Unauthenticated user is correctly rejected with 401.")

    # 2. Public config does not leak secrets
    def test_02_auth_config_public_safety(self):
        res = client.get("/api/auth/config")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("configured", data)
        self.assertIn("initial_admins_configured", data)
        self.assertNotIn("client_secret", str(data).lower())
        self.assertNotIn("session_secret", str(data).lower())
        print("[PASS] TEST 2: Public config returns OAuth status without exposing secrets.")

    # 3. Invalid/malformed Google token rejection
    def test_03_invalid_token_rejected(self):
        res = client.post("/api/auth/google", json={
            "credential": "invalid_fake_jwt_token_12345",
            "requested_role": "it_team"
        })
        self.assertEqual(res.status_code, 401)
        print("[PASS] TEST 3: Malformed/fake Google ID token is rejected with 401.")

    # 4. Verified Google Identity for IT Team
    @patch("server.auth.verify_google_id_token")
    def test_04_google_auth_it_team_provisioning(self, mock_verify):
        mock_verify.return_value = {
            "google_sub": "google-sub-it-user-999",
            "email": "sarah.connor@example.com",
            "email_verified": True,
            "name": "Sarah Connor",
            "picture": "https://lh3.googleusercontent.com/a/sample_it_avatar"
        }

        res = client.post("/api/auth/google", json={
            "credential": "valid_google_signed_jwt_token",
            "requested_role": "it_team"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["authorized_role"], "it_team")
        self.assertEqual(data["email"], "sarah.connor@example.com")
        self.assertEqual(data["account_status"], "active")

        # Verify session cookie was set
        self.assertIn(COOKIE_NAME, res.cookies)
        cookie_val = res.cookies[COOKIE_NAME]

        # Verify /api/auth/me using cookie
        me_res = client.get("/api/auth/me", cookies={COOKIE_NAME: cookie_val})
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertEqual(me_data["name"], "Sarah Connor")
        self.assertEqual(me_data["authorized_role"], "it_team")
        print("[PASS] TEST 4: Google OAuth succeeds and provisions IT Team user with secure session cookie.")

    # 5. CRITICAL SECURITY: Ordinary user cannot grant themselves Admin
    @patch("server.auth.verify_google_id_token")
    def test_05_prevent_admin_self_escalation(self, mock_verify):
        """
        An ordinary user selects 'Admin' on the frontend radio button.
        The backend MUST NOT grant admin privileges.
        """
        mock_verify.return_value = {
            "google_sub": "google-sub-regular-user-404",
            "email": "curious.operator@example.com",
            "email_verified": True,
            "name": "Curious Operator",
            "picture": "https://lh3.googleusercontent.com/a/sample_regular_avatar"
        }

        res = client.post("/api/auth/google", json={
            "credential": "valid_google_signed_jwt_token",
            "requested_role": "admin"  # Attempting privilege escalation
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # CRITICAL ASSERTIONS:
        self.assertEqual(data["authorized_role"], "it_team", "Security Breach: Ordinary user must NOT receive admin role!")
        self.assertEqual(data["requested_role"], "admin")
        self.assertEqual(data["account_status"], "pending_admin_approval")
        self.assertIn("requires authorization", data["message"])

        # Verify database record
        conn = get_db_connection()
        user_row = conn.execute("SELECT * FROM users WHERE email = 'curious.operator@example.com'").fetchone()
        conn.close()
        self.assertEqual(user_row["authorized_role"], "it_team")
        print("[PASS] TEST 5 (SECURITY): Ordinary user selecting Admin is safely restricted to IT Team with pending status.")

    # 6. Authorized Admin receives Admin permissions
    @patch("server.auth.verify_google_id_token")
    def test_06_authorized_admin_provisioning(self, mock_verify):
        admin_email = INITIAL_ADMIN_EMAILS[0] if INITIAL_ADMIN_EMAILS else "admin@vytron.ai"
        mock_verify.return_value = {
            "google_sub": "google-sub-admin-master-001",
            "email": admin_email,
            "email_verified": True,
            "name": "Platform Administrator",
            "picture": "https://lh3.googleusercontent.com/a/sample_admin_avatar"
        }

        res = client.post("/api/auth/google", json={
            "credential": "valid_google_signed_jwt_token",
            "requested_role": "admin"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["authorized_role"], "admin")
        self.assertEqual(data["account_status"], "active")
        print(f"[PASS] TEST 6: Pre-authorized administrator ({admin_email}) correctly receives Admin role.")

    # 7. Backend-enforced role authorization: IT Team cannot access /api/admin/users
    @patch("server.auth.verify_google_id_token")
    def test_07_backend_role_authorization_enforced(self, mock_verify):
        mock_verify.return_value = {
            "google_sub": "google-sub-it-user-888",
            "email": "dev.operator@example.com",
            "email_verified": True,
            "name": "Dev Operator",
            "picture": ""
        }

        res_login = client.post("/api/auth/google", json={
            "credential": "valid_google_token",
            "requested_role": "it_team"
        })
        cookie_val = res_login.cookies[COOKIE_NAME]

        # Attempt to access admin endpoint with IT Team session
        admin_res = client.get("/api/admin/users", cookies={COOKIE_NAME: cookie_val})
        self.assertEqual(admin_res.status_code, 403, "IT Team user must receive 403 Forbidden on admin endpoints")
        self.assertIn("Administrator privileges required", admin_res.json()["detail"])
        print("[PASS] TEST 7: Backend strictly blocks IT Team user from admin endpoint with 403 Forbidden.")

    # 8. Authorized Admin can access /api/admin/users
    @patch("server.auth.verify_google_id_token")
    def test_08_admin_can_access_admin_endpoints(self, mock_verify):
        admin_email = INITIAL_ADMIN_EMAILS[0] if INITIAL_ADMIN_EMAILS else "admin@vytron.ai"
        mock_verify.return_value = {
            "google_sub": "google-sub-admin-002",
            "email": admin_email,
            "email_verified": True,
            "name": "Lead SRE Admin",
            "picture": ""
        }

        res_login = client.post("/api/auth/google", json={
            "credential": "valid_google_token",
            "requested_role": "admin"
        })
        cookie_val = res_login.cookies[COOKIE_NAME]

        # Access admin endpoint with Admin session
        admin_res = client.get("/api/admin/users", cookies={COOKIE_NAME: cookie_val})
        self.assertEqual(admin_res.status_code, 200)
        data = admin_res.json()
        self.assertIn("users", data)
        self.assertGreaterEqual(data["total_users"], 1)
        print("[PASS] TEST 8: Authorized Admin successfully accesses /api/admin/users.")

    # 9. Admin role assignment / promotion
    @patch("server.auth.verify_google_id_token")
    def test_09_admin_assign_role(self, mock_verify):
        # 1. Create IT Team user
        user_it = upsert_user("sub-it-promote", "Candidate Operator", "candidate@example.com", "", "it_team")
        self.assertEqual(user_it["authorized_role"], "it_team")

        # 2. Login as Admin
        admin_email = INITIAL_ADMIN_EMAILS[0] if INITIAL_ADMIN_EMAILS else "admin@vytron.ai"
        mock_verify.return_value = {
            "google_sub": "sub-admin-promoter",
            "email": admin_email,
            "email_verified": True,
            "name": "Promoting Admin",
            "picture": ""
        }
        res_login = client.post("/api/auth/google", json={"credential": "v", "requested_role": "admin"})
        cookie_val = res_login.cookies[COOKIE_NAME]

        # 3. Promote IT Team user to Admin
        res_promote = client.post(
            "/api/admin/assign-role",
            cookies={COOKIE_NAME: cookie_val},
            json={"user_id": user_it["user_id"], "new_role": "admin"}
        )
        self.assertEqual(res_promote.status_code, 200)
        self.assertTrue(res_promote.json()["success"])

        # 4. Verify user is now Admin in SQLite
        conn = get_db_connection()
        updated_user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_it["user_id"],)).fetchone()
        conn.close()
        self.assertEqual(updated_user["authorized_role"], "admin")
        print("[PASS] TEST 9: Admin successfully promotes IT Team user to Admin.")

    # 10. Logout invalidates session
    @patch("server.auth.verify_google_id_token")
    def test_10_logout_invalidates_session(self, mock_verify):
        mock_verify.return_value = {
            "google_sub": "sub-logout-test",
            "email": "logout.user@example.com",
            "email_verified": True,
            "name": "Logout Tester",
            "picture": ""
        }
        res_login = client.post("/api/auth/google", json={"credential": "v", "requested_role": "it_team"})
        cookie_val = res_login.cookies[COOKIE_NAME]

        # Verify active
        self.assertEqual(client.get("/api/auth/me", cookies={COOKIE_NAME: cookie_val}).status_code, 200)

        # Logout
        res_logout = client.post("/api/auth/logout", cookies={COOKIE_NAME: cookie_val})
        self.assertEqual(res_logout.status_code, 200)
        self.assertTrue(res_logout.json()["success"])

        # Verify session is now rejected
        me_after = client.get("/api/auth/me", cookies={COOKIE_NAME: cookie_val})
        self.assertEqual(me_after.status_code, 401)
        print("[PASS] TEST 10: Logout successfully invalidates session.")

    # 11. Expired session rejected
    def test_11_expired_session_handling(self):
        user = upsert_user("sub-expired", "Expired User", "expired@example.com", "", "it_team")
        conn = get_db_connection()
        # Insert already expired session (2 hours ago)
        expired_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn.execute("INSERT INTO sessions (session_id, user_id, created_at, expires_at) VALUES ('sess_expired_123', ?, ?, ?)",
                     (user["user_id"], expired_time, expired_time))
        conn.commit()
        conn.close()

        res = client.get("/api/auth/me", cookies={COOKIE_NAME: "sess_expired_123"})
        self.assertEqual(res.status_code, 401)
        print("[PASS] TEST 11: Expired session is correctly detected and rejected with 401.")

    # 12. Regression check: existing endpoints remain functional
    def test_12_regression_existing_endpoints(self):
        res_servers = client.get("/api/servers")
        self.assertEqual(res_servers.status_code, 200)
        self.assertIn("servers", res_servers.json())

        res_chat_health = client.get("/api/chat/health")
        self.assertEqual(res_chat_health.status_code, 200)
        self.assertEqual(res_chat_health.json()["status"], "healthy")

        res_sources = client.get("/api/knowledge/sources")
        self.assertEqual(res_sources.status_code, 200)
        print("[PASS] TEST 12: Regression check passed — existing telemetry, monitoring, and RAG endpoints operate normally.")


if __name__ == "__main__":
    unittest.main()
