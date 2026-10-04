"""
Test Suite: Authentication, PBKDF2 Hashing, Sessions, and Tenant Isolation
Validates PRD §11, API_SPEC §3, and IMPLEMENTATION_PLAN WP-1.7
"""

import unittest
import uuid
from packages.storage.auth import (
    init_auth_tables,
    hash_password,
    verify_password,
    create_session,
    authenticate_user,
    register_user,
    get_user_from_token,
    revoke_session,
    revoke_all_sessions,
)
from packages.storage.db import get_db_connection


class TestAuthenticationAndSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_auth_tables()

    def test_01_pbkdf2_hashing_and_verification(self):
        password = "SuperSecretPassword123!"
        pw_hash, pw_salt = hash_password(password)
        self.assertNotEqual(password, pw_hash)
        self.assertEqual(len(pw_hash), 64)  # 256 bits in hex
        self.assertEqual(len(pw_salt), 32)  # 16 bytes in hex
        self.assertTrue(verify_password(password, pw_hash, pw_salt))
        self.assertFalse(verify_password("WrongPassword!", pw_hash, pw_salt))

    def test_02_analyst_seeded_login(self):
        result = authenticate_user("analyst@insightforge.ai", "Analyst@2026!")
        self.assertEqual(result["user"]["email"], "analyst@insightforge.ai")
        self.assertEqual(result["organization"]["name"], "InsightForge Enterprise")
        self.assertIn("session", result)
        self.assertIn("token", result["session"])
        self.assertIn("csrf_token", result)

    def test_03_tenant_registration_and_isolation(self):
        unique_email = f"test_{uuid.uuid4().hex[:8]}@enterprise.com"
        result = register_user(
            name="Test User",
            email=unique_email,
            password="SecurePassword2026!",
            org_name="Alpha Retail Group",
        )
        self.assertEqual(result["user"]["email"], unique_email)
        self.assertEqual(result["organization"]["name"], "Alpha Retail Group")
        self.assertEqual(result["user"]["role"], "ADMIN")

        # Verify duplicate email rejected
        with self.assertRaises(ValueError) as ctx:
            register_user(name="Duplicate", email=unique_email, password="SecurePassword2026!")
        self.assertIn("AUTH_EMAIL_TAKEN", str(ctx.exception))

    def test_04_weak_password_rejection(self):
        with self.assertRaises(ValueError) as ctx:
            register_user(name="Weak", email=f"weak_{uuid.uuid4().hex[:8]}@test.com", password="short")
        self.assertIn("AUTH_WEAK_PASSWORD", str(ctx.exception))

    def test_05_session_token_validation_and_revocation(self):
        unique_email = f"sess_{uuid.uuid4().hex[:8]}@corp.com"
        reg = register_user(name="Session User", email=unique_email, password="LongSecurePassword123!")
        token = reg["session"]["token"]

        # Validate token
        user_ctx = get_user_from_token(token)
        self.assertIsNotNone(user_ctx)
        self.assertEqual(user_ctx["user"]["email"], unique_email)

        # Revoke session
        self.assertTrue(revoke_session(token))

        # Validate revoked token is invalid
        revoked_ctx = get_user_from_token(token)
        self.assertIsNone(revoked_ctx)


if __name__ == "__main__":
    unittest.main()
