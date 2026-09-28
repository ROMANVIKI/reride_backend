from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import EmailOTP, User


class RegistrationOTPFlowTests(APITestCase):
    """End-to-end cover for register -> OTP -> verified JWT login."""

    def register(self, email="rider@example.com"):
        return self.client.post(
            reverse("auth-register"),
            {
                "fullName": "Test Rider",
                "email": email,
                "phone": "9876543210",
                "password": "StrongPass!234",
                "confirmPassword": "StrongPass!234",
            },
            format="json",
        )

    def test_register_creates_unverified_user_and_sends_otp(self):
        response = self.register()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="rider@example.com")
        self.assertFalse(user.is_email_verified)
        self.assertEqual(EmailOTP.objects.filter(user=user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_login_blocked_until_verified(self):
        self.register()
        response = self.client.post(
            reverse("auth-login"),
            {"email": "rider@example.com", "password": "StrongPass!234"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_returns_tokens(self):
        self.register()
        otp = EmailOTP.objects.get(email="rider@example.com")

        response = self.client.post(
            reverse("auth-verify-otp"),
            {"email": "rider@example.com", "code": otp.code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(User.objects.get(email="rider@example.com").is_email_verified)

    def test_wrong_code_is_rejected_and_counted(self):
        self.register()
        response = self.client.post(
            reverse("auth-verify-otp"),
            {"email": "rider@example.com", "code": "000000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_after_verification_succeeds(self):
        self.register()
        otp = EmailOTP.objects.get(email="rider@example.com")
        self.client.post(
            reverse("auth-verify-otp"),
            {"email": "rider@example.com", "code": otp.code},
            format="json",
        )
        response = self.client.post(
            reverse("auth-login"),
            {"email": "rider@example.com", "password": "StrongPass!234"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_me_requires_authentication(self):
        self.assertEqual(
            self.client.get(reverse("auth-me")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
