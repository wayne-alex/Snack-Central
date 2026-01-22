from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login_rider, name='login-dispatcher'),
    path('dashboard/', views.dashboard_rider, name='dashboard-dispatcher'),


]
