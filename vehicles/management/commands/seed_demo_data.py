"""
Populate the database with the catalogue the frontend used to hardcode.

Everything here previously lived in the Next.js app's `lib/data.ts`. Moving
it into the database is what lets the frontend drop its static arrays.

    python manage.py seed_demo_data
    python manage.py seed_demo_data --flush     # wipe catalogue first
    python manage.py seed_demo_data --with-user # also create a demo login
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from vehicles.models import (
    FAQ,
    ServicePackage,
    ServicePackageItem,
    SiteStat,
    Store,
    Testimonial,
    Vehicle,
    VehicleHighlight,
)

User = get_user_model()


STORES = [
    {
        "name": "SriBalajiBikes RR Nagar",
        "area": "RR Nagar",
        "city": "Bengaluru",
        "address": "24, Ideal Homes Township, RR Nagar, Bengaluru 560098",
        "phone": "+91 12-4718-2200",
        "latitude": "12.921900",
        "longitude": "77.518600",
    },
    {
        "name": "SriBalajiBikes Indiranagar",
        "area": "Indiranagar",
        "city": "Bengaluru",
        "address": "100 Feet Road, Indiranagar, Bengaluru 560038",
        "phone": "+91 12-4718-2201",
        "latitude": "12.971800",
        "longitude": "77.641200",
    },
    {
        "name": "SriBalajiBikes Electronic City",
        "area": "Electronic City",
        "city": "Bengaluru",
        "address": "Phase 1, Electronic City, Bengaluru 560100",
        "phone": "+91 12-4718-2202",
        "latitude": "12.845000",
        "longitude": "77.660600",
    },
]


VEHICLES = [
    {
        "slug": "honda-activa-6g-2021-rr-nagar",
        "brand": "Honda", "model_name": "Activa 6G", "variant": "STD",
        "type": "Scooter", "year": 2021, "km": 14446, "owners": "1st owner",
        "price": 79000, "original_price": 92000,
        "city": "Bengaluru", "area": "RR Nagar", "tier": "Certified",
        "fuel": "Petrol", "color": "Pearl White", "registration": "KA-05",
        "warranty": True, "free_service": True, "demand": "High", "sold_last_month": 38,
        "store": "SriBalajiBikes RR Nagar",
        "description": (
            "A single-owner Activa 6G that has spent its life on short city "
            "commutes. Cleared our 220-point inspection with no engine or "
            "electrical faults, and has just been through a full service."
        ),
        "highlights": [
            "220-point inspection passed",
            "Extended warranty eligible",
            "Fresh service done",
        ],
    },
    {
        "slug": "tvs-ntorq-125-2025-electronic-city",
        "brand": "TVS", "model_name": "Ntorq 125", "variant": "Race XP",
        "type": "Scooter", "year": 2025, "km": 3384, "owners": "1st owner",
        "price": 95000, "original_price": None,
        "city": "Bengaluru", "area": "Electronic City", "tier": "Certified",
        "fuel": "Petrol", "color": "Matte Black", "registration": "KA-01",
        "warranty": True, "free_service": True, "demand": "High", "sold_last_month": 41,
        "store": "SriBalajiBikes Electronic City",
        "description": (
            "Barely run Race XP with the Bluetooth cluster fully functional. "
            "Still inside the manufacturer warranty window."
        ),
        "highlights": [
            "Near-new condition",
            "Bluetooth cluster intact",
            "Single key available",
        ],
    },
    {
        "slug": "suzuki-access-125-2025-kasturi-nagar",
        "brand": "Suzuki", "model_name": "Access 125", "variant": "Standard",
        "type": "Scooter", "year": 2025, "km": 7445, "owners": "1st owner",
        "price": 94000, "original_price": None,
        "city": "Bengaluru", "area": "Kasturi Nagar", "tier": "Certified",
        "fuel": "Petrol", "color": "Metallic Grey", "registration": "KA-04",
        "warranty": True, "free_service": True, "demand": "Moderate", "sold_last_month": 22,
        "store": "SriBalajiBikes Indiranagar",
        "description": "Low-usage Access 125 still under manufacturer warranty, on original tyres.",
        "highlights": [
            "Under manufacturer warranty",
            "Single owner, low usage",
            "Original tyres",
        ],
    },
    {
        "slug": "yamaha-fascino-110-2018-indiranagar",
        "brand": "Yamaha", "model_name": "Fascino 110", "variant": "STD",
        "type": "Scooter", "year": 2018, "km": 22411, "owners": "1st owner",
        "price": 65000, "original_price": 78000,
        "city": "Bengaluru", "area": "Indiranagar", "tier": "Certified",
        "fuel": "Petrol", "color": "Cherry Red", "registration": "KA-04",
        "warranty": True, "free_service": True, "demand": "Moderate", "sold_last_month": 17,
        "store": "SriBalajiBikes Indiranagar",
        "description": (
            "Refurbished in-house: panels repainted to the original shade and a "
            "new battery fitted. Full service history available."
        ),
        "highlights": [
            "Repainted panels",
            "New battery fitted",
            "Service records available",
        ],
    },
    {
        "slug": "honda-dio-125-2024-electronic-city",
        "brand": "Honda", "model_name": "Dio 125", "variant": "DLX",
        "type": "Scooter", "year": 2024, "km": 12807, "owners": "1st owner",
        "price": 90000, "original_price": None,
        "city": "Bengaluru", "area": "Electronic City", "tier": "Verified",
        "fuel": "Petrol", "color": "Sports Red", "registration": "KA-01",
        "warranty": False, "free_service": True, "demand": "High", "sold_last_month": 29,
        "store": "SriBalajiBikes Electronic City",
        "description": "Seller-owned Dio 125 that has passed our document and condition check.",
        "highlights": [
            "Seller-listed, RTO checked",
            "Basic quality assessment passed",
            "Test ride available",
        ],
    },
    {
        "slug": "tvs-jupiter-110-2018-rr-nagar",
        "brand": "TVS", "model_name": "Jupiter 110", "variant": "STD",
        "type": "Scooter", "year": 2018, "km": 23464, "owners": "1st owner",
        "price": 63000, "original_price": 71000,
        "city": "Bengaluru", "area": "RR Nagar", "tier": "Certified",
        "fuel": "Petrol", "color": "Titanium Grey", "registration": "KA-05",
        "warranty": True, "free_service": True, "demand": "Moderate", "sold_last_month": 19,
        "store": "SriBalajiBikes RR Nagar",
        "description": "Suspension refurbished and new brake pads fitted before listing.",
        "highlights": [
            "Refurbished suspension",
            "New brake pads",
            "1-year warranty included",
        ],
    },
    {
        "slug": "royal-enfield-classic-350-2020-marathahalli",
        "brand": "Royal Enfield", "model_name": "Classic 350", "variant": "Chrome",
        "type": "Motorcycle", "year": 2020, "km": 18230, "owners": "1st owner",
        "price": 132000, "original_price": None,
        "city": "Bengaluru", "area": "Marathahalli", "tier": "Certified",
        "fuel": "Petrol", "color": "Chrome Black", "registration": "KA-03",
        "warranty": True, "free_service": True, "demand": "High", "sold_last_month": 31,
        "store": "SriBalajiBikes Indiranagar",
        "description": (
            "Genuine chrome kit, top-end serviced by our workshop, and all "
            "documents verified against the RTO record."
        ),
        "highlights": [
            "Genuine chrome kit",
            "Engine top-end serviced",
            "Documents verified",
        ],
    },
    {
        "slug": "bajaj-pulsar-150-2019-btm",
        "brand": "Bajaj", "model_name": "Pulsar 150", "variant": "Twin Disc",
        "type": "Motorcycle", "year": 2019, "km": 27650, "owners": "2nd owner",
        "price": 71000, "original_price": 84000,
        "city": "Bengaluru", "area": "BTM Layout", "tier": "Verified",
        "fuel": "Petrol", "color": "Racing Blue", "registration": "KA-41",
        "warranty": False, "free_service": True, "demand": "Moderate", "sold_last_month": 14,
        "store": None,
        "description": "Twin-disc Pulsar listed by its owner, with clear RTO paperwork.",
        "highlights": ["Twin-disc variant", "Owner-listed", "RTO papers clear"],
    },
    {
        "slug": "hero-splendor-plus-2017-nagarbhavi",
        "brand": "Hero", "model_name": "Splendor Plus", "variant": "STD",
        "type": "Motorcycle", "year": 2017, "km": 31200, "owners": "2nd owner",
        "price": 42000, "original_price": None,
        "city": "Bengaluru", "area": "Nagarbhavi", "tier": "Direct",
        "fuel": "Petrol", "color": "Black & Red", "registration": "KA-02",
        "warranty": False, "free_service": False, "demand": "Low", "sold_last_month": 6,
        "store": None,
        "description": "Owner-priced commuter, negotiable. Basic checks only — inspect carefully.",
        "highlights": ["Priced by owner", "Negotiable", "Basic checks done"],
    },
]


FAQS = [
    (
        "What checks does a Certified vehicle go through?",
        "Every Certified listing clears a 220-point inspection covering engine "
        "health, brakes, electricals, frame condition and paperwork before it's "
        "refurbished and priced.",
    ),
    (
        "What's the difference between Certified, Verified and Direct?",
        "Certified vehicles are inspected and refurbished by SriBalajiBikes with "
        "a warranty. Verified means the seller's vehicle passed a basic check and "
        "document review. Direct means you deal with the owner directly at their "
        "listed price.",
    ),
    (
        "Does SriBalajiBikes handle the RC transfer?",
        "Yes, for Certified and Verified purchases we manage the paperwork end to "
        "end, including RC transfer and insurance continuation.",
    ),
    (
        "Is a test ride possible before I buy?",
        "Yes. You can book a test ride from any listing page, or for Direct "
        "listings we coordinate a time directly with the seller.",
    ),
    (
        "What if the vehicle develops a fault after purchase?",
        "Certified purchases include a limited warranty on major components and "
        "two free services. Verified and Direct listings can add optional "
        "protection plans at checkout.",
    ),
    (
        "Do I need an account to browse or buy?",
        "Browsing is open to everyone. You need a verified account to post an ad, "
        "save favourites, book a test ride or reserve a vehicle.",
    ),
]


TESTIMONIALS = [
    (
        "Ananya R.",
        "Indiranagar, Bengaluru",
        "Picked up a Ntorq for my daughter within a week. The inspection report "
        "matched exactly what we saw in person.",
    ),
    (
        "Suresh K.",
        "Electronic City, Bengaluru",
        "Sold my old Activa in three days. Fair valuation, and the payment cleared "
        "before I'd even handed over the keys.",
    ),
    (
        "Divya M.",
        "RR Nagar, Bengaluru",
        "First time buying a used bike and I was nervous about being cheated. The "
        "paperwork support made it painless.",
    ),
]


SERVICE_PACKAGES = [
    {
        "code": "basic",
        "name": "Basic check-up",
        "price": 499,
        "order": 1,
        "is_highlighted": False,
        "description": "A quick health check to keep your ride smooth between full services.",
        "items": [
            "Engine oil top-up",
            "Brake inspection",
            "Chain lube & adjustment",
            "Tyre pressure check",
        ],
    },
    {
        "code": "standard",
        "name": "Standard service",
        "price": 999,
        "order": 2,
        "is_highlighted": True,
        "description": "Our most popular package — the regular service most riders need twice a year.",
        "items": [
            "Everything in Basic",
            "Oil filter replacement",
            "Battery health check",
            "Electricals inspection",
            "Wheel alignment check",
        ],
    },
    {
        "code": "full",
        "name": "Full refurbishment",
        "price": 2499,
        "order": 3,
        "is_highlighted": False,
        "description": "A complete workshop overhaul, the same one Certified stock goes through.",
        "items": [
            "Everything in Standard",
            "Carburettor / throttle body clean",
            "Suspension check",
            "Full body wash & polish",
            "30-day service warranty",
        ],
    },
]


SITE_STATS = [
    ("220+", "inspection checkpoints per vehicle"),
    ("1 yr", "warranty on Certified listings"),
    ("3 days", "average time to sell your bike"),
]


class Command(BaseCommand):
    help = "Seed the catalogue, service packages, FAQs, testimonials and stats."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing catalogue rows before seeding.",
        )
        parser.add_argument(
            "--with-user",
            action="store_true",
            help="Also create a verified demo account (demo@sribalajibikes.com / Demo@12345).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Clearing existing catalogue data...")
            Vehicle.objects.all().delete()
            Store.objects.all().delete()
            FAQ.objects.all().delete()
            Testimonial.objects.all().delete()
            ServicePackage.objects.all().delete()
            SiteStat.objects.all().delete()

        stores = {}
        for data in STORES:
            store, _ = Store.objects.update_or_create(
                name=data["name"], defaults=data
            )
            stores[store.name] = store
        self.stdout.write(self.style.SUCCESS(f"Stores: {len(stores)}"))

        created = 0
        for data in VEHICLES:
            payload = dict(data)
            highlights = payload.pop("highlights")
            store_name = payload.pop("store", None)
            payload["store"] = stores.get(store_name) if store_name else None
            slug = payload.pop("slug")

            vehicle, was_created = Vehicle.objects.update_or_create(
                slug=slug, defaults=payload
            )
            vehicle.highlights.all().delete()
            VehicleHighlight.objects.bulk_create(
                [
                    VehicleHighlight(vehicle=vehicle, text=text, order=index)
                    for index, text in enumerate(highlights)
                ]
            )
            created += int(was_created)
        self.stdout.write(
            self.style.SUCCESS(f"Vehicles: {len(VEHICLES)} ({created} new)")
        )

        for index, (question, answer) in enumerate(FAQS):
            FAQ.objects.update_or_create(
                question=question, defaults={"answer": answer, "order": index}
            )
        self.stdout.write(self.style.SUCCESS(f"FAQs: {len(FAQS)}"))

        for index, (name, location, quote) in enumerate(TESTIMONIALS):
            Testimonial.objects.update_or_create(
                name=name,
                defaults={"location": location, "quote": quote, "order": index},
            )
        self.stdout.write(self.style.SUCCESS(f"Testimonials: {len(TESTIMONIALS)}"))

        for data in SERVICE_PACKAGES:
            payload = dict(data)
            items = payload.pop("items")
            package, _ = ServicePackage.objects.update_or_create(
                code=payload.pop("code"), defaults=payload
            )
            package.items.all().delete()
            ServicePackageItem.objects.bulk_create(
                [
                    ServicePackageItem(package=package, text=text, order=index)
                    for index, text in enumerate(items)
                ]
            )
        self.stdout.write(
            self.style.SUCCESS(f"Service packages: {len(SERVICE_PACKAGES)}")
        )

        for index, (value, label) in enumerate(SITE_STATS):
            SiteStat.objects.update_or_create(
                value=value, defaults={"label": label, "order": index}
            )
        self.stdout.write(self.style.SUCCESS(f"Site stats: {len(SITE_STATS)}"))

        if options["with_user"]:
            email = "demo@sribalajibikes.com"
            user, was_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": "Demo Rider",
                    "phone": "9876543210",
                    "city": "Bengaluru",
                    "is_email_verified": True,
                },
            )
            user.is_email_verified = True
            user.set_password("Demo@12345")
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo account {'created' if was_created else 'updated'}: "
                    f"{email} / Demo@12345"
                )
            )

        self.stdout.write(self.style.SUCCESS("\nSeeding complete."))
