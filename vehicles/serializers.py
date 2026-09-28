from django.conf import settings
from rest_framework import serializers

from .models import (
    FAQ,
    Favorite,
    ServicePackage,
    ServicePackageItem,
    SiteStat,
    Store,
    Testimonial,
    Vehicle,
    VehicleHighlight,
    VehicleImage,
)
from .pricing import estimate_price


def absolute_url(request, file_field):
    if not file_field:
        return None
    url = file_field.url
    return request.build_absolute_uri(url) if request else url


# --------------------------------------------------------------------------
# Supporting objects
# --------------------------------------------------------------------------


class VehicleImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    isPrimary = serializers.BooleanField(source="is_primary", read_only=True)

    class Meta:
        model = VehicleImage
        fields = ["id", "url", "caption", "isPrimary", "order"]

    def get_url(self, obj):
        return absolute_url(self.context.get("request"), obj.image)


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = [
            "id", "name", "area", "city", "address", "phone",
            "latitude", "longitude",
        ]


class SellerSerializer(serializers.Serializer):
    """Minimal, privacy-conscious view of whoever posted a listing."""

    id = serializers.IntegerField()
    name = serializers.CharField(source="get_full_name")
    city = serializers.CharField()
    memberSince = serializers.DateTimeField(source="date_joined")


# --------------------------------------------------------------------------
# Vehicles — read
# --------------------------------------------------------------------------


class VehicleListSerializer(serializers.ModelSerializer):
    """
    Card shape for the /buy grid and homepage. The keys intentionally match
    the frontend's `Vehicle` type so components need no remapping.
    """

    model = serializers.CharField(source="model_name", read_only=True)
    modelYear = serializers.IntegerField(source="year", read_only=True)
    originalPrice = serializers.IntegerField(source="original_price", read_only=True)
    freeService = serializers.BooleanField(source="free_service", read_only=True)
    soldLastMonth = serializers.IntegerField(source="sold_last_month", read_only=True)
    discountPercent = serializers.IntegerField(source="discount_percent", read_only=True)
    highlights = serializers.SlugRelatedField(
        slug_field="text", many=True, read_only=True
    )
    image = serializers.SerializerMethodField()
    isFavorite = serializers.SerializerMethodField()
    isMine = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id", "slug", "brand", "model", "variant", "type", "modelYear",
            "km", "owners", "price", "originalPrice", "discountPercent", "emi",
            "city", "area", "tier", "fuel", "color", "registration",
            "highlights", "warranty", "freeService", "demand", "soldLastMonth",
            "status", "image", "isFavorite", "isMine", "createdAt",
        ]

    def get_image(self, obj):
        img = obj.primary_image
        return absolute_url(self.context.get("request"), img.image) if img else None

    def get_isFavorite(self, obj):
        favorite_ids = self.context.get("favorite_ids")
        if favorite_ids is not None:
            return obj.id in favorite_ids
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return Favorite.objects.filter(user=request.user, vehicle=obj).exists()

    def get_isMine(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.seller_id == request.user.id


class VehicleDetailSerializer(VehicleListSerializer):
    images = VehicleImageSerializer(many=True, read_only=True)
    store = StoreSerializer(read_only=True)
    seller = serializers.SerializerMethodField()
    viewsCount = serializers.IntegerField(source="views_count", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta(VehicleListSerializer.Meta):
        fields = VehicleListSerializer.Meta.fields + [
            "description", "images", "store", "seller", "viewsCount", "updatedAt",
        ]

    def get_seller(self, obj):
        if not obj.seller:
            return {"name": "SriBalajiBikes", "city": obj.city, "isDealer": True}
        return {
            "id": obj.seller.id,
            "name": obj.seller.get_full_name(),
            "city": obj.seller.city or obj.city,
            "memberSince": obj.seller.date_joined,
            "isDealer": False,
        }


# --------------------------------------------------------------------------
# Vehicles — write
# --------------------------------------------------------------------------


class VehicleWriteSerializer(serializers.ModelSerializer):
    """
    Create/update shape used by the "Post an ad" flow and the seller
    dashboard. Accepts the same camelCase keys the frontend form produces.
    """

    model = serializers.CharField(source="model_name", max_length=80)
    modelYear = serializers.IntegerField(source="year")
    originalPrice = serializers.IntegerField(
        source="original_price", required=False, allow_null=True
    )
    freeService = serializers.BooleanField(source="free_service", required=False)
    highlights = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Vehicle
        fields = [
            "brand", "model", "variant", "type", "modelYear", "km", "owners",
            "price", "originalPrice", "city", "area", "fuel", "color",
            "registration", "warranty", "freeService", "description",
            "highlights", "images", "status",
        ]

    # -- validation -------------------------------------------------------

    def validate_price(self, value):
        if value < 1000:
            raise serializers.ValidationError("Price must be at least Rs 1,000.")
        if value > 10_000_000:
            raise serializers.ValidationError("Price looks too high. Please check it.")
        return value

    def validate_km(self, value):
        if value > 500_000:
            raise serializers.ValidationError(
                "Kilometres run looks too high. Please check it."
            )
        return value

    def validate_modelYear(self, value):
        from datetime import date

        current = date.today().year
        if value < 1980 or value > current:
            raise serializers.ValidationError(
                f"Model year must be between 1980 and {current}."
            )
        return value

    def validate_images(self, value):
        if len(value) > 8:
            raise serializers.ValidationError("You can upload up to 8 photos.")
        limit = settings.MAX_UPLOAD_SIZE
        for image in value:
            if image.size > limit:
                raise serializers.ValidationError(
                    f"Each photo must be under {limit // (1024 * 1024)}MB."
                )
        return value

    def validate(self, attrs):
        price = attrs.get("price", getattr(self.instance, "price", None))
        original = attrs.get(
            "original_price", getattr(self.instance, "original_price", None)
        )
        if original and price and original <= price:
            raise serializers.ValidationError(
                {"originalPrice": "The original price must be higher than the asking price."}
            )
        return attrs

    # -- persistence ------------------------------------------------------

    def _sync_highlights(self, vehicle, highlights):
        vehicle.highlights.all().delete()
        VehicleHighlight.objects.bulk_create(
            [
                VehicleHighlight(vehicle=vehicle, text=text, order=index)
                for index, text in enumerate(highlights)
                if text.strip()
            ]
        )

    def _add_images(self, vehicle, images):
        has_primary = vehicle.images.filter(is_primary=True).exists()
        start = vehicle.images.count()
        for index, image in enumerate(images):
            VehicleImage.objects.create(
                vehicle=vehicle,
                image=image,
                order=start + index,
                is_primary=(not has_primary and index == 0),
            )

    def create(self, validated):
        highlights = validated.pop("highlights", None)
        images = validated.pop("images", [])
        request = self.context["request"]

        vehicle = Vehicle.objects.create(
            seller=request.user,
            # Owner-posted ads are always Direct listings; Certified and
            # Verified tiers are assigned by staff after inspection.
            tier=Vehicle.Tier.DIRECT,
            demand=Vehicle.Demand.LOW,
            sold_last_month=0,
            is_approved=settings.AUTO_APPROVE_LISTINGS,
            **validated,
        )
        self._sync_highlights(
            vehicle,
            highlights if highlights is not None else ["Seller-listed", "Posted via SriBalajiBikes"],
        )
        if images:
            self._add_images(vehicle, images)
        return vehicle

    def update(self, instance, validated):
        highlights = validated.pop("highlights", None)
        images = validated.pop("images", [])

        for field, value in validated.items():
            setattr(instance, field, value)
        # Price changes must flow through to the quoted EMI.
        instance.emi = instance.calculate_emi()
        instance.save()

        if highlights is not None:
            self._sync_highlights(instance, highlights)
        if images:
            self._add_images(instance, images)
        return instance

    def to_representation(self, instance):
        return VehicleDetailSerializer(instance, context=self.context).data


# --------------------------------------------------------------------------
# Favourites
# --------------------------------------------------------------------------


class FavoriteSerializer(serializers.ModelSerializer):
    vehicle = VehicleListSerializer(read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Favorite
        fields = ["id", "vehicle", "createdAt"]


# --------------------------------------------------------------------------
# Valuation
# --------------------------------------------------------------------------


class ValuationSerializer(serializers.Serializer):
    """Input for POST /api/valuation/ — the instant-estimate widget."""

    brand = serializers.CharField(max_length=60)
    type = serializers.ChoiceField(choices=Vehicle.VehicleType.choices)
    modelYear = serializers.IntegerField(min_value=1980)
    km = serializers.IntegerField(min_value=0, max_value=500_000)
    owners = serializers.ChoiceField(choices=Vehicle.Owners.choices)
    fuel = serializers.ChoiceField(
        choices=Vehicle.Fuel.choices, required=False, default="Petrol"
    )
    condition = serializers.ChoiceField(
        choices=["excellent", "good", "fair", "poor"],
        required=False,
        default="good",
    )

    def validate_modelYear(self, value):
        from datetime import date

        current = date.today().year
        if value > current:
            raise serializers.ValidationError(
                f"Model year cannot be later than {current}."
            )
        return value

    def estimate(self):
        data = self.validated_data
        return estimate_price(
            brand=data["brand"],
            vehicle_type=data["type"],
            model_year=data["modelYear"],
            km=data["km"],
            owners=data["owners"],
            fuel=data.get("fuel", "Petrol"),
            condition=data.get("condition", "good"),
        )


# --------------------------------------------------------------------------
# Site content
# --------------------------------------------------------------------------


class ServicePackageItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePackageItem
        fields = ["id", "text"]


class ServicePackageSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    isHighlighted = serializers.BooleanField(source="is_highlighted", read_only=True)
    priceLabel = serializers.SerializerMethodField()

    class Meta:
        model = ServicePackage
        fields = [
            "id", "code", "name", "price", "priceLabel", "description",
            "items", "isHighlighted",
        ]

    def get_items(self, obj):
        return [item.text for item in obj.items.all()]

    def get_priceLabel(self, obj):
        return f"\u20b9{obj.price:,}"


class FAQSerializer(serializers.ModelSerializer):
    q = serializers.CharField(source="question", read_only=True)
    a = serializers.CharField(source="answer", read_only=True)

    class Meta:
        model = FAQ
        fields = ["id", "q", "a"]


class TestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = ["id", "name", "location", "quote"]


class SiteStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteStat
        fields = ["id", "value", "label"]
