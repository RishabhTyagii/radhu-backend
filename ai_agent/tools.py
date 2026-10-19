"""
RADHU AI TOOLS & KNOWLEDGE ENGINE
Provides full database access, complete Django model introspection,
view function documentation, and frontend page routing for Radhu ERP.
"""
import os
import json
import datetime
from decimal import Decimal
from django.db import connection
from django.apps import apps

# -------------------------------------------------------------
# STATIC REGISTRIES FOR FAST SEARCH (VIEWS & FRONTEND PAGES)
# -------------------------------------------------------------

FRONTEND_PAGES = [
    {
        "route": "/",
        "file": "frontend/src/app/page.js",
        "title": "Main Dashboard",
        "description": "Factory-wide summary, quick KPI cards, navigation cards to all modules.",
        "apis": ["/api/stock/dashboard/", "/api/cycletyres/dashboard/", "/api/cycletube/dashboard/"]
    },
    {
        "route": "/stock",
        "file": "frontend/src/app/stock/page.js",
        "title": "Auto Tyre Dashboard",
        "description": "Auto Tyre stock inventory, low stock alerts, production & dispatch summary.",
        "apis": ["/api/stock/dashboard/"]
    },
    {
        "route": "/stock/production",
        "file": "frontend/src/app/stock/production/page.js",
        "title": "Auto Tyre Production Entry",
        "description": "Daily production entry for Auto Tyres (Brand, Size, Pattern, Type, Quantity, Grade).",
        "apis": ["/api/stock/production/", "/api/stock/tyres/"]
    },
    {
        "route": "/stock/dispatch",
        "file": "frontend/src/app/stock/dispatch/page.js",
        "title": "Auto Tyre Dispatch Entry",
        "description": "Dispatch tyre entries by party, invoice, quantities, reducing live stock.",
        "apis": ["/api/stock/dispatch/"]
    },
    {
        "route": "/stock/adjustment",
        "file": "frontend/src/app/stock/adjustment/page.js",
        "title": "Auto Tyre Stock Adjustment",
        "description": "Audit and physical stock adjustments (+/- corrections) for Auto Tyres.",
        "apis": ["/api/stock/adjustment/"]
    },
    {
        "route": "/stock/add-tyre",
        "file": "frontend/src/app/stock/add-tyre/page.js",
        "title": "Add Auto Tyre Item",
        "description": "Create new Auto Tyre master item with size, pattern, ply, opening stock.",
        "apis": ["/api/stock/tyres/create/"]
    },
    {
        "route": "/stock/entries",
        "file": "frontend/src/app/stock/entries/page.js",
        "title": "Auto Tyre Daily Log",
        "description": "Audit log of all production, dispatch, and adjustment transactions.",
        "apis": ["/api/stock/entries/"]
    },
    {
        "route": "/stock/daily-summary",
        "file": "frontend/src/app/stock/daily-summary/page.js",
        "title": "Auto Tyre Daily Summary",
        "description": "Daily reconciliation sheet comparing production, dispatch, wastage, and mixing actual compound.",
        "apis": ["/api/stock/daily-summary/"]
    },
    {
        "route": "/stock/monthly-report",
        "file": "frontend/src/app/stock/monthly-report/page.js",
        "title": "Auto Tyre Monthly Report",
        "description": "Month-wise aggregation of production, dispatch, second grade, and wastage.",
        "apis": ["/api/stock/monthly-report/"]
    },
    {
        "route": "/cycletyres",
        "file": "frontend/src/app/cycletyres/page.js",
        "title": "Cycle Tyre Dashboard",
        "description": "Cycle Tyre stock inventory, brand/size breakdown, production vs dispatch KPIs.",
        "apis": ["/api/cycletyres/dashboard/"]
    },
    {
        "route": "/cycletyres/production",
        "file": "frontend/src/app/cycletyres/production/page.js",
        "title": "Cycle Tyre Production Entry",
        "description": "Log cycle tyre press production by size, brand, box type, material.",
        "apis": ["/api/cycletyres/production/", "/api/cycletyres/items/"]
    },
    {
        "route": "/cycletyres/sale",
        "file": "frontend/src/app/cycletyres/sale/page.js",
        "title": "Cycle Tyre Sale / Dispatch",
        "description": "Dispatch entries for Cycle Tyres to dealers and distributors.",
        "apis": ["/api/cycletyres/dispatch/"]
    },
    {
        "route": "/cycletyres/summary",
        "file": "frontend/src/app/cycletyres/summary/page.js",
        "title": "Cycle Tyre Daily Summary Sheet",
        "description": "Daily cycle tyre summary sheet with packing pcs, parchi kg, mixing actual compound, chakka, tar, wastage.",
        "apis": ["/api/cycletyres/daily-summary/"]
    },
    {
        "route": "/cycletyres/entries",
        "file": "frontend/src/app/cycletyres/entries/page.js",
        "title": "Cycle Tyre Entries Log",
        "description": "History log of all cycle tyre transactions with filter and edit/delete.",
        "apis": ["/api/cycletyres/entries/"]
    },
    {
        "route": "/cycletyres/add-item",
        "file": "frontend/src/app/cycletyres/add-item/page.js",
        "title": "Add Cycle Tyre Master Item",
        "description": "Create new cycle tyre master item.",
        "apis": ["/api/cycletyres/items/create/"]
    },
    {
        "route": "/cycletube",
        "file": "frontend/src/app/cycletube/page.js",
        "title": "Cycle Tube Dashboard",
        "description": "Cycle Tube stock inventory, sizes, brands, production and dispatch metrics.",
        "apis": ["/api/cycletube/dashboard/"]
    },
    {
        "route": "/cycletube/production",
        "file": "frontend/src/app/cycletube/production/page.js",
        "title": "Cycle Tube Production Entry",
        "description": "Log cycle tube extrusion and moulding production.",
        "apis": ["/api/cycletube/production/", "/api/cycletube/items/"]
    },
    {
        "route": "/cycletube/sale",
        "file": "frontend/src/app/cycletube/sale/page.js",
        "title": "Cycle Tube Sale / Dispatch",
        "description": "Dispatch entries for Cycle Tubes.",
        "apis": ["/api/cycletube/dispatch/"]
    },
    {
        "route": "/cycletube/summary",
        "file": "frontend/src/app/cycletube/summary/page.js",
        "title": "Cycle Tube Daily Summary Sheet",
        "description": "Daily cycle tube summary with valve body issued, actual wt gross, actual mixing compound, jali, die wastage, tube cutting.",
        "apis": ["/api/cycletube/daily-summary/"]
    },
    {
        "route": "/rawmaterial/mixing",
        "file": "frontend/src/app/rawmaterial/mixing/page.js",
        "title": "Raw Material Mixing Sheet",
        "description": "Dual table (Compound vs Rubber) for 13 product types + bundles + diff reconciliation. Supports math expressions (e.g. 26*10 -> 260) and auto-syncs to Cycle Tyre, Cycle Tube, and Auto Tyre summary sheets.",
        "apis": ["/api/rawmaterial/mixing/", "/api/rawmaterial/mixing/export/"]
    },
    {
        "route": "/tallysync",
        "file": "frontend/src/app/tallysync/page.js",
        "title": "Tally Sales & Invoices",
        "description": "List of all sales vouchers synced from Tally ERP via XML webhook. View party, invoice no, amount, item breakdown, and pending unmapped items.",
        "apis": ["/api/tallysync/sales/", "/api/tallysync/pending-items/"]
    },
    {
        "route": "/tallysync/invoice/[id]",
        "file": "frontend/src/app/tallysync/invoice/[id]/page.js",
        "title": "Tally Invoice Detail",
        "description": "Full bill breakdown with buyer/consignee details, line items, rates, taxes, and dispatch sync status.",
        "apis": ["/api/tallysync/invoice/<id>/"]
    },
    {
        "route": "/tallysync/mapping",
        "file": "frontend/src/app/tallysync/mapping/page.js",
        "title": "Tally Item Mapping",
        "description": "Map Tally ledger item names to Radhu ERP inventory master items (Cycle Tyre, Tube, Auto Tyre).",
        "apis": ["/api/tallysync/mapping/"]
    },
    {
        "route": "/hrms/employees",
        "file": "frontend/src/app/hrms/employees/page.js",
        "title": "HRMS Employees List",
        "description": "Worker & staff master: personal details, designation, department, wage type (piece-rate vs monthly), rate per piece, bank info.",
        "apis": ["/api/hrms/employees/"]
    },
    {
        "route": "/hrms/attendance",
        "file": "frontend/src/app/hrms/attendance/page.js",
        "title": "HRMS Bulk Attendance",
        "description": "Daily attendance marking (Present, Absent, Half Day, Leave) with overtime hours.",
        "apis": ["/api/hrms/attendance/"]
    },
    {
        "route": "/hrms/production",
        "file": "frontend/src/app/hrms/production/page.js",
        "title": "HRMS Worker Production",
        "description": "Track daily piece-rate production per worker for pressing, moulding, building, extrusion.",
        "apis": ["/api/hrms/production/"]
    },
    {
        "route": "/hrms/salary",
        "file": "frontend/src/app/hrms/salary/page.js",
        "title": "HRMS Salary Sheet & Slips",
        "description": "Monthly payroll generation calculating piece-rate earnings + overtime + bonuses - advances - deductions = net pay.",
        "apis": ["/api/hrms/salary/"]
    },
    {
        "route": "/orders",
        "file": "frontend/src/app/orders/page.js",
        "title": "Orders Management",
        "description": "Dealer & customer sales orders, pending orders, order fulfillment status.",
        "apis": ["/api/orders/"]
    },
    {
        "route": "/orders/create",
        "file": "frontend/src/app/orders/create/page.js",
        "title": "Create Sales Order",
        "description": "Book new customer order with line items, quantities, agreed rates, delivery dates.",
        "apis": ["/api/orders/create/", "/api/orders/parties/"]
    },
    {
        "route": "/ai-agent",
        "file": "frontend/src/app/ai-agent/page.js",
        "title": "RADHU AI Assistant",
        "description": "Interactive AI Assistant with full database query access, schema awareness, and ERP action proposals.",
        "apis": ["/api/ai/chat/", "/api/ai/status/", "/api/ai/actions/confirm/", "/api/ai/actions/reject/"]
    }
]

BACKEND_VIEWS = [
    {
        "name": "mixing_sheet_view",
        "module": "rawmaterial.views",
        "url": "/api/rawmaterial/mixing/",
        "methods": ["GET", "POST"],
        "description": "GET returns mixing entries for given month/year (defaults to latest entry month) with KPI totals and active month/year. POST creates or updates an entry for a date and automatically calls sync_mixing_to_summaries to update Cycle Tyre, Cycle Tube, and Auto Tyre summary sheets."
    },
    {
        "name": "sync_mixing_to_summaries",
        "module": "rawmaterial.views",
        "url": "Internal function",
        "methods": ["N/A"],
        "description": "Formula synchronization: Cycle Tyre mixing_actual_compound = CT + CC + CRT + NCC + NCT + NRT (Compound side). Cycle Tube actual_mixing_compound = Air Bag & Tar + Cycle Tube + Moulding Tube (Compound side). Auto Tyre mixing_actual_compound = Auto Tyre + LCV Tyre + Auto Calender + Tractor (Compound side)."
    },
    {
        "name": "delete_mixing_entry",
        "module": "rawmaterial.views",
        "url": "/api/rawmaterial/mixing/<id>/delete/",
        "methods": ["DELETE"],
        "description": "Deletes a mixing entry by ID."
    },
    {
        "name": "export_excel_view",
        "module": "rawmaterial.views",
        "url": "/api/rawmaterial/mixing/export/",
        "methods": ["GET"],
        "description": "Exports raw material mixing entries for month/year to styled Excel file with Compound and Rubber tables."
    },
    {
        "name": "stock_dashboard",
        "module": "stock.views",
        "url": "/api/stock/dashboard/",
        "methods": ["GET"],
        "description": "Returns Auto Tyre stock inventory, total stock, second stock, low stock list, and monthly production/dispatch totals."
    },
    {
        "name": "stock_add_production",
        "module": "stock.views",
        "url": "/api/stock/production/",
        "methods": ["POST"],
        "description": "Adds Auto Tyre daily production entry, updates TyreItem stock."
    },
    {
        "name": "stock_add_dispatch",
        "module": "stock.views",
        "url": "/api/stock/dispatch/",
        "methods": ["POST"],
        "description": "Dispatches Auto Tyres to parties/dealers, reduces TyreItem stock."
    },
    {
        "name": "stock_daily_summary",
        "module": "stock.views",
        "url": "/api/stock/daily-summary/",
        "methods": ["GET", "POST"],
        "description": "GET returns daily summary rows with production, dispatch, wastage, and manual entry (parchi_kg, mixing_actual_compound, wastage). POST saves DailyProductionManualEntry."
    },
    {
        "name": "cycletyres_dashboard",
        "module": "cycletyres.views",
        "url": "/api/cycletyres/dashboard/",
        "methods": ["GET"],
        "description": "Returns Cycle Tyre dashboard metrics, items, stock counts, second stock, and monthly stats."
    },
    {
        "name": "cycletyres_daily_summary",
        "module": "cycletyres.views",
        "url": "/api/cycletyres/daily-summary/",
        "methods": ["GET", "POST"],
        "description": "Cycle Tyre Daily Summary Sheet with packing_pcs, parchi_kg, mixing_actual_compound, chakka, tar, packing_wastage. Auto-synced from Raw Material mixing."
    },
    {
        "name": "cycletube_dashboard",
        "module": "cycletube.views",
        "url": "/api/cycletube/dashboard/",
        "methods": ["GET"],
        "description": "Returns Cycle Tube dashboard metrics, sizes, stock levels, production vs dispatch."
    },
    {
        "name": "cycletube_daily_summary",
        "module": "cycletube.views",
        "url": "/api/cycletube/daily-summary/",
        "methods": ["GET", "POST"],
        "description": "Cycle Tube Daily Summary Sheet with valve_body_issued, actual_wt_gross, actual_mixing_compound, jali, die_wastage, tube_cutting. Auto-synced from Raw Material mixing."
    },
    {
        "name": "tally_webhook",
        "module": "tallysync.views",
        "url": "/tallysync/webhook/",
        "methods": ["POST"],
        "description": "Receives XML payload from Tally ERP (UTF-16-LE encoded, parsed with BeautifulSoup xml), validates API key fc2e1029465c118d144c93a093c0efd2cfa2d40a258c32c8, creates/updates TallyInvoice, TallyInvoiceLine, and queues unmapped items into TallyPendingItem."
    },
    {
        "name": "tally_sales_summary",
        "module": "tallysync.views",
        "url": "/api/tallysync/sales/",
        "methods": ["GET"],
        "description": "Returns list of synced Tally sales invoices with party filter, date range, total pieces, tax breakdown, and item lists."
    },
    {
        "name": "hrms_salary_generate",
        "module": "hrms.views",
        "url": "/api/hrms/salary/generate/",
        "methods": ["POST"],
        "description": "Calculates monthly salary for all employees based on piece-rate production, fixed wage, attendance days, overtime hours, advances, and deductions."
    },
    {
        "name": "ai_agent_chat",
        "module": "ai_agent.views",
        "url": "/api/ai/chat/",
        "methods": ["POST"],
        "description": "Main AI chat endpoint with multi-turn history, automatic live SQL query execution, model schema introspection, and ERP action proposal generation."
    }
]

# -------------------------------------------------------------
# GEMINI FUNCTION CALLING TOOLS
# -------------------------------------------------------------

def execute_sql_query(query: str) -> str:
    """Executes a read-only SQL query (SELECT, SHOW, DESCRIBE, EXPLAIN) against the Radhu ERP MySQL database and returns results as JSON.
    Use this to look up ANY live data: mixing records, stocks, sales, invoices, parties, employees, attendance, salaries, production.
    DO NOT execute INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or mutation queries."""
    clean = query.strip().upper()
    if not (clean.startswith('SELECT') or clean.startswith('SHOW') or clean.startswith('DESCRIBE') or clean.startswith('EXPLAIN')):
        return json.dumps({"error": "Only read-only queries (SELECT, SHOW, DESCRIBE, EXPLAIN) are permitted."})

    for bad in ['DROP ', 'DELETE ', 'UPDATE ', 'INSERT ', 'ALTER ', 'TRUNCATE ', 'REPLACE ', 'CREATE ', 'GRANT ', 'REVOKE ']:
        if bad in clean:
            return json.dumps({"error": f"Mutation statement with '{bad.strip()}' is blocked in read-only execute_sql_query."})

    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            if not cursor.description:
                return json.dumps({"rows": [], "count": 0})
            cols = [col[0] for col in cursor.description]
            rows = cursor.fetchmany(100)
            res = []
            for r in rows:
                item = {}
                for col, val in zip(cols, r):
                    if isinstance(val, (datetime.date, datetime.datetime)):
                        item[col] = val.isoformat()
                    elif isinstance(val, Decimal):
                        item[col] = float(val)
                    else:
                        item[col] = val
                res.append(item)
            return json.dumps({"count": len(res), "rows": res}, default=str)
    except Exception as e:
        return json.dumps({"error": f"SQL Error: {str(e)}", "query": query})


def get_model_schema(model_or_table_name: str) -> str:
    """Returns the full field-by-field schema, data types, nullability, relationships, and table name for any Django model in Radhu ERP.
    Example: get_model_schema('MixingEntry') or get_model_schema('rawmaterial_mixing') or get_model_schema('Employee')."""
    target = model_or_table_name.strip().lower()
    for m in apps.get_models():
        if m.__name__.lower() == target or m._meta.db_table.lower() == target:
            fields = []
            for f in m._meta.get_fields():
                f_type = f.get_internal_type() if hasattr(f, 'get_internal_type') else type(f).__name__
                rel = ""
                if hasattr(f, 'related_model') and f.related_model:
                    rel = f"{f.related_model._meta.app_label}.{f.related_model.__name__}"
                fields.append({
                    "name": f.name,
                    "type": f_type,
                    "null": getattr(f, 'null', False),
                    "blank": getattr(f, 'blank', False),
                    "primary_key": getattr(f, 'primary_key', False),
                    "related_to": rel if rel else None,
                    "choices": [c[0] for c in f.choices] if hasattr(f, 'choices') and f.choices else None,
                    "verbose_name": str(getattr(f, 'verbose_name', f.name))
                })
            return json.dumps({
                "app": m._meta.app_label,
                "model": m.__name__,
                "db_table": m._meta.db_table,
                "total_fields": len(fields),
                "fields": fields
            })
    return json.dumps({"error": f"Model or table '{model_or_table_name}' not found."})


def list_all_models_and_tables() -> str:
    """Returns a complete catalog of all apps, models, database table names, and current live row counts in Radhu ERP."""
    catalog = {}
    with connection.cursor() as cursor:
        for app_config in apps.get_app_configs():
            models = list(app_config.get_models())
            if not models:
                continue
            if app_config.label in ['admin', 'contenttypes', 'sessions']:
                continue
            catalog[app_config.label] = []
            for m in models:
                table = m._meta.db_table
                cnt = 0
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                    cnt = cursor.fetchone()[0]
                except Exception:
                    cnt = -1
                catalog[app_config.label].append({
                    "model": m.__name__,
                    "table": table,
                    "fields_count": len(m._meta.get_fields()),
                    "row_count": cnt
                })
    return json.dumps(catalog, indent=2)


def get_view_function_info(query: str) -> str:
    """Search or describe any backend view function, API endpoint URL, HTTP method, and what it does.
    Example: get_view_function_info('mixing') or get_view_function_info('salary') or get_view_function_info('tally_webhook')."""
    q = query.strip().lower()
    matches = []
    for v in BACKEND_VIEWS:
        if q in v["name"].lower() or q in v["module"].lower() or q in v["url"].lower() or q in v["description"].lower():
            matches.append(v)
    if matches:
        return json.dumps({"matches_found": len(matches), "views": matches})
    return json.dumps({
        "message": f"No direct match for '{query}'. All registered views: " + ", ".join(v["name"] for v in BACKEND_VIEWS)
    })


def get_frontend_page_info(page_route_or_keyword: str) -> str:
    """Returns information about frontend pages, Next.js routes, component files, and what APIs they use.
    Example: get_frontend_page_info('/rawmaterial/mixing') or get_frontend_page_info('production') or get_frontend_page_info('tally')."""
    q = page_route_or_keyword.strip().lower()
    matches = []
    for p in FRONTEND_PAGES:
        if q in p["route"].lower() or q in p["file"].lower() or q in p["title"].lower() or q in p["description"].lower():
            matches.append(p)
    if matches:
        return json.dumps({"matches_found": len(matches), "pages": matches})
    return json.dumps({
        "message": f"No direct match for '{page_route_or_keyword}'. Available routes: " + ", ".join(p["route"] for p in FRONTEND_PAGES)
    })


def describe_table_columns(table_name: str) -> str:
    """Runs MySQL DESCRIBE on any database table to return column names, types, nullability, and default values.
    Example: describe_table_columns('rawmaterial_mixing') or describe_table_columns('stock_tyreitem')."""
    clean_table = table_name.strip().replace(";", "").replace("`", "")
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DESCRIBE `{clean_table}`")
            cols = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            res = [dict(zip(cols, r)) for r in rows]
            return json.dumps({"table": clean_table, "columns": res})
    except Exception as e:
        return json.dumps({"error": str(e), "table": clean_table})


# List of tool functions to provide to Gemini
ALL_AI_TOOLS = [
    execute_sql_query,
    get_model_schema,
    list_all_models_and_tables,
    get_view_function_info,
    get_frontend_page_info,
    describe_table_columns,
]
