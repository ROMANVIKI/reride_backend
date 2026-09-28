from django.conf import settings
from django.db import models

from vehicles.models import ServicePackage, Store, Vehicle


class TimeStampedLead(models.Model):
    """Shared base for everything that arrives from a public form."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Set when the enquiry came from a signed-in user.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class SellLead(models.Model):
    """
    Someone asking us to buy their two-wheeler, captured from the Sell page
    valuation widget. The estimate is computed server-side and stored, so a
    seller can't talk us into a number they typed themselves.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        INSPECTION_BOOKED = "inspection_booked", "Inspection booked"
        INSPECTED = "inspected", "Inspected"
        OFFER_MADE = "offer_made", "Offer made"
        PURCHASED = "purchased", "Purchased"
        CLOSED = "closed", "Closed / lost"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sell_leads",
    )

    name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)

    brand = models.CharField(max_length=60)
    model_name = models.CharField(max_length=80, blank=True, verbose_name="Model")
    type = models.CharField(
        max_length=12, choices=Vehicle.VehicleType.choices, default=Vehicle.VehicleType.SCOOTER
    )
    year = models.PositiveIntegerField(null=True, blank=True)
    km = models.PositiveIntegerField(null=True, blank=True)
    owners = models.CharField(max_length=40, blank=True)
    fuel = models.CharField(max_length=30, default="Petrol")
    registration_number = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=80, blank=True)

    # Server-computed valuation band at the time of enquiry.
    estimated_low = models.PositiveIntegerField(null=True, blank=True)
    estimated_price = models.PositiveIntegerField(null=True, blank=True)
    estimated_high = models.PositiveIntegerField(null=True, blank=True)

    preferred_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.brand} {self.model_name} — {self.phone} ({self.status})"


class ContactMessage(TimeStampedLead):
    """A message from the /contact form."""

    class Subject(models.TextChoices):
        GENERAL = "general", "General enquiry"
        BUYING = "buying", "Buying a vehicle"
        SELLING = "selling", "Selling a vehicle"
        SERVICE = "service", "Service booking"
        SUPPORT = "support", "Existing order / support"

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    subject = models.CharField(
        max_length=20, choices=Subject.choices, default=Subject.GENERAL
    )
    message = models.TextField()

    # Set when the enquiry was raised from a specific listing page.
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enquiries",
    )

    is_read = models.BooleanField(default=False)
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedLead.Meta):
        pass

    def __str__(self):
        return f"{self.name} — {self.get_subject_display()}"


class ServiceBooking(TimeStampedLead):
    """A workshop booking from the /service page."""

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)

    package = models.ForeignKey(
        ServicePackage, on_delete=models.PROTECT, related_name="bookings"
    )
    vehicle_details = models.CharField(
        max_length=160, blank=True, help_text="e.g. Honda Activa 6G, 2021"
    )
    registration_number = models.CharField(max_length=20, blank=True)

    preferred_date = models.DateField(null=True, blank=True)
    preferred_slot = models.CharField(
        max_length=40, blank=True, help_text="e.g. Morning (9am-12pm)"
    )
    is_doorstep = models.BooleanField(default=True)
    address = models.TextField(blank=True, help_text="Required for doorstep pickup.")
    store = models.ForeignKey(
        Store, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings"
    )
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.REQUESTED, db_index=True
    )

    class Meta(TimeStampedLead.Meta):
        pass

    def __str__(self):
        return f"{self.name} — {self.package.name}"


class TestRideBooking(TimeStampedLead):
    """A request to test ride a specific listing."""

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="test_ride_bookings"
    )
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)

    preferred_date = models.DateField(null=True, blank=True)
    preferred_slot = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.REQUESTED, db_index=True
    )

    class Meta(TimeStampedLead.Meta):
        pass

    def __str__(self):
        return f"Test ride: {self.vehicle} for {self.name}"


class Reservation(TimeStampedLead):
    """
    A soft hold on a listing against a token amount. Confirming a
    reservation flips the vehicle's status to 'reserved'.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        CONVERTED = "converted", "Converted to sale"

    DEFAULT_AMOUNT = 2000

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="reservations"
    )
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)

    amount = models.PositiveIntegerField(default=DEFAULT_AMOUNT)
    reference = models.CharField(
        max_length=40, blank=True, help_text="Payment gateway reference, once paid."
    )
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    class Meta(TimeStampedLead.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle", "user"],
                condition=models.Q(status__in=["pending", "confirmed"]),
                name="one_active_reservation_per_user_per_vehicle",
            )
        ]

    def __str__(self):
        return f"Reservation: {self.vehicle} by {self.name}"
