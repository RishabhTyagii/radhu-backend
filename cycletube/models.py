from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User

TUBE_QUALITY_CHOICES = [
    ("normal", "Normal"),
    ("molded", "Molded"),
    ("second", "Second"),
]

class CycleTubeItem(models.Model):
    size = models.CharField("SIZE", max_length=50)
    type = models.CharField("TYPE", max_length=20)
    brand = models.CharField("BRAND", max_length=80)
    weight = models.DecimalField("Weight (Kg)", max_digits=8, decimal_places=4, default=Decimal("0.0000"))
    stock = models.IntegerField("STOCK", default=0)
    rfm_stock = models.IntegerField("R.F.M. Stock", default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["size", "type", "brand"]
        unique_together = ("size", "type", "brand")

    def __str__(self):
        return f"{self.size} {self.type} {self.brand}".strip()

    @property
    def total_stock(self):
        return self.stock + self.rfm_stock

BUCKET_CHOICES = [
    ("stock", "STOCK"),
    ("rfm_stock", "R.F.M. Stock"),
]

ENTRY_TYPE_CHOICES = [
    ("production", "Production"),
    ("sale", "Sale / Dispatch"),
    ("adjustment", "Stock Adjustment"),
]

class CycleTubeEntry(models.Model):
    tube_item = models.ForeignKey(CycleTubeItem, on_delete=models.CASCADE, related_name="entries")
    entry_type = models.CharField(max_length=15, choices=ENTRY_TYPE_CHOICES)
    bucket = models.CharField(max_length=15, choices=BUCKET_CHOICES, default="stock")
    quantity = models.IntegerField()
    tube_quality = models.CharField(max_length=10, choices=TUBE_QUALITY_CHOICES, default="normal")
    date = models.DateField()
    bill_number = models.CharField(max_length=50, blank=True)
    remark = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="cycletube_entries")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

PACK_FACTOR = Decimal("0.0075")
VB_FACTOR = Decimal("0.015")
COMB_FACTOR = Decimal("0.0225")

class CycleTubeDailyManualEntry(models.Model):
    date = models.DateField(unique=True)
    valve_body_issued = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    actual_wt_gross = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    actual_mixing_compound = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    jali = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    die_wastage = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tube_cutting = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_tube_waste = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
