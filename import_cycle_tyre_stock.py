import os
import django
import pandas as pd

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'radhu.settings')
django.setup()

from cycletyres.models import CycleTyreItem

# Step 1: Reset all existing cycle tyre dummy stocks to 0
items_reset = CycleTyreItem.objects.update(stock=0, second_stock=0, rfm_stock=0)
print(f"Reset dummy stocks to 0 for {items_reset} items.")

# Step 2: Load Excel file
excel_path = r'C:\Users\risha\Desktop\cycle tyre  stock.xlsx'
df = pd.read_excel(excel_path)

created_count = 0
updated_count = 0
total_first = 0
total_second = 0
total_rfm = 0

for idx in range(4, len(df)):
    row = df.iloc[idx]
    
    val_ply = row.iloc[0]
    val_size = str(row.iloc[2]).strip() if not pd.isna(row.iloc[2]) else ""
    val_box = str(row.iloc[3]).strip() if not pd.isna(row.iloc[3]) else "CTC"
    val_brand = str(row.iloc[4]).strip() if not pd.isna(row.iloc[4]) else "GENERAL"

    if not val_size or val_size.lower() == 'nan':
        continue

    def clean_int(val):
        try:
            if pd.isna(val):
                return 0
            return int(float(val))
        except Exception:
            return 0

    first_qty = clean_int(row.iloc[5])
    second_qty = clean_int(row.iloc[6])
    rfm_qty = clean_int(row.iloc[7])

    total_first += first_qty
    total_second += second_qty
    total_rfm += rfm_qty

    if not pd.isna(val_ply):
        ply_str = f"{int(val_ply)} Ply"
    else:
        ply_str = "Standard"

    material = f"{val_box} ({ply_str})" if ply_str != "Standard" else val_box

    item = CycleTyreItem.objects.filter(
        box_type=val_box,
        size=val_size,
        material=material,
        brand=val_brand
    ).first()

    if not item:
        item = CycleTyreItem.objects.filter(
            box_type=val_box,
            size=val_size,
            brand=val_brand
        ).first()

    if not item:
        item, created = CycleTyreItem.objects.get_or_create(
            box_type=val_box,
            size=val_size,
            material=material,
            brand=val_brand,
            defaults={'stock': first_qty, 'second_stock': second_qty, 'rfm_stock': rfm_qty}
        )
        if created:
            created_count += 1
    else:
        item.stock = first_qty
        item.second_stock = second_qty
        item.rfm_stock = rfm_qty
        item.save()
        updated_count += 1

print(f"Cycle Tyre New Production & Stock Import Complete!")
print(f"Items Created: {created_count}, Items Updated: {updated_count}")
print(f"Total 1st Grade Stock: {total_first} Pcs")
print(f"Total 2nd Grade Stock: {total_second} Pcs")
print(f"Total R.F.M Stock: {total_rfm} Pcs")
print(f"Grand Total Curing Stock: {total_first + total_second + total_rfm} Pcs")
