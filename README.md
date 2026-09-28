# SriBalajiBikes — Backend API

Django 6 + Django REST Framework. JWT auth with e-mail OTP verification.
See the root `README.md` for the full API reference and deployment guide.

## Run

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data --with-user
python manage.py runserver
```

Visit `http://localhost:8000/` for a live map of every endpoint.

Demo account: `demo@sribalajibikes.com` / `Demo@12345`

## Apps

| App | Responsibility |
|---|---|
| `accounts` | Custom e-mail user model, OTP issue/verify, JWT, passwords |
| `vehicles` | Listings, images, favourites, valuation engine, site content |
| `leads` | Sell enquiries, contact, service bookings, test rides, reservations |

## E-mail in development

The console backend prints OTPs to this terminal. While `DEBUG=True` the API
also returns the code as `debugCode` so you can register without SMTP.
Set `OTP_DEBUG_IN_RESPONSE=False` before deploying — see the root README.

## Tests

```bash
python manage.py test
```

## Config

Copy `.env.example` to `.env`. All values have working local defaults.
# reride_backend
