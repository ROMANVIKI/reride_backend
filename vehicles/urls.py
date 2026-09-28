from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    FAQListView,
    FavoriteListView,
    ServicePackageListView,
    SiteStatListView,
    StoreListView,
    TestimonialListView,
    ValuationView,
    VehicleViewSet,
    health,
)

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="vehicle")

urlpatterns = [
    path("", include(router.urls)),
    path("favorites/", FavoriteListView.as_view(), name="favorite-list"),
    path("valuation/", ValuationView.as_view(), name="valuation"),
    path("stores/", StoreListView.as_view(), name="store-list"),
    path("faqs/", FAQListView.as_view(), name="faq-list"),
    path("testimonials/", TestimonialListView.as_view(), name="testimonial-list"),
    path("service-packages/", ServicePackageListView.as_view(), name="service-package-list"),
    path("stats/", SiteStatListView.as_view(), name="site-stat-list"),
    path("health/", health, name="health"),
]
