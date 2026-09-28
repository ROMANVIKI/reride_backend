import django_filters
from django.db.models import F, Q

from .models import Vehicle


class CommaSeparatedFilter(django_filters.CharFilter):
    """
    Accepts either `?brand=Honda` or `?brand=Honda,TVS`, matching the
    frontend's multi-select checkbox filters.
    """

    def __init__(self, *args, field=None, **kwargs):
        self.target_field = field
        super().__init__(*args, **kwargs)

    def filter(self, queryset, value):
        if not value:
            return queryset
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            return queryset
        return queryset.filter(**{f"{self.target_field}__in": values})


class VehicleFilter(django_filters.FilterSet):
    """
    Query parameters for /api/vehicles/:

        ?type=Scooter
        &tier=Certified,Verified
        &brand=Honda,TVS
        &min_price=30000&max_price=150000
        &max_km=20000&min_year=2019
        &owners=1st owner
        &warranty=true&free_service=true
        &city=Bengaluru
        &search=activa
        &ordering=price | -price | km | -km | year | -year | created_at | -created_at
    """

    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    min_km = django_filters.NumberFilter(field_name="km", lookup_expr="gte")
    max_km = django_filters.NumberFilter(field_name="km", lookup_expr="lte")
    min_year = django_filters.NumberFilter(field_name="year", lookup_expr="gte")
    max_year = django_filters.NumberFilter(field_name="year", lookup_expr="lte")

    brand = CommaSeparatedFilter(field="brand")
    tier = CommaSeparatedFilter(field="tier")
    owners = CommaSeparatedFilter(field="owners")
    fuel = CommaSeparatedFilter(field="fuel")
    demand = CommaSeparatedFilter(field="demand")

    type = django_filters.CharFilter(field_name="type", lookup_expr="iexact")
    city = django_filters.CharFilter(field_name="city", lookup_expr="iexact")
    area = django_filters.CharFilter(field_name="area", lookup_expr="icontains")

    warranty = django_filters.BooleanFilter(field_name="warranty")
    free_service = django_filters.BooleanFilter(field_name="free_service")
    discounted = django_filters.BooleanFilter(method="filter_discounted")

    ordering = django_filters.OrderingFilter(
        fields=(
            ("price", "price"),
            ("km", "km"),
            ("year", "year"),
            ("created_at", "created_at"),
            ("views_count", "views"),
        ),
    )

    class Meta:
        model = Vehicle
        fields = ["brand", "city", "type", "tier", "owners", "fuel", "status"]

    def filter_discounted(self, queryset, name, value):
        """Listings whose original price is genuinely above the asking price."""
        if value is None:
            return queryset
        discounted = Q(original_price__isnull=False) & Q(original_price__gt=F("price"))
        return queryset.filter(discounted) if value else queryset.exclude(discounted)
