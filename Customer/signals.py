from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from Customer.models import Cart, Order, Notification, OrderItem


@receiver(post_save, sender=User)
def create_user_cart(sender, instance, created, **kwargs):
    """Automatically create a cart when user registers"""
    if created:
        Cart.objects.create(user=instance)


@receiver(post_save, sender=Order)
def update_user_stats_on_delivery(sender, instance, **kwargs):
    """Update user stats when order is delivered"""
    if instance.status == 'delivered' and instance.delivered_at:
        # Only update once
        if not hasattr(instance, '_stats_updated'):
            instance.user.total_orders += 1

            # Award loyalty points (10 points per KES 100 spent)
            points = int(instance.total_price / 100) * 10
            if points > 0:
                instance.user.loyalty_points += points

                # Create notification
                Notification.objects.create(
                    user=instance.user,
                    notification_type='order_update',
                    title='Points Earned! 🎉',
                    message=f'You earned {points} points from order {instance.order_id}'
                )

            instance.user.save()
            instance._stats_updated = True


@receiver(post_save, sender=OrderItem)
def update_menu_item_stats(sender, instance, created, **kwargs):
    """Track how many times each item is ordered"""
    if created:
        instance.item.times_ordered += instance.quantity
        instance.item.save()


@receiver(post_save, sender=Order)
def send_order_notification(sender, instance, created, **kwargs):
    """Send notification when order status changes"""
    if created:
        Notification.objects.create(
            user=instance.user,
            notification_type='order_update',
            title='Order Placed Successfully! 🎉',
            message=f'Your order {instance.order_id} has been placed and will be delivered soon.'
        )
    elif instance.status == 'out_for_delivery':
        Notification.objects.create(
            user=instance.user,
            notification_type='order_update',
            title='Order On The Way! 🏍️',
            message=f'Your order {instance.order_id} is out for delivery. Arriving in 15-20 minutes.'
        )
    elif instance.status == 'delivered':
        Notification.objects.create(
            user=instance.user,
            notification_type='order_update',
            title='Order Delivered! ✅',
            message=f'Your order {instance.order_id} has been delivered. Enjoy your meal!'
        )
