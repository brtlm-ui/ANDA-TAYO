from django.db import migrations
from django.db.models import F


def forwards(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('core', 'Profile')
    Spot = apps.get_model('core', 'Spot')

    # Accounts created before roles existed: staff become Admin, everyone else Student.
    for user in User.objects.all():
        Profile.objects.get_or_create(user=user, defaults={'role': 'admin' if user.is_staff else 'student'})

    # Spots that are already live count as approved when they were created.
    Spot.objects.filter(is_approved=True, approved_at__isnull=True).update(approved_at=F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_accounts_roles_ownership'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
