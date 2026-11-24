"""Accounts: log in / sign up / log out, account settings, saved spots and "My reviews"."""
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import AccountForm, LoginForm, SignupForm, StyledPasswordChangeForm
from .models import Bookmark, Profile, Spot
from .roles import get_profile, landing_url, role_of


def _safe_next(request):
    nxt = request.POST.get('next') or request.GET.get('next') or ''
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return ''


def _hero(name):
    spot = Spot.objects.filter(name=name).first()
    return spot.image_src if spot else ''


# --------------------------------------------------------------------------- log in / out / sign up

def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request) or landing_url(request.user))
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.user
        login(request, user)
        if not form.cleaned_data.get('remember'):
            request.session.set_expiry(0)          # log out when the browser closes
        messages.success(request, f'Welcome back, {user.first_name or user.email}!')
        return redirect(_safe_next(request) or landing_url(user))
    return render(request, 'accounts/login.html', {
        'form': form, 'next': _safe_next(request), 'hero_photo': _hero('Paseo del Mar'),
    })


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, 'You are logged out. See you at the next tambayan!')
    return redirect('home')


def signup_view(request):
    if request.user.is_authenticated:
        return redirect(landing_url(request.user))
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        if form.cleaned_data.get('wants_owner'):
            profile = get_profile(user)
            profile.owner_requested_at = timezone.now()
            profile.save(update_fields=['owner_requested_at'])
        login(request, user, backend='core.backends.EmailBackend')
        if form.cleaned_data.get('wants_owner'):
            messages.success(request, 'Account created! Your Spot Owner request was sent to the admins.')
        else:
            messages.success(request, f'Welcome to Anda Tayo, {user.first_name}!')
        return redirect(_safe_next(request) or 'home')
    return render(request, 'accounts/signup.html', {
        'form': form, 'next': _safe_next(request), 'hero_photo': _hero('Dennis Coffee Garden'),
    })


# --------------------------------------------------------------------------- account settings

@login_required
def account_view(request):
    profile = get_profile(request.user)
    account_form = AccountForm(request.user)
    password_form = StyledPasswordChangeForm(request.user)

    if request.method == 'POST' and 'save_profile' in request.POST:
        account_form = AccountForm(request.user, request.POST)
        if account_form.is_valid():
            account_form.save()
            messages.success(request, 'Your details were updated.')
            return redirect('account')
    elif request.method == 'POST' and 'change_password' in request.POST:
        password_form = StyledPasswordChangeForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)    # stay logged in after changing the password
            messages.success(request, 'Your password was changed.')
            return redirect('account')

    return render(request, 'accounts/account.html', {
        'account_form': account_form, 'password_form': password_form,
        'profile': profile, 'role': role_of(request.user),
    })


@login_required
@require_POST
def request_owner(request):
    profile = get_profile(request.user)
    if role_of(request.user) == Profile.STUDENT and not profile.owner_requested_at:
        profile.owner_requested_at = timezone.now()
        profile.save(update_fields=['owner_requested_at'])
        messages.success(request, 'Request sent! An admin will review it soon.')
    return redirect('account')


# --------------------------------------------------------------------------- saved spots & my reviews

@login_required
def saved_spots(request):
    spots = (Spot.objects.filter(bookmarks__user=request.user, is_approved=True)
             .select_related('mood').prefetch_related('amenities')
             .annotate(avg_rating=Avg('reviews__rating'), review_total=Count('reviews', distinct=True))
             .order_by('-bookmarks__created_at'))
    return render(request, 'accounts/saved.html', {'spots': spots})


@login_required
@require_POST
def toggle_save(request, id):
    spot = get_object_or_404(Spot, id=id, is_approved=True)
    bookmark, created = Bookmark.objects.get_or_create(user=request.user, spot=spot)
    if created:
        messages.success(request, f'Saved "{spot.name}" to your spots.')
    else:
        bookmark.delete()
        messages.success(request, f'Removed "{spot.name}" from your saved spots.')
    nxt = _safe_next(request)
    return redirect(nxt) if nxt else redirect('spot_detail', id=spot.id)


@login_required
def my_reviews(request):
    reviews = request.user.reviews.select_related('spot').order_by('-created_at')
    return render(request, 'accounts/my_reviews.html', {'reviews': reviews})
