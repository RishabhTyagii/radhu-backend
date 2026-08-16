import os
import django
import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "radhu.settings")
django.setup()

from django.contrib.auth.models import User
from stock.models import TyreItem, DailyEntry, DailyProductionManualEntry

def run():
    print("Seeding database...")
    # 1. User
    user, _ = User.objects.get_or_create(username="admin", defaults={"email": "admin@example.com", "is_superuser": True, "is_staff": True})
    user.set_password("admin123")
    user.save()

    # 2. TyreItems
    tyres = [
        {"tyre": "275-18", "pattern": "PANTHER", "type": "TT", "weight": 8.50, "stock": 100, "repair_tyre_stock": 10, "rfm_ok_tyre": 5, "old_tyres_2025": 20, "on_hold_export": 15},
        {"tyre": "300-18", "pattern": "GRIP", "type": "TL", "weight": 9.20, "stock": 80, "repair_tyre_stock": 5, "rfm_ok_tyre": 12, "old_tyres_2025": 0, "on_hold_export": 0},
        {"tyre": "325-18", "pattern": "RADHU PREMIUM", "type": "TT", "weight": 10.00, "stock": 150, "repair_tyre_stock": 8, "rfm_ok_tyre": 20, "old_tyres_2025": 30, "on_hold_export": 5},
    ]

    items = []
    for t in tyres:
        obj, _ = TyreItem.objects.update_or_create(
            tyre=t["tyre"], pattern=t["pattern"], type=t["type"],
            defaults=t
        )
        items.append(obj)

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    # 3. Daily Entries (Production)
    DailyEntry.objects.update_or_create(
        tyre_item=items[0], date=today, entry_type="production",
        defaults={
            "bucket": "stock",
            "quantity": 40,
            "all_curing": 50,
            "production_tyre": 5,
            "repair": 2,
            "second_grade": 5,
            "third_grade": 2,
            "lose_tyre": 10,
            "user": user,
            "remark": "Morning Shift"
        }
    )

    # 4. Daily Entries (Dispatch)
    DailyEntry.objects.update_or_create(
        tyre_item=items[0], bill_number="INV-1001", entry_type="dispatch",
        defaults={
            "bucket": "stock",
            "quantity": 15,
            "date": today,
            "user": user,
            "remark": "Customer Dispatch"
        }
    )

    # 5. Adjustment
    DailyEntry.objects.update_or_create(
        tyre_item=items[0], date=today, entry_type="adjustment", bucket="rfm_ok_tyre",
        defaults={
            "quantity": 5,
            "user": user,
            "remark": "RFM Stock Verified"
        }
    )

    # 6. Manual Entry
    DailyProductionManualEntry.objects.update_or_create(
        date=today,
        defaults={
            "parchi_kg": 400.50,
            "mixing_actual_compound": 380.00,
            "wastage": 12.50
        }
    )

    print("Seeding finished successfully!")

if __name__ == "__main__":
    run()
