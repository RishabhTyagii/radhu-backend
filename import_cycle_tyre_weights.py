import os
import django
import pandas as pd
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'radhu.settings')
django.setup()

from cycletyres.models import CycleTyreItem

excel_path = r'C:\Users\risha\Desktop\cycle tyre weight.xlsx'
df = pd.read_excel(excel_path)

created_count = 0
updated_count = 0

for idx, row in df.iterrows():
    val_weight = row.iloc[5]
    if pd.isna(val_weight):
        continue
    
    # Try converting weight to float/Decimal
    try:
        weight_num = Decimal(str(float(val_weight)))
    except Exception:
        continue

    val_ply = row.iloc[0]
    val_size = str(row.iloc[2]).strip() if not pd.isna(row.iloc[2]) else ""
    val_box = str(row.iloc[3]).strip() if not pd.isna(row.iloc[3]) else "CTC"
    val_brand = str(row.iloc[4]).strip() if not pd.isna(row.iloc[4]) else "GENERAL"

    if not val_size or val_size.lower() == 'nan':
        continue

    # Determine material & ply info
    if not pd.isna(val_ply):
        ply_str = f"{int(val_ply)} Ply"
    else:
        ply_str = "Standard"

    material = f"{val_box} ({ply_str})" if ply_str != "Standard" else val_box

    # Create or update CycleTyreItem
    item, created = CycleTyreItem.objects.get_or_create(
        box_type=val_box,
        size=val_size,
        material=material,
        brand=val_brand,
        defaults={'weight': weight_num, 'stock': 100}
    )

    if created:
        created_count += 1
    else:
        item.weight = weight_num
        item.save()
        updated_count += 1

print(f"Cycle Tyre Weights Import Complete! Created: {created_count}, Updated: {updated_count}")
