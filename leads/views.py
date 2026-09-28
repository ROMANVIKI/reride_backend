from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.emails import notify_team

from .models import (
    ContactMessage,
    Reservation,
    SellLead,
    ServiceBooking,
    TestRideBooking,
)
from .serializers import (
    ContactMessageSerializer,
    ReservationSerializer,
    SellLeadSerializer,
    ServiceBookingSerializer,
    TestRideBookingSerializer,
)


class PublicCreateMixin:
    """
    A lead endpoint: anyone may submit, but only the person who submitted it
    (signed in) can list their own history back.
    """

    permission_classes = [AllowAny]
    filter_backends = []
    notify_subject = "New lead"

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.none()
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(user=user)

    def perform_create(self, serializer):
        instance = serializer.save()
        notify_team(self.notify_subject, str(instance))
        return instance


class SellLeadViewSet(
    PublicCreateMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST /api/leads/sell/        submit a sell enquiry (public)
    GET  /api/leads/sell/        your own enquiries        [auth]
    GET  /api/leads/sell/{id}/   one enquiry               [auth]
    """

    queryset = SellLead.objects.all()
    serializer_class = SellLeadSerializer
    notify_subject = "New sell enquiry"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        return Response(
            {
                **serializer.data,
                "detail": (
                    "Thanks — we'll call you within one working day to book a "
                    "free inspection."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ContactMessageViewSet(
    PublicCreateMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """POST /api/leads/contact/ — the contact form and listing enquiries."""

    queryset = ContactMessage.objects.select_related("vehicle")
    serializer_class = ContactMessageSerializer
    notify_subject = "New contact message"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                **serializer.data,
                "detail": "Message received. We usually reply within a working day.",
            },
            status=status.HTTP_201_CREATED,
        )


class ServiceBookingViewSet(
    PublicCreateMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST   /api/leads/service-bookings/        book a service package
    GET    /api/leads/service-bookings/        your bookings        [auth]
    PATCH  /api/leads/service-bookings/{id}/   reschedule/cancel    [auth]
    """

    queryset = ServiceBooking.objects.select_related("package", "store")
    serializer_class = ServiceBookingSerializer
    notify_subject = "New service booking"

    def get_permissions(self):
        if self.action in ("list", "retrieve", "update", "partial_update"):
            return [IsAuthenticated()]
        return [AllowAny()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                **serializer.data,
                "detail": "Booking requested. We'll confirm your slot by phone shortly.",
            },
            status=status.HTTP_201_CREATED,
        )


class TestRideBookingViewSet(
    PublicCreateMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """POST /api/leads/test-rides/ — book a test ride on a listing."""

    queryset = TestRideBooking.objects.select_related("vehicle").prefetch_related(
        "vehicle__images"
    )
    serializer_class = TestRideBookingSerializer
    notify_subject = "New test ride request"

    def get_permissions(self):
        if self.action in ("list", "retrieve", "update", "partial_update"):
            return [IsAuthenticated()]
        return [AllowAny()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                **serializer.data,
                "detail": "Test ride requested. We'll confirm the time with you shortly.",
            },
            status=status.HTTP_201_CREATED,
        )


class ReservationViewSet(
    PublicCreateMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST /api/leads/reservations/   hold a vehicle against a token amount [auth]
    GET  /api/leads/reservations/   your reservations                     [auth]
    """

    queryset = Reservation.objects.select_related("vehicle").prefetch_related(
        "vehicle__images"
    )
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    notify_subject = "New reservation"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        return Response(
            {
                **self.get_serializer(instance).data,
                "detail": (
                    f"Reserved. Pay \u20b9{instance.amount:,} to confirm — our team "
                    f"will share payment details on {instance.phone}."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class MyActivityView(generics.GenericAPIView):
    """
    GET /api/leads/my-activity/

    One call that powers the dashboard: everything the signed-in user has
    submitted, plus counts.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        context = {"request": request}
        user = request.user

        sell_leads = SellLead.objects.filter(user=user)[:20]
        test_rides = TestRideBooking.objects.filter(user=user).select_related(
            "vehicle"
        )[:20]
        reservations = Reservation.objects.filter(user=user).select_related(
            "vehicle"
        )[:20]
        bookings = ServiceBooking.objects.filter(user=user).select_related("package")[:20]
        messages = ContactMessage.objects.filter(user=user)[:20]

        return Response(
            {
                "sellLeads": SellLeadSerializer(sell_leads, many=True, context=context).data,
                "testRides": TestRideBookingSerializer(test_rides, many=True, context=context).data,
                "reservations": ReservationSerializer(reservations, many=True, context=context).data,
                "serviceBookings": ServiceBookingSerializer(bookings, many=True, context=context).data,
                "messages": ContactMessageSerializer(messages, many=True, context=context).data,
                "counts": {
                    "sellLeads": SellLead.objects.filter(user=user).count(),
                    "testRides": TestRideBooking.objects.filter(user=user).count(),
                    "reservations": Reservation.objects.filter(user=user).count(),
                    "serviceBookings": ServiceBooking.objects.filter(user=user).count(),
                    "messages": ContactMessage.objects.filter(user=user).count(),
                },
            }
        )
