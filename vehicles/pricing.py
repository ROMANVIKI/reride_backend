"""
Price-estimation engine for used two-wheelers.

This is the server-side home of the logic that previously lived in the
frontend's `lib/pricing.ts`. Keeping it here means the estimate a seller is
shown, the suggested price on the post-an-ad form, and the number stored
against a sell lead all come from one place and can be tuned without a
frontend deploy.

It is deliberately simple and explainable: a brand baseline, then
multiplicative factors for age, usage and ownership history.
"""

from datetime import date

# Approximate ex-showroom price by brand, used as the "new" baseline (INR).
BRAND_BASE_PRICE = {
    "Honda": 85000,
    "TVS": 88000,
    "Suzuki": 92000,
    "Yamaha": 90000,
    "Hero": 78000,
    "Royal Enfield": 195000,
    "Bajaj": 110000,
    "KTM": 210000,
    "Ather": 145000,
    "Ola": 130000,
}

TYPE_DEFAULT_BASE_PRICE = {
    "Scooter": 88000,
    "Motorcycle": 115000,
}

OWNER_FACTOR = {
    "1st owner": 1.0,
    "2nd owner": 0.92,
    "3rd owner or more": 0.83,
}

# An electric two-wheeler loses value faster than petrol, mostly on battery
# health, so it carries an extra haircut.
FUEL_FACTOR = {
    "Petrol": 1.0,
    "Electric": 0.93,
}


def age_factor(age_years):
    """
    Depreciation curve: roughly 10% in year one, then ~7% per subsequent
    year, floored so age alone never drops a vehicle below 30% of base.
    """
    clamped = max(0, int(age_years))
    factor = 1.0
    for year_index in range(clamped):
        factor *= 0.90 if year_index == 0 else 0.93
    return max(factor, 0.30)


def km_factor(km, age_years):
    """
    Usage penalty. Under 8,000 km per year of age counts as low usage and
    earns a small bonus; above that, every extra 10,000 km costs ~2.5%,
    capped at a 35% total reduction.
    """
    expected_km = max(age_years, 1) * 8000
    excess_km = max(0, km - expected_km)
    penalty = min(0.35, (excess_km / 10000) * 0.025)
    low_usage_bonus = 0.03 if km < expected_km * 0.6 else 0.0
    return max(0.60, 1 - penalty + low_usage_bonus)


def condition_factor(condition):
    """Optional self-reported condition, applied when the caller supplies it."""
    return {
        "excellent": 1.05,
        "good": 1.0,
        "fair": 0.92,
        "poor": 0.82,
    }.get((condition or "good").lower(), 1.0)


def estimate_price(
    brand,
    vehicle_type,
    model_year,
    km,
    owners,
    fuel="Petrol",
    condition="good",
):
    """
    Return a dict with a low/mid/high band plus the factors that produced
    it, so the UI can explain the number rather than just assert it.
    """
    current_year = date.today().year
    age_years = max(0, current_year - int(model_year))

    base = BRAND_BASE_PRICE.get(
        brand, TYPE_DEFAULT_BASE_PRICE.get(vehicle_type, 95000)
    )

    af = age_factor(age_years)
    kf = km_factor(int(km), age_years)
    of = OWNER_FACTOR.get(owners, 0.85)
    ff = FUEL_FACTOR.get(fuel, 1.0)
    cf = condition_factor(condition)

    raw = base * af * kf * of * ff * cf

    # Round to the nearest 500 and give a +/-5% band.
    mid = int(round(raw / 500) * 500)
    low = int(round(mid * 0.95 / 500) * 500)
    high = int(round(mid * 1.05 / 500) * 500)

    return {
        "low": low,
        "mid": mid,
        "high": high,
        "base": base,
        "ageYears": age_years,
        "factors": {
            "age": round(af, 4),
            "km": round(kf, 4),
            "owners": round(of, 4),
            "fuel": round(ff, 4),
            "condition": round(cf, 4),
        },
        "explanation": (
            f"Starting from an approximate new price of Rs {base:,} for a {brand} "
            f"{vehicle_type.lower()}, adjusted for {age_years} year(s) of age, "
            f"{int(km):,} km run and {owners}."
        ),
    }
