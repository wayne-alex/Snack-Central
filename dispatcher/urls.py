from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login_dispatcher, name='login-dispatcher'),
    path('dashboard/', views.dashboard_dispatcher, name='dashboard-dispatcher'),


]
