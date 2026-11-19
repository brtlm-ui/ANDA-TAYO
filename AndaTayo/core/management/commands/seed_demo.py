"""
Loads DEMO spots (the ones named in the Figma mockup) so the pages are not empty while developing.

    python manage.py seed_demo            # add the demo spots + 2 demo reviews
    python manage.py seed_demo --remove   # delete everything this command added

Notes
- Prices and hours come from the mockup. Coordinates are only APPROXIMATE (near the middle of each
  area) - fix them in /admin/ by clicking the real place on the map.
- Distance from WMSU is calculated automatically from the coordinates when a spot is saved.
- Amenities are only set where the mockup shows them (e.g. "Sockets at every desk", "85 Mbps Fiber").
- No ratings are invented: ratings on the site come from real rows in the Review table.
  The two reviews added here are the sample testimonials written in the mockup.
"""
from datetime import time
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import Amenity, Mood, Review, Spot

MARKER = '[DEMO from Figma mockup]'

# Cover photos exported from the Figma mockup (see core/demo_photos/CREDITS.md).
# File name = slugified spot name, e.g. "Library Coffee + Study" -> library-coffee-study.jpg
PHOTO_DIR = Path(__file__).resolve().parents[2] / 'demo_photos'

FOCUS, BARKADA, AESTHETIC, TIPID = 'Deep Focus', 'Barkada Energy', 'Aesthetic & Shoots', 'Tipid / Budget'

# name, category, address, area, mood, price, min_spend_note, closing, is_24h, top_pick, (lat, lng), wifi_mbps, amenity codes
SPOTS = [
    ("Seattle's Best Coffee", 'cafe', 'Campaner St., Brgy. Zone III, Zamboanga City', 'wmsu', FOCUS, 120, 'Min. spend / table', time(23), False, True, (6.9120, 122.0640), None, []),
    ('Paseo del Mar', 'food_park', 'Valderosa St., Coastal Sunset Boulevard', 'paseo', BARKADA, 50, 'Min. spend / table', time(0), False, False, (6.9040, 122.0720), None, ['outdoor']),
    ('Dennis Coffee Garden', 'cafe', 'La Purisima St., Zamboanga City', 'ateneo', AESTHETIC, 135, 'Min. spend / table', time(22), False, False, (6.9068, 122.0763), None, []),
    ('Hacienda de Palmeras Garden', 'restaurant', 'Pasonanca Road, Zamboanga City', 'other', TIPID, 110, 'Min. spend / table', time(23), False, False, (6.9300, 122.0900), None, []),
    ('Library Coffee + Study', 'study_spot', 'Nunez Extension Street, Brgy. Zone III', 'wmsu', FOCUS, 150, 'Unlimited 4-hr pass', None, True, False, (6.9128, 122.0625), None, []),
    ("Jimmy's Satti Food Haus", 'street_food', 'Pilar St., Downtown, Zamboanga City', 'other', TIPID, 50, 'Min. spend / table', time(11), False, False, (6.9060, 122.0760), None, []),
    ('Bay Tal Mal Restaurant', 'restaurant', 'SM City Mindpro, La Purisima St.', 'ateneo', BARKADA, 85, 'Min. spend / table', time(22), False, False, (6.9075, 122.0770), None, []),
    ('Taza Coffee Company', 'cafe', 'Mayor Jaldon Street, Brgy. Canelar', 'other', AESTHETIC, 95, 'Min. spend / table', time(23), False, False, (6.9150, 122.0700), None, []),
    ('Coffee Spot', 'cafe', 'San Jose Road, Zamboanga City', 'wmsu', FOCUS, 110, 'Min. spend', time(22), False, False, (6.9145, 122.0670), 85, ['wifi', 'outlets']),
    ('Canelar Alley Cafe', 'cafe', 'Canelar, Zamboanga City', 'other', FOCUS, 100, 'Min. spend / table', time(22), False, False, (6.9155, 122.0710), None, ['outlets']),
]

REVIEWS = [
    # spot, name, note, rating, comment (the sample testimonials from the mockup)
    ('Paseo del Mar', 'Bea Alcantara', 'WMSU Biology Graduate', 5,
     'Dito kami nag-celebrate nung nakapasa buong block namin sa finals. Bumili lang kami ng satti tapos '
     'tapat yung Paseo sunset. 10/10 student memory with the people.'),
    ('Canelar Alley Cafe', 'Fatima Sahir', 'WMSU CS Student', 5,
     'Corner booth table at Canelar Alley Cafe has 4 dedicated outlets and zero glare on laptop screen. '
     'Na-submit ko draft ng capstone on time! Would recommend to every thesis warrior.'),
]


class Command(BaseCommand):
    help = 'Add (or with --remove, delete) demo spots taken from the Figma mockup.'

    def add_arguments(self, parser):
        parser.add_argument('--remove', action='store_true', help='Delete the demo spots (and their reviews).')

    def handle(self, *args, **options):
        if options['remove']:
            deleted, _ = Spot.objects.filter(description__startswith=MARKER).delete()
            self.stdout.write(self.style.SUCCESS(f'Removed demo data ({deleted} rows).'))
            return

        moods = {m.name: m for m in Mood.objects.all()}
        amenities = {a.code: a for a in Amenity.objects.all()}
        missing = {FOCUS, BARKADA, AESTHETIC, TIPID} - set(moods)
        if missing:
            self.stderr.write(f'Missing moods {sorted(missing)}. Run "python manage.py migrate" first.')
            return

        created = 0
        for (name, category, address, area, mood, price, note, closing, is24, top, (lat, lng), wifi, codes) in SPOTS:
            spot, was_created = Spot.objects.get_or_create(
                name=name,
                defaults=dict(
                    category=category, address=address, area=area, mood=moods[mood],
                    starts_at_price=Decimal(price), min_spend_note=note,
                    opening_time=None if is24 else time(8), closing_time=closing, is_24_hours=is24,
                    is_top_pick=top, is_approved=True, latitude=lat, longitude=lng,
                    wifi_speed_mbps=wifi,
                    description=f'{MARKER} Edit or delete this spot in /admin/.',
                ),
            )
            if was_created:
                spot.amenities.set([amenities[c] for c in codes if c in amenities])
            created += was_created

        # Attach mockup photos to demo spots that don't have a cover photo yet (safe to re-run).
        photos = 0
        for spot in Spot.objects.filter(description__startswith=MARKER, cover_image=''):
            path = PHOTO_DIR / f'{slugify(spot.name)}.jpg'
            if path.exists():
                with path.open('rb') as fh:
                    spot.cover_image.save(path.name, File(fh), save=True)
                photos += 1

        added_reviews = 0
        for spot_name, who, note, rating, comment in REVIEWS:
            spot = Spot.objects.get(name=spot_name)
            _, was_created = Review.objects.get_or_create(
                spot=spot, reviewer_name=who,
                defaults=dict(reviewer_note=note, rating=rating, comment=comment),
            )
            added_reviews += was_created

        self.stdout.write(self.style.SUCCESS(
            f'Demo data ready: {created} new spot(s), {photos} photo(s) attached, {added_reviews} new review(s). '
            'Coordinates are approximate - correct them in /admin/.'
        ))
