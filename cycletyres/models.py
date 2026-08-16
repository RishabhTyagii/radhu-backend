from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User

class CycleTyreItem(models.Model):
    """Master list of cycle tyres (BOX TYPE + SIZE + MATERIAL + BRAND)."""
    box_type = models.CharField("BOX TYPE", max_length=30)
    size = models.CharField("SIZE", max_length=50)
    material = models.CharField("MATERIAL", max_length=20)
    brand = models.CharField("BRAND", max_length=80)

    weight = models.DecimalField("Weight (Kg)", max_digits=8, decimal_places=3, default=Decimal("0.000"))
    stock = models.IntegerField("STOCK (1st Grade / Black)", default=0)
    second_stock = models.IntegerField("2nd Grade Stock", default=0)
    rfm_stock = models.IntegerField("R.F.M. Stock", default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["size", "box_type", "material", "brand"]
        unique_together = ("box_type", "size", "material", "brand")

    def __str__(self):
        w_str = f" [{self.weight}kg]" if self.weight else ""
        return f"{self.size} {self.box_type} {self.material} {self.brand}{w_str}".strip()

    @property
    def total_stock(self):
        return self.stock + self.rfm_stock

BUCKET_CHOICES = [
    ("stock", "STOCK (1st Grade)"),
    ("second_stock", "2nd Grade Stock"),
    ("rfm_stock", "R.F.M. Stock"),
]

ENTRY_TYPE_CHOICES = [
    ("production", "Production"),
    ("sale", "Sale / Dispatch"),
    ("adjustment", "Stock Adjustment"),
]

class CycleTyreEntry(models.Model):
    tyre_item = models.ForeignKey(CycleTyreItem, on_delete=models.CASCADE, related_name="entries")
    entry_type = models.CharField(max_length=15, choices=ENTRY_TYPE_CHOICES)
    bucket = models.CharField(max_length=15, choices=BUCKET_CHOICES, default="stock")
    quantity = models.IntegerField()
    
    # Grade breakdown fields for production entries
    all_curing = models.IntegerField("All Curing", default=0)
    first_grade = models.IntegerField("1st Grade (Black)", default=0)
    second_grade = models.IntegerField("2nd Grade", default=0)
    rejected_grade = models.IntegerField("Rejected Grade", default=0)

    date = models.DateField()
    bill_number = models.CharField(max_length=50, blank=True)
    remark = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="cycletyre_entries")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "Cycle tyre entries"

    def __str__(self):
        return f"{self.date} | {self.tyre_item} | {self.entry_type} | {self.quantity}"

COMPOUND_PERCENT = Decimal("0.825")

class CycleTyreDailyManualEntry(models.Model):
    date = models.DateField(unique=True)
    parchi_kg = models.DecimalField("Packing Parch Kg", max_digits=10, decimal_places=2, default=0)
    mixing_actual_compound = models.DecimalField("Mixing Actual Compound", max_digits=10, decimal_places=2, default=0)
    chakka = models.DecimalField("Chakka", max_digits=10, decimal_places=2, default=0)
    calander_bias_cutt = models.DecimalField("Calander Bias Cutt.", max_digits=10, decimal_places=2, default=0)
    packing_wastage = models.DecimalField("Packing Wastage", max_digits=10, decimal_places=2, default=0)
    tar = models.DecimalField("Tar", max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Cycle Tyre Daily Manual Entry"
        verbose_name_plural = "Cycle Tyre Daily Manual Entries"

    def __str__(self):
        return f"Cycle Tyre Daily Manual - {self.date}"
