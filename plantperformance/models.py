from django.db import models


class PlantPerformanceDailyLog(models.Model):
    date = models.DateField(unique=True, db_index=True)

    # MIXING
    mixing_variation = models.DecimalField(
        "Mixing Variation (Kg)", max_digits=10, decimal_places=2, default=0
    )

    # PATTI & DAGHA CALENDER
    calender_prod_kg = models.DecimalField(
        "Calender Prod Kg", max_digits=10, decimal_places=2, default=0
    )
    calender_fab_scrap = models.DecimalField(
        "Calender Fab Scrap (Kg)", max_digits=10, decimal_places=2, default=0
    )
    calender_com_scrap = models.DecimalField(
        "Calender Com Scrap (Kg)", max_digits=10, decimal_places=2, default=0
    )

    # AUTO TYRE BUILDING
    auto_building_prod_num = models.IntegerField("Auto Building Prod Num", default=0)
    auto_building_fab_scrap = models.DecimalField(
        "Auto Building Fab Scrap (Kg)", max_digits=10, decimal_places=2, default=0
    )

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plantperformance_dailylog"
        ordering = ["date"]
        verbose_name = "Plant Performance Daily Log"
        verbose_name_plural = "Plant Performance Daily Logs"

    def __str__(self):
        return f"Plant Performance Log - {self.date}"
