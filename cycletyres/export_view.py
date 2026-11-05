from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import openpyxl
import os
from django.conf import settings
from .views import dashboard

MAPPING_DICT = {7: 3, 8: 4, 9: 18, 10: 10, 11: 8, 12: 1, 13: 12, 14: 14, 17: 3, 18: 18, 19: 16, 20: 19, 21: 10, 22: 21, 23: 27, 26: 30, 27: 10, 28: 12, 29: 14, 30: 40, 31: 39, 32: 42, 33: 49, 34: 44, 35: 53, 36: 53, 37: 55, 38: 71, 39: 25, 40: 37, 41: 64, 44: 23, 45: 22, 46: 26, 47: 29, 51: 41, 52: 3, 53: 52, 54: 50, 55: 45, 56: 42, 57: 49, 58: 51, 59: 3, 60: 49, 61: 3, 62: 53, 63: 53, 64: 53, 65: 53, 66: 53, 67: 81, 68: 77, 71: 75, 72: 75, 73: 75, 74: 78}

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_template(request):
    res = dashboard(request._request)
    data = res.data
    items = data.get("items", [])
    totals = data.get("totals", {})
    
    template_path = os.path.join(settings.BASE_DIR, "cycletyres", "template.xlsx")
    wb = openpyxl.load_workbook(template_path)
    ws = wb.worksheets[0]
    
    headers = [
        "PREV CL(1ST)", "PREV CL(2ND)", "PROD A(1ST)", "PROD B(2ND)", "PROD C(REJ)",
        "TOTAL PROD", "SALE(1ST)", "RFM", "CLOSING(1ST)", "CLOSING(2ND)", "TOTAL STOCK"
    ]
    for col_idx, header in enumerate(headers, start=3):
        ws.cell(row=5, column=col_idx, value=header)
        
    item_to_row = {v: k for k, v in MAPPING_DICT.items()}
    
    for item in items:
        item_id = item["id"]
        if item_id in item_to_row:
            row_idx = item_to_row[item_id]
            ws.cell(row=row_idx, column=3, value=item.get("prev_closing_first", 0))
            ws.cell(row=row_idx, column=4, value=item.get("prev_closing_second", 0))
            ws.cell(row=row_idx, column=5, value=item.get("month_prod_first", 0))
            ws.cell(row=row_idx, column=6, value=item.get("month_prod_second", 0))
            ws.cell(row=row_idx, column=7, value=item.get("month_prod_rejected", 0))
            ws.cell(row=row_idx, column=8, value=item.get("month_prod_total", 0))
            ws.cell(row=row_idx, column=9, value=item.get("month_sale_first", 0))
            ws.cell(row=row_idx, column=10, value=item.get("rfm_stock", 0))
            ws.cell(row=row_idx, column=11, value=item.get("closing_first", 0))
            ws.cell(row=row_idx, column=12, value=item.get("closing_second", 0))
            ws.cell(row=row_idx, column=13, value=item.get("total_stock", 0))

    ws.cell(row=78, column=3, value=totals.get("prev_closing_first", 0))
    ws.cell(row=78, column=4, value=totals.get("prev_closing_second", 0))
    ws.cell(row=78, column=5, value=totals.get("month_prod_first", 0))
    ws.cell(row=78, column=6, value=totals.get("month_prod_second", 0))
    ws.cell(row=78, column=7, value=totals.get("month_prod_rejected", 0))
    ws.cell(row=78, column=8, value=totals.get("month_prod_total", 0))
    ws.cell(row=78, column=9, value=totals.get("month_sale_first", 0))
    ws.cell(row=78, column=10, value=totals.get("rfm_stock", 0))
    ws.cell(row=78, column=11, value=totals.get("closing_first", 0))
    ws.cell(row=78, column=12, value=totals.get("closing_second", 0))
    ws.cell(row=78, column=13, value=totals.get("total_stock", 0))
    
    from io import BytesIO
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="Cycle_Tyre_CB_Export.xlsx"'
    return response
