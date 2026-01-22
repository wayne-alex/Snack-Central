# admin.py
from django.contrib import admin

from .models import (
    User, Category, MenuItem, Cart, CartItem,
    DeliveryLocation, Order, OrderItem, Rider,
    Notification, Favorite
)

# You can register multiple models at once by passing them in a list
admin.site.register([
    User, Category, MenuItem, Cart, CartItem,
    DeliveryLocation, Order, OrderItem, Rider,
    Notification, Favorite
])
