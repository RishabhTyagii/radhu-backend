"""Execute confirmed RADHU AI ERP actions. Never called without a stored proposal."""
import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

ALLOWED_MODULES = {"cycle_tyre", "cycle_tube", "auto_tyre"}
ALLOWED_ACTIONS = {
    "add_item",
    "delete_item",
    "add_production",
    "add_sale",
    "add_dispatch",
    "add_adjustment",
    "import_items",
    "import_production",
}
HIGH_RISK_ACTIONS = {"delete_item"}
MAX_IMPORT_ROWS = 80


def _today():
    return timezone.localdate()


def _parse_date(value):
    if not value:
        return _today()
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    text = str(value).strip()[:10]
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return _today()


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _dec(value, default="0"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _module(payload, fallback=""):
    module = (payload.get("module") or fallback or "").strip().lower().replace(" ", "_")
    aliases = {
        "cycletyre": "cycle_tyre",
        "cycletyres": "cycle_tyre",
        "tyre": "cycle_tyre",
        "cycletube": "cycle_tube",
        "tube": "cycle_tube",
        "auto": "auto_tyre",
        "autotyre": "auto_tyre",
        "stock": "auto_tyre",
    }
    module = aliases.get(module, module)
    if module not in ALLOWED_MODULES:
        raise ValueError(f"Unknown module '{payload.get('module')}'. Use cycle_tyre, cycle_tube, or auto_tyre.")
    return module


def normalize_action(raw):
    if not isinstance(raw, dict):
        raise ValueError("Each action must be an object.")
    action_type = str(raw.get("action") or raw.get("action_type") or "").strip()
    if action_type == "add_sale" and _safe_module(raw) == "auto_tyre":
        action_type = "add_dispatch"
    if action_type not in ALLOWED_ACTIONS:
        raise ValueError(f"Action '{action_type}' is not allowed.")
    payload = dict(raw)
    payload.pop("action", None)
    payload.pop("action_type", None)
    module = _module(payload, payload.get("module") or "")
    payload["module"] = module
    if action_type in ("import_items", "import_production"):
        rows = payload.get("rows") or []
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{action_type} needs a non-empty rows list.")
        if len(rows) > MAX_IMPORT_ROWS:
            raise ValueError(f"{action_type} limited to {MAX_IMPORT_ROWS} rows.")
        payload["clear_existing"] = False
        payload["rows"] = rows[:MAX_IMPORT_ROWS]
    risk = "high" if action_type in HIGH_RISK_ACTIONS else "normal"
    return action_type, module, payload, risk


def _safe_module(raw):
    try:
        return _module(raw, raw.get("module") or "")
    except Exception:
        return ""


def summarize_action(action_type, module, payload):
    label = {
        "cycle_tyre": "Cycle Tyre",
        "cycle_tube": "Cycle Tube",
        "auto_tyre": "Auto Tyre",
    }.get(module, module)
    if action_type == "add_item":
        name = _item_label(module, payload)
        return f"Add {label} item: {name}"
    if action_type == "delete_item":
        name = _item_label(module, payload) or f"id={payload.get('item_id')}"
        return f"Delete / deactivate {label} item: {name}"
    if action_type == "add_production":
        qty = payload.get("all_curing") or payload.get("quantity") or "?"
        return f"Add {label} production: {qty} pcs — {_item_label(module, payload)}"
    if action_type in ("add_sale", "add_dispatch"):
        kind = "dispatch" if action_type == "add_dispatch" else "sale"
        return f"Add {label} {kind}: {payload.get('quantity')} pcs — {_item_label(module, payload)}"
    if action_type == "add_adjustment":
        return f"Adjust {label} stock by {payload.get('quantity')} — {_item_label(module, payload)}"
    if action_type == "import_items":
        return f"Import {len(payload.get('rows') or [])} {label} items from sheet"
    if action_type == "import_production":
        return f"Import {len(payload.get('rows') or [])} {label} production rows from sheet"
    return f"{action_type} on {label}"


def _item_label(module, payload):
    if module == "cycle_tyre":
        parts = [payload.get("size"), payload.get("box_type"), payload.get("material"), payload.get("brand")]
        return " ".join(str(p) for p in parts if p) or str(payload.get("item_id") or "")
    if module == "cycle_tube":
        parts = [payload.get("size"), payload.get("type"), payload.get("brand")]
        return " ".join(str(p) for p in parts if p) or str(payload.get("item_id") or "")
    parts = [payload.get("tyre"), payload.get("pattern"), payload.get("type")]
    return " ".join(str(p) for p in parts if p) or str(payload.get("item_id") or payload.get("name") or "")


def find_cycle_tyre(payload):
    from cycletyres.models import CycleTyreItem

    item_id = payload.get("item_id") or payload.get("tyre_item") or payload.get("id")
    if item_id:
        item = CycleTyreItem.objects.filter(pk=_int(item_id)).first()
        if item:
            return item
    size = (payload.get("size") or "").strip()
    brand = (payload.get("brand") or "").strip()
    box_type = (payload.get("box_type") or "").strip()
    material = (payload.get("material") or "").strip()
    qs = CycleTyreItem.objects.all()
    if size:
        qs = qs.filter(size__iexact=size)
    if brand:
        qs = qs.filter(brand__iexact=brand)
    if box_type:
        qs = qs.filter(box_type__iexact=box_type)
    if material:
        qs = qs.filter(material__iexact=material)
    if size or brand:
        item = qs.first()
        if item:
            return item
    raise ValueError(f"Cycle tyre item not found ({_item_label('cycle_tyre', payload)}).")


def find_cycle_tube(payload):
    from cycletube.models import CycleTubeItem

    item_id = payload.get("item_id") or payload.get("tube_item") or payload.get("id")
    if item_id:
        item = CycleTubeItem.objects.filter(pk=_int(item_id)).first()
        if item:
            return item
    size = (payload.get("size") or "").strip()
    brand = (payload.get("brand") or "").strip()
    ttype = (payload.get("type") or "").strip()
    qs = CycleTubeItem.objects.all()
    if size:
        qs = qs.filter(size__iexact=size)
    if brand:
        qs = qs.filter(brand__iexact=brand)
    if ttype:
        qs = qs.filter(type__iexact=ttype)
    if size or brand:
        item = qs.first()
        if item:
            return item
    raise ValueError(f"Cycle tube item not found ({_item_label('cycle_tube', payload)}).")


def find_auto_tyre(payload):
    from stock.models import TyreItem

    item_id = payload.get("item_id") or payload.get("tyre_item") or payload.get("id")
    if item_id:
        item = TyreItem.objects.filter(pk=_int(item_id)).first()
        if item:
            return item
    tyre = (payload.get("tyre") or payload.get("name") or "").strip()
    pattern = (payload.get("pattern") or "").strip()
    ttype = (payload.get("type") or "").strip()
    qs = TyreItem.objects.all()
    if tyre:
        qs = qs.filter(tyre__iexact=tyre)
    if pattern:
        qs = qs.filter(pattern__iexact=pattern)
    if ttype:
        qs = qs.filter(type__iexact=ttype)
    item = qs.first()
    if item:
        return item
    if tyre:
        item = TyreItem.objects.filter(tyre__icontains=tyre.split()[0]).first()
        if item:
            return item
    raise ValueError(f"Auto tyre item not found ({_item_label('auto_tyre', payload)}).")


def _find(module, payload):
    if module == "cycle_tyre":
        return find_cycle_tyre(payload)
    if module == "cycle_tube":
        return find_cycle_tube(payload)
    return find_auto_tyre(payload)


def execute_action(action_type, module, payload, user):
    if action_type == "add_item":
        return _add_item(module, payload)
    if action_type == "delete_item":
        return _delete_item(module, payload)
    if action_type == "add_production":
        return _add_production(module, payload, user)
    if action_type in ("add_sale", "add_dispatch"):
        return _add_sale_or_dispatch(module, payload, user)
    if action_type == "add_adjustment":
        return _add_adjustment(module, payload, user)
    if action_type == "import_items":
        return _import_items(module, payload)
    if action_type == "import_production":
        return _import_production(module, payload, user)
    raise ValueError(f"Unsupported action {action_type}")


def _add_item(module, payload):
    if module == "cycle_tyre":
        from cycletyres.models import CycleTyreItem

        size = (payload.get("size") or "").strip()
        box_type = (payload.get("box_type") or "BOX").strip() or "BOX"
        material = (payload.get("material") or "").strip()
        brand = (payload.get("brand") or "").strip()
        if not size or not material or not brand:
            raise ValueError("Cycle tyre add needs size, material, and brand.")
        item, created = CycleTyreItem.objects.get_or_create(
            size=size, box_type=box_type, material=material, brand=brand,
            defaults={
                "weight": _dec(payload.get("weight") or 0),
                "is_active": True,
            },
        )
        if not created:
            if not item.is_active:
                item.is_active = True
                item.save(update_fields=["is_active"])
                return {"ok": True, "created": False, "reactivated": True, "id": item.id, "label": str(item)}
            raise ValueError(f"Item already exists: {item}")
        return {"ok": True, "created": True, "id": item.id, "label": str(item)}

    if module == "cycle_tube":
        from cycletube.models import CycleTubeItem

        size = (payload.get("size") or "").strip()
        ttype = (payload.get("type") or "").strip()
        brand = (payload.get("brand") or "").strip()
        if not size or not ttype or not brand:
            raise ValueError("Cycle tube add needs size, type, and brand.")
        item, created = CycleTubeItem.objects.get_or_create(
            size=size, type=ttype, brand=brand,
            defaults={"weight": _dec(payload.get("weight") or 0), "is_active": True},
        )
        if not created:
            if not item.is_active:
                item.is_active = True
                item.save(update_fields=["is_active"])
                return {"ok": True, "created": False, "reactivated": True, "id": item.id, "label": str(item)}
            raise ValueError(f"Item already exists: {item}")
        return {"ok": True, "created": True, "id": item.id, "label": str(item)}

    from stock.models import TyreItem

    tyre = (payload.get("tyre") or payload.get("size") or "").strip()
    pattern = (payload.get("pattern") or "").strip() or "DEFAULT"
    ttype = (payload.get("type") or "TT").strip() or "TT"
    if not tyre:
        raise ValueError("Auto tyre add needs tyre size.")
    item, created = TyreItem.objects.get_or_create(
        tyre=tyre, pattern=pattern, type=ttype,
        defaults={"weight": _dec(payload.get("weight") or 0), "is_active": True},
    )
    if not created:
        if not item.is_active:
            item.is_active = True
            item.save(update_fields=["is_active"])
            return {"ok": True, "created": False, "reactivated": True, "id": item.id, "label": str(item)}
        raise ValueError(f"Item already exists: {item}")
    return {"ok": True, "created": True, "id": item.id, "label": str(item)}


def _delete_item(module, payload):
    item = _find(module, payload)
    hard = str(payload.get("hard") or "").lower() in ("true", "1", "yes")
    if module == "cycle_tyre":
        has_entries = item.entries.exists()
    elif module == "cycle_tube":
        has_entries = item.entries.exists()
    else:
        has_entries = item.entries.exists()

    label = str(item)
    item_id = item.id
    if hard and not has_entries:
        item.delete()
        return {"ok": True, "deleted": True, "id": item_id, "label": label, "mode": "hard"}
    item.is_active = False
    item.save(update_fields=["is_active"])
    return {
        "ok": True,
        "deleted": False,
        "deactivated": True,
        "id": item_id,
        "label": label,
        "mode": "deactivate",
        "reason": "Has history entries — deactivated instead of hard delete." if has_entries else "Soft delete.",
    }


def _add_production(module, payload, user):
    date_val = _parse_date(payload.get("date"))
    remark = (payload.get("remark") or "").strip() or "RADHU AI"
    item = _find(module, payload)

    if module == "cycle_tyre":
        from cycletyres.models import CycleTyreEntry

        all_curing = _int(payload.get("all_curing") or payload.get("quantity"))
        second_grade = _int(payload.get("second_grade"))
        rejected_grade = _int(payload.get("rejected_grade"))
        if all_curing <= 0:
            raise ValueError("Production needs all_curing / quantity > 0.")
        first_grade = all_curing - (second_grade + rejected_grade)
        if first_grade < 0:
            raise ValueError("2nd + rejected cannot exceed all curing.")
        with transaction.atomic():
            item.stock += first_grade
            item.second_stock += second_grade
            item.rejected_stock += rejected_grade
            item.save(update_fields=["stock", "second_stock", "rejected_stock"])
            entry = CycleTyreEntry.objects.create(
                tyre_item=item,
                entry_type="production",
                bucket="stock",
                quantity=first_grade,
                all_curing=all_curing,
                first_grade=first_grade,
                second_grade=second_grade,
                rejected_grade=rejected_grade,
                date=date_val,
                remark=remark,
                user=user,
            )
        return {"ok": True, "entry_id": entry.id, "item": str(item), "first_grade": first_grade}

    if module == "cycle_tube":
        from cycletube.models import CycleTubeEntry

        quantity = _int(payload.get("quantity") or payload.get("all_curing"))
        bucket = payload.get("bucket") or "stock"
        if quantity <= 0:
            raise ValueError("Production quantity must be > 0.")
        if bucket == "rfm_stock":
            item.rfm_stock += quantity
            item.save(update_fields=["rfm_stock"])
        else:
            item.stock += quantity
            item.save(update_fields=["stock"])
        entry = CycleTubeEntry.objects.create(
            tube_item=item,
            entry_type="production",
            bucket=bucket if bucket in ("stock", "rfm_stock") else "stock",
            quantity=quantity,
            tube_quality=payload.get("tube_quality") or "normal",
            date=date_val,
            remark=remark,
            user=user,
        )
        return {"ok": True, "entry_id": entry.id, "item": str(item), "quantity": quantity}

    from stock.models import DailyEntry

    all_curing = _int(payload.get("all_curing") or payload.get("quantity"))
    production_tyre = _int(payload.get("production_tyre"))
    repair = _int(payload.get("repair"))
    second_grade = _int(payload.get("second_grade"))
    third_grade = _int(payload.get("third_grade"))
    lose_tyre = _int(payload.get("lose_tyre"))
    packing = (all_curing + repair + production_tyre) - (second_grade + third_grade + lose_tyre)
    if packing < 0:
        raise ValueError("Packing quantity cannot be negative.")
    with transaction.atomic():
        item.stock += packing
        item.second_stock += second_grade
        item.third_stock += third_grade
        item.save(update_fields=["stock", "second_stock", "third_stock"])
        entry = DailyEntry.objects.create(
            tyre_item=item,
            entry_type="production",
            bucket="stock",
            quantity=packing,
            date=date_val,
            all_curing=all_curing,
            production_tyre=production_tyre,
            repair=repair,
            second_grade=second_grade,
            third_grade=third_grade,
            lose_tyre=lose_tyre,
            remark=remark,
            user=user,
        )
    return {"ok": True, "entry_id": entry.id, "item": str(item), "packing": packing}


def _add_sale_or_dispatch(module, payload, user):
    date_val = _parse_date(payload.get("date"))
    remark = (payload.get("remark") or "").strip() or "RADHU AI"
    quantity = _int(payload.get("quantity"))
    bucket = payload.get("bucket") or "stock"
    bill_number = (payload.get("bill_number") or "").strip()
    if quantity <= 0:
        raise ValueError("Sale/dispatch quantity must be > 0.")
    item = _find(module, payload)

    if module == "cycle_tyre":
        from cycletyres.models import BUCKET_CHOICES, CycleTyreEntry

        if bill_number and CycleTyreEntry.objects.filter(bill_number__iexact=bill_number, entry_type="sale").exists():
            raise ValueError(f"Bill number '{bill_number}' already exists.")
        if not hasattr(item, bucket):
            raise ValueError(f"Invalid bucket '{bucket}'.")
        available = getattr(item, bucket)
        if quantity > available:
            name = dict(BUCKET_CHOICES).get(bucket, bucket)
            raise ValueError(f"Insufficient stock in '{name}'. Available: {available}.")
        with transaction.atomic():
            setattr(item, bucket, available - quantity)
            item.save(update_fields=[bucket])
            entry = CycleTyreEntry.objects.create(
                tyre_item=item, entry_type="sale", bucket=bucket, quantity=quantity,
                date=date_val, bill_number=bill_number, remark=remark, user=user,
            )
        return {"ok": True, "entry_id": entry.id, "item": str(item), "quantity": quantity}

    if module == "cycle_tube":
        from cycletube.models import CycleTubeEntry

        if bill_number and CycleTubeEntry.objects.filter(bill_number=bill_number, entry_type="sale").exists():
            raise ValueError(f"Bill number '{bill_number}' already exists.")
        available = item.rfm_stock if bucket == "rfm_stock" else item.stock
        if quantity > available:
            raise ValueError(f"Insufficient stock. Available: {available}.")
        if bucket == "rfm_stock":
            item.rfm_stock -= quantity
            item.save(update_fields=["rfm_stock"])
        else:
            item.stock -= quantity
            item.save(update_fields=["stock"])
        entry = CycleTubeEntry.objects.create(
            tube_item=item, entry_type="sale",
            bucket="rfm_stock" if bucket == "rfm_stock" else "stock",
            quantity=quantity, tube_quality=payload.get("tube_quality") or "normal",
            date=date_val, bill_number=bill_number, remark=remark, user=user,
        )
        return {"ok": True, "entry_id": entry.id, "item": str(item), "quantity": quantity}

    from stock.models import DailyEntry

    if bill_number and DailyEntry.objects.filter(entry_type="dispatch", bill_number__iexact=bill_number).exists():
        raise ValueError("Duplicate bill number.")
    if not hasattr(item, bucket):
        raise ValueError(f"Invalid bucket '{bucket}'.")
    current = getattr(item, bucket)
    if quantity > current:
        raise ValueError(f"Only {current} available.")
    with transaction.atomic():
        setattr(item, bucket, current - quantity)
        item.save(update_fields=[bucket])
        entry = DailyEntry.objects.create(
            tyre_item=item, entry_type="dispatch", bucket=bucket, quantity=quantity,
            date=date_val, bill_number=bill_number, remark=remark, user=user,
        )
    return {"ok": True, "entry_id": entry.id, "item": str(item), "quantity": quantity}


def _add_adjustment(module, payload, user):
    date_val = _parse_date(payload.get("date"))
    remark = (payload.get("remark") or "").strip() or "RADHU AI"
    quantity = _int(payload.get("quantity"))
    action = (payload.get("action") or "").lower()
    bucket = payload.get("bucket") or "stock"
    if action == "subtract" and quantity > 0:
        quantity = -quantity
    if quantity == 0:
        raise ValueError("Adjustment quantity cannot be 0.")
    item = _find(module, payload)

    if module == "cycle_tyre":
        from cycletyres.models import CycleTyreEntry

        if not hasattr(item, bucket):
            raise ValueError(f"Invalid bucket '{bucket}'.")
        curr = getattr(item, bucket)
        if quantity < 0 and curr + quantity < 0:
            raise ValueError("Adjustment would make stock negative.")
        with transaction.atomic():
            setattr(item, bucket, curr + quantity)
            item.save(update_fields=[bucket])
            entry = CycleTyreEntry.objects.create(
                tyre_item=item, entry_type="adjustment", bucket=bucket,
                quantity=quantity, date=date_val, remark=remark, user=user,
            )
        return {"ok": True, "entry_id": entry.id, "item": str(item), "quantity": quantity}

    if module == "cycle_tube":
        from cycletube.models import CycleTubeEntry

        curr = item.rfm_stock if bucket == "rfm_stock" else item.stock
        if quantity < 0 and curr + quantity < 0:
            raise ValueError("Adjustment would make stock negative.")
        if bucket == "rfm_stock":
            item.rfm_stock = curr + quantity
            item.save(update_fields=["rfm_stock"])
        else:
            item.stock = curr + quantity
            item.save(update_fields=["stock"])
        entry = CycleTubeEntry.objects.create(
            tube_item=item, entry_type="adjustment",
            bucket="rfm_stock" if bucket == "rfm_stock" else "stock",
            quantity=quantity, date=date_val, remark=remark, user=user,
        )
        return {"ok": True, "entry_id": entry.id, "item": str(item), "quantity": quantity}

    from stock.models import DailyEntry

    if not hasattr(item, bucket):
        raise ValueError(f"Invalid bucket '{bucket}'.")
    curr = getattr(item, bucket)
    if quantity < 0 and curr + quantity < 0:
        raise ValueError("Not enough stock for adjustment.")
    with transaction.atomic():
        setattr(item, bucket, curr + quantity)
        item.save(update_fields=[bucket])
        entry = DailyEntry.objects.create(
            tyre_item=item, entry_type="adjustment", bucket=bucket,
            quantity=quantity, date=date_val, remark=remark, user=user,
        )
    return {"ok": True, "entry_id": entry.id, "item": str(item), "quantity": quantity}


def _import_items(module, payload):
    rows = payload.get("rows") or []
    created, skipped, errors = [], [], []
    for row in rows[:MAX_IMPORT_ROWS]:
        if not isinstance(row, dict):
            errors.append({"row": row, "error": "Row must be an object."})
            continue
        row = dict(row)
        row["module"] = module
        try:
            result = _add_item(module, row)
            created.append(result)
        except Exception as e:
            msg = str(e)
            if "already exists" in msg.lower():
                skipped.append({"label": _item_label(module, row), "reason": msg})
            else:
                errors.append({"label": _item_label(module, row), "error": msg})
    return {
        "ok": True,
        "created": len(created),
        "skipped": len(skipped),
        "errors": len(errors),
        "details": {"created": created, "skipped": skipped, "errors": errors},
    }


def _import_production(module, payload, user):
    rows = payload.get("rows") or []
    created, errors = [], []
    for row in rows[:MAX_IMPORT_ROWS]:
        if not isinstance(row, dict):
            errors.append({"row": row, "error": "Row must be an object."})
            continue
        row = dict(row)
        row["module"] = module
        try:
            created.append(_add_production(module, row, user))
        except Exception as e:
            errors.append({"label": _item_label(module, row), "error": str(e)})
    return {
        "ok": True,
        "created": len(created),
        "errors": len(errors),
        "details": {"created": created, "errors": errors},
    }


HEADER_ALIASES = {
    "box": "box_type",
    "boxtype": "box_type",
    "box_type": "box_type",
    "tyre_size": "size",
    "item": "name",
    "item_name": "name",
    "qty": "quantity",
    "qty.": "quantity",
    "allcuring": "all_curing",
    "all_curing": "all_curing",
    "curing": "all_curing",
    "2nd": "second_grade",
    "2nd_grade": "second_grade",
    "second": "second_grade",
    "rejected": "rejected_grade",
    "pattern_name": "pattern",
    "tyre_name": "tyre",
    "brand_name": "brand",
}


def guess_module_from_text(text):
    msg = (text or "").lower()
    if "tube" in msg:
        return "cycle_tube"
    if "auto" in msg:
        return "auto_tyre"
    return "cycle_tyre"


def table_to_import_actions(table, user_message):
    """Build one import_* action from a header+rows table when user asks to import/add."""
    if not table or len(table) < 2:
        return []
    msg = (user_message or "").lower()
    if any(w in msg for w in ("kya hai", "analyse", "analyze", "dikhao", "summary", "explain")) and not any(
        w in msg for w in ("import", "add kar", "save", "daal")
    ):
        return []
    wants_write = (not msg) or any(w in msg for w in (
        "import", "add kar", "add karo", "sheet se", "excel", "upload", "daal", "save kar",
        "production",
    ))
    if not wants_write:
        return []

    headers = []
    for h in table[0]:
        key = str(h or "").strip().lower().replace(" ", "_").replace("-", "_")
        headers.append(HEADER_ALIASES.get(key, key))

    module = guess_module_from_text(user_message)
    prod_cols = {"all_curing", "quantity", "production_tyre", "second_grade"}
    is_prod = bool(prod_cols.intersection(headers)) and (
        "production" in msg or "curing" in msg or "all_curing" in headers
    )

    rows = []
    for raw in table[1: MAX_IMPORT_ROWS + 1]:
        if not raw or all(v is None or str(v).strip() == "" for v in raw):
            continue
        obj = {"module": module}
        for i, key in enumerate(headers):
            if not key or i >= len(raw) or raw[i] is None:
                continue
            val = raw[i]
            if isinstance(val, float) and val == int(val):
                val = int(val)
            obj[key] = str(val).strip() if not isinstance(val, (int, float)) else val
        if module == "cycle_tyre":
            obj.setdefault("box_type", "BOX")
            if not obj.get("material"):
                obj["material"] = "Nylon"
        if module == "auto_tyre" and obj.get("name") and not obj.get("tyre"):
            obj["tyre"] = obj["name"]
        if module == "cycle_tyre" and not obj.get("size"):
            continue
        if module == "cycle_tube" and not obj.get("size"):
            continue
        if module == "auto_tyre" and not (obj.get("tyre") or obj.get("size")):
            continue
        if module == "auto_tyre" and obj.get("size") and not obj.get("tyre"):
            obj["tyre"] = obj["size"]
        rows.append(obj)

    if not rows:
        return []
    action = "import_production" if is_prod else "import_items"
    return [{"action": action, "module": module, "rows": rows}]

