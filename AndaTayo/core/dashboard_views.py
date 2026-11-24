"""Admin dashboard (/dashboard/) and Spot Owner dashboard (/owner/)."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Profile, Review, Spot
from .roles import ROLE_STYLE, admin_required, get_profile, owner_required, pending_counts

User = get_user_model()

REJECT_REASONS = [
    'Duplicate of an existing spot',
    'Location or details are wrong',
    'Not a hangout or study spot',
    'Photos are not appropriate',
]


def _pending_spots():
    return (Spot.objects.filter(is_approved=False, rejected_at__isnull=True)
            .select_related('mood', 'submitted_by', 'owner').prefetch_related('amenities')
            .order_by('created_at'))


def _owner_requests():
    return (Profile.objects.filter(owner_requested_at__isnull=False).exclude(role=Profile.OWNER)
            .select_related('user').order_by('owner_requested_at'))


def _with_ratings(qs):
    return qs.annotate(avg_rating=Avg('reviews__rating'), review_total=Count('reviews', distinct=True))


def _back(request, fallback):
    """Go back to the page that posted the form (same-site paths only), else `fallback`."""
    nxt = request.POST.get('next', '')
    return redirect(nxt if nxt.startswith('/') and not nxt.startswith('//') else fallback)


def _base(active, **extra):
    counts = pending_counts()
    return {'active': active, 'pending_total': counts['spots'] + counts['owners'], 'counts': counts, **extra}


# --------------------------------------------------------------------------- ADMIN: overview

@admin_required
def dashboard(request):
    week_ago = timezone.now() - timedelta(days=7)
    counts = pending_counts()
    live = Spot.objects.filter(is_approved=True)

    by_category = live.values('category').annotate(n=Count('id')).order_by('-n')
    labels = dict(Spot.CATEGORY_CHOICES)
    top = max([c['n'] for c in by_category] or [1])

    # Recent activity, built from what the database already records
    events = []
    for s in Spot.objects.select_related('submitted_by').order_by('-created_at')[:6]:
        who = (s.submitted_by.get_full_name() or s.submitted_by.email) if s.submitted_by else 'Demo data'
        events.append({'when': s.created_at, 'icon': 'plus', 'text': f'{s.name} was added', 'who': who})
    for s in live.filter(approved_at__isnull=False).order_by('-approved_at')[:6]:
        events.append({'when': s.approved_at, 'icon': 'check', 'text': f'{s.name} went live', 'who': 'Admin'})
    for r in Review.objects.select_related('spot').order_by('-created_at')[:6]:
        events.append({'when': r.created_at, 'icon': 'chat', 'text': f'New review on {r.spot.name} ({r.rating}/5)', 'who': r.reviewer_name})
    for u in User.objects.order_by('-date_joined')[:6]:
        events.append({'when': u.date_joined, 'icon': 'user', 'text': 'New account', 'who': u.get_full_name() or u.email})
    events.sort(key=lambda e: e['when'], reverse=True)

    return render(request, 'dashboard/overview.html', _base(
        'overview',
        stats=[
            {'label': 'Pending approvals', 'value': counts['spots'] + counts['owners'], 'icon': 'inbox', 'bg': 'var(--butter)',
             'note': f"{counts['spots']} spot{'s' if counts['spots'] != 1 else ''}, {counts['owners']} owner request{'s' if counts['owners'] != 1 else ''}"},
            {'label': 'Live spots', 'value': live.count(), 'icon': 'pin', 'bg': '#a9d8ff', 'note': 'Approved and visible'},
            {'label': 'Reviews this week', 'value': Review.objects.filter(created_at__gte=week_ago).count(),
             'icon': 'chat', 'bg': '#ffa8a8', 'note': f'{Review.objects.count()} in total'},
            {'label': 'Users', 'value': User.objects.count(), 'icon': 'users', 'bg': '#d9ccff',
             'note': f"{User.objects.filter(date_joined__gte=week_ago).count()} joined this week"},
        ],
        pending_spots=_pending_spots()[:5],
        owner_requests=_owner_requests()[:5],
        activity=events[:8],
        by_category=[{'label': labels.get(c['category'], c['category']), 'n': c['n'],
                      'color': Spot.CATEGORY_STYLE.get(c['category'], Spot.CATEGORY_STYLE['other'])['color'],
                      'pct': round(100 * c['n'] / top)} for c in by_category],
    ))


# --------------------------------------------------------------------------- ADMIN: approvals

@admin_required
def approvals(request):
    show = request.GET.get('show', 'all')
    return render(request, 'dashboard/approvals.html', _base(
        'approvals', show=show,
        pending_spots=_pending_spots() if show in ('all', 'spots') else [],
        owner_requests=_owner_requests() if show in ('all', 'owners') else [],
        reject_reasons=REJECT_REASONS,
    ))


@admin_required
@require_POST
def approve_spot(request, id):
    spot = get_object_or_404(Spot, id=id)
    spot.is_approved, spot.approved_at = True, timezone.now()
    spot.rejected_at, spot.rejection_reason = None, ''
    # a Spot Owner who submitted their own place manages it from now on
    if spot.owner_id is None and spot.submitted_by and get_profile(spot.submitted_by).role == Profile.OWNER:
        spot.owner = spot.submitted_by
    spot.save()
    messages.success(request, f'"{spot.name}" is now live.')
    return _back(request, 'dashboard_approvals')


@admin_required
@require_POST
def reject_spot(request, id):
    spot = get_object_or_404(Spot, id=id)
    reason = (request.POST.get('reason') or '').strip()
    note = (request.POST.get('note') or '').strip()
    full = '. '.join(part for part in (reason, note) if part)[:200] or 'Not approved'
    spot.is_approved, spot.rejected_at, spot.rejection_reason = False, timezone.now(), full
    spot.save(update_fields=['is_approved', 'rejected_at', 'rejection_reason'])
    messages.success(request, f'"{spot.name}" was rejected. The submitter will see your reason.')
    return _back(request, 'dashboard_approvals')


@admin_required
@require_POST
def decide_owner_request(request, user_id):
    profile = get_object_or_404(Profile, user_id=user_id)
    who = profile.user.get_full_name() or profile.user.email
    if request.POST.get('decision') == 'approve':
        profile.role = Profile.OWNER
        messages.success(request, f'{who} is now a Spot Owner.')
    else:
        messages.success(request, f"{who}'s Spot Owner request was declined.")
    profile.owner_requested_at = None
    profile.save(update_fields=['role', 'owner_requested_at'])
    return _back(request, 'dashboard_approvals')


# --------------------------------------------------------------------------- ADMIN: spots

@admin_required
def spots(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', 'all')
    category = request.GET.get('category', '')
    qs = _with_ratings(Spot.objects.select_related('mood', 'owner')).order_by('name')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if status == 'live':
        qs = qs.filter(is_approved=True)
    elif status == 'pending':
        qs = qs.filter(is_approved=False, rejected_at__isnull=True)
    elif status == 'rejected':
        qs = qs.filter(rejected_at__isnull=False)
    if category in dict(Spot.CATEGORY_CHOICES):
        qs = qs.filter(category=category)
    return render(request, 'dashboard/spots.html', _base(
        'spots', spots=qs, q=q, status=status, category=category, category_choices=Spot.CATEGORY_CHOICES,
    ))


# --------------------------------------------------------------------------- ADMIN: reviews

@admin_required
def reviews(request):
    q = request.GET.get('q', '').strip()
    qs = Review.objects.select_related('spot', 'user').order_by('-created_at')
    if q:
        qs = qs.filter(Q(comment__icontains=q) | Q(spot__name__icontains=q) | Q(reviewer_name__icontains=q))
    return render(request, 'dashboard/reviews.html', _base('reviews', reviews=qs[:200], q=q))


# --------------------------------------------------------------------------- ADMIN: users & roles

@admin_required
def users(request):
    q = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')
    qs = User.objects.select_related('profile').order_by('-date_joined')
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q))
    if role == Profile.ADMIN:
        qs = qs.filter(is_staff=True)
    elif role in (Profile.OWNER, Profile.STUDENT):
        qs = qs.filter(is_staff=False, profile__role=role)
    return render(request, 'dashboard/users.html', _base(
        'users', users=qs[:200], q=q, role=role, role_choices=Profile.ROLE_CHOICES, role_style=ROLE_STYLE,
    ))


@admin_required
@require_POST
def set_role(request, user_id):
    target = get_object_or_404(User, id=user_id)
    new_role = request.POST.get('role')
    if new_role not in dict(Profile.ROLE_CHOICES):
        messages.error(request, 'Unknown role.')
    elif target == request.user:
        messages.error(request, "You can't change your own role. Ask another admin.")
    elif target.is_superuser:
        messages.error(request, 'Superusers are managed from the command line / Django admin.')
    else:
        profile = get_profile(target)
        profile.role = new_role
        profile.owner_requested_at = None
        profile.save(update_fields=['role', 'owner_requested_at'])
        target.is_staff = new_role == Profile.ADMIN      # Admin role = staff, nothing else is
        target.save(update_fields=['is_staff'])
        messages.success(request, f'{target.get_full_name() or target.email} is now {profile.get_role_display()}.')
    return _back(request, 'dashboard_users')


# --------------------------------------------------------------------------- SPOT OWNER

@owner_required
def owner_dashboard(request):
    user = request.user
    my_spots = _with_ratings(Spot.objects.filter(owner=user).select_related('mood')).order_by('name')
    submissions = (Spot.objects.filter(submitted_by=user).filter(Q(is_approved=False))
                   .exclude(owner=user).order_by('-created_at'))
    latest = Review.objects.filter(spot__owner=user).select_related('spot').order_by('-created_at')[:6]
    return render(request, 'owner/dashboard.html', {
        'active': 'owner', 'my_spots': my_spots, 'submissions': submissions, 'latest_reviews': latest,
    })
