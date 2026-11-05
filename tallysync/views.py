import json
import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import TallyItemMapping, TallyInvoice, TallySyncLog, TallyPendingItem, MODULE_CHOICES
from .serializers import (
    TallyItemMappingSerializer, TallyInvoiceSerializer, TallyInvoiceListSerializer,
    TallySyncLogSerializer, TallyPendingItemSerializer,
)


def _to_decimal(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _reduce_stock_for_item(module, item, qty, voucher_number, voucher_date, party_name, tally_item_name="", pending_id=None):
    """Create a sale/dispatch entry for this item, reducing its appropriate stock bucket:
       - Export bills (RI/EX/ prefix): deduct from on_hold_export stock (tyre only)
       - 1st Grade / Main Stock
       - B Grade (2nd Grade Stock)
       - C Grade (3rd Grade / Reject / RFM Stock)
    """
    if item is None:
        return False, "Mapped item not found in the module (was it deleted?)."

    category_override = None
    if pending_id:
        pending = TallyPendingItem.objects.filter(pk=pending_id).first()
        if pending:
            category_override = pending.category_override

    name_lower = str(tally_item_name or "").lower()

    is_c_grade = (category_override == "cgrade") or any(k in name_lower for k in ["c grade", "c-grade", "3rd grade", "3rd", "c_grade", "c.grade", "reject"])
    is_b_grade = ((category_override == "bgrade") or any(k in name_lower for k in ["b grade", "b-grade", "2nd grade", "2nd", "b_grade", "b.grade"])) and not is_c_grade

    # Detect Export bills by voucher number prefix RI/EX/
    is_export = str(voucher_number or "").upper().startswith("RI/EX/")

    base_remark = f"Tally auto-sync | Party: {party_name or '-'}"
    if is_export:
        base_remark += " [EXPORT]"

    if module == "tyre":
        from stock.models import DailyEntry
        if is_export:
            # Export bills → deduct from on_hold_export
            bucket = "on_hold_export"
            current = getattr(item, "on_hold_export", 0) or 0
            stock_field = "on_hold_export"
            remark = f"{base_remark} [Export On-Hold Stock]"
        elif is_c_grade:
            bucket = "third_stock"
            current = getattr(item, "third_stock", 0)
            stock_field = "third_stock"
            remark = f"{base_remark} [C-Grade / 3rd Stock]"
        elif is_b_grade:
            bucket = "second_stock"
            current = getattr(item, "second_stock", 0)
            stock_field = "second_stock"
            remark = f"{base_remark} [B-Grade / 2nd Stock]"
        else:
            bucket = "stock"
            current = item.stock
            stock_field = "stock"
            remark = base_remark

        with transaction.atomic():
            setattr(item, stock_field, current - qty)
            item.save(update_fields=[stock_field])
            DailyEntry.objects.create(
                tyre_item=item, entry_type="dispatch", bucket=bucket,
                quantity=qty, date=voucher_date, bill_number=voucher_number,
                remark=remark, user=None,
            )

    elif module == "tube":
        from cycletube.models import CycleTubeEntry
        if is_c_grade:
            bucket = "rfm_stock"
            current = item.rfm_stock
            stock_field = "rfm_stock"
            remark = f"{base_remark} [C-Grade / Reject Stock]"
        else:
            bucket = "stock"
            current = item.stock
            stock_field = "stock"
            remark = base_remark

        with transaction.atomic():
            setattr(item, stock_field, current - qty)
            item.save(update_fields=[stock_field])
            CycleTubeEntry.objects.create(
                tube_item=item, entry_type="sale", bucket=bucket,
                quantity=qty, date=voucher_date, bill_number=voucher_number,
                remark=remark, user=None,
            )

    elif module == "cycletyre":
        from cycletyres.models import CycleTyreEntry
        if is_c_grade:
            bucket = "rejected_stock"
            current = getattr(item, "rejected_stock", 0)
            stock_field = "rejected_stock"
            remark = f"{base_remark} [C-Grade / Reject Stock]"
        elif is_b_grade:
            bucket = "second_stock"
            current = item.second_stock
            stock_field = "second_stock"
            remark = f"{base_remark} [B-Grade Stock]"
        else:
            bucket = "stock"
            current = item.stock
            stock_field = "stock"
            remark = base_remark

        with transaction.atomic():
            setattr(item, stock_field, current - qty)
            item.save(update_fields=[stock_field])
            CycleTyreEntry.objects.create(
                tyre_item=item, entry_type="sale", bucket=bucket,
                quantity=qty, date=voucher_date, bill_number=voucher_number,
                remark=remark, user=None,
            )
    else:
        return False, f"Unknown module '{module}'."

    return True, "ok"


def _maybe_mark_invoice_synced(invoice):
    still_pending = invoice.pending_items.filter(resolved=False).exists()
    if not still_pending and not invoice.stock_synced:
        invoice.stock_synced = True
        invoice.save(update_fields=["stock_synced"])


def retry_pending_items(tally_item_name=None):
    pending_qs = TallyPendingItem.objects.filter(resolved=False).select_related("invoice")
    if tally_item_name:
        pending_qs = pending_qs.filter(tally_item_name__iexact=tally_item_name)

    resolved_count = 0
    for pending in pending_qs:
        mapping = TallyItemMapping.objects.filter(tally_item_name__iexact=pending.tally_item_name).first()
        if not mapping:
            continue

        item = mapping.get_item()
        ok, msg = _reduce_stock_for_item(
            mapping.module, item, pending.qty,
            pending.voucher_number, pending.voucher_date, pending.party_name,
            tally_item_name=pending.tally_item_name,
            pending_id=pending.id
        )
        if ok:
            pending.resolved = True
            pending.resolved_at = timezone.now()
            pending.save(update_fields=["resolved", "resolved_at"])
            TallySyncLog.objects.create(
                invoice=pending.invoice, level="info",
                message=f"Resolved on retry: '{pending.tally_item_name}' x{pending.qty} — stock deducted."
            )
            _maybe_mark_invoice_synced(pending.invoice)
            resolved_count += 1

    return resolved_count


# ============================================================
# WEBHOOK — Called by TallySync GUI (.exe) / bridge script
# ============================================================

@csrf_exempt
def tally_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    api_key = request.headers.get("X-API-KEY", "")
    expected_key = getattr(settings, "TALLY_SYNC_API_KEY", "")
    if not expected_key or api_key != expected_key:
        return JsonResponse({"error": "invalid api key"}, status=403)

    retry_pending_items()

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    voucher_number = str(payload.get("voucher_number", "")).strip()
    if not voucher_number:
        return JsonResponse({"error": "voucher_number is required"}, status=400)

    voucher_date_raw = payload.get("date", "")
    try:
        voucher_date = datetime.datetime.strptime(voucher_date_raw, "%Y-%m-%d").date()
    except ValueError:
        voucher_date = datetime.date.today()

    party_name = str(payload.get("party_name", "")).strip()
    party_gstin = str(payload.get("party_gstin", "")).strip()
    party_address = str(payload.get("party_address", "")).strip()
    party_pincode = str(payload.get("party_pincode", "")).strip()
    consignee_name = str(payload.get("consignee_name", "")).strip()
    consignee_gstin = str(payload.get("consignee_gstin", "")).strip()
    consignee_address = str(payload.get("consignee_address", "")).strip()
    consignee_state = str(payload.get("consignee_state", "")).strip()
    consignee_pincode = str(payload.get("consignee_pincode", "")).strip()
    place_of_supply = str(payload.get("place_of_supply", "")).strip()
    state_name = str(payload.get("state_name", "")).strip()
    gst_registration_type = str(payload.get("gst_registration_type", "")).strip()

    # Transport & Logistics
    transporter_name = str(payload.get("transporter_name", "")).strip()
    transporter_id = str(payload.get("transporter_id", "")).strip()
    vehicle_number = str(payload.get("vehicle_number", "")).strip()
    lr_number = str(payload.get("lr_number", "")).strip()
    lr_date = str(payload.get("lr_date", "")).strip()

    # e-Invoice & E-Way Bill
    irn = str(payload.get("irn", "")).strip()
    ack_number = str(payload.get("ack_number", "")).strip()
    ack_date = str(payload.get("ack_date", "")).strip()
    eway_bill_number = str(payload.get("eway_bill_number", "")).strip()
    eway_bill_date = str(payload.get("eway_bill_date", "")).strip()

    # Sales / GST Ledger
    sales_ledger = str(payload.get("sales_ledger", "")).strip()

    items = payload.get("items", [])

    cgst_val = _to_decimal(payload.get("cgst"))
    sgst_val = _to_decimal(payload.get("sgst"))
    igst_val = _to_decimal(payload.get("igst"))
    total_val = _to_decimal(payload.get("total_value"))
    taxable_val = _to_decimal(payload.get("taxable_value"))
    gst_total = cgst_val + sgst_val + igst_val

    items_sum = Decimal("0")
    for line in items:
        items_sum += _to_decimal(line.get("amount", 0))

    if items_sum > 0:
        taxable_val = items_sum
    elif (taxable_val == total_val and gst_total > 0) or taxable_val <= 0:
        taxable_val = max(total_val - gst_total, Decimal("0"))

    payload["taxable_value"] = float(taxable_val)

    # Check if invoice already exists - if so, update fields without double deducting stock
    existing = TallyInvoice.objects.filter(voucher_number=voucher_number).first()
    if existing:
        existing.voucher_date = voucher_date
        existing.party_name = party_name
        existing.party_gstin = party_gstin
        existing.party_address = party_address
        existing.party_pincode = party_pincode
        existing.consignee_name = consignee_name
        existing.consignee_gstin = consignee_gstin
        existing.consignee_address = consignee_address
        existing.consignee_state = consignee_state
        existing.consignee_pincode = consignee_pincode
        existing.place_of_supply = place_of_supply
        existing.state_name = state_name
        existing.gst_registration_type = gst_registration_type
        existing.transporter_name = transporter_name
        existing.transporter_id = transporter_id
        existing.vehicle_number = vehicle_number
        existing.lr_number = lr_number
        existing.lr_date = lr_date
        existing.irn = irn
        existing.ack_number = ack_number
        existing.ack_date = ack_date
        existing.eway_bill_number = eway_bill_number
        existing.eway_bill_date = eway_bill_date
        existing.sales_ledger = sales_ledger
        existing.taxable_value = taxable_val
        existing.cgst = cgst_val
        existing.sgst = sgst_val
        existing.igst = igst_val
        existing.total_value = total_val
        existing.raw_payload = json.dumps(payload, indent=2)
        existing.save()
        return JsonResponse({"status": "updated", "voucher_number": voucher_number}, status=200)

    invoice = TallyInvoice.objects.create(
        voucher_number=voucher_number,
        voucher_date=voucher_date,
        party_name=party_name,
        party_gstin=party_gstin,
        party_address=party_address,
        party_pincode=party_pincode,
        consignee_name=consignee_name,
        consignee_gstin=consignee_gstin,
        consignee_address=consignee_address,
        consignee_state=consignee_state,
        consignee_pincode=consignee_pincode,
        place_of_supply=place_of_supply,
        state_name=state_name,
        gst_registration_type=gst_registration_type,
        transporter_name=transporter_name,
        transporter_id=transporter_id,
        vehicle_number=vehicle_number,
        lr_number=lr_number,
        lr_date=lr_date,
        irn=irn,
        ack_number=ack_number,
        ack_date=ack_date,
        eway_bill_number=eway_bill_number,
        eway_bill_date=eway_bill_date,
        sales_ledger=sales_ledger,
        taxable_value=taxable_val,
        cgst=cgst_val,
        sgst=sgst_val,
        igst=igst_val,
        total_value=total_val,
        raw_payload=json.dumps(payload, indent=2),
    )

    all_ok = True
    results = []
    for line in items:
        tally_name = str(line.get("name", "")).strip()
        qty = int(line.get("qty", 0) or 0)

        mapping = TallyItemMapping.objects.filter(tally_item_name__iexact=tally_name).first()
        if not mapping:
            all_ok = False
            msg = f"Item '{tally_name}' is not mapped — stock not updated."
            TallySyncLog.objects.create(invoice=invoice, level="warning", message=msg)
            TallyPendingItem.objects.create(
                invoice=invoice, tally_item_name=tally_name, qty=qty,
                voucher_number=voucher_number, voucher_date=voucher_date,
                party_name=party_name, reason="unmapped",
            )
            results.append({"item": tally_name, "ok": False, "reason": "unmapped"})
            continue

        item = mapping.get_item()
        ok, msg = _reduce_stock_for_item(
            mapping.module, item, qty, voucher_number, voucher_date, party_name,
            tally_item_name=tally_name
        )
        if not ok:
            all_ok = False
            TallySyncLog.objects.create(invoice=invoice, level="error", message=msg)
            TallyPendingItem.objects.create(
                invoice=invoice, tally_item_name=tally_name, qty=qty,
                voucher_number=voucher_number, voucher_date=voucher_date,
                party_name=party_name, reason="insufficient_stock",
            )
        results.append({"item": tally_name, "ok": ok, "reason": msg})

    invoice.stock_synced = all_ok and len(items) > 0
    invoice.save(update_fields=["stock_synced"])

    if all_ok:
        TallySyncLog.objects.create(invoice=invoice, level="info", message="All items processed successfully, stock updated.")

    return JsonResponse({"status": "processed", "voucher_number": voucher_number, "items": results})


# ============================================================
# REST API — Sales Summary (Invoices list)
# ============================================================

@csrf_exempt
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def sales_summary(request):
    today = datetime.date.today()
    month_str = request.query_params.get("month", "")
    from_date_str = request.query_params.get("from_date", "")
    to_date_str = request.query_params.get("to_date", "")
    party_query = request.query_params.get("party", "")
    ledger_query = request.query_params.get("ledger", "").strip()

    invoices = TallyInvoice.objects.all()

    if from_date_str or to_date_str:
        if from_date_str:
            try:
                invoices = invoices.filter(voucher_date__gte=datetime.datetime.strptime(from_date_str, "%Y-%m-%d").date())
            except ValueError:
                pass
        if to_date_str:
            try:
                invoices = invoices.filter(voucher_date__lte=datetime.datetime.strptime(to_date_str, "%Y-%m-%d").date())
            except ValueError:
                pass
    elif month_str:
        if month_str.lower() != "all":
            try:
                y, m = month_str.split("-")
                year, month = int(y), int(m)
                invoices = invoices.filter(voucher_date__year=year, voucher_date__month=month)
            except ValueError:
                pass
    # If month_str is empty, default to current month unless all_months=true or view_all=true
    elif request.query_params.get("all_months") != "true" and request.query_params.get("view_all") != "true" and not party_query:
        year, month = today.year, today.month
        invoices = invoices.filter(voucher_date__year=year, voucher_date__month=month)

    if party_query:
        invoices = invoices.filter(
            Q(party_name__icontains=party_query) |
            Q(voucher_number__icontains=party_query) |
            Q(party_gstin__icontains=party_query)
        )

    if ledger_query:
        ledger_list = [l.strip() for l in ledger_query.split(",") if l.strip()]
        if ledger_list:
            ledger_q = Q()
            for l in ledger_list:
                ledger_q |= Q(sales_ledger__icontains=l) | Q(raw_payload__icontains=l)
            invoices = invoices.filter(ledger_q)

    agg = invoices.aggregate(
        total_sale=Sum("total_value"),
        total_taxable=Sum("taxable_value"),
        total_cgst=Sum("cgst"),
        total_sgst=Sum("sgst"),
        total_igst=Sum("igst"),
    )

    total_cgst = agg["total_cgst"] or 0
    total_sgst = agg["total_sgst"] or 0
    total_igst = agg["total_igst"] or 0

    # Calculate total pcs across filtered invoices
    total_pcs = 0
    for inv in invoices.only("raw_payload"):
        try:
            payload = json.loads(inv.raw_payload or "{}")
            total_pcs += sum(int(it.get("qty", 0) or 0) for it in payload.get("items", []))
        except Exception:
            pass

    # Extract distinct ledger names strictly from synced Tally invoices
    ledger_set = set()
    raw_ledgers = TallyInvoice.objects.exclude(sales_ledger__isnull=True).exclude(sales_ledger="").values_list("sales_ledger", flat=True).distinct()
    for l in raw_ledgers:
        if l:
            for part in str(l).split(","):
                cleaned = part.strip()
                if cleaned:
                    ledger_set.add(cleaned)

    # Also scan raw_payload for any item-level ledgers
    for inv in TallyInvoice.objects.only("raw_payload"):
        try:
            payload = json.loads(inv.raw_payload or "{}")
            sl = payload.get("sales_ledger")
            if sl:
                for part in str(sl).split(","):
                    c = part.strip()
                    if c: ledger_set.add(c)
            for it in payload.get("items", []):
                il = it.get("ledger") or it.get("sales_ledger")
                if il:
                    c = str(il).strip()
                    if c: ledger_set.add(c)
        except Exception:
            pass

    invoices_ordered = invoices.order_by("-pk", "-voucher_date")
    serialized = TallyInvoiceListSerializer(invoices_ordered[:1000], many=True).data

    return Response({
        "invoices": serialized,
        "totals": {
            "total_sale": str(agg["total_sale"] or 0),
            "total_taxable": str(agg["total_taxable"] or 0),
            "total_cgst": str(total_cgst),
            "total_sgst": str(total_sgst),
            "total_igst": str(total_igst),
            "total_gst": str(total_cgst + total_sgst + total_igst),
            "total_pcs": total_pcs,
        },
        "invoice_count": invoices.count(),
        "unmapped_count": invoices.filter(stock_synced=False).count(),
        "available_ledgers": sorted(list(ledger_set)),
    })


# ============================================================
# Invoice Detail
# ============================================================

@csrf_exempt
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def invoice_detail(request, pk):
    invoice = get_object_or_404(TallyInvoice, pk=pk)
    data = TallyInvoiceSerializer(invoice).data
    pending_items = TallyPendingItemSerializer(invoice.pending_items.all(), many=True).data
    logs = TallySyncLogSerializer(invoice.logs.all(), many=True).data
    return Response({"invoice": data, "pending_items": pending_items, "logs": logs})


# ============================================================
# Item Mapping CRUD
# ============================================================

@csrf_exempt
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def mapping_list(request):
    mappings = TallyItemMapping.objects.all()
    rows = []
    for m in mappings:
        item = m.get_item()
        row = TallyItemMappingSerializer(m).data
        row["resolved_item_label"] = str(item) if item else f"(deleted #{m.item_id})"
        rows.append(row)
    return Response(rows)


@csrf_exempt
@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def add_mapping(request):
    from stock.models import TyreItem
    from cycletube.models import CycleTubeItem
    from cycletyres.models import CycleTyreItem

    if request.method == "GET":
        tyre_items = [{"id": t.id, "label": str(t)} for t in TyreItem.objects.filter(is_active=True)]
        tube_items = [{"id": t.id, "label": str(t)} for t in CycleTubeItem.objects.filter(is_active=True)]
        cycletyre_items = [{"id": t.id, "label": str(t)} for t in CycleTyreItem.objects.filter(is_active=True)]
        return Response({
            "tyre_items": tyre_items,
            "tube_items": tube_items,
            "cycletyre_items": cycletyre_items,
        })

    tally_item_name = str(request.data.get("tally_item_name", "")).strip()
    module = str(request.data.get("module", "")).strip()
    item_id = request.data.get("item_id")

    if not tally_item_name or not module or not item_id:
        return Response({"error": "tally_item_name, module, and item_id are required."}, status=status.HTTP_400_BAD_REQUEST)

    mapping, created = TallyItemMapping.objects.update_or_create(
        tally_item_name=tally_item_name,
        defaults={"module": module, "item_id": int(item_id)},
    )
    resolved = retry_pending_items(tally_item_name=tally_item_name)
    return Response({
        "ok": True,
        "mapping": TallyItemMappingSerializer(mapping).data,
        "resolved_count": resolved,
    }, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(["DELETE", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def delete_mapping(request, pk):
    mapping = TallyItemMapping.objects.filter(pk=pk).first()
    if mapping:
        mapping.delete()
    return Response({"ok": True, "message": "Mapping deleted successfully."})


@csrf_exempt
@api_view(["PATCH", "POST", "PUT"])
@authentication_classes([])
@permission_classes([AllowAny])
def update_mapping(request, pk):
    mapping = get_object_or_404(TallyItemMapping, pk=pk)
    module = str(request.data.get("module", "")).strip()
    item_id = request.data.get("item_id")

    if module:
        mapping.module = module
    if item_id is not None:
        mapping.item_id = int(item_id)
    mapping.save()

    resolved = retry_pending_items(tally_item_name=mapping.tally_item_name)
    item = mapping.get_item()
    data = TallyItemMappingSerializer(mapping).data
    data["resolved_item_label"] = str(item) if item else f"(deleted #{mapping.item_id})"

    return Response({
        "ok": True,
        "mapping": data,
        "resolved_count": resolved,
    })


# ============================================================
# Sync Logs & Pending Items
# ============================================================

@csrf_exempt
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def sync_log(request):
    try:
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 15))
    except ValueError:
        page = 1
        page_size = 15

    logs_qs = TallySyncLog.objects.select_related("invoice")
    total_logs = logs_qs.count()

    start = (page - 1) * page_size
    end = start + page_size

    logs = logs_qs[start:end]
    pending = TallyPendingItem.objects.filter(resolved=False).select_related("invoice")

    import math
    total_pages = math.ceil(total_logs / page_size) if total_logs > 0 else 1

    response = Response({
        "logs": TallySyncLogSerializer(logs, many=True).data,
        "total_logs": total_logs,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "pending": TallyPendingItemSerializer(pending, many=True).data,
        "pending_total": pending.count(),
    })
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def retry_pending_now(request):
    count = retry_pending_items()
    return Response({"resolved_count": count, "message": f"{count} pending item(s) resolved."})


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def retry_single_pending(request, pk):
    pending = TallyPendingItem.objects.filter(pk=pk).first()
    if not pending or pending.resolved:
        return Response({"ok": True, "message": "Already resolved or removed."})

    mapping = TallyItemMapping.objects.filter(tally_item_name__iexact=pending.tally_item_name).first()
    if not mapping:
        return Response({"error": f"'{pending.tally_item_name}' is not mapped."}, status=status.HTTP_400_BAD_REQUEST)

    item = mapping.get_item()
    ok, msg = _reduce_stock_for_item(
        mapping.module, item, pending.qty,
        pending.voucher_number, pending.voucher_date, pending.party_name,
        tally_item_name=pending.tally_item_name,
        pending_id=pending.id
    )
    if ok:
        pending.resolved = True
        pending.resolved_at = timezone.now()
        pending.save(update_fields=["resolved", "resolved_at"])
        if pending.invoice:
            TallySyncLog.objects.create(invoice=pending.invoice, level="info",
                message=f"Manual retry resolved: '{pending.tally_item_name}' x{pending.qty}.")
            _maybe_mark_invoice_synced(pending.invoice)
        return Response({"ok": True, "message": f"Resolved: {pending.tally_item_name} x{pending.qty}"})
    else:
        return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(["POST", "PATCH"])
@authentication_classes([])
@permission_classes([AllowAny])
def update_pending_category(request, pk):
    pending = TallyPendingItem.objects.filter(pk=pk).first()
    if not pending:
        return Response({"error": "Pending item not found."}, status=status.HTTP_404_NOT_FOUND)
    category = str(request.data.get("category", "")).strip()
    if category:
        pending.category_override = category
        pending.save(update_fields=["category_override"])
    return Response({"ok": True, "category": pending.category_override})


@csrf_exempt
@api_view(["POST", "DELETE"])
@authentication_classes([])
@permission_classes([AllowAny])
def delete_pending_item(request, pk):
    try:
        pending = TallyPendingItem.objects.filter(pk=pk).first()
        if not pending:
            return Response({"ok": True, "message": "Pending item already removed."})

        delete_mode = str(request.data.get("mode", request.query_params.get("mode", "mapping_only"))).strip()
        invoice = pending.invoice

        if invoice and delete_mode == "full":
            TallySyncLog.objects.create(
                invoice=invoice,
                level="warning",
                message=f"FULL DELETE: Item '{pending.tally_item_name}' (Qty: {pending.qty}) completely removed from invoice {pending.voucher_number}."
            )
            pending.delete()
            _maybe_mark_invoice_synced(invoice)
            return Response({"ok": True, "message": f"Full delete complete for '{pending.tally_item_name}'."})
        else:
            if invoice:
                TallySyncLog.objects.create(
                    invoice=invoice,
                    level="info",
                    message=f"Sync entry '{pending.tally_item_name}' removed from pending list."
                )
            pending.delete()
            if invoice:
                _maybe_mark_invoice_synced(invoice)
            return Response({"ok": True, "message": f"Pending item '{pending.tally_item_name}' removed from pending list."})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def map_pending_item(request, pk):
    """Inline map & sync from pending items list."""
    pending = TallyPendingItem.objects.filter(pk=pk).first()
    if not pending:
        return Response({"ok": True, "message": "Pending item already resolved or removed."})

    module = str(request.data.get("module", "")).strip()
    item_id = request.data.get("item_id")
    mapping_type = str(request.data.get("mapping_type", "permanent")).strip()

    if not module or not item_id:
        return Response({"error": "module and item_id are required."}, status=status.HTTP_400_BAD_REQUEST)

    from stock.models import TyreItem
    from cycletube.models import CycleTubeItem
    from cycletyres.models import CycleTyreItem

    target_item = None
    if module == "tyre":
        target_item = TyreItem.objects.filter(pk=item_id).first()
    elif module == "tube":
        target_item = CycleTubeItem.objects.filter(pk=item_id).first()
    elif module == "cycletyre":
        target_item = CycleTyreItem.objects.filter(pk=item_id).first()

    if not target_item:
        return Response({"error": "Selected item not found."}, status=status.HTTP_400_BAD_REQUEST)

    if mapping_type == "one_time":
        ok, msg = _reduce_stock_for_item(
            module, target_item, pending.qty,
            pending.voucher_number, pending.voucher_date, pending.party_name,
            tally_item_name=pending.tally_item_name,
            pending_id=pending.id
        )
        if ok:
            pending.resolved = True
            pending.resolved_at = timezone.now()
            pending.save(update_fields=["resolved", "resolved_at"])
            if pending.invoice:
                TallySyncLog.objects.create(invoice=pending.invoice, level="info",
                    message=f"1-Time Sync: '{pending.tally_item_name}' x{pending.qty} mapped to {target_item}.")
                _maybe_mark_invoice_synced(pending.invoice)
            return Response({"ok": True, "message": f"One-time resolved: {pending.tally_item_name} x{pending.qty}"})
        else:
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
    else:
        TallyItemMapping.objects.update_or_create(
            tally_item_name=pending.tally_item_name,
            defaults={"module": module, "item_id": int(item_id)},
        )
        resolved = retry_pending_items(tally_item_name=pending.tally_item_name)
        return Response({
            "ok": True,
            "message": f"Permanent mapping saved. {resolved} pending item(s) resolved.",
            "resolved_count": resolved,
        })



# ============================================================
# All items list (for mapping dropdowns)
# ============================================================

@csrf_exempt
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def all_stock_items(request):
    from stock.models import TyreItem
    from cycletube.models import CycleTubeItem
    from cycletyres.models import CycleTyreItem

    tyre_items = [{"id": t.id, "label": str(t), "module": "tyre"} for t in TyreItem.objects.all()]
    tube_items = [{"id": t.id, "label": str(t), "module": "tube"} for t in CycleTubeItem.objects.all()]
    cycletyre_items = [{"id": t.id, "label": str(t), "module": "cycletyre"} for t in CycleTyreItem.objects.all()]

    return Response({
        "items": tyre_items + tube_items + cycletyre_items,
        "tyre_items": tyre_items,
        "tube_items": tube_items,
        "cycletyre_items": cycletyre_items,
    })


# ============================================================
# Excel mapping import / export
# ============================================================

@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def import_mapping_excel(request):
    file_obj = request.FILES.get("file") or request.FILES.get("excel_file")
    if not file_obj:
        return Response(
            {"error": "No file uploaded. Select the Tally mapping Excel (.xlsx)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    name = (file_obj.name or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        return Response(
            {"error": "Please upload an .xlsx file (Excel 2007+)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    dry_run = str(request.data.get("dry_run", "")).lower() in {"1", "true", "yes"}

    from .excel_mapping import parse_mapping_workbook, import_mapping_rows

    try:
        rows = parse_mapping_workbook(file_obj)
    except Exception as exc:
        return Response(
            {"error": f"Could not read Excel file: {exc}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not rows:
        return Response(
            {"error": "No Tally item rows found. Use the 'Tally Item Mapping' sheet with a Tally Item Name column."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = import_mapping_rows(rows, dry_run=dry_run)
    resolved = 0
    if not dry_run:
        for tally_name in result["imported_names"]:
            resolved += retry_pending_items(tally_item_name=tally_name)

    return Response({
        "ok": True,
        "dry_run": dry_run,
        "row_count": len(rows),
        "created": result["created"],
        "updated": result["updated"],
        "skipped": result["skipped"],
        "imported_count": result["imported_count"],
        "unmatched": result["unmatched"],
        "unmatched_count": len(result["unmatched"]),
        "resolved_count": resolved,
        "message": (
            f"{'Preview: ' if dry_run else ''}"
            f"{result['created']} new, {result['updated']} updated, "
            f"{result['skipped']} skipped, {len(result['unmatched'])} unmatched."
        ),
    })


@csrf_exempt
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def export_mapping_excel(request):
    from django.http import HttpResponse
    from .excel_mapping import build_export_workbook

    buf = build_export_workbook()
    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="Radhu_Tally_Item_Mapping.xlsx"'
    return response
