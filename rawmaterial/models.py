from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─── Tally Card / Stock Ledger Models ─────────────────────────────────────────

class MaterialGroup(models.Model):
    """Groups like: Compound, Rubber, Chemical, Carbon Black, etc."""
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        db_table = "rawmaterial_materialgroup"

    def __str__(self):
        return self.name


class Material(models.Model):
    """Individual raw material under a group."""
    group = models.ForeignKey(
        MaterialGroup,
        on_delete=models.CASCADE,
        related_name="materials"
    )
    name = models.CharField(max_length=150)
    unit = models.CharField(max_length=20, default="Kg")
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    standard_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Standard Rate (Rs/Unit)")
    per_bag = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Per Bag/Pack (Kg)")
    hsn_code = models.CharField(max_length=20, blank=True, verbose_name="HSN Code")

    class Meta:
        ordering = ["group", "name"]
        db_table = "rawmaterial_material"

    def __str__(self):
        return self.name


class StockEntry(models.Model):
    """Daily tally card: Opening → Received → Used → Closing per material."""
    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name="entries"
    )
    date = models.DateField()
    opening = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received_by = models.CharField(max_length=150, blank=True)
    
    # Enhanced Inward / Purchase Tracking
    supplier_name = models.CharField(max_length=200, blank=True, verbose_name="Supplier Name")
    bill_challan_no = models.CharField(max_length=100, blank=True, verbose_name="Bill / Challan No")
    vehicle_no = models.CharField(max_length=50, blank=True, verbose_name="Vehicle No")
    rate_per_unit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Purchase Rate (Rs/Unit)")
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name="Total Cost (Rs)")

    used_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, verbose_name="Remarks / Shift Notes")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        unique_together = ("material", "date")
        db_table = "rawmaterial_stockentry"

    def save(self, *args, **kwargs):
        # Auto-calculate closing
        self.closing = (self.opening or 0) + (self.received_quantity or 0) - (self.used_quantity or 0)
        if self.rate_per_unit and self.received_quantity:
            self.total_cost = self.rate_per_unit * self.received_quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.material} - {self.date}"


# ─── Existing Model ────────────────────────────────────────────────────────────

class MixingEntry(models.Model):
    date = models.DateField(unique=True, db_index=True)

    # --- Compound (in Kgs) ---
    compound_ct = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="CT Compound")
    compound_cc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="CC Compound")
    compound_crt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="CRT Compound")
    compound_ncc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="NCC Compound")
    compound_nct = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="NCT Compound")
    compound_nrt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="NRT Compound")
    compound_tar = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Air Bag & Tar Compound")
    compound_cycle_tube = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Cycle Tube Compound")
    compound_moulding_tube = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Moulding Tube Compound")
    compound_auto_tyre = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Auto Tyre Compound")
    compound_lcv_tyre = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="LCV Tyre Compound")
    compound_auto_calender = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Auto Calender Compound")
    compound_tractor = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Tractor Compound")
    compound_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Total Compound")

    # --- Rubber (in Kgs) ---
    rubber_ct = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="CT Rubber")
    rubber_cc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="CC Rubber")
    rubber_crt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="CRT Rubber")
    rubber_ncc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="NCC Rubber")
    rubber_nct = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="NCT Rubber")
    rubber_nrt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="NRT Rubber")
    rubber_tar = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Air Bag & Tar Rubber")
    rubber_cycle_tube = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Cycle Tube Rubber")
    rubber_moulding_tube = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Moulding Tube Rubber")
    rubber_auto_tyre = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Auto Tyre Rubber")
    rubber_lcv_tyre = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="LCV Tyre Rubber")
    rubber_auto_calender = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Auto Calender Rubber")
    rubber_tractor = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Tractor Rubber")
    rubber_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Total Rubber")

    # --- Rubber Bundles & Reconciliation ---
    rubber_bdls = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Rubber Bundles")
    rubber_kgs = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Rubber Kgs (Bdls * 50)")
    diff = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Difference (Total Rubber - Rubber Kgs)")

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rawmaterial_mixing"
        ordering = ["date"]
        verbose_name = "Mixing Entry"
        verbose_name_plural = "Mixing Entries"

    def calculate_totals(self):
        # Auto calculate compound total
        self.compound_total = (
            (self.compound_ct or 0)
            + (self.compound_cc or 0)
            + (self.compound_crt or 0)
            + (self.compound_ncc or 0)
            + (self.compound_nct or 0)
            + (self.compound_nrt or 0)
            + (self.compound_tar or 0)
            + (self.compound_cycle_tube or 0)
            + (self.compound_moulding_tube or 0)
            + (self.compound_auto_tyre or 0)
            + (self.compound_lcv_tyre or 0)
            + (self.compound_auto_calender or 0)
            + (self.compound_tractor or 0)
        )

        # Auto calculate rubber total
        self.rubber_total = (
            (self.rubber_ct or 0)
            + (self.rubber_cc or 0)
            + (self.rubber_crt or 0)
            + (self.rubber_ncc or 0)
            + (self.rubber_nct or 0)
            + (self.rubber_nrt or 0)
            + (self.rubber_tar or 0)
            + (self.rubber_cycle_tube or 0)
            + (self.rubber_moulding_tube or 0)
            + (self.rubber_auto_tyre or 0)
            + (self.rubber_lcv_tyre or 0)
            + (self.rubber_auto_calender or 0)
            + (self.rubber_tractor or 0)
        )

        # 1 Bundle = 50 Kgs
        self.rubber_kgs = (self.rubber_bdls or 0) * 50
        # Diff = Total Rubber - Rubber Kgs
        self.diff = self.rubber_total - self.rubber_kgs

    def save(self, *args, **kwargs):
        self.calculate_totals()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Mixing {self.date} - Compound: {self.compound_total} Kg, Rubber: {self.rubber_total} Kg"
