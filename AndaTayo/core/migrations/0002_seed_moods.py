from django.db import migrations

# (name, icon, pin color, chip/category pastel, map-legend text) - taken from the Figma mockup
MOODS = [
    ('Deep Focus', '\U0001F4DA', '#2eaaf0', '#d9ccff', 'Silent & WiFi'),
    ('Barkada Energy', '\U0001F465', '#f06a8d', '#a9d8ff', 'Group Tables & Games'),
    ('Aesthetic & Shoots', '\U0001F4F8', '#1fb36b', '#ffa8a8', 'Sunset & OOTD'),
    ('Tipid / Budget', '\U0001F4B8', '#f5a623', '#ffe14a', 'Student Meals < P99'),
]


def seed_moods(apps, schema_editor):
    Mood = apps.get_model('core', 'Mood')
    for name, icon, color, pastel, legend in MOODS:
        Mood.objects.get_or_create(
            name=name,
            defaults={'icon': icon, 'color': color, 'pastel': pastel, 'legend': legend},
        )


def remove_moods(apps, schema_editor):
    # Only removes seeded moods that no spot is using.
    Mood = apps.get_model('core', 'Mood')
    Mood.objects.filter(name__in=[m[0] for m in MOODS], spots__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_moods, remove_moods),
    ]
