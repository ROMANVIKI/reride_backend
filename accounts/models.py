import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Manager for the e-mail-as-username user model."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An e-mail address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        # Self-service signups stay unverified until the OTP is confirmed.
        extra.setdefault("is_email_verified", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        extra.setdefault("is_email_verified", True)
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Marketplace user. The e-mail address is the login identifier, and an
    account cannot obtain JWT tokens until `is_email_verified` is True.
    """

    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=80, blank=True)
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", null=True, blank=True)

    is_email_verified = models.BooleanField(
        default=False,
        help_text="Set automatically once the registration OTP is confirmed.",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.full_name or self.email

    def get_short_name(self):
        return (self.full_name or self.email).split(" ")[0]

    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        super().save(*args, **kwargs)


def generate_otp_code(length=None):
    """Cryptographically random numeric code, zero-padded to `length`."""
    length = length or getattr(settings, "OTP_LENGTH", 6)
    upper = 10**length
    return str(secrets.randbelow(upper)).zfill(length)


class EmailOTP(models.Model):
    """
    A one-time password sent to an e-mail address.

    Used for three purposes: verifying a new registration, resetting a
    forgotten password, and confirming an e-mail address change.
    """

    class Purpose(models.TextChoices):
        REGISTER = "register", "Registration"
        PASSWORD_RESET = "password_reset", "Password reset"
        EMAIL_CHANGE = "email_change", "E-mail change"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=10)
    purpose = models.CharField(
        max_length=20, choices=Purpose.choices, default=Purpose.REGISTER
    )

    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email", "purpose", "is_used"])]
        verbose_name = "E-mail OTP"
        verbose_name_plural = "E-mail OTPs"

    def __str__(self):
        return f"{self.email} — {self.get_purpose_display()}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return (
            not self.is_used
            and not self.is_expired
            and self.attempts < settings.OTP_MAX_ATTEMPTS
        )

    @classmethod
    def issue(cls, user, purpose=Purpose.REGISTER, email=None):
        """Invalidate any outstanding codes and mint a fresh one."""
        target_email = (email or user.email).lower()
        cls.objects.filter(
            user=user, purpose=purpose, is_used=False
        ).update(is_used=True)
        return cls.objects.create(
            user=user,
            email=target_email,
            code=generate_otp_code(),
            purpose=purpose,
            expires_at=timezone.now()
            + timedelta(minutes=settings.OTP_TTL_MINUTES),
        )

    @classmethod
    def latest_for(cls, user, purpose):
        return (
            cls.objects.filter(user=user, purpose=purpose, is_used=False)
            .order_by("-created_at")
            .first()
        )

    def seconds_until_resend_allowed(self):
        cooldown = timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
        ready_at = self.created_at + cooldown
        remaining = (ready_at - timezone.now()).total_seconds()
        return max(0, int(remaining))
