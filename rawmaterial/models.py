from django.db import models
from django.utils import timezone


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
