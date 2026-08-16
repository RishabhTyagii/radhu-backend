from django.db import models

MODULE_CHOICES = [
    ("tyre", "Auto Tyre"),
    ("tube", "Cycle Tube"),
    ("cycletyre", "Cycle Tyre"),
]


class TallyItemMapping(models.Model):
    """Maps a Tally stock-item name to one of our items in the 3 modules."""
    tally_item_name = models.CharField(max_length=150, unique=True)
    module = models.CharField(max_length=15, choices=MODULE_CHOICES)
    item_id = models.PositiveIntegerField(help_text="The ID of the matching item in that module")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tally_item_name"]

    def __str__(self):
        return f"{self.tally_item_name} → {self.get_module_display()} #{self.item_id}"

    def get_item(self):
        if self.module == "tyre":
            from stock.models import TyreItem
            return TyreItem.objects.filter(pk=self.item_id).first()
        elif self.module == "tube":
            from cycletube.models import CycleTubeItem
            return CycleTubeItem.objects.filter(pk=self.item_id).first()
        elif self.module == "cycletyre":
            from cycletyres.models import CycleTyreItem
            return CycleTyreItem.objects.filter(pk=self.item_id).first()
        return None


class TallyInvoice(models.Model):
    """One synced Sales voucher from Tally, with GST breakup + party/GST details."""
    voucher_number = models.CharField(max_length=50, unique=True)
    voucher_date = models.DateField()

    party_name = models.CharField(max_length=200, blank=True)
    party_gstin = models.CharField(max_length=20, blank=True)
    party_address = models.TextField(blank=True)
    consignee_name = models.CharField(max_length=200, blank=True)
    consignee_gstin = models.CharField(max_length=20, blank=True)
    place_of_supply = models.CharField(max_length=100, blank=True)
    state_name = models.CharField(max_length=100, blank=True)
    gst_registration_type = models.CharField(max_length=50, blank=True)

    taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_synced = models.BooleanField(default=False, help_text="True if all line items matched & stock was reduced")
    raw_payload = models.TextField(blank=True)
    synced_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-voucher_date", "-synced_at"]

    def __str__(self):
        return f"{self.voucher_number} | {self.voucher_date} | {self.party_name} | ₹{self.total_value}"

    @property
    def gst_total(self):
        return self.cgst + self.sgst + self.igst


LOG_LEVEL_CHOICES = [
    ("info", "Info"),
    ("warning", "Warning"),
    ("error", "Error"),
]


class TallySyncLog(models.Model):
    invoice = models.ForeignKey(TallyInvoice, on_delete=models.CASCADE, null=True, blank=True, related_name="logs")
    level = models.CharField(max_length=10, choices=LOG_LEVEL_CHOICES, default="info")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.level}] {self.message[:80]}"


PENDING_REASON_CHOICES = [
    ("unmapped", "Item Not Mapped"),
    ("insufficient_stock", "Insufficient Stock"),
]


class TallyPendingItem(models.Model):
    """A voucher line item that couldn't be stock-synced yet."""
    invoice = models.ForeignKey(TallyInvoice, on_delete=models.CASCADE, related_name="pending_items")
    tally_item_name = models.CharField(max_length=150)
    qty = models.IntegerField()
    voucher_number = models.CharField(max_length=50)
    voucher_date = models.DateField()
    party_name = models.CharField(max_length=200, blank=True)
    reason = models.CharField(max_length=25, choices=PENDING_REASON_CHOICES)
    resolved = models.BooleanField(default=False)
    category_override = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        status = "resolved" if self.resolved else "PENDING"
        return f"{self.tally_item_name} x{self.qty} ({self.get_reason_display()}) - {status}"
