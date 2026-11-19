from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .geo import WMSU_COORDS, haversine_km
from .icons import ICON_CHOICES

MAX_IMAGE_MB = 5


def validate_image_size(image):
    if image.size > MAX_IMAGE_MB * 1024 * 1024:
        raise ValidationError(f'Please upload an image smaller than {MAX_IMAGE_MB} MB.')


class Mood(models.Model):
    """The 'vibe' a spot fits: Deep Focus, Barkada Energy, Aesthetic & Shoots, Tipid / Budget."""

    name = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=20, choices=ICON_CHOICES, default='pin')  # see core/icons.py
    color = models.CharField(max_length=7, default='#f59a23')         # map pin / legend color
    pastel = models.CharField(max_length=7, default='#f3e8d8')        # chip / category block color
    legend = models.CharField(max_length=80, blank=True)              # e.g. "Silent & WiFi" (map legend)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class Amenity(models.Model):
    """Wi-Fi, Aircon, Power Outlets, Pet-Friendly, ... (admins can add more in /admin/)."""

    code = models.SlugField(max_length=30, unique=True)   # used in URLs: ?amenity=wifi
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=20, choices=ICON_CHOICES, default='pin')  # see core/icons.py

    class Meta:
        ordering = ['id']
        verbose_name_plural = 'amenities'

    def __str__(self):
        return self.name


class Spot(models.Model):
    CATEGORY_CHOICES = [
        ('cafe', 'Cafe'),
        ('restaurant', 'Restaurant'),
        ('food_park', 'Food Park'),
        ('street_food', 'Street Food'),
        ('study_spot', 'Study Spot'),
        ('other', 'Other'),
    ]
    # Pin color + icon per category (used by the map, badges and the admin)
    CATEGORY_STYLE = {
        'cafe': {'icon': 'coffee', 'color': '#b45309'},
        'restaurant': {'icon': 'utensils', 'color': '#dc2626'},
        'food_park': {'icon': 'tree', 'color': '#16a34a'},
        'street_food': {'icon': 'flame', 'color': '#ea580c'},
        'study_spot': {'icon': 'book', 'color': '#2563eb'},
        'other': {'icon': 'pin', 'color': '#6b7280'},
    }
    AREA_CHOICES = [
        ('wmsu', 'WMSU Area'),
        ('ateneo', 'Ateneo Area'),
        ('paseo', 'Paseo Waterfront'),
        ('tetuan', 'Tetuan Hub'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='cafe')
    address = models.CharField(max_length=255)
    area = models.CharField(max_length=10, choices=AREA_CHOICES, default='other')
    mood = models.ForeignKey(Mood, on_delete=models.PROTECT, related_name='spots')
    description = models.TextField(blank=True)

    # Photo: upload one, or paste a link (the upload wins if both are set)
    cover_image = models.ImageField(upload_to='spots/%Y/%m/', blank=True, validators=[validate_image_size])
    photo_url = models.URLField(max_length=500, blank=True, help_text='Or paste a link to a photo.')

    # Price: "Starts at P120 / Min. spend per table"
    starts_at_price = models.DecimalField(max_digits=7, decimal_places=2)
    min_spend_note = models.CharField(max_length=60, blank=True, help_text='e.g. Min. spend / table')

    # Operating hours
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    is_24_hours = models.BooleanField(default=False)

    amenities = models.ManyToManyField(Amenity, related_name='spots', blank=True)
    wifi_speed_mbps = models.PositiveIntegerField(null=True, blank=True, help_text='Leave blank if unknown.')

    # Location (plain floats - distances are computed with the Haversine formula, see core/geo.py)
    latitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    # Filled in automatically from the coordinates on save (straight-line distance)
    distance_from_wmsu_m = models.PositiveIntegerField(null=True, blank=True, editable=False)

    is_top_pick = models.BooleanField(default=False)
    # Community submissions stay hidden until an admin approves them.
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.latitude is not None and self.longitude is not None:
            self.distance_from_wmsu_m = round(haversine_km(*WMSU_COORDS, self.latitude, self.longitude) * 1000)
        else:
            self.distance_from_wmsu_m = None
        super().save(*args, **kwargs)

    # ----- display helpers used by the templates and the JSON API -----
    @property
    def image_src(self):
        if self.cover_image:
            return self.cover_image.url
        return self.photo_url

    @property
    def category_icon(self):
        return self.CATEGORY_STYLE.get(self.category, self.CATEGORY_STYLE['other'])['icon']

    @property
    def category_color(self):
        return self.CATEGORY_STYLE.get(self.category, self.CATEGORY_STYLE['other'])['color']

    @property
    def price_level(self):
        """P / PP / PPP from the starting price."""
        price = self.starts_at_price or 0
        return '₱' * (1 if price <= 100 else 2 if price <= 250 else 3)

    def is_open_now(self):
        if self.is_24_hours:
            return True
        if not (self.opening_time and self.closing_time):
            return None  # unknown
        now = timezone.localtime().time()
        if self.opening_time <= self.closing_time:
            return self.opening_time <= now <= self.closing_time
        return now >= self.opening_time or now <= self.closing_time  # closes after midnight

    def hours_label(self):
        if self.is_24_hours:
            return '24 Hours Open'
        if self.closing_time:
            fmt = '%I %p' if self.closing_time.minute == 0 else '%I:%M %p'
            return 'Open till ' + self.closing_time.strftime(fmt).lstrip('0')
        return ''

    def distance_label(self):
        m = self.distance_from_wmsu_m
        if m is None:
            return ''
        return f'{m} m to WMSU' if m < 1000 else f'{m / 1000:.1f} km to WMSU'


class Review(models.Model):
    """A short review ("Tambayan Tale") left by a student."""

    spot = models.ForeignKey(Spot, on_delete=models.CASCADE, related_name='reviews')
    reviewer_name = models.CharField(max_length=80)
    reviewer_note = models.CharField(max_length=100, blank=True, help_text='e.g. WMSU CS Student')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reviewer_name} - {self.spot.name} ({self.rating}/5)'
