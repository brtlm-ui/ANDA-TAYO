from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Avg, Count, Min, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .forms import ReviewForm, SpotForm
from .geo import DEFAULT_CENTER, WMSU_COORDS, annotate_distance, within_radius
from .icons import ICONS
from .models import Amenity, Mood, Review, Spot

# Only staff (the superuser / admins) can edit or delete spots from the site.
staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/admin/login/')

# Where the map jumps to for each area chip (approximate centers).
AREA_CENTERS = {
    'wmsu': {'label': 'WMSU Area', 'lat': 6.9128, 'lng': 122.0631},
    'ateneo': {'label': 'Ateneo Area', 'lat': 6.9068, 'lng': 122.0763},
    'paseo': {'label': 'Paseo Waterfront', 'lat': 6.9040, 'lng': 122.0720},
    'tetuan': {'label': 'Tetuan Hub', 'lat': 6.9370, 'lng': 122.0830},
}

PAGE_SIZE = 8
RADIUS_CHOICES_KM = [1, 3, 5, 10]
MAX_RADIUS_KM = 50
MAX_API_RESULTS = 200


def visible_spots(user):
    """Everyone sees approved spots; staff also see pending community submissions."""
    spots = Spot.objects.select_related('mood').prefetch_related('amenities').annotate(
        avg_rating=Avg('reviews__rating'),
        review_total=Count('reviews', distinct=True),
    )
    return spots if user.is_staff else spots.filter(is_approved=True)


# ---------------------------------------------------------------------------
# Landing page (Discover)
# ---------------------------------------------------------------------------

def home(request):
    approved = Spot.objects.filter(is_approved=True)
    reviews = Review.objects.filter(spot__is_approved=True)
    stats = {
        'spots': approved.count(),
        'reviews': reviews.count(),
        'avg_rating': reviews.aggregate(a=Avg('rating'))['a'],
        'areas': approved.exclude(area='other').values('area').distinct().count(),
    }
    top_spots = visible_spots(request.user).filter(is_approved=True).order_by(
        '-is_top_pick', '-avg_rating', '-review_total'
    )[:4]
    moods = Mood.objects.annotate(spot_total=Count('spots', filter=Q(spots__is_approved=True)))
    tales = reviews.select_related('spot').order_by('-created_at')[:2]
    return render(request, 'home.html', {
        'stats': stats, 'top_spots': top_spots, 'moods': moods, 'tales': tales,
    })


def about(request):
    return render(request, 'about.html')


# ---------------------------------------------------------------------------
# READ: browse spots as a list (search, filters, sort)
# ---------------------------------------------------------------------------

def spot_list(request):
    get = request.GET
    if get.get('view') == 'map':
        # The map now lives at /map/ - keep old links (and their filters) working.
        params = get.copy()
        params.pop('view', None)
        url = reverse('map_explorer')
        return redirect(f'{url}?{params.urlencode()}' if params else url)

    spots = visible_spots(request.user)

    q = get.get('q', '').strip()
    if q:
        spots = spots.filter(Q(name__icontains=q) | Q(address__icontains=q) | Q(description__icontains=q))

    mood = get.get('mood', '')
    if mood.isdigit():
        spots = spots.filter(mood_id=int(mood))

    category = get.get('category', '')
    if category in dict(Spot.CATEGORY_CHOICES):
        spots = spots.filter(category=category)

    area = get.get('area', '')
    if area in dict(Spot.AREA_CHOICES):
        spots = spots.filter(area=area)

    budget = get.get('budget', '')
    if budget.isdigit():
        spots = spots.filter(starts_at_price__lte=int(budget))

    distance = get.get('distance', '')
    if distance.isdigit():
        spots = spots.filter(distance_from_wmsu_m__lte=int(distance))

    chosen_amenities = [a for a in get.getlist('amenity') if a]
    for code in chosen_amenities:
        spots = spots.filter(amenities__code=code)       # must have ALL chosen amenities
    if get.get('open24') == '1':
        spots = spots.filter(is_24_hours=True)

    sort = get.get('sort', 'rating')
    if sort == 'nearest':
        spots = spots.filter(distance_from_wmsu_m__isnull=False).order_by('distance_from_wmsu_m')
    elif sort == 'cheapest':
        spots = spots.order_by('starts_at_price', 'name')
    elif sort == 'newest':
        spots = spots.order_by('-created_at')
    else:
        sort = 'rating'
        spots = spots.order_by('-avg_rating', '-review_total', 'name')

    total = spots.count()
    limit = PAGE_SIZE
    if get.get('limit', '').isdigit():
        limit = min(max(int(get['limit']), PAGE_SIZE), 200)
    shown = list(spots[:limit])

    curated = Spot.objects.filter(is_approved=True)
    curated_total = curated.count()

    # Query string without limit so "Load more" keeps the filters
    base_params = get.copy()
    base_params.pop('limit', None)

    return render(request, 'spot_list.html', {
        'spots': shown, 'total': total,
        'moods': Mood.objects.all(), 'amenities': Amenity.objects.all(),
        'area_choices': Spot.AREA_CHOICES, 'category_choices': Spot.CATEGORY_CHOICES,
        'filter_query': base_params.urlencode(),
        'map_query': base_params.urlencode(),
        'next_limit': limit + PAGE_SIZE, 'has_more': total > len(shown),
        'sel': {
            'q': q, 'mood': mood, 'category': category, 'area': area, 'budget': budget,
            'distance': distance, 'amenities': chosen_amenities,
            'open24': get.get('open24') == '1', 'sort': sort,
        },
        'curated_total': curated_total,
        'wifi_pct': round(100 * curated.filter(amenities__code='wifi').distinct().count() / curated_total) if curated_total else 0,
        'min_price': curated.aggregate(m=Min('starts_at_price'))['m'],
        'pending_count': Spot.objects.filter(is_approved=False).count() if request.user.is_staff else 0,
    })


def spot_detail(request, id):
    spot = get_object_or_404(visible_spots(request.user), id=id)
    return render(request, 'spot_detail.html', {
        'spot': spot, 'reviews': spot.reviews.all(), 'review_form': ReviewForm(),
    })


# ---------------------------------------------------------------------------
# MAP EXPLORER + JSON API ("nearby" search with the Haversine formula)
# ---------------------------------------------------------------------------

def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_map_filters(get):
    """Reads ?lat=&lng=&radius=&category=&amenity=&mood=&q= and returns (filters, errors)."""
    errors = []
    lat, lng = _float(get.get('lat')), _float(get.get('lng'))
    if (get.get('lat') or get.get('lng')) and (lat is None or lng is None):
        errors.append('lat and lng must both be numbers.')
        lat = lng = None
    elif lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
        errors.append('lat must be between -90 and 90, lng between -180 and 180.')
        lat = lng = None

    radius = _float(get.get('radius'))
    if get.get('radius') and (radius is None or not 0 < radius <= MAX_RADIUS_KM):
        errors.append(f'radius must be a number of km between 0 and {MAX_RADIUS_KM}.')
        radius = None

    category = get.get('category', '')
    if category not in dict(Spot.CATEGORY_CHOICES):
        category = ''

    mood = get.get('mood', '')
    q = get.get('q', '').strip()[:100]

    return {
        'lat': lat, 'lng': lng, 'radius': radius, 'category': category,
        'amenities': [a for a in get.getlist('amenity') if a][:10],
        'mood': int(mood) if mood.isdigit() else None,
        'q': q,
    }, errors


def find_spots(user, f):
    """Applies the map filters. Returns spots that have coordinates, nearest first when located."""
    spots = visible_spots(user).filter(latitude__isnull=False, longitude__isnull=False)
    if f['category']:
        spots = spots.filter(category=f['category'])
    for code in f['amenities']:
        spots = spots.filter(amenities__code=code)
    if f['mood']:
        spots = spots.filter(mood_id=f['mood'])
    if f['q']:
        spots = spots.filter(Q(name__icontains=f['q']) | Q(address__icontains=f['q']))

    if f['lat'] is not None:
        if f['radius']:
            spots = within_radius(spots, f['lat'], f['lng'], f['radius'])
        else:
            spots = annotate_distance(spots, f['lat'], f['lng']).order_by('distance_km')
    else:
        spots = spots.order_by('-is_top_pick', '-avg_rating', 'name')
    return spots[:MAX_API_RESULTS]


def _distance_text(km):
    if km is None:
        return ''
    return f'{round(km * 1000)} m away' if km < 1 else f'{km:.1f} km away'


def serialize_spot(spot):
    """Plain dict for the JSON API / the map page. Text is escaped by the front end (textContent)."""
    km = getattr(spot, 'distance_km', None)
    return {
        'id': spot.id,
        'name': spot.name,
        'address': spot.address,
        'lat': spot.latitude,
        'lng': spot.longitude,
        'category': {
            'code': spot.category, 'label': spot.get_category_display(),
            'icon': spot.category_icon, 'color': spot.category_color,
        },
        'mood': {'name': spot.mood.name, 'pastel': spot.mood.pastel},
        'image': spot.image_src or '',
        'price': {'starts_at': f'{spot.starts_at_price:.0f}', 'level': spot.price_level},
        'hours': spot.hours_label(),
        'open_now': spot.is_open_now(),
        'rating': round(spot.avg_rating, 1) if getattr(spot, 'avg_rating', None) else None,
        'reviews': getattr(spot, 'review_total', 0),
        'amenities': [{'code': a.code, 'name': a.name, 'icon': a.icon} for a in spot.amenities.all()],
        'wifi_mbps': spot.wifi_speed_mbps,
        'distance_km': round(km, 2) if km is not None else None,
        'distance_text': _distance_text(km),
        'wmsu_text': spot.distance_label(),
        'is_approved': spot.is_approved,
        'url': reverse('spot_detail', args=[spot.id]),
        # Opens walking directions from the visitor's current location (no API key needed)
        'directions': (f'https://www.google.com/maps/dir/?api=1&destination='
                       f'{spot.latitude},{spot.longitude}&travelmode=walking'),
    }


@require_GET
def spots_api(request):
    """GET /api/spots/?lat=6.91&lng=122.06&radius=3&category=cafe&amenity=wifi&amenity=aircon"""
    filters, errors = parse_map_filters(request.GET)
    if errors:
        return JsonResponse({'errors': errors}, status=400)
    spots = [serialize_spot(s) for s in find_spots(request.user, filters)]
    return JsonResponse({
        'count': len(spots),
        'origin': {'lat': filters['lat'], 'lng': filters['lng']} if filters['lat'] is not None else None,
        'radius_km': filters['radius'] if filters['lat'] is not None else None,
        'spots': spots,
    })


def map_explorer(request):
    """Full-screen map. The first batch of spots is embedded as JSON; filters re-query /api/spots/."""
    filters, _errors = parse_map_filters(request.GET)   # bad values are simply ignored here
    spots = [serialize_spot(s) for s in find_spots(request.user, filters)]
    return render(request, 'map.html', {
        'initial': {
            'spots': spots,
            'filters': filters,
            'api_url': reverse('spots_api'),
            'default_center': DEFAULT_CENTER,
            'wmsu': WMSU_COORDS,
            'areas': AREA_CENTERS,
            'icons': ICONS,      # same line icons as the templates (core/icons.py)
        },
        'categories': [
            {'code': code, 'label': label, **Spot.CATEGORY_STYLE[code]}
            for code, label in Spot.CATEGORY_CHOICES
        ],
        'amenities': Amenity.objects.all(),
        'moods': Mood.objects.all(),
        'radius_choices': RADIUS_CHOICES_KM,
        'filters': filters,
    })


# ---------------------------------------------------------------------------
# CREATE: "Submit a Tambayan Spot" (anyone can submit; admins approve)
# ---------------------------------------------------------------------------

def add_spot(request):
    if request.method == 'POST':
        form = SpotForm(request.POST, request.FILES)
        if form.is_valid():
            spot = form.save(commit=False)
            spot.is_approved = request.user.is_staff   # community submissions wait for approval
            spot.save()
            form.save_m2m()
            if spot.is_approved:
                messages.success(request, f'"{spot.name}" was added.')
                return redirect('spot_detail', id=spot.id)
            messages.success(request, 'Thanks! Your spot was submitted and will show up once it is verified.')
            return redirect('spot_list')
    else:
        form = SpotForm()
    return render(request, 'add_spot.html', {'form': form})


# ---------------------------------------------------------------------------
# UPDATE / DELETE (staff only)
# ---------------------------------------------------------------------------

@staff_required
def edit_spot(request, id):
    spot = get_object_or_404(Spot, id=id)
    if request.method == 'POST':
        form = SpotForm(request.POST, request.FILES, instance=spot)
        if form.is_valid():
            form.save()
            messages.success(request, 'Spot updated.')
            return redirect('spot_detail', id=spot.id)
    else:
        form = SpotForm(instance=spot)
    return render(request, 'edit_spot.html', {'form': form, 'spot': spot})


@staff_required
@require_POST
def delete_spot(request, id):
    spot = get_object_or_404(Spot, id=id)
    spot.delete()
    messages.success(request, f'"{spot.name}" was deleted.')
    return redirect('spot_list')


# ---------------------------------------------------------------------------
# Reviews ("Tambayan Tales")
# ---------------------------------------------------------------------------

@require_POST
def add_review(request, id):
    spot = get_object_or_404(visible_spots(request.user), id=id)
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.spot = spot
        review.save()
        messages.success(request, 'Thanks for sharing your tambayan tale!')
    else:
        messages.error(request, 'Please fill in your name, a rating and a short comment.')
    return redirect('spot_detail', id=spot.id)


@staff_required
@require_POST
def delete_review(request, id):
    review = get_object_or_404(Review, id=id)
    spot_id = review.spot_id
    review.delete()
    messages.success(request, 'Review deleted.')
    return redirect('spot_detail', id=spot_id)
