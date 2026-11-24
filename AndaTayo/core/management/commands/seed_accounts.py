"""
Creates one demo login per role so you can try every part of the site.

    python manage.py seed_accounts            # create (or reset) the demo accounts
    python manage.py seed_accounts --remove   # delete them again

All demo accounts share the password below. Running the command again resets their passwords and
roles, so it is safe to run more than once. It never touches any other account.
DEV ONLY: remove these accounts (or change the passwords) before putting the site online.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Profile, Spot

PASSWORD = 'AndaTayo2026!'

# username, email, full name, role, is_superuser
ACCOUNTS = [
    ('superadmin', 'superadmin@andatayo.test', 'Super Admin', Profile.ADMIN, True),
    ('admin', 'admin@andatayo.test', 'Anda Admin', Profile.ADMIN, False),
    ('owner', 'owner@andatayo.test', 'Olivia Owner', Profile.OWNER, False),
    ('student', 'student@andatayo.test', 'Sam Student', Profile.STUDENT, False),
]

# The demo owner manages this demo spot so the owner dashboard isn't empty.
OWNER_SPOT = 'Library Coffee + Study'


class Command(BaseCommand):
    help = 'Create (or --remove) one demo account per role.'

    def add_arguments(self, parser):
        parser.add_argument('--remove', action='store_true', help='Delete the demo accounts.')

    def handle(self, *args, remove=False, **options):
        User = get_user_model()
        usernames = [a[0] for a in ACCOUNTS]

        if remove:
            Spot.objects.filter(owner__username='owner', name=OWNER_SPOT).update(owner=None)
            deleted, _ = User.objects.filter(username__in=usernames).delete()
            self.stdout.write(self.style.SUCCESS(f'Removed the demo accounts ({deleted} rows).'))
            return

        for username, email, full_name, role, superuser in ACCOUNTS:
            user, _ = User.objects.get_or_create(username=username)
            user.email = email
            user.first_name = full_name
            user.is_superuser = superuser
            user.is_staff = role == Profile.ADMIN   # Admin role <=> staff, same as the dashboard does
            user.is_active = True
            user.set_password(PASSWORD)
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.owner_requested_at = None
            profile.save()

        owner = User.objects.get(username='owner')
        linked = Spot.objects.filter(name=OWNER_SPOT).update(owner=owner)

        self.stdout.write(self.style.SUCCESS('Demo accounts ready (log in with the email or the username):'))
        for username, email, _, role, superuser in ACCOUNTS:
            label = 'Superadmin' if superuser else dict(Profile.ROLE_CHOICES)[role]
            self.stdout.write(f'  {label:<11} {email:<26} / {username:<10}  password: {PASSWORD}')
        if not linked:
            self.stdout.write(f'  (Run seed_demo first if you want the owner to manage "{OWNER_SPOT}".)')
