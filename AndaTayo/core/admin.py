from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .icons import svg
from .models import Amenity, Bookmark, Mood, Profile, Review, Spot

LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'


@admin.register(Mood)
class MoodAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'color', 'pastel')


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'code')
    prepopulated_fields = {'code': ('name',)}


@admin.register(Spot)
class SpotAdmin(admin.ModelAdmin):
    list_display = ('thumbnail', 'name', 'category', 'mood', 'area', 'starts_at_price', 'is_top_pick', 'is_approved')
    list_display_links = ('thumbnail', 'name')
    list_filter = ('is_approved', 'category', 'is_top_pick', 'mood', 'area', 'amenities')
    list_editable = ('is_approved',)   # quick-approve community submissions
    search_fields = ('name', 'address')
    filter_horizontal = ('amenities',)
    readonly_fields = ('photo_preview', 'distance_from_wmsu_m', 'created_at')

    fieldsets = (
        (None, {'fields': ('name', 'category', 'mood', 'area', 'address', 'description')}),
        ('Photo', {'fields': ('cover_image', 'photo_preview', 'photo_url')}),
        ('Price & hours', {'fields': ('starts_at_price', 'min_spend_note', 'opening_time', 'closing_time', 'is_24_hours')}),
        ('Amenities', {'fields': ('amenities', 'wifi_speed_mbps')}),
        ('Location', {
            'description': 'Click the map to set the pin. Distance from WMSU is calculated automatically when you save.',
            'fields': ('latitude', 'longitude', 'distance_from_wmsu_m'),
        }),
        ('Status', {'fields': ('is_top_pick', 'is_approved', 'created_at')}),
    )

    class Media:
        # Leaflet + our click-to-pick map (static/js/location-picker.js) on the add/change page
        css = {'all': (LEAFLET_CSS,)}
        js = (LEAFLET_JS, 'js/map-config.js', 'js/location-picker.js')

    @admin.display(description='')
    def thumbnail(self, spot):
        if spot.image_src:
            return format_html('<img src="{}" style="width:48px;height:36px;object-fit:cover;border-radius:6px">', spot.image_src)
        return mark_safe(svg(spot.category_icon, ''))   # our own icon markup (core/icons.py)

    @admin.display(description='Current photo')
    def photo_preview(self, spot):
        if spot.image_src:
            return format_html('<img src="{}" style="max-width:320px;max-height:200px;border-radius:10px">', spot.image_src)
        return 'No photo yet'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('spot', 'reviewer_name', 'rating', 'created_at')
    list_filter = ('rating',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'school', 'owner_requested_at')
    list_filter = ('role',)
    search_fields = ('user__email', 'user__first_name', 'user__username')


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'spot', 'created_at')
