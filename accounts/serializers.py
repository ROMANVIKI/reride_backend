from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP, User


# --------------------------------------------------------------------------
# User representation
# --------------------------------------------------------------------------


class UserSerializer(serializers.ModelSerializer):
    """The `user` object returned alongside tokens and from /auth/me/."""

    fullName = serializers.CharField(source="full_name", required=False)
    isEmailVerified = serializers.BooleanField(source="is_email_verified", read_only=True)
    isStaff = serializers.BooleanField(source="is_staff", read_only=True)
    dateJoined = serializers.DateTimeField(source="date_joined", read_only=True)
    avatar = serializers.ImageField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "fullName",
            "phone",
            "city",
            "avatar",
            "isEmailVerified",
            "isStaff",
            "dateJoined",
        ]
        read_only_fields = ["id", "email"]


def tokens_for(user):
    """Issue an access/refresh pair for a verified user."""
    refresh = RefreshToken.for_user(user)
    refresh["email"] = user.email
    refresh["full_name"] = user.full_name
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


class RegisterSerializer(serializers.Serializer):
    """
    Step 1 of signup. Creates an unverified account and triggers an OTP.
    No tokens are issued until the OTP is confirmed.
    """

    fullName = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    city = serializers.CharField(max_length=80, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    confirmPassword = serializers.CharField(write_only=True, required=False)

    def validate_email(self, value):
        email = value.lower().strip()
        existing = User.objects.filter(email=email).first()
        if existing and existing.is_email_verified:
            raise serializers.ValidationError(
                "An account with this e-mail already exists. Try signing in."
            )
        return email

    def validate(self, attrs):
        confirm = attrs.pop("confirmPassword", None)
        if confirm is not None and confirm != attrs["password"]:
            raise serializers.ValidationError(
                {"confirmPassword": "The two passwords do not match."}
            )
        password_validation.validate_password(attrs["password"])
        return attrs

    def create(self, validated):
        email = validated["email"]

        # Re-registering an address that was never verified simply refreshes
        # the pending account rather than erroring out.
        user = User.objects.filter(email=email, is_email_verified=False).first()
        if user:
            user.full_name = validated["fullName"]
            user.phone = validated.get("phone", "")
            user.city = validated.get("city", "")
            user.set_password(validated["password"])
            user.save()
        else:
            user = User.objects.create_user(
                email=email,
                password=validated["password"],
                full_name=validated["fullName"],
                phone=validated.get("phone", ""),
                city=validated.get("city", ""),
            )
        return user


# --------------------------------------------------------------------------
# OTP verification
# --------------------------------------------------------------------------


class _OTPCheckMixin:
    """Shared OTP lookup + attempt accounting."""

    otp_purpose = EmailOTP.Purpose.REGISTER

    def resolve_otp(self, email, code):
        email = email.lower().strip()
        user = User.objects.filter(email=email).first()
        if not user:
            raise serializers.ValidationError(
                {"email": "No account found for this e-mail address."}
            )

        otp = EmailOTP.latest_for(user, self.otp_purpose)
        if not otp:
            raise serializers.ValidationError(
                {"code": "No active code. Request a new one."}
            )
        if otp.is_expired:
            raise serializers.ValidationError(
                {"code": "This code has expired. Request a new one."}
            )
        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise serializers.ValidationError(
                {"code": "Too many incorrect attempts. Request a new code."}
            )
        if otp.code != code.strip():
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            remaining = max(0, settings.OTP_MAX_ATTEMPTS - otp.attempts)
            raise serializers.ValidationError(
                {"code": f"Incorrect code. {remaining} attempt(s) left."}
            )

        return user, otp


class VerifyOTPSerializer(_OTPCheckMixin, serializers.Serializer):
    """Step 2 of signup. Confirms the code and returns JWT tokens."""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=10)

    otp_purpose = EmailOTP.Purpose.REGISTER

    def validate(self, attrs):
        user, otp = self.resolve_otp(attrs["email"], attrs["code"])
        attrs["user"] = user
        attrs["otp"] = otp
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        otp = self.validated_data["otp"]

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        if not user.is_email_verified:
            user.is_email_verified = True
            user.is_active = True
            user.save(update_fields=["is_email_verified", "is_active", "updated_at"])
        return user


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=EmailOTP.Purpose.choices, default=EmailOTP.Purpose.REGISTER
    )

    def validate(self, attrs):
        email = attrs["email"].lower().strip()
        user = User.objects.filter(email=email).first()
        if not user:
            raise serializers.ValidationError(
                {"email": "No account found for this e-mail address."}
            )
        if (
            attrs["purpose"] == EmailOTP.Purpose.REGISTER
            and user.is_email_verified
        ):
            raise serializers.ValidationError(
                {"email": "This address is already verified. You can sign in."}
            )

        # Cooldown so the endpoint can't be used to spam an inbox.
        last = EmailOTP.latest_for(user, attrs["purpose"])
        if last:
            wait = last.seconds_until_resend_allowed()
            if wait > 0:
                raise serializers.ValidationError(
                    {"detail": f"Please wait {wait} more second(s) before requesting another code."}
                )

        attrs["user"] = user
        return attrs


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    JWT login keyed on e-mail, with a clear error when the address has not
    been verified yet so the frontend can route to the OTP screen.
    """

    username_field = "email"

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["full_name"] = user.full_name
        return token

    def validate(self, attrs):
        email = attrs.get("email", "").lower().strip()
        password = attrs.get("password")

        user = User.objects.filter(email=email).first()
        if user and not user.check_password(password):
            raise serializers.ValidationError(
                {"detail": "Incorrect e-mail or password."}
            )
        if not user:
            raise serializers.ValidationError(
                {"detail": "Incorrect e-mail or password."}
            )
        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "This account has been disabled. Contact support."}
            )
        if not user.is_email_verified:
            raise serializers.ValidationError(
                {
                    "detail": "Your e-mail address is not verified yet.",
                    "code": "email_not_verified",
                    "email": user.email,
                }
            )

        authenticate(
            request=self.context.get("request"), username=email, password=password
        )

        refresh = self.get_token(user)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(
                user, context=self.context
            ).data,
        }


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class ResetPasswordSerializer(_OTPCheckMixin, serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=10)
    password = serializers.CharField(write_only=True, min_length=8)
    confirmPassword = serializers.CharField(write_only=True, required=False)

    otp_purpose = EmailOTP.Purpose.PASSWORD_RESET

    def validate(self, attrs):
        confirm = attrs.pop("confirmPassword", None)
        if confirm is not None and confirm != attrs["password"]:
            raise serializers.ValidationError(
                {"confirmPassword": "The two passwords do not match."}
            )
        user, otp = self.resolve_otp(attrs["email"], attrs["code"])
        password_validation.validate_password(attrs["password"], user)
        attrs["user"] = user
        attrs["otp"] = otp
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        otp = self.validated_data["otp"]

        user.set_password(self.validated_data["password"])
        # Completing a reset also proves ownership of the address.
        user.is_email_verified = True
        user.save(update_fields=["password", "is_email_verified", "updated_at"])

        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return user


class ChangePasswordSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_currentPassword(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password", "updated_at"])
        return user


class ProfileUpdateSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source="full_name", required=False)

    class Meta:
        model = User
        fields = ["fullName", "phone", "city", "avatar"]
