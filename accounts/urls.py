from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='api_login'),
    path('logout/', views.logout_view, name='api_logout'),
    path('me/', views.me_view, name='api_me'),
    path('pages-map/', views.pages_map_view, name='pages_map'),
    path('users/', views.user_list_create, name='user_list_create'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
]
