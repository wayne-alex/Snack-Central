from django.urls import path

from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('auth/', views.auth, name='auth'),
    path('auth/login/', views.loginUser, name='login'),
    path('auth/signup/', views.signup, name='signup'),
    path('auth/forgot-password/', views.forgetpassword, name='forgot_password'),
    path('auth/resetpassword/', views.resetpassword, name='resetPassword'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/checkout/', views.checkout_order, name='checkout_order'),
    path('order/details/<int:order_id>/', views.order_details, name='order_details'),
    path('cart/', views.get_cart, name='get_cart'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/', views.update_cart_item, name='update_cart_item'),

]
