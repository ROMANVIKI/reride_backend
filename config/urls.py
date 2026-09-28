"""Root URL configuration for the SriBalajiBikes API."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def api_root(request):
    """A map of the public API, handy while wiring up the frontend."""
    return JsonResponse(
        {
            "service": "SriBalajiBikes API",
            "version": "1.0",
            "auth": {
                "register": "/api/auth/register/",
                "verifyOtp": "/api/auth/verify-otp/",
                "resendOtp": "/api/auth/resend-otp/",
                "login": "/api/auth/login/",
                "refresh": "/api/auth/refresh/",
                "logout": "/api/auth/logout/",
                "me": "/api/auth/me/",
                "forgotPassword": "/api/auth/password/forgot/",
                "resetPassword": "/api/auth/password/reset/",
                "changePassword": "/api/auth/password/change/",
            },
            "catalogue": {
                "vehicles": "/api/vehicles/",
                "vehicleDetail": "/api/vehicles/{slug}/",
                "myListings": "/api/vehicles/mine/",
                "facets": "/api/vehicles/facets/",
                "similar": "/api/vehicles/{slug}/similar/",
                "toggleFavorite": "/api/vehicles/{slug}/favorite/",
                "favorites": "/api/favorites/",
                "valuation": "/api/valuation/",
                "servicePackages": "/api/service-packages/",
                "faqs": "/api/faqs/",
                "testimonials": "/api/testimonials/",
                "stats": "/api/stats/",
                "stores": "/api/stores/",
            },
            "leads": {
                "sell": "/api/leads/sell/",
                "contact": "/api/leads/contact/",
                "serviceBookings": "/api/leads/service-bookings/",
                "testRides": "/api/leads/test-rides/",
                "reservations": "/api/leads/reservations/",
                "myActivity": "/api/leads/my-activity/",
            },
            "admin": "/admin/",
            "health": "/api/health/",
        }
    )


urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/leads/", include("leads.urls")),
    path("api/", include("vehicles.urls")),
    path("api-auth/", include("rest_framework.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "SriBalajiBikes administration"
admin.site.site_title = "SriBalajiBikes"
admin.site.index_title = "Marketplace operations"
