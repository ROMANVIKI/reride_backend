from django.conf import settings
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .emails import send_otp_email, send_welcome_email
from .models import EmailOTP, User
from .serializers import (
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    ForgotPasswordSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    ResendOTPSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VerifyOTPSerializer,
    tokens_for,
)


def _otp_payload(otp, extra=None):
    """
    Standard response for endpoints that dispatch a code. The code itself is
    only echoed back while OTP_DEBUG_IN_RESPONSE is on (development), so the
    flow can be tested without an inbox.
    """
    payload = {
        "email": otp.email,
        "expiresInMinutes": settings.OTP_TTL_MINUTES,
        "resendAfterSeconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
    }
    if settings.OTP_DEBUG_IN_RESPONSE:
        payload["debugCode"] = otp.code
    if extra:
        payload.update(extra)
    return payload


class RegisterView(APIView):
    """
    POST /api/auth/register/

    Creates an unverified account and e-mails a 6-digit OTP. The client then
    calls /api/auth/verify-otp/ with the code to activate and receive tokens.
    """

    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        otp = EmailOTP.issue(user, EmailOTP.Purpose.REGISTER)
        delivered = send_otp_email(otp)

        return Response(
            _otp_payload(
                otp,
                {
                    "detail": (
                        "Account created. Check your e-mail for the verification code."
                        if delivered
                        else "Account created, but we couldn't send the e-mail. "
                        "Use 'resend code' in a moment."
                    ),
                    "emailSent": delivered,
                    "nextStep": "verify-otp",
                },
            ),
            status=status.HTTP_201_CREATED,
        )


class VerifyOTPView(APIView):
    """POST /api/auth/verify-otp/ — confirm the code and return JWT tokens."""

    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        send_welcome_email(user)

        tokens = tokens_for(user)
        return Response(
            {
                **tokens,
                "user": UserSerializer(user, context={"request": request}).data,
                "detail": "E-mail verified. You are signed in.",
            }
        )


class ResendOTPView(APIView):
    """POST /api/auth/resend-otp/ — mint and send a fresh code."""

    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        purpose = serializer.validated_data["purpose"]

        otp = EmailOTP.issue(user, purpose)
        delivered = send_otp_email(otp)

        return Response(
            _otp_payload(
                otp,
                {
                    "detail": "A new code is on its way."
                    if delivered
                    else "We couldn't send the e-mail. Please try again shortly.",
                    "emailSent": delivered,
                },
            )
        )


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — e-mail + password, returns access/refresh/user."""

    serializer_class = EmailTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_scope = "login"


class RefreshView(TokenRefreshView):
    """POST /api/auth/refresh/ — exchange a refresh token for a new access token."""

    permission_classes = [AllowAny]


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklist the supplied refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "A refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            # Already expired or blacklisted — the client is logged out either way.
            pass
        return Response({"detail": "Signed out."})


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ — read or update the signed-in user's profile."""

    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return ProfileUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        return Response(
            UserSerializer(request.user, context={"request": request}).data
        )


class ForgotPasswordView(APIView):
    """
    POST /api/auth/password/forgot/

    Always returns 200 so the endpoint can't be used to discover which
    addresses have accounts.
    """

    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        generic = {
            "detail": "If an account exists for that address, a reset code has been sent.",
            "email": email,
            "expiresInMinutes": settings.OTP_TTL_MINUTES,
        }

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(generic)

        last = EmailOTP.latest_for(user, EmailOTP.Purpose.PASSWORD_RESET)
        if last and last.seconds_until_resend_allowed() > 0:
            return Response(generic)

        otp = EmailOTP.issue(user, EmailOTP.Purpose.PASSWORD_RESET)
        send_otp_email(otp)

        if settings.OTP_DEBUG_IN_RESPONSE:
            generic["debugCode"] = otp.code
        return Response(generic)


class ResetPasswordView(APIView):
    """POST /api/auth/password/reset/ — set a new password using the OTP."""

    permission_classes = [AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        tokens = tokens_for(user)
        return Response(
            {
                **tokens,
                "user": UserSerializer(user, context={"request": request}).data,
                "detail": "Password updated. You are signed in.",
            }
        )


class ChangePasswordView(APIView):
    """POST /api/auth/password/change/ — change password while signed in."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Rotate tokens so the old access token can't outlive the change.
        return Response({**tokens_for(user), "detail": "Password changed."})
