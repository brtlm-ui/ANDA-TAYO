from datetime import time
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Amenity, Mood, Review, Spot


def make_spot(mood, **overrides):
    data = dict(
        name='Test Cafe', address='Normal Road', area='wmsu', mood=mood,
        starts_at_price=Decimal('100'), opening_time=time(8), closing_time=time(22), is_approved=True,
    )
    data.update(overrides)
    return Spot.objects.create(**data)


class SeedAndModelTests(TestCase):
    def test_four_moods_are_seeded_by_migration(self):
        names = set(Mood.objects.values_list('name', flat=True))
        self.assertEqual(names, {'Deep Focus', 'Barkada Energy', 'Aesthetic & Shoots', 'Tipid / Budget'})

    def test_hours_and_distance_labels(self):
        mood = Mood.objects.first()
        spot = make_spot(mood, closing_time=time(23))
        self.assertEqual(spot.distance_label(), '')          # no coordinates yet
        spot.distance_from_wmsu_m = 700
        self.assertEqual(spot.hours_label(), 'Open till 11 PM')
        self.assertEqual(spot.distance_label(), '700 m to WMSU')
        spot.distance_from_wmsu_m = 2500
        self.assertEqual(spot.distance_label(), '2.5 km to WMSU')
        spot.is_24_hours = True
        self.assertEqual(spot.hours_label(), '24 Hours Open')
        self.assertTrue(spot.is_open_now())

    def test_demo_command_is_repeatable_and_removable(self):
        call_command('seed_demo')
        call_command('seed_demo')  # running twice must not duplicate
        self.assertEqual(Spot.objects.count(), 10)
        self.assertEqual(Review.objects.count(), 2)
        call_command('seed_demo', '--remove')
        self.assertEqual(Spot.objects.count(), 0)


class PublicPageTests(TestCase):
    def setUp(self):
        self.focus = Mood.objects.get(name='Deep Focus')
        self.barkada = Mood.objects.get(name='Barkada Energy')
        self.a = make_spot(self.focus, name='Quiet Cafe', starts_at_price=Decimal('150'),
                           wifi_speed_mbps=85, latitude=6.9100, longitude=122.0600)   # ~460 m from WMSU
        self.a.amenities.set(Amenity.objects.filter(code__in=['wifi', 'outlets']))
        self.b = make_spot(self.barkada, name='Loud Tea', starts_at_price=Decimal('50'), area='paseo',
                           is_24_hours=True, category='street_food')
        self.hidden = make_spot(self.focus, name='Pending Place', is_approved=False)
        Review.objects.create(spot=self.a, reviewer_name='Ana', rating=5, comment='Great')
        Review.objects.create(spot=self.a, reviewer_name='Ben', rating=4, comment='Good')

    def names(self, **params):
        response = self.client.get(reverse('spot_list'), params)
        self.assertEqual(response.status_code, 200)
        return [s.name for s in response.context['spots']]

    def test_pages_render(self):
        for name in ('home', 'about', 'spot_list', 'add_spot'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse('spot_detail', args=[self.a.id])).status_code, 200)

    def test_landing_stats_are_computed_from_real_rows(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['stats']['reviews'], 2)
        self.assertEqual(response.context['stats']['spots'], 2)       # pending spot not counted
        self.assertEqual(response.context['stats']['avg_rating'], 4.5)

    def test_pending_spots_are_hidden_from_the_public(self):
        self.assertNotIn('Pending Place', self.names())
        self.assertEqual(self.client.get(reverse('spot_detail', args=[self.hidden.id])).status_code, 404)

    def test_filters(self):
        self.assertEqual(sorted(self.names()), ['Loud Tea', 'Quiet Cafe'])
        self.assertEqual(self.names(mood=self.focus.id), ['Quiet Cafe'])
        self.assertEqual(self.names(budget=100), ['Loud Tea'])
        self.assertEqual(self.names(area='paseo'), ['Loud Tea'])
        self.assertEqual(self.names(amenity='wifi'), ['Quiet Cafe'])
        self.assertEqual(self.names(amenity=['wifi', 'outlets']), ['Quiet Cafe'])
        self.assertEqual(self.names(amenity='aircon'), [])
        self.assertEqual(self.names(category='street_food'), ['Loud Tea'])
        self.assertEqual(self.names(category='cafe'), ['Quiet Cafe'])
        self.assertEqual(self.names(open24=1), ['Loud Tea'])
        self.assertEqual(self.names(distance=1000), ['Quiet Cafe'])
        self.assertEqual(self.names(q='tea'), ['Loud Tea'])

    def test_sorting(self):
        self.assertEqual(self.names(sort='rating')[0], 'Quiet Cafe')     # only one with reviews
        self.assertEqual(self.names(sort='cheapest')[0], 'Loud Tea')

    def test_junk_parameters_do_not_crash(self):
        response = self.client.get(reverse('spot_list'), {'mood': 'abc', 'budget': 'x', 'limit': '-5', 'sort': 'zzz', 'area': '??'})
        self.assertEqual(response.status_code, 200)

    def test_load_more_limit(self):
        for i in range(10):
            make_spot(self.focus, name=f'Extra {i}')
        response = self.client.get(reverse('spot_list'))
        self.assertEqual(len(response.context['spots']), 8)
        self.assertTrue(response.context['has_more'])
        response = self.client.get(reverse('spot_list'), {'limit': 16})
        self.assertEqual(len(response.context['spots']), 12)
        self.assertFalse(response.context['has_more'])

    def test_old_map_links_redirect_to_the_explorer(self):
        response = self.client.get(reverse('spot_list'), {'view': 'map', 'mood': self.focus.id})
        self.assertRedirects(response, f"{reverse('map_explorer')}?mood={self.focus.id}")


class SubmitAndManageTests(TestCase):
    def setUp(self):
        self.mood = Mood.objects.first()
        self.spot = make_spot(self.mood, name='Existing')
        self.staff = User.objects.create_user('admin1', password='pass12345!', is_staff=True)
        self.form = {
            'name': 'Hidden Gem', 'category': 'cafe', 'address': 'Tetuan', 'area': 'tetuan', 'mood': self.mood.id,
            'starts_at_price': '80', 'opening_time': '09:00', 'closing_time': '21:00',
        }

    def test_public_submission_waits_for_approval(self):
        response = self.client.post(reverse('add_spot'), self.form)
        self.assertRedirects(response, reverse('spot_list'))
        self.assertFalse(Spot.objects.get(name='Hidden Gem').is_approved)

    def test_staff_submission_is_approved_immediately(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('add_spot'), self.form)
        self.assertTrue(Spot.objects.get(name='Hidden Gem').is_approved)

    def test_invalid_submission_shows_errors(self):
        response = self.client.post(reverse('add_spot'), {'name': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Spot.objects.filter(name='').exists())

    def test_edit_and_delete_require_staff(self):
        edit_url = reverse('edit_spot', args=[self.spot.id])
        delete_url = reverse('delete_spot', args=[self.spot.id])
        self.assertEqual(self.client.get(edit_url).status_code, 302)       # redirected to login
        self.client.post(delete_url)
        self.assertTrue(Spot.objects.filter(id=self.spot.id).exists())

        self.client.force_login(self.staff)
        self.client.post(edit_url, {**self.form, 'name': 'Renamed'})
        self.spot.refresh_from_db()
        self.assertEqual(self.spot.name, 'Renamed')
        self.assertEqual(self.client.get(delete_url).status_code, 405)     # delete must be POST
        self.client.post(delete_url)
        self.assertFalse(Spot.objects.filter(id=self.spot.id).exists())

    def test_anyone_can_post_a_review(self):
        url = reverse('add_review', args=[self.spot.id])
        self.client.post(url, {'reviewer_name': 'Ana', 'reviewer_note': 'WMSU', 'rating': 5, 'comment': 'Nice'})
        self.assertEqual(self.spot.reviews.count(), 1)
        self.client.post(url, {'reviewer_name': 'Ana', 'rating': 9, 'comment': 'bad rating'})
        self.assertEqual(self.spot.reviews.count(), 1)  # rating 9 rejected

    def test_only_staff_can_delete_reviews(self):
        review = Review.objects.create(spot=self.spot, reviewer_name='Ana', rating=5, comment='x')
        url = reverse('delete_review', args=[review.id])
        self.client.post(url)
        self.assertTrue(Review.objects.filter(id=review.id).exists())
        self.client.force_login(self.staff)
        self.client.post(url)
        self.assertFalse(Review.objects.filter(id=review.id).exists())
