"""Accounts, roles, dashboards, saved spots - the logged-in side of Anda Tayo."""
from datetime import time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import Bookmark, Mood, Profile, Review, Spot

User = get_user_model()
PASSWORD = 'Tambayan-2026!'


def make_user(email, role=Profile.STUDENT, name='Test User', **extra):
    user = User.objects.create_user(username=email, email=email, password=PASSWORD, first_name=name, **extra)
    if role != Profile.STUDENT:
        user.profile.role = role
        user.profile.save()
    return user


def make_admin(email='admin@example.com'):
    return make_user(email, role=Profile.ADMIN, name='Admin Person', is_staff=True)


def make_spot(**overrides):
    data = dict(name='Test Cafe', address='Normal Road', area='wmsu', mood=Mood.objects.first(),
                starts_at_price=Decimal('100'), opening_time=time(8), closing_time=time(22), is_approved=True)
    data.update(overrides)
    return Spot.objects.create(**data)


class SignupAndLoginTests(TestCase):
    def signup(self, **overrides):
        data = {'full_name': 'Ana Reyes', 'email': 'Ana.Reyes@Example.com', 'password1': PASSWORD,
                'password2': PASSWORD, 'agree': 'on'}
        data.update(overrides)
        return self.client.post(reverse('signup'), data)

    def test_signup_creates_a_student_and_logs_in(self):
        response = self.signup()
        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(email='ana.reyes@example.com')        # stored lower-case
        self.assertEqual(user.profile.role, Profile.STUDENT)
        self.assertIsNone(user.profile.owner_requested_at)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)

    def test_signup_can_request_owner_access(self):
        self.signup(wants_owner='on')
        profile = User.objects.get(email='ana.reyes@example.com').profile
        self.assertEqual(profile.role, Profile.STUDENT)                # still a student until approved
        self.assertIsNotNone(profile.owner_requested_at)

    def test_signup_validation(self):
        make_user('ana.reyes@example.com')
        self.assertContains(self.signup(), 'already exists')
        self.assertContains(self.signup(email='new@example.com', password2='different'), "don&#x27;t match")
        self.assertContains(self.signup(email='new@example.com', password1='123', password2='123'), 'too short')
        self.assertContains(self.signup(email='new@example.com', agree=''), 'Please agree')
        self.assertEqual(User.objects.count(), 1)

    def test_login_with_email_case_insensitive(self):
        make_user('ana@example.com')
        response = self.client.post(reverse('login'), {'email': 'ANA@example.com', 'password': PASSWORD})
        self.assertRedirects(response, reverse('home'))

    def test_wrong_password_shows_error(self):
        make_user('ana@example.com')
        response = self.client.post(reverse('login'), {'email': 'ana@example.com', 'password': 'nope'})
        self.assertContains(response, "don&#x27;t match")
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_old_accounts_can_still_log_in_with_username(self):
        User.objects.create_superuser('princess', 'p@example.com', PASSWORD)
        response = self.client.post(reverse('login'), {'email': 'princess', 'password': PASSWORD})
        self.assertRedirects(response, reverse('dashboard'))

    def test_each_role_lands_in_its_own_place(self):
        make_user('student@example.com')
        make_user('owner@example.com', role=Profile.OWNER)
        make_admin()
        for email, url_name in (('student@example.com', 'home'), ('owner@example.com', 'owner_dashboard'),
                                ('admin@example.com', 'dashboard')):
            response = self.client.post(reverse('login'), {'email': email, 'password': PASSWORD})
            self.assertRedirects(response, reverse(url_name), fetch_redirect_response=False, msg_prefix=email)
            self.client.post(reverse('logout'))

    def test_next_is_followed_but_only_on_this_site(self):
        make_user('ana@example.com')
        response = self.client.post(reverse('login') + '?next=/map/', {'email': 'ana@example.com', 'password': PASSWORD})
        self.assertRedirects(response, '/map/')
        self.client.post(reverse('logout'))
        response = self.client.post(reverse('login') + '?next=https://evil.example/', {'email': 'ana@example.com', 'password': PASSWORD})
        self.assertRedirects(response, reverse('home'))

    def test_remember_me_off_ends_session_with_browser(self):
        make_user('ana@example.com')
        self.client.post(reverse('login'), {'email': 'ana@example.com', 'password': PASSWORD, 'remember': 'on'})
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.client.post(reverse('logout'))
        self.client.post(reverse('login'), {'email': 'ana@example.com', 'password': PASSWORD, 'remember': ''})
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_logout_must_be_post(self):
        self.client.force_login(make_user('ana@example.com'))
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_header_shows_login_or_account_menu(self):
        self.assertContains(self.client.get(reverse('home')), 'Sign up')
        self.client.force_login(make_user('ana@example.com', name='Ana Reyes'))
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('data-account-menu', html)
        self.assertIn('Saved spots', html)
        self.assertNotIn('Admin dashboard', html)

    def test_superusers_get_an_admin_profile(self):
        user = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.assertEqual(user.profile.role, Profile.ADMIN)

    def test_password_reset_sends_an_email(self):
        make_user('ana@example.com')
        response = self.client.post(reverse('password_reset'), {'email': 'ana@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/password-reset/', mail.outbox[0].body)


class AccountPageTests(TestCase):
    def setUp(self):
        self.user = make_user('ana@example.com', name='Ana Reyes')
        self.client.force_login(self.user)

    def test_update_details(self):
        self.client.post(reverse('account'), {'save_profile': '1', 'full_name': 'Ana R.', 'email': 'ana.r@example.com',
                                              'school': 'WMSU CS'})
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.email, self.user.username), ('Ana R.', 'ana.r@example.com', 'ana.r@example.com'))
        self.assertEqual(self.user.profile.school, 'WMSU CS')

    def test_change_password_keeps_you_logged_in(self):
        self.client.post(reverse('account'), {'change_password': '1', 'old_password': PASSWORD,
                                              'new_password1': 'New-Tambayan-99', 'new_password2': 'New-Tambayan-99'})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-Tambayan-99'))
        self.assertEqual(self.client.get(reverse('account')).status_code, 200)

    def test_request_owner_access(self):
        self.client.post(reverse('request_owner'))
        self.user.profile.refresh_from_db()
        self.assertIsNotNone(self.user.profile.owner_requested_at)

    def test_save_and_unsave_a_spot(self):
        spot = make_spot()
        self.client.post(reverse('toggle_save', args=[spot.id]))
        self.assertTrue(Bookmark.objects.filter(user=self.user, spot=spot).exists())
        self.assertContains(self.client.get(reverse('saved_spots')), 'Test Cafe')
        self.client.post(reverse('toggle_save', args=[spot.id]))
        self.assertFalse(Bookmark.objects.exists())

    def test_my_reviews_lists_only_mine(self):
        spot = make_spot()
        Review.objects.create(spot=spot, user=self.user, reviewer_name='Ana', rating=5, comment='Mine!')
        Review.objects.create(spot=spot, reviewer_name='Other', rating=3, comment='Not mine')
        html = self.client.get(reverse('my_reviews')).content.decode()
        self.assertIn('Mine!', html)
        self.assertNotIn('Not mine', html)

    def test_account_pages_need_login(self):
        self.client.logout()
        for name in ('account', 'saved_spots', 'my_reviews'):
            response = self.client.get(reverse(name))
            self.assertRedirects(response, f"{reverse('login')}?next={reverse(name)}", msg_prefix=name)


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.owner = make_user('owner@example.com', role=Profile.OWNER, name='Marco Lim')
        self.student = make_user('ana@example.com', name='Ana Reyes')
        self.pending = make_spot(name='New Place', is_approved=False, submitted_by=self.owner)

    def test_dashboard_pages_are_admin_only(self):
        pages = ['dashboard', 'dashboard_approvals', 'dashboard_spots', 'dashboard_reviews', 'dashboard_users']
        for name in pages:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302, name)       # to login
        self.client.force_login(self.student)
        for name in pages:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        self.client.force_login(self.admin)
        for name in pages:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_overview_counts_real_rows(self):
        self.student.profile.owner_requested_at = self.student.date_joined
        self.student.profile.save()
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['stats'][0]['value'], 2)        # 1 spot + 1 owner request
        self.assertContains(response, 'New Place')

    def test_approve_spot_makes_it_live_and_gives_it_to_its_owner(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('approve_spot', args=[self.pending.id]))
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_approved)
        self.assertIsNotNone(self.pending.approved_at)
        self.assertEqual(self.pending.owner, self.owner)

    def test_reject_spot_with_reason(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('reject_spot', args=[self.pending.id]), {'reason': 'Duplicate of an existing spot', 'note': 'See Coffee Spot'})
        self.pending.refresh_from_db()
        self.assertFalse(self.pending.is_approved)
        self.assertIsNotNone(self.pending.rejected_at)
        self.assertIn('See Coffee Spot', self.pending.rejection_reason)
        # gone from the queue, and the owner sees the reason
        self.assertEqual(list(self.client.get(reverse('dashboard_approvals')).context['pending_spots']), [])
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('owner_dashboard')), 'See Coffee Spot')

    def test_owner_request_approve_and_decline(self):
        for decision, expected in (('approve', Profile.OWNER), ('decline', Profile.STUDENT)):
            user = make_user(f'{decision}@example.com')
            user.profile.owner_requested_at = user.date_joined
            user.profile.save()
            self.client.force_login(self.admin)
            self.client.post(reverse('decide_owner_request', args=[user.id]), {'decision': decision})
            user.profile.refresh_from_db()
            self.assertEqual(user.profile.role, expected)
            self.assertIsNone(user.profile.owner_requested_at)

    def test_set_role_syncs_staff_flag(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('set_role', args=[self.student.id]), {'role': 'admin'})
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_staff)
        self.client.post(reverse('set_role', args=[self.student.id]), {'role': 'owner'})
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_staff)
        self.assertEqual(self.student.profile.role, Profile.OWNER)

    def test_cannot_change_own_role_or_a_superuser(self):
        root = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.client.force_login(self.admin)
        self.client.post(reverse('set_role', args=[self.admin.id]), {'role': 'student'})
        self.client.post(reverse('set_role', args=[root.id]), {'role': 'student'})
        self.admin.refresh_from_db(); root.refresh_from_db()
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(root.is_staff)

    def test_spots_table_filters(self):
        make_spot(name='Live One')
        self.client.force_login(self.admin)
        names = lambda **p: [s.name for s in self.client.get(reverse('dashboard_spots'), p).context['spots']]
        self.assertEqual(names(status='pending'), ['New Place'])
        self.assertEqual(names(status='live'), ['Live One'])
        self.assertEqual(names(q='live'), ['Live One'])

    def test_admin_actions_need_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('approve_spot', args=[self.pending.id])).status_code, 405)


class OwnerTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner@example.com', role=Profile.OWNER, name='Marco Lim')
        self.mine = make_spot(name='My Cafe', owner=self.owner)
        self.other = make_spot(name='Not Mine')
        self.client.force_login(self.owner)

    def form(self, **overrides):
        data = {'name': 'My Cafe', 'category': 'cafe', 'address': 'Tetuan', 'area': 'tetuan',
                'mood': Mood.objects.first().id, 'starts_at_price': '90', 'opening_time': '09:00', 'closing_time': '21:00'}
        data.update(overrides)
        return data

    def test_owner_dashboard_lists_my_spots(self):
        html = self.client.get(reverse('owner_dashboard')).content.decode()
        self.assertIn('My Cafe', html)
        self.assertNotIn('Not Mine', html)

    def test_owner_edits_only_their_spots(self):
        self.client.post(reverse('edit_spot', args=[self.mine.id]), self.form(name='My Cafe 2'))
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.name, 'My Cafe 2')
        self.assertEqual(self.client.get(reverse('edit_spot', args=[self.other.id])).status_code, 403)

    def test_owner_cannot_approve_or_change_owner_fields(self):
        self.client.post(reverse('edit_spot', args=[self.mine.id]), self.form(is_top_pick='on', owner=''))
        self.mine.refresh_from_db()
        self.assertFalse(self.mine.is_top_pick)
        self.assertEqual(self.mine.owner, self.owner)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 403)

    def test_owner_submission_is_theirs_but_pending(self):
        self.client.post(reverse('add_spot'), self.form(name='Second Branch'))
        spot = Spot.objects.get(name='Second Branch')
        self.assertEqual((spot.owner, spot.submitted_by, spot.is_approved), (self.owner, self.owner, False))

    def test_students_cannot_open_owner_dashboard(self):
        self.client.force_login(make_user('ana@example.com'))
        self.assertEqual(self.client.get(reverse('owner_dashboard')).status_code, 403)
