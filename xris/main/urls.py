from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('xmpr/', views.live_radar, name='live_radar'),
    path('home/', views.home, name='home'),
    path('activity/', views.activity, name='activity'),
    path('profile/', views.profile, name='profile'),
]
