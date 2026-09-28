from django.db.models import Count, F, Max, Min, Q
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    FAQ,
    Favorite,
    ServicePackage,
    SiteStat,
    Store,
    Testimonial,
    Vehicle,
    VehicleImage,
)
from .filters import VehicleFilter
from .serializers import (
    FAQSerializer,
    FavoriteSerializer,
    ServicePackageSerializer,
    SiteStatSerializer,
    StoreSerializer,
    TestimonialSerializer,
    ValuationSerializer,
    VehicleDetailSerializer,
    VehicleListSerializer,
    VehicleWriteSerializer,
)


class IsSellerOrReadOnly(BasePermission):
    """Anyone may read a listing; only its seller (or staff) may change it."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        return obj.seller_id == request.user.id


class VehicleViewSet(viewsets.ModelViewSet):
    """
    GET    /api/vehicles/              list published listings (filterable)
    POST   /api/vehicles/              create a listing            [auth]
    GET    /api/vehicles/{slug}/       listing detail
    PATCH  /api/vehicles/{slug}/       update own listing          [owner]
    DELETE /api/vehicles/{slug}/       delete own listing          [owner]
    GET    /api/vehicles/mine/         the signed-in user's listings  [auth]
    GET    /api/vehicles/facets/       filter options for the sidebar
    GET    /api/vehicles/{slug}/similar/   related listings
    POST   /api/vehicles/{slug}/favorite/  toggle favourite        [auth]
    POST   /api/vehicles/{slug}/images/    add photos              [owner]
    DELETE /api/vehicles/{slug}/images/{id}/  remove a photo       [owner]
    """

    lookup_field = "slug"
    permission_classes = [IsSellerOrReadOnly]
    filterset_class = VehicleFilter
    search_fields = ["brand", "model_name", "variant", "area", "city", "description"]
    ordering_fields = ["price", "km", "year", "created_at"]
    ordering = ["-created_at"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        base = Vehicle.objects.with_relations()

        user = self.request.user

        if self.action == "mine":
            return base.filter(seller=user)

        # The owner and staff can always reach a listing by slug, even while
        # it's unapproved or already sold.
        if self.action in (
            "retrieve", "update", "partial_update", "destroy",
            "add_images", "delete_image", "favorite", "similar",
        ):
            if user.is_authenticated:
                if user.is_staff:
                    return base
                return base.filter(Q(is_approved=True) | Q(seller=user))
            return base.filter(is_approved=True)

        return base.published()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return VehicleWriteSerializer
        if self.action in ("retrieve",):
            return VehicleDetailSerializer
        return VehicleListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        if user.is_authenticated:
            # One query for the whole page instead of one per card.
            context["favorite_ids"] = set(
                Favorite.objects.filter(user=user).values_list("vehicle_id", flat=True)
            )
        return context

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Cheap, race-free view counter that doesn't touch updated_at.
        Vehicle.objects.filter(pk=instance.pk).update(
            views_count=F("views_count") + 1
        )
        instance.refresh_from_db(fields=["views_count"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        # Listings with enquiries attached are archived rather than removed,
        # so the lead history stays intact.
        if instance.test_ride_bookings.exists() or instance.reservations.exists():
            instance.is_approved = False
            instance.status = Vehicle.Status.SOLD
            instance.save(update_fields=["is_approved", "status", "updated_at"])
        else:
            instance.delete()

    # -- extra routes -----------------------------------------------------

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def mine(self, request):
        """Every listing the signed-in user has posted, any status."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = VehicleListSerializer(
            page if page is not None else queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def facets(self, request):
        """Filter sidebar options, derived from what's actually in stock."""
        queryset = Vehicle.objects.published()
        bounds = queryset.aggregate(
            minPrice=Min("price"),
            maxPrice=Max("price"),
            minYear=Min("year"),
            maxYear=Max("year"),
            maxKm=Max("km"),
        )
        return Response(
            {
                "brands": list(
                    queryset.values_list("brand", flat=True).distinct().order_by("brand")
                ),
                "cities": list(
                    queryset.values_list("city", flat=True).distinct().order_by("city")
                ),
                "areas": list(
                    queryset.exclude(area="")
                    .values_list("area", flat=True)
                    .distinct()
                    .order_by("area")
                ),
                "types": [c[0] for c in Vehicle.VehicleType.choices],
                "tiers": [c[0] for c in Vehicle.Tier.choices],
                "owners": [c[0] for c in Vehicle.Owners.choices],
                "fuels": [c[0] for c in Vehicle.Fuel.choices],
                "priceRange": {
                    "min": bounds["minPrice"] or 30000,
                    "max": bounds["maxPrice"] or 200000,
                },
                "yearRange": {
                    "min": bounds["minYear"] or 2010,
                    "max": bounds["maxYear"] or 2026,
                },
                "maxKm": bounds["maxKm"] or 100000,
                "total": queryset.count(),
                "byTier": list(
                    queryset.values("tier").annotate(count=Count("id")).order_by("tier")
                ),
            }
        )

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def similar(self, request, slug=None):
        """Same body type, close in price — used by the detail page."""
        vehicle = self.get_object()
        candidates = (
            Vehicle.objects.published()
            .with_relations()
            .filter(type=vehicle.type)
            .exclude(pk=vehicle.pk)
            .order_by("-created_at")[:24]
        )
        near = sorted(candidates, key=lambda v: abs(v.price - vehicle.price))[:3]
        return Response(
            VehicleListSerializer(
                near, many=True, context=self.get_serializer_context()
            ).data
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def favorite(self, request, slug=None):
        """Toggle this listing in the user's shortlist."""
        vehicle = self.get_object()
        existing = Favorite.objects.filter(user=request.user, vehicle=vehicle).first()
        if existing:
            existing.delete()
            return Response({"isFavorite": False, "detail": "Removed from favourites."})
        Favorite.objects.create(user=request.user, vehicle=vehicle)
        return Response({"isFavorite": True, "detail": "Saved to favourites."})

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser],
        url_path="images",
    )
    def add_images(self, request, slug=None):
        """Attach one or more photos to a listing the caller owns."""
        vehicle = self.get_object()
        self.check_object_permissions(request, vehicle)

        files = request.FILES.getlist("images") or request.FILES.getlist("image")
        if not files:
            return Response(
                {"detail": "No image files were provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if vehicle.images.count() + len(files) > 8:
            return Response(
                {"detail": "A listing can have at most 8 photos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        has_primary = vehicle.images.filter(is_primary=True).exists()
        start = vehicle.images.count()
        for index, uploaded in enumerate(files):
            VehicleImage.objects.create(
                vehicle=vehicle,
                image=uploaded,
                order=start + index,
                is_primary=(not has_primary and index == 0),
            )

        return Response(
            VehicleDetailSerializer(
                vehicle, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        permission_classes=[IsAuthenticated],
        url_path=r"images/(?P<image_id>[0-9]+)",
    )
    def delete_image(self, request, slug=None, image_id=None):
        vehicle = self.get_object()
        self.check_object_permissions(request, vehicle)

        image = vehicle.images.filter(pk=image_id).first()
        if not image:
            return Response(
                {"detail": "Photo not found."}, status=status.HTTP_404_NOT_FOUND
            )
        was_primary = image.is_primary
        image.delete()
        if was_primary:
            replacement = vehicle.images.first()
            if replacement:
                replacement.is_primary = True
                replacement.save(update_fields=["is_primary"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class FavoriteListView(generics.ListAPIView):
    """GET /api/favorites/ — the signed-in user's saved listings."""

    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = []

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related(
            "vehicle"
        ).prefetch_related("vehicle__images", "vehicle__highlights")


class ValuationView(APIView):
    """
    POST /api/valuation/

    Instant price estimate for a two-wheeler. Powers the Sell page widget
    and the suggested price on the post-an-ad form.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ValuationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.estimate())


class StoreListView(generics.ListAPIView):
    queryset = Store.objects.filter(is_active=True)
    serializer_class = StoreSerializer
    filter_backends = []


class FAQListView(generics.ListAPIView):
    queryset = FAQ.objects.filter(is_active=True)
    serializer_class = FAQSerializer
    pagination_class = None
    filter_backends = []


class TestimonialListView(generics.ListAPIView):
    queryset = Testimonial.objects.filter(is_active=True)
    serializer_class = TestimonialSerializer
    pagination_class = None
    filter_backends = []


class ServicePackageListView(generics.ListAPIView):
    queryset = ServicePackage.objects.filter(is_active=True).prefetch_related("items")
    serializer_class = ServicePackageSerializer
    pagination_class = None
    filter_backends = []


class SiteStatListView(generics.ListAPIView):
    queryset = SiteStat.objects.filter(is_active=True)
    serializer_class = SiteStatSerializer
    pagination_class = None
    filter_backends = []


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Lightweight readiness probe for your host's health checks."""
    return Response({"status": "ok", "service": "sribalajibikes-api"})
