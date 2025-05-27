from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    path('', views.SubscriptionView, name='subscription'),
    path('checkout/', views.CheckoutView, name='checkout'),
    path('customer/', views.CustomerView, name='customer'),
    path('webhook/', views.WebhookView, name='webhook'),
]