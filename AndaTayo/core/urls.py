from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),

    # Map explorer (Leaflet + OpenStreetMap) and its JSON API
    path('map/', views.map_explorer, name='map_explorer'),
    path('api/spots/', views.spots_api, name='spots_api'),

    # Spots (CRUD)
    path('spots/', views.spot_list, name='spot_list'),
    path('spots/add/', views.add_spot, name='add_spot'),
    path('spots/<int:id>/', views.spot_detail, name='spot_detail'),
    path('spots/<int:id>/edit/', views.edit_spot, name='edit_spot'),
    path('spots/<int:id>/delete/', views.delete_spot, name='delete_spot'),

    # Reviews
    path('spots/<int:id>/review/', views.add_review, name='add_review'),
    path('reviews/<int:id>/delete/', views.delete_review, name='delete_review'),
]
