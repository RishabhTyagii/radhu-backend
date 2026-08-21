from django.db import models
from django.contrib.auth.models import User
from stock.models import TyreItem
from cycletube.models import CycleTubeItem
from cycletyres.models import CycleTyreItem


class Party(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='parties')
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('dispatched', 'Dispatched'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='orders')
    date = models.DateField(auto_now_add=True)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_orders')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Order #{self.id} - {self.party.name}"

    @property
    def is_overdue(self):
        from django.utils import timezone
        import datetime
        if self.deadline and self.status == 'pending':
            d = self.deadline
            if isinstance(d, str):
                try:
                    d = datetime.datetime.strptime(d, "%Y-%m-%d").date()
                except ValueError:
                    return False
            return d < timezone.now().date()
        return False


class OrderItem(models.Model):
    CATEGORY_AUTO_TYRE = 'auto_tyre'
    CATEGORY_CYCLE_TUBE = 'cycle_tube'
    CATEGORY_CYCLE_TYRE = 'cycle_tyre'
    CATEGORY_CHOICES = (
        (CATEGORY_AUTO_TYRE, 'Auto Tyre'),
        (CATEGORY_CYCLE_TUBE, 'Cycle Tube'),
        (CATEGORY_CYCLE_TYRE, 'Cycle Tyre'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_AUTO_TYRE)

    tyre_item = models.ForeignKey(TyreItem, null=True, blank=True, on_delete=models.CASCADE, related_name='order_items')
    tube_item = models.ForeignKey(CycleTubeItem, null=True, blank=True, on_delete=models.CASCADE, related_name='order_items')
    cycle_tyre_item = models.ForeignKey(CycleTyreItem, null=True, blank=True, on_delete=models.CASCADE, related_name='order_items')

    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.quantity} x {self.item_display} @ ₹{self.price}"

    @property
    def item_display(self):
        if self.category == self.CATEGORY_AUTO_TYRE and self.tyre_item:
            return f"{self.tyre_item.tyre} {self.tyre_item.pattern} {self.tyre_item.type}"
        elif self.category == self.CATEGORY_CYCLE_TUBE and self.tube_item:
            return f"{self.tube_item.size} {self.tube_item.type} {self.tube_item.brand}"
        elif self.category == self.CATEGORY_CYCLE_TYRE and self.cycle_tyre_item:
            return f"{self.cycle_tyre_item.size} {self.cycle_tyre_item.box_type} {self.cycle_tyre_item.brand}"
        return "Unknown Item"

    @property
    def item_stock(self):
        if self.category == self.CATEGORY_AUTO_TYRE and self.tyre_item:
            return self.tyre_item.stock
        elif self.category == self.CATEGORY_CYCLE_TUBE and self.tube_item:
            return self.tube_item.stock
        elif self.category == self.CATEGORY_CYCLE_TYRE and self.cycle_tyre_item:
            return self.cycle_tyre_item.stock
        return 0
