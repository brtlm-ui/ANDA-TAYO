from django.db import migrations

from core.geo import WMSU_COORDS, haversine_km

AMENITIES = [
    # code, name, icon
    ('wifi', 'Wi-Fi', '\U0001F4F6'),
    ('aircon', 'Aircon', '❄️'),
    ('outlets', 'Power Outlets', '\U0001F50C'),
    ('pet_friendly', 'Pet-Friendly', '\U0001F43E'),
    ('parking', 'Parking', '\U0001F17F️'),
    ('outdoor', 'Outdoor Seating', '\U0001F33F'),
    ('restroom', 'Restroom', '\U0001F6BB'),
    ('group_tables', 'Group Tables', '\U0001F465'),
]

# Categories for the demo spots loaded by `manage.py seed_demo` (matched by name).
DEMO_CATEGORIES = {
    "Seattle's Best Coffee": 'cafe',
    'Paseo del Mar': 'food_park',
    'Dennis Coffee Garden': 'cafe',
    'Hacienda de Palmeras Garden': 'restaurant',
    'Library Coffee + Study': 'study_spot',
    "Jimmy's Satti Food Haus": 'street_food',
    'Bay Tal Mal Restaurant': 'restaurant',
    'Taza Coffee Company': 'cafe',
    'Coffee Spot': 'cafe',
    'Canelar Alley Cafe': 'cafe',
}


def forwards(apps, schema_editor):
    Amenity = apps.get_model('core', 'Amenity')
    Spot = apps.get_model('core', 'Spot')

    amenities = {}
    for code, name, icon in AMENITIES:
        amenities[code], _ = Amenity.objects.get_or_create(code=code, defaults={'name': name, 'icon': icon})

    for spot in Spot.objects.all():
        # old checkbox / WiFi speed -> amenities
        if spot.has_sockets:
            spot.amenities.add(amenities['outlets'])
        if spot.wifi_speed_mbps:
            spot.amenities.add(amenities['wifi'])
        # demo spots get a category
        if spot.name in DEMO_CATEGORIES and spot.description.startswith('[DEMO'):
            spot.category = DEMO_CATEGORIES[spot.name]
        # distance from WMSU is now computed from the coordinates
        if spot.latitude is not None and spot.longitude is not None:
            spot.distance_from_wmsu_m = round(haversine_km(*WMSU_COORDS, spot.latitude, spot.longitude) * 1000)
        else:
            spot.distance_from_wmsu_m = None
        spot.save(update_fields=['category', 'distance_from_wmsu_m'])


def backwards(apps, schema_editor):
    Spot = apps.get_model('core', 'Spot')
    for spot in Spot.objects.filter(amenities__code='outlets'):
        spot.has_sockets = True
        spot.save(update_fields=['has_sockets'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_spot_category_amenities_photo'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
