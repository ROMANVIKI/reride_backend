from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContactMessageViewSet,
    MyActivityView,
    ReservationViewSet,
    SellLeadViewSet,
    ServiceBookingViewSet,
    TestRideBookingViewSet,
)

router = DefaultRouter()
router.register("sell", SellLeadViewSet, basename="lead-sell")
router.register("contact", ContactMessageViewSet, basename="lead-contact")
router.register("service-bookings", ServiceBookingViewSet, basename="lead-service-booking")
router.register("test-rides", TestRideBookingViewSet, basename="lead-test-ride")
router.register("reservations", ReservationViewSet, basename="lead-reservation")

urlpatterns = [
    path("my-activity/", MyActivityView.as_view(), name="lead-my-activity"),
    path("", include(router.urls)),
]
