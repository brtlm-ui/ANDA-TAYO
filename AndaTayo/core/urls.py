from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import account_views, dashboard_views, views
from .forms import TailwindMixin
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm


class StyledPasswordResetForm(TailwindMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(TailwindMixin, SetPasswordForm):
    pass


urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),

    # Map explorer (Leaflet + OpenStreetMap) and its JSON API
    path('map/', views.map_explorer, name='map_explorer'),
    path('api/spots/', views.spots_api, name='spots_api'),

    # Spots
    path('spots/', views.spot_list, name='spot_list'),
    path('spots/add/', views.add_spot, name='add_spot'),
    path('spots/<int:id>/', views.spot_detail, name='spot_detail'),
    path('spots/<int:id>/edit/', views.edit_spot, name='edit_spot'),
    path('spots/<int:id>/delete/', views.delete_spot, name='delete_spot'),
    path('spots/<int:id>/save/', account_views.toggle_save, name='toggle_save'),

    # Reviews
    path('spots/<int:id>/review/', views.add_review, name='add_review'),
    path('reviews/<int:id>/delete/', views.delete_review, name='delete_review'),

    # Accounts (one login for every role)
    path('login/', account_views.login_view, name='login'),
    path('logout/', account_views.logout_view, name='logout'),
    path('signup/', account_views.signup_view, name='signup'),
    path('account/', account_views.account_view, name='account'),
    path('account/request-owner/', account_views.request_owner, name='request_owner'),
    path('account/saved/', account_views.saved_spots, name='saved_spots'),
    path('account/reviews/', account_views.my_reviews, name='my_reviews'),

    # Forgot password (Django's built-in flow; in development the email is printed in the runserver console)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html', form_class=StyledPasswordResetForm,
        email_template_name='accounts/password_reset_email.txt',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done')), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html', form_class=StyledSetPasswordForm,
        success_url=reverse_lazy('password_reset_complete')), name='password_reset_confirm'),
    path('password-reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),

    # Admin dashboard (admins only)
    path('dashboard/', dashboard_views.dashboard, name='dashboard'),
    path('dashboard/approvals/', dashboard_views.approvals, name='dashboard_approvals'),
    path('dashboard/approvals/spot/<int:id>/approve/', dashboard_views.approve_spot, name='approve_spot'),
    path('dashboard/approvals/spot/<int:id>/reject/', dashboard_views.reject_spot, name='reject_spot'),
    path('dashboard/approvals/owner/<int:user_id>/', dashboard_views.decide_owner_request, name='decide_owner_request'),
    path('dashboard/spots/', dashboard_views.spots, name='dashboard_spots'),
    path('dashboard/reviews/', dashboard_views.reviews, name='dashboard_reviews'),
    path('dashboard/users/', dashboard_views.users, name='dashboard_users'),
    path('dashboard/users/<int:user_id>/role/', dashboard_views.set_role, name='set_role'),

    # Spot Owner dashboard
    path('owner/', dashboard_views.owner_dashboard, name='owner_dashboard'),
]
