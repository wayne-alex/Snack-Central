import json
import uuid

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt

from Customer.models import Order, Category, MenuItem, OrderItem, Cart, CartItem, DeliveryLocation

User = get_user_model()


def send_mail(name, to, subject, email):
    url = "https://node-mailer-brown.vercel.app/send-email"
    email_data = {
        "name": name,
        "to": to,
        "subject": subject,
        "html_message": email,
    }

    headers = {
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=email_data, headers=headers)
        response.raise_for_status()

        print("Response:", response.json())

    except requests.exceptions.RequestException as e:
        print("Error:", str(e))


def generate_order_id():
    return f"ORD-{uuid.uuid4().hex[:5].upper()}"


# Create your views here.
def landing(request):
    return render(request, 'Landing.html')


def auth(request):
    return render(request, 'auth.html')


def loginUser(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    data = json.loads(request.body)
    phone = data.get('phone')
    password = data.get('password')

    user = authenticate(request, username=phone, password=password)

    if user:
        login(request, user)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid credentials'}, status=401)


def signup(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    data = json.loads(request.body)

    phone = data.get("phone")
    email = data.get("email")
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    password = data.get("password")

    if not all([phone, email, first_name, last_name, password]):
        return JsonResponse({"error": "All fields are required"}, status=400)

    if User.objects.filter(phone=phone).exists():
        return JsonResponse({"error": "Phone number already registered"}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=400)

    user = User.objects.create_user(
        phone=phone,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )

    return JsonResponse(
        {"message": "Account created successfully"},
        status=201
    )


def forgetpassword(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    data = json.loads(request.body)
    email = data.get('email')

    try:
        user = User.objects.get(email=email)
        send_mail(
            name='Snack Central',
            subject='🔐 Reset Your Password – Snack Central',
            to=email,
            email=render_to_string('forgetpassword_email.html', {
                "fullname": user.first_name,
                "reset_link": user,
            })

        )
        return JsonResponse({'success': True})
    except User.DoesNotExist:
        return JsonResponse({'error': 'Email not found'}, status=404)


@login_required
def dashboard(request):
    user = request.user

    orders = (
        Order.objects.filter(user=user)
        .prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('item'))
        )
        .order_by('-placed_at')
    )

    loyalty_points = getattr(user, 'loyalty_points', 0)

    recent_order = orders.first()

    active_order = (
        orders.filter(status__in=['pending', 'preparing', 'out_for_delivery'])
        .first()
    )

    categories = Category.objects.filter(
        is_active=True
    ).prefetch_related(
        Prefetch(
            'items',
            queryset=MenuItem.objects.filter(
                is_active=True,
                in_stock=True
            )
        )
    )

    return render(request, 'dashboard.html', {
        'orders': orders,
        'points': loyalty_points,
        'recent_order': recent_order,
        'active_order': active_order,
        'categories': categories
    })


@login_required
def checkout(request):
    # DEFAULT LOCATION
    # CART ITEMS
    default_location = DeliveryLocation.objects.filter(user=request.user).first()
    if default_location:
        cart = get_or_create_cart(request.user)
        items = cart_response1(cart)
        return render(request, 'checkout.html', {'location': default_location, 'cart': items})

    else:
        cart = get_or_create_cart(request.user)
        items = cart_response1(cart)
        return render(request, 'checkout.html', {'cart': items})


def resetpassword(request):
    return render(request, 'resetpassword.html')


@csrf_exempt
@login_required
def checkout_order(request):
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Invalid request"},
            status=400
        )

    data = json.loads(request.body)

    location = data.get("location")
    payment_method = data.get("payment_method")
    delivery_note = data.get("delivery_note", "")

    # 🛒 Get cart
    cart = get_or_create_cart(request.user)

    cart_items = CartItem.objects.select_related('item').filter(cart=cart)

    if not cart_items.exists():
        return JsonResponse(
            {"success": False, "error": "Cart is empty"},
            status=400
        )

    # 📍 Delivery location (ONE per user)
    delivery_location, _ = DeliveryLocation.objects.get_or_create(
        user=request.user,
        defaults={"name": "Main Gate"}
    )

    if location != "main-gate":
        delivery_location.name = location
    else:
        delivery_location.name = "Main Gate"

    delivery_location.save()

    # 💰 Calculate subtotal from cart items (source of truth)
    subtotal = sum(
        item.item.price * item.quantity
        for item in cart_items
    )

    with transaction.atomic():
        # 1️⃣ Create order
        order = Order.objects.create(
            order_id=generate_order_id(),
            user=request.user,
            payment_method=payment_method,
            subtotal=subtotal,
            delivery_fee=0,
            total_price=subtotal,
            delivery_location=delivery_location,
            delivery_notes=delivery_note,
        )

        # 2️⃣ Create order items (CRITICAL FIX)
        order_items = [
            OrderItem(
                order=order,
                item=cart_item.item,
                quantity=cart_item.quantity,
                price_at_order=cart_item.item.price
            )
            for cart_item in cart_items
        ]

        OrderItem.objects.bulk_create(order_items)

        # 3️⃣ Clear cart
        cart_items.delete()

    return JsonResponse({
        "success": True,
        "order_id": order.order_id
    })


def order_details(request, order_id):
    try:
        order = Order.objects.prefetch_related('items__item').get(id=order_id, user=request.user)
        items = [
            {
                "name": oi.item.name,
                "emoji": oi.item.emoji,
                "quantity": oi.quantity,
                "price": oi.price_at_order,
            }
            for oi in order.items.all()
        ]
        return JsonResponse({
            "success": True,
            "order": {
                "customer_name": order.user.get_full_name(),
                "order_id": order.order_id,
                "status": order.get_status_display(),
                "placed_at": order.placed_at.strftime("%b %d, %Y, %I:%M %p"),
                "delivery_location": order.delivery_location.name if order.delivery_location else "",
                "payment_method": order.get_payment_method_display(),
                "items": items,
                "total_price": str(order.total_price),
            }
        })
    except Order.DoesNotExist:
        return JsonResponse({"success": False, "error": "Order not found"}, status=404)


def cart_response(cart):
    items = []
    for ci in cart.items.select_related('item'):
        items.append({
            'id': ci.item.id,
            'name': ci.item.name,
            'price': float(ci.item.price),
            'quantity': ci.quantity,
            'emoji': ci.item.emoji,
            'total': float(ci.total_price)
        })

    return JsonResponse({
        'items': items,
        'total_items': cart.total_items,
        'subtotal': float(cart.subtotal)
    })


def cart_response1(cart):
    items = []
    for ci in cart.items.select_related('item'):
        items.append({
            'id': ci.item.id,
            'name': ci.item.name,
            'price': float(ci.item.price),
            'quantity': ci.quantity,
            'emoji': ci.item.emoji,
            'total': float(ci.total_price)
        })

    return {
        'items': items,
        'total_items': cart.total_items,
        'subtotal': float(cart.subtotal)
    }


@login_required
@csrf_exempt
def add_to_cart(request):
    data = json.loads(request.body)
    item_id = data.get('item_id')

    cart = get_or_create_cart(request.user)
    menu_item = MenuItem.objects.get(id=item_id)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        item=menu_item
    )

    if not created:
        cart_item.quantity += 1
    cart_item.save()

    return cart_response(cart)


@login_required
@csrf_exempt
def update_cart_item(request):
    data = json.loads(request.body)
    item_id = data.get('item_id')
    change = int(data.get('change'))

    cart = get_or_create_cart(request.user)

    try:
        cart_item = CartItem.objects.get(cart=cart, item_id=item_id)
        cart_item.quantity += change

        if cart_item.quantity <= 0:
            cart_item.delete()
        else:
            cart_item.save()
    except CartItem.DoesNotExist:
        pass

    return cart_response(cart)


def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@login_required
def get_cart(request):
    cart = get_or_create_cart(request.user)
    return cart_response(cart)
