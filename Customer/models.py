import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, phone, email, password=None, **extra_fields):
        if not phone:
            raise ValueError('Phone number is required')
        if not email:
            raise ValueError('Email is required')

        email = self.normalize_email(email)
        user = self.model(phone=phone, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone_regex = RegexValidator(
        regex=r'^07\d{8}$',
        message="Phone number must be in format: '07XXXXXXXX'"
    )

    phone = models.CharField(
        max_length=10,
        validators=[phone_regex],
        unique=True,
        primary_key=True
    )
    email = models.EmailField(max_length=255, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)

    # User Stats
    total_orders = models.PositiveIntegerField(default=0)
    loyalty_points = models.PositiveIntegerField(default=0)

    # Settings
    notification_enabled = models.BooleanField(default=True)

    # Authentication
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def initials(self):
        return (
                (self.first_name[0] if self.first_name else "").upper() +
                (self.last_name[0] if self.last_name else "").upper()
        )


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Set expiry only on creation (15 minutes)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)

    def is_valid(self):
        return (
                not self.is_used
                and timezone.now() < self.expires_at
        )

    def __str__(self):
        return f"Password reset token for {self.user}"


class Category(models.Model):
    name = models.CharField(max_length=50)
    emoji = models.CharField(max_length=10, default='🍔')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    # Display
    emoji = models.CharField(max_length=10, default='🍔')

    # Stats
    times_ordered = models.PositiveIntegerField(default=0)
    average_rating = models.FloatField(default=4.5, validators=[MinValueValidator(0), MaxValueValidator(5)])

    # Stock
    in_stock = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())

    def __str__(self):
        return f"Cart for {self.user.get_full_name()}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return self.item.price * self.quantity

    class Meta:
        unique_together = ['cart', 'item']

    def __str__(self):
        return f"{self.quantity}x {self.item.name}"


class DeliveryLocation(models.Model):
    """Predefined delivery locations at EAVI campus"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=100,blank=True)  # e.g., "Block A - Room 204"
    building = models.CharField(max_length=50,blank=True)  # e.g., "Block A"
    room = models.CharField(max_length=20, blank=True)  # e.g., "204"
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.name} - {self.user.get_full_name()}"


class Order(models.Model):
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('cash', 'Cash on Delivery'),
    ]

    # Order Identification
    order_id = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')

    # Status
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_completed = models.BooleanField(default=False)

    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Delivery
    delivery_location = models.ForeignKey(DeliveryLocation, on_delete=models.SET_NULL, null=True)
    delivery_notes = models.TextField(blank=True)

    # Timing
    placed_at = models.DateTimeField(auto_now_add=True)
    estimated_delivery = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    # Rider
    assigned_rider = models.ForeignKey('Rider', on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ['-placed_at']

    def __str__(self):
        return f"{self.order_id} - {self.user.get_full_name()}"


    @property
    def is_active(self):
        return self.status in ['pending', 'confirmed', 'preparing', 'out_for_delivery']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total_price(self):
        return self.price_at_order * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.item.name}"


class Rider(models.Model):
    RIDER_STATUS = [
        ('available', 'Available'),
        ('busy', 'On Delivery'),
        ('offline', 'Offline'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rider_profile')
    rider_id = models.CharField(max_length=20, unique=True)

    # Status
    status = models.CharField(max_length=20, choices=RIDER_STATUS, default='offline')

    # Location (for real-time tracking)
    current_latitude = models.FloatField(blank=True, null=True)
    current_longitude = models.FloatField(blank=True, null=True)

    # Stats
    total_deliveries = models.PositiveIntegerField(default=0)
    average_rating = models.FloatField(default=5.0)

    # Availability
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rider {self.rider_id} - {self.user.get_full_name()}"

    @property
    def is_available(self):
        return self.status == 'available' and self.is_active


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'item']
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.get_full_name()}'s favorite: {self.item.name}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('order_update', 'Order Update'),
        ('promotion', 'Promotion'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()

    # Read Status
    is_read = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"
