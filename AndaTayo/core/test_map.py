"""Tests for nearby search (Haversine), the JSON API, the map explorer and photo uploads."""
import io
import shutil
import tempfile
from datetime import time
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .geo import WMSU_COORDS, annotate_distance, haversine_km
from .models import Amenity, Mood, Spot, validate_image_size


def make_spot(mood, **overrides):
    data = dict(
        name='Test Cafe', address='Normal Road', area='wmsu', mood=mood,
        starts_at_price=Decimal('100'), opening_time=time(8), closing_time=time(22), is_approved=True,
    )
    data.update(overrides)
    return Spot.objects.create(**data)


class GeoTests(TestCase):
    def test_haversine_matches_known_distance(self):
        # One degree of longitude on the equator is about 111.19 km
        self.assertAlmostEqual(haversine_km(0, 0, 0, 1), 111.19, places=1)
        self.assertEqual(haversine_km(6.9, 122.0, 6.9, 122.0), 0)

    def test_database_distance_matches_python(self):
        make_spot(Mood.objects.first(), name='Somewhere', latitude=6.9300, longitude=122.0900)
        spot = annotate_distance(Spot.objects.all(), *WMSU_COORDS).get()
        self.assertAlmostEqual(spot.distance_km, haversine_km(*WMSU_COORDS, 6.93, 122.09), places=4)

    def test_save_computes_distance_from_wmsu(self):
        spot = make_spot(Mood.objects.first(), latitude=6.9100, longitude=122.0600)
        self.assertEqual(spot.distance_from_wmsu_m, round(haversine_km(*WMSU_COORDS, 6.91, 122.06) * 1000))
        spot.latitude = spot.longitude = None
        spot.save()
        self.assertIsNone(spot.distance_from_wmsu_m)

    def test_price_level(self):
        mood = Mood.objects.first()
        self.assertEqual(make_spot(mood, starts_at_price=Decimal('80')).price_level, '₱')
        self.assertEqual(make_spot(mood, starts_at_price=Decimal('200')).price_level, '₱₱')
        self.assertEqual(make_spot(mood, starts_at_price=Decimal('300')).price_level, '₱₱₱')


class SpotsApiTests(TestCase):
    ORIGIN = (6.9128, 122.0631)

    def setUp(self):
        mood = Mood.objects.first()
        lat, lng = self.ORIGIN
        self.near = make_spot(mood, name='Near Cafe', latitude=lat + 0.0027, longitude=lng)                         # ~0.3 km
        self.mid = make_spot(mood, name='Mid Study', category='study_spot', latitude=lat + 0.0225, longitude=lng)  # ~2.5 km
        self.far = make_spot(mood, name='Far Resto', category='restaurant', latitude=lat + 0.072, longitude=lng)   # ~8 km
        make_spot(mood, name='No Coordinates')
        make_spot(mood, name='Pending Pin', latitude=lat, longitude=lng, is_approved=False)
        wifi, aircon = Amenity.objects.get(code='wifi'), Amenity.objects.get(code='aircon')
        self.near.amenities.set([wifi, aircon])
        self.mid.amenities.set([wifi])

    def api(self, **params):
        return self.client.get(reverse('spots_api'), params)

    def names(self, **params):
        response = self.api(**params)
        self.assertEqual(response.status_code, 200, response.content)
        return [s['name'] for s in response.json()['spots']]

    def test_without_location_returns_only_mapped_approved_spots(self):
        self.assertEqual(sorted(self.names()), ['Far Resto', 'Mid Study', 'Near Cafe'])

    def test_with_location_sorts_nearest_first_with_distance(self):
        lat, lng = self.ORIGIN
        data = self.api(lat=lat, lng=lng).json()
        self.assertEqual([s['name'] for s in data['spots']], ['Near Cafe', 'Mid Study', 'Far Resto'])
        near = data['spots'][0]
        expected = haversine_km(lat, lng, self.near.latitude, self.near.longitude)
        self.assertAlmostEqual(near['distance_km'], expected, places=2)
        self.assertEqual(near['distance_text'], f'{round(expected * 1000)} m away')

    def test_radius(self):
        lat, lng = self.ORIGIN
        self.assertEqual(self.names(lat=lat, lng=lng, radius=1), ['Near Cafe'])
        self.assertEqual(self.names(lat=lat, lng=lng, radius=3), ['Near Cafe', 'Mid Study'])
        self.assertEqual(self.names(lat=lat, lng=lng, radius=10), ['Near Cafe', 'Mid Study', 'Far Resto'])

    def test_category_and_amenities(self):
        self.assertEqual(self.names(category='study_spot'), ['Mid Study'])
        self.assertEqual(sorted(self.names(amenity='wifi')), ['Mid Study', 'Near Cafe'])
        self.assertEqual(self.names(amenity=['wifi', 'aircon']), ['Near Cafe'])   # must have ALL

    def test_payload_shape(self):
        spot = self.api(lat=self.ORIGIN[0], lng=self.ORIGIN[1]).json()['spots'][0]
        for key in ('id', 'name', 'lat', 'lng', 'category', 'image', 'price', 'amenities', 'distance_km', 'url', 'directions'):
            self.assertIn(key, spot)
        self.assertEqual(spot['category']['code'], 'cafe')
        self.assertEqual({a['code'] for a in spot['amenities']}, {'wifi', 'aircon'})

    def test_bad_input_returns_400(self):
        for params in ({'lat': 'abc', 'lng': '122'}, {'lat': '6.9'}, {'lat': '95', 'lng': '122'},
                       {'lat': 'nan', 'lng': '122'}, {'lat': '6.9', 'lng': '122', 'radius': '0'},
                       {'lat': '6.9', 'lng': '122', 'radius': '999'}, {'radius': 'far'}):
            response = self.api(**params)
            self.assertEqual(response.status_code, 400, params)
            self.assertIn('errors', response.json())

    def test_pending_spots_only_for_staff(self):
        self.assertNotIn('Pending Pin', self.names())
        staff = User.objects.create_user('admin1', password='pass12345!', is_staff=True)
        self.client.force_login(staff)
        self.assertIn('Pending Pin', self.names())

    def test_map_page_embeds_initial_spots(self):
        lat, lng = self.ORIGIN
        response = self.client.get(reverse('map_explorer'), {'lat': lat, 'lng': lng, 'radius': 1})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="map-initial"')
        self.assertEqual([s['name'] for s in response.context['initial']['spots']], ['Near Cafe'])

    def test_map_page_ignores_bad_params(self):
        response = self.client.get(reverse('map_explorer'), {'lat': 'x', 'radius': '-3', 'category': 'nope'})
        self.assertEqual(response.status_code, 200)


class PhotoUploadTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.staff = User.objects.create_user('admin1', password='pass12345!', is_staff=True)
        self.mood = Mood.objects.first()

    def png(self):
        buf = io.BytesIO()
        Image.new('RGB', (20, 20), (245, 147, 50)).save(buf, 'PNG')
        return SimpleUploadedFile('cover.png', buf.getvalue(), content_type='image/png')

    def test_staff_can_upload_cover_photo(self):
        with override_settings(MEDIA_ROOT=self.media):
            self.client.force_login(self.staff)
            self.client.post(reverse('add_spot'), {
                'name': 'Photo Cafe', 'category': 'cafe', 'address': 'Normal Road', 'area': 'wmsu',
                'mood': self.mood.id, 'starts_at_price': '90', 'cover_image': self.png(),
                'latitude': '6.9130', 'longitude': '122.0630',
            })
            spot = Spot.objects.get(name='Photo Cafe')
            self.assertTrue(spot.image_src.startswith('/media/spots/'))
            self.assertIsNotNone(spot.distance_from_wmsu_m)

    def test_non_image_is_rejected(self):
        with override_settings(MEDIA_ROOT=self.media):
            fake = SimpleUploadedFile('cover.png', b'not really an image', content_type='image/png')
            self.client.post(reverse('add_spot'), {
                'name': 'Bad Photo', 'category': 'cafe', 'address': 'x', 'area': 'wmsu',
                'mood': self.mood.id, 'starts_at_price': '90', 'cover_image': fake,
            })
            self.assertFalse(Spot.objects.filter(name='Bad Photo').exists())

    def test_size_limit(self):
        class Big:
            size = 6 * 1024 * 1024
        with self.assertRaises(ValidationError):
            validate_image_size(Big())


class IconAndTileTests(TestCase):
    """Icon set consistency, the tile Referer fix, and demo photos."""

    def test_every_category_mood_and_amenity_has_a_real_icon(self):
        from .icons import ICONS
        for style in Spot.CATEGORY_STYLE.values():
            self.assertIn(style['icon'], ICONS)
        for mood in Mood.objects.all():
            self.assertIn(mood.icon, ICONS, mood.name)
        for amenity in Amenity.objects.all():
            self.assertIn(amenity.icon, ICONS, amenity.name)

    def test_icon_tag_renders_svg(self):
        from django.template import Context, Template
        html = Template("{% load ui %}{% icon 'wifi' 'h-5 w-5' %}").render(Context())
        self.assertTrue(html.startswith('<svg class="h-5 w-5"'))
        self.assertIn('viewBox="0 0 24 24"', html)

    def test_pages_send_origin_as_referer_to_tile_servers(self):
        # OpenStreetMap blocks tile requests without a Referer ("Access blocked")
        response = self.client.get(reverse('map_explorer'))
        self.assertEqual(response['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertIn('icons', response.context['initial'])

    def test_seed_demo_attaches_photos(self):
        from django.core.management import call_command
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media):
            call_command('seed_demo', verbosity=0)
            with_photo = Spot.objects.exclude(cover_image='').count()
            self.assertEqual(with_photo, 9)          # Canelar Alley Cafe has no photo in the mockup
            call_command('seed_demo', verbosity=0)   # re-running must not duplicate files
            self.assertEqual(Spot.objects.exclude(cover_image='').count(), 9)
