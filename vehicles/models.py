from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify


class Store(models.Model):
    """A physical SriBalajiBikes location that stocks Certified vehicles."""

    name = models.CharField(max_length=100)
    area = models.CharField(max_length=100)
    city = models.CharField(max_length=100, default="Bengaluru")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["city", "name"]

    def __str__(self):
        return f"{self.name} ({self.city})"


class VehicleQuerySet(models.QuerySet):
    def published(self):
        """Listings the public /buy grid is allowed to show."""
        return self.filter(is_approved=True).exclude(status=Vehicle.Status.SOLD)

    def with_relations(self):
        return self.select_related("store", "seller").prefetch_related(
            "highlights", "images"
        )


class Vehicle(models.Model):
    """
    A listing. Mirrors the shape the Next.js frontend consumes, so the
    serialiser can emit exactly the keys the UI already expects.
    """

    class VehicleType(models.TextChoices):
        SCOOTER = "Scooter", "Scooter"
        MOTORCYCLE = "Motorcycle", "Motorcycle"

    class Tier(models.TextChoices):
        CERTIFIED = "Certified", "Certified"
        VERIFIED = "Verified", "Verified"
        DIRECT = "Direct", "Direct"

    class Owners(models.TextChoices):
        FIRST = "1st owner", "1st owner"
        SECOND = "2nd owner", "2nd owner"
        THIRD_PLUS = "3rd owner or more", "3rd owner or more"

    class Demand(models.TextChoices):
        HIGH = "High", "High — selling fast"
        MODERATE = "Moderate", "Moderate — selling steadily"
        LOW = "Low", "Low — slow moving"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"

    class Fuel(models.TextChoices):
        PETROL = "Petrol", "Petrol"
        ELECTRIC = "Electric", "Electric"

    # Identity
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listings",
        null=True,
        blank=True,
        help_text="Blank for dealer-owned stock managed from the admin.",
    )

    # Vehicle details
    brand = models.CharField(max_length=60, db_index=True)
    model_name = models.CharField(max_length=80, verbose_name="Model")
    variant = models.CharField(max_length=80, blank=True)
    type = models.CharField(max_length=12, choices=VehicleType.choices, db_index=True)
    year = models.PositiveIntegerField(
        verbose_name="Model year", validators=[MinValueValidator(1980)]
    )
    km = models.PositiveIntegerField(verbose_name="Kilometres run")
    owners = models.CharField(
        max_length=40, choices=Owners.choices, default=Owners.FIRST
    )
    fuel = models.CharField(max_length=30, choices=Fuel.choices, default=Fuel.PETROL)
    color = models.CharField(max_length=40, blank=True)
    registration = models.CharField(max_length=20, blank=True, help_text="e.g. KA-05")

    # Commercials
    price = models.PositiveIntegerField(help_text="Listing price in INR")
    original_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Market value before discount. Leave blank when not discounted.",
    )
    emi = models.PositiveIntegerField(
        default=0, help_text="Estimated monthly EMI in INR. Auto-calculated when 0."
    )

    # Location
    city = models.CharField(max_length=80, default="Bengaluru", db_index=True)
    area = models.CharField(max_length=80, blank=True)
    store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicles",
    )

    # Trust signals
    tier = models.CharField(
        max_length=12, choices=Tier.choices, default=Tier.DIRECT, db_index=True
    )
    warranty = models.BooleanField(default=False, verbose_name="Warranty included")
    free_service = models.BooleanField(default=False, verbose_name="Free service included")
    demand = models.CharField(
        max_length=10, choices=Demand.choices, default=Demand.MODERATE
    )
    sold_last_month = models.PositiveIntegerField(
        default=0, help_text="How many similar vehicles sold recently."
    )

    # Lifecycle
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.AVAILABLE, db_index=True
    )
    is_approved = models.BooleanField(
        default=True, help_text="Uncheck to hide a listing from the public site."
    )
    views_count = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = VehicleQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["price"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["is_approved", "status"]),
        ]

    def __str__(self):
        return f"{self.brand} {self.model_name} {self.variant} ({self.year})".strip()

    # -- derived values ---------------------------------------------------

    @property
    def title(self):
        return f"{self.brand} {self.model_name}".strip()

    @property
    def discount_percent(self):
        """Percentage off, or None when the listing isn't discounted."""
        if not self.original_price or self.original_price <= self.price:
            return None
        return round((self.original_price - self.price) / self.original_price * 100)

    @property
    def primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()

    def calculate_emi(self, annual_rate=0.115, months=24, down_payment_ratio=0.2):
        """
        Flat monthly instalment on 80% of the price over 24 months at 11.5%
        — the same assumption the UI quotes to buyers.
        """
        principal = self.price * (1 - down_payment_ratio)
        monthly_rate = annual_rate / 12
        if monthly_rate == 0:
            return int(principal / months)
        factor = (1 + monthly_rate) ** months
        return int(round(principal * monthly_rate * factor / (factor - 1)))

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(
                f"{self.brand}-{self.model_name}-{self.variant}-{self.year}-{self.area or self.city}"
            )[:200]
            slug = base
            i = 1
            while Vehicle.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        if not self.emi:
            self.emi = self.calculate_emi()
        super().save(*args, **kwargs)


class VehicleHighlight(models.Model):
    """A bullet point shown under 'What's included' on the detail page."""

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="highlights"
    )
    text = models.CharField(max_length=200)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class VehicleImage(models.Model):
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="vehicles/%Y/%m/")
    caption = models.CharField(max_length=120, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "order", "id"]

    def __str__(self):
        return f"Image for {self.vehicle}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Exactly one primary image per vehicle.
        if self.is_primary:
            VehicleImage.objects.filter(vehicle=self.vehicle).exclude(
                pk=self.pk
            ).update(is_primary=False)
        elif not VehicleImage.objects.filter(
            vehicle=self.vehicle, is_primary=True
        ).exists():
            VehicleImage.objects.filter(pk=self.pk).update(is_primary=True)


class Favorite(models.Model):
    """A saved listing in a signed-in user's shortlist."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "vehicle"], name="unique_user_vehicle_favorite"
            )
        ]

    def __str__(self):
        return f"{self.user.email} ♥ {self.vehicle}"


class ServicePackage(models.Model):
    """A bookable workshop package shown on /service."""

    class Code(models.TextChoices):
        BASIC = "basic", "Basic check-up"
        STANDARD = "standard", "Standard service"
        FULL = "full", "Full refurbishment"

    code = models.CharField(max_length=20, choices=Code.choices, unique=True)
    name = models.CharField(max_length=100)
    price = models.PositiveIntegerField(help_text="Price in INR")
    description = models.TextField(blank=True)
    is_highlighted = models.BooleanField(
        default=False, help_text="Renders as the featured card on the pricing grid."
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "price"]

    def __str__(self):
        return self.name


class ServicePackageItem(models.Model):
    package = models.ForeignKey(
        ServicePackage, on_delete=models.CASCADE, related_name="items"
    )
    text = models.CharField(max_length=160)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class Testimonial(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    quote = models.TextField()
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.name} — {self.location}"


class SiteStat(models.Model):
    """The three headline numbers on the homepage hero."""

    value = models.CharField(max_length=20, help_text="e.g. 220+")
    label = models.CharField(max_length=120)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.value} {self.label}"
