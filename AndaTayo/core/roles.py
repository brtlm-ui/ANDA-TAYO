"""
Roles: Student (default), Spot Owner, Admin.

- Admin  = Django `is_staff` (kept in sync with Profile.role by the Users & roles page).
- Owner  = Profile.role == 'owner'  -> manages the spots where Spot.owner is them.
- Student = everyone else.

Use the decorators below on views; never rely on hiding buttons alone.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from .models import Profile, Spot

ROLE_STYLE = {
    Profile.STUDENT: {'label': 'Student', 'badge': '#d9ccff', 'icon': 'user'},
    Profile.OWNER: {'label': 'Spot Owner', 'badge': '#a9d8ff', 'icon': 'store'},
    Profile.ADMIN: {'label': 'Admin', 'badge': '#ffe24a', 'icon': 'shield'},
}


def get_profile(user):
    profile, _ = Profile.objects.get_or_create(
        user=user, defaults={'role': Profile.ADMIN if user.is_staff else Profile.STUDENT},
    )
    return profile


def role_of(user):
    if not user.is_authenticated:
        return None
    if user.is_staff:
        return Profile.ADMIN
    role = get_profile(user).role
    return Profile.STUDENT if role == Profile.ADMIN else role   # "admin" without is_staff = no admin rights


def is_admin(user):
    return user.is_authenticated and user.is_active and user.is_staff


def is_owner(user):
    return role_of(user) == Profile.OWNER


def can_manage_spot(user, spot):
    """Admins manage every spot; Spot Owners manage the spots assigned to them."""
    return is_admin(user) or (is_owner(user) and spot.owner_id == user.id)


def landing_url(user):
    """Where each role goes after logging in (when there's no ?next=)."""
    role = role_of(user)
    if role == Profile.ADMIN:
        return reverse('dashboard')
    if role == Profile.OWNER:
        return reverse('owner_dashboard')
    return reverse('home')


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return login_required(wrapper)


def owner_required(view):
    """Spot Owners and Admins."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not (is_owner(request.user) or is_admin(request.user)):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return login_required(wrapper)


def pending_counts():
    return {
        'spots': Spot.objects.filter(is_approved=False, rejected_at__isnull=True).count(),
        'owners': Profile.objects.filter(owner_requested_at__isnull=False).exclude(role=Profile.OWNER).count(),
    }


def initials(user):
    name = user.get_full_name().strip() or user.email or user.username
    parts = [p for p in name.replace('@', ' ').split() if p]
    return ''.join(p[0] for p in parts[:2]).upper() or '?'


def account_menu(user):
    """Everything the header avatar menu needs for the signed-in user."""
    role = role_of(user)
    style = ROLE_STYLE[role]
    links = []
    if role == Profile.ADMIN:
        counts = pending_counts()
        links = [
            {'label': 'Admin dashboard', 'icon': 'grid', 'url': reverse('dashboard')},
            {'label': 'Pending approvals', 'icon': 'inbox', 'url': reverse('dashboard_approvals'),
             'badge': counts['spots'] + counts['owners']},
        ]
    elif role == Profile.OWNER:
        links = [
            {'label': 'My spots', 'icon': 'store', 'url': reverse('owner_dashboard')},
            {'label': 'Add a spot', 'icon': 'plus', 'url': reverse('add_spot')},
        ]
    links += [
        {'label': 'Saved spots', 'icon': 'bookmark', 'url': reverse('saved_spots')},
        {'label': 'My reviews', 'icon': 'chat', 'url': reverse('my_reviews')},
        {'label': 'Account settings', 'icon': 'settings', 'url': reverse('account')},
    ]
    return {
        'name': user.get_full_name().strip() or user.email or user.username,
        'first_name': (user.first_name or user.email or user.username).split()[0].split('@')[0],
        'email': user.email,
        'initials': initials(user),
        'role': role,
        'role_label': style['label'],
        'badge_bg': style['badge'],
        'role_icon': style['icon'],
        'links': links,
    }
