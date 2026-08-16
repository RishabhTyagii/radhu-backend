from django.db import models
from django.contrib.auth.models import User


class TyreItem(models.Model):
    tyre = models.CharField("TYRE", max_length=50)
    pattern = models.CharField("PATTERN", max_length=80)
    type = models.CharField("TYPE", max_length=20)
    weight = models.DecimalField(
        "Standard Weight (KG per tyre)", max_digits=6, decimal_places=2, default=0,
    )
    repair_tyre_stock = models.IntegerField("Repair Tyre Stock", default=0)
    rfm_ok_tyre = models.IntegerField("RFM OK Tyre", default=0)
    old_tyres_2025 = models.IntegerField("2025 Old Tyres", default=0)
    stock = models.IntegerField("STOCK", default=0)
    on_hold_export = models.IntegerField("On hold for Export / OR", default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tyre", "pattern", "type"]
        unique_together = ("tyre", "pattern", "type")

    def __str__(self):
        return f"{self.tyre} {self.pattern} {self.type}"

    @property
    def total_stock(self):
        return (
            self.repair_tyre_stock
            + self.rfm_ok_tyre
            + self.old_tyres_2025
            + self.stock
            + self.on_hold_export
        )


BUCKET_CHOICES = [
    ("stock", "STOCK"),
    ("repair_tyre_stock", "Repair Tyre Stock"),
    ("rfm_ok_tyre", "RFM OK Tyre"),
    ("old_tyres_2025", "2025 Old Tyres"),
    ("on_hold_export", "On hold for Export / OR"),
]

ENTRY_TYPE_CHOICES = [
    ("production", "Production (Daily Curing)"),
    ("dispatch", "Dispatch"),
    ("adjustment", "Stock Adjustment"),
]


class DailyEntry(models.Model):
    tyre_item = models.ForeignKey(TyreItem, on_delete=models.CASCADE, related_name="entries")
    entry_type = models.CharField(max_length=15, choices=ENTRY_TYPE_CHOICES)
    bucket = models.CharField(max_length=25, choices=BUCKET_CHOICES, default="stock")
    quantity = models.IntegerField(help_text="Enter positive quantity")
    date = models.DateField()
    bill_number = models.CharField(max_length=50, blank=True)
    remark = models.CharField(max_length=255, blank=True)
    actual_weight = models.DecimalField(
        "Actual Weight (KG)", max_digits=8, decimal_places=2, null=True, blank=True,
    )
    all_curing = models.IntegerField("All Curing", default=0)
    production_tyre = models.IntegerField("Production Tyre", default=0)
    repair = models.IntegerField("Repair", default=0)
    second_grade = models.IntegerField("2nd Grade", default=0)
    third_grade = models.IntegerField("3rd Grade", default=0)
    lose_tyre = models.IntegerField("Lose Tyre", default=0)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="stock_entries")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} | {self.tyre_item} | {self.get_entry_type_display()} | {self.quantity}"

    @property
    def expected_weight(self):
        return self.quantity * self.tyre_item.weight

    @property
    def weight_variance(self):
        if self.actual_weight is None:
            return None
        return self.actual_weight - self.expected_weight


class DailyProductionManualEntry(models.Model):
    date = models.DateField(unique=True)
    parchi_kg = models.DecimalField("Parchi KG", max_digits=10, decimal_places=2, default=0)
    mixing_actual_compound = models.DecimalField("Mixing Actual Compound", max_digits=10, decimal_places=2, default=0)
    wastage = models.DecimalField("Wastage", max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Manual entry - {self.date}"
