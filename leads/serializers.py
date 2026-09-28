from rest_framework import serializers

from vehicles.models import ServicePackage, Vehicle
from vehicles.pricing import estimate_price
from vehicles.serializers import VehicleListSerializer

from .models import (
    ContactMessage,
    Reservation,
    SellLead,
    ServiceBooking,
    TestRideBooking,
)


PHONE_HELP = "Enter a 10-digit Indian mobile number."


def validate_phone(value):
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise serializers.ValidationError(PHONE_HELP)
    return digits


class AuthorAwareMixin:
    """Attaches the signed-in user and back-fills blank contact details."""

    def _attach_user(self, validated):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            validated["user"] = user
            if not validated.get("name"):
                validated["name"] = user.get_full_name()
            if not validated.get("email"):
                validated["email"] = user.email
            if not validated.get("phone") and user.phone:
                validated["phone"] = user.phone
        return validated


# --------------------------------------------------------------------------
# Sell leads
# --------------------------------------------------------------------------


class SellLeadSerializer(AuthorAwareMixin, serializers.ModelSerializer):
    """
    POST /api/leads/sell/ — the "book a free inspection" form.

    The valuation band is recalculated on the server from the vehicle
    details; any estimate sent by the client is ignored.
    """

    model = serializers.CharField(
        source="model_name", required=False, allow_blank=True, max_length=80
    )
    modelYear = serializers.IntegerField(source="year", required=False, allow_null=True)
    registrationNumber = serializers.CharField(
        source="registration_number", required=False, allow_blank=True, max_length=20
    )
    preferredDate = serializers.DateField(
        source="preferred_date", required=False, allow_null=True
    )
    estimatedLow = serializers.IntegerField(source="estimated_low", read_only=True)
    estimatedPrice = serializers.IntegerField(source="estimated_price", read_only=True)
    estimatedHigh = serializers.IntegerField(source="estimated_high", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = SellLead
        fields = [
            "id", "name", "phone", "email", "brand", "model", "type",
            "modelYear", "km", "owners", "fuel", "registrationNumber", "city",
            "preferredDate", "notes", "status",
            "estimatedLow", "estimatedPrice", "estimatedHigh", "createdAt",
        ]
        read_only_fields = ["id", "status", "createdAt"]

    def validate_phone(self, value):
        return validate_phone(value)

    def create(self, validated):
        validated = self._attach_user(validated)

        if validated.get("year") and validated.get("km") is not None:
            estimate = estimate_price(
                brand=validated["brand"],
                vehicle_type=validated.get("type", "Scooter"),
                model_year=validated["year"],
                km=validated["km"],
                owners=validated.get("owners", "1st owner"),
                fuel=validated.get("fuel", "Petrol"),
            )
            validated["estimated_low"] = estimate["low"]
            validated["estimated_price"] = estimate["mid"]
            validated["estimated_high"] = estimate["high"]

        return super().create(validated)


# --------------------------------------------------------------------------
# Contact
# --------------------------------------------------------------------------


class ContactMessageSerializer(AuthorAwareMixin, serializers.ModelSerializer):
    vehicleSlug = serializers.SlugRelatedField(
        source="vehicle",
        slug_field="slug",
        queryset=Vehicle.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ContactMessage
        fields = [
            "id", "name", "phone", "email", "subject", "message",
            "vehicleSlug", "createdAt",
        ]
        read_only_fields = ["id", "createdAt"]

    def validate_phone(self, value):
        return validate_phone(value) if value else value

    def validate_message(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Please give us a little more detail (at least 10 characters)."
            )
        return value.strip()

    def create(self, validated):
        return super().create(self._attach_user(validated))


# --------------------------------------------------------------------------
# Service bookings
# --------------------------------------------------------------------------


class ServiceBookingSerializer(AuthorAwareMixin, serializers.ModelSerializer):
    packageCode = serializers.SlugRelatedField(
        source="package",
        slug_field="code",
        queryset=ServicePackage.objects.filter(is_active=True),
        write_only=True,
    )
    packageName = serializers.CharField(source="package.name", read_only=True)
    packagePrice = serializers.IntegerField(source="package.price", read_only=True)
    vehicleDetails = serializers.CharField(
        source="vehicle_details", required=False, allow_blank=True, max_length=160
    )
    registrationNumber = serializers.CharField(
        source="registration_number", required=False, allow_blank=True, max_length=20
    )
    preferredDate = serializers.DateField(
        source="preferred_date", required=False, allow_null=True
    )
    preferredSlot = serializers.CharField(
        source="preferred_slot", required=False, allow_blank=True, max_length=40
    )
    isDoorstep = serializers.BooleanField(source="is_doorstep", required=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ServiceBooking
        fields = [
            "id", "name", "phone", "email", "packageCode", "packageName",
            "packagePrice", "vehicleDetails", "registrationNumber",
            "preferredDate", "preferredSlot", "isDoorstep", "address",
            "notes", "status", "createdAt",
        ]
        read_only_fields = ["id", "status", "createdAt"]

    def validate_phone(self, value):
        return validate_phone(value)

    def validate(self, attrs):
        doorstep = attrs.get(
            "is_doorstep", getattr(self.instance, "is_doorstep", True)
        )
        address = attrs.get("address", getattr(self.instance, "address", ""))
        if doorstep and not (address or "").strip():
            raise serializers.ValidationError(
                {"address": "We need a pickup address for doorstep service."}
            )
        return attrs

    def create(self, validated):
        return super().create(self._attach_user(validated))


# --------------------------------------------------------------------------
# Test rides
# --------------------------------------------------------------------------


class TestRideBookingSerializer(AuthorAwareMixin, serializers.ModelSerializer):
    vehicleSlug = serializers.SlugRelatedField(
        source="vehicle",
        slug_field="slug",
        queryset=Vehicle.objects.published(),
        write_only=True,
    )
    vehicle = VehicleListSerializer(read_only=True)
    preferredDate = serializers.DateField(
        source="preferred_date", required=False, allow_null=True
    )
    preferredSlot = serializers.CharField(
        source="preferred_slot", required=False, allow_blank=True, max_length=40
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = TestRideBooking
        fields = [
            "id", "vehicleSlug", "vehicle", "name", "phone", "email",
            "preferredDate", "preferredSlot", "notes", "status", "createdAt",
        ]
        read_only_fields = ["id", "status", "createdAt"]

    def validate_phone(self, value):
        return validate_phone(value)

    def validate(self, attrs):
        vehicle = attrs.get("vehicle")
        if vehicle and vehicle.status == Vehicle.Status.SOLD:
            raise serializers.ValidationError(
                {"vehicleSlug": "This vehicle has already been sold."}
            )
        return attrs

    def create(self, validated):
        return super().create(self._attach_user(validated))


# --------------------------------------------------------------------------
# Reservations
# --------------------------------------------------------------------------


class ReservationSerializer(AuthorAwareMixin, serializers.ModelSerializer):
    vehicleSlug = serializers.SlugRelatedField(
        source="vehicle",
        slug_field="slug",
        queryset=Vehicle.objects.published(),
        write_only=True,
    )
    vehicle = VehicleListSerializer(read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id", "vehicleSlug", "vehicle", "name", "phone", "email",
            "amount", "reference", "notes", "status", "createdAt",
        ]
        read_only_fields = ["id", "amount", "status", "createdAt"]

    def validate_phone(self, value):
        return validate_phone(value)

    def validate(self, attrs):
        vehicle = attrs.get("vehicle")
        if not vehicle:
            return attrs
        if vehicle.status != Vehicle.Status.AVAILABLE:
            raise serializers.ValidationError(
                {"vehicleSlug": "This vehicle is no longer available to reserve."}
            )
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            clash = Reservation.objects.filter(
                vehicle=vehicle,
                user=user,
                status__in=[Reservation.Status.PENDING, Reservation.Status.CONFIRMED],
            ).exists()
            if clash:
                raise serializers.ValidationError(
                    {"vehicleSlug": "You already have an active reservation on this vehicle."}
                )
        return attrs

    def create(self, validated):
        validated = self._attach_user(validated)
        validated["amount"] = Reservation.DEFAULT_AMOUNT
        reservation = super().create(validated)

        # Hold the vehicle so it stops appearing as freely available.
        vehicle = reservation.vehicle
        vehicle.status = Vehicle.Status.RESERVED
        vehicle.save(update_fields=["status", "updated_at"])
        return reservation
