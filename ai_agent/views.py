"""
AI Agent views — Gemini-powered ERP assistant for Radhu Industries.
"""
import csv
import datetime
import json
import os
import re
import time
import uuid
from collections import defaultdict
from decimal import Decimal
from io import BytesIO, StringIO

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

MAX_FILE_BYTES = 8 * 1024 * 1024
CONTEXT_TTL_SECONDS = 60
_CHAT_SESSIONS = {}
_CONTEXT_CACHE = {"built_at": 0, "text": ""}


def _get_effective_ai_config():
    """
    Returns AI config dict. Prefers database AiConfig record from Django admin,
    falls back to environment variables.
    """
    try:
        from .models import AiConfig
        cfg = AiConfig.get_solo()
        api_key = (cfg.api_key or "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
        primary_model = (cfg.model_name or "").strip() or "gemini-2.5-flash"
        fallback_model = (cfg.fallback_model or "").strip() or "gemini-1.5-flash"
        is_enabled = bool(cfg.is_enabled)
        temp = float(cfg.temperature) if cfg.temperature is not None else 0.4
        extra = (cfg.system_instructions_extra or "").strip()
        return {
            "api_key": api_key,
            "primary_model": primary_model,
            "fallback_model": fallback_model,
            "is_enabled": is_enabled,
            "temperature": temp,
            "extra_instructions": extra,
        }
    except Exception:
        return {
            "api_key": os.environ.get("GEMINI_API_KEY", "").strip(),
            "primary_model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
            "fallback_model": "gemini-1.5-flash",
            "is_enabled": True,
            "temperature": 0.4,
            "extra_instructions": "",
        }

ACTION_BLOCK_RE = re.compile(r"```radhu_action\s*([\s\S]*?)```", re.I)
PROPOSAL_TTL_MINUTES = 30


def invalidate_context_cache():
    _CONTEXT_CACHE["text"] = ""
    _CONTEXT_CACHE["built_at"] = 0


def _parse_action_payload(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and isinstance(data.get("actions"), list):
        return data["actions"]
    if isinstance(data, dict) and (data.get("action") or data.get("action_type")):
        return [data]
    if isinstance(data, list):
        return data
    return None


def extract_actions_from_reply(text):
    if not text:
        return "", []
    actions = []
    reply = text
    for match in ACTION_BLOCK_RE.finditer(text):
        raw = (match.group(1) or "").strip()
        parsed = _parse_action_payload(raw)
        if parsed is None:
            continue
        actions.extend(parsed)
        reply = reply.replace(match.group(0), "")
    if not actions:
        marker = text.find('{"actions"')
        if marker >= 0:
            snippet = text[marker:]
            end = snippet.rfind("}")
            if end > 0:
                parsed = _parse_action_payload(snippet[: end + 1])
                if parsed:
                    actions.extend(parsed)
                    reply = (text[:marker] + text[marker + end + 1 :]).strip()
    return reply.strip(), actions[:20]


def store_proposed_actions(user, session_key, raw_actions):
    from .actions import normalize_action, summarize_action
    from .models import AiAuditLog

    batch_id = uuid.uuid4().hex
    expires_at = timezone.now() + datetime.timedelta(minutes=PROPOSAL_TTL_MINUTES)
    proposed = []
    errors = []
    for raw in raw_actions:
        try:
            action_type, module, payload, risk = normalize_action(raw)
            summary = summarize_action(action_type, module, payload)
            log = AiAuditLog.objects.create(
                user=user,
                batch_id=batch_id,
                confirm_token=uuid.uuid4().hex,
                action_type=action_type,
                module=module,
                status=AiAuditLog.STATUS_PROPOSED,
                risk_level=risk,
                summary=summary,
                payload=payload,
                expires_at=expires_at,
            )
            proposed.append({
                "id": log.id,
                "token": log.confirm_token,
                "batch_id": batch_id,
                "action": action_type,
                "module": module,
                "risk_level": risk,
                "summary": summary,
                "payload": payload,
                "requires_typed_delete": action_type == "delete_item",
                "expires_at": expires_at.isoformat(),
            })
        except Exception as e:
            errors.append(str(e))
    return proposed, errors


class ERPJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)


def _dumps(data):
    return json.dumps(data, cls=ERPJSONEncoder, ensure_ascii=False)


def _history_for_gemini(raw_history):
    """Keep only text parts so Gemini start_chat() accepts stored history."""
    out = []
    for item in raw_history[-40:]:
        if isinstance(item, dict):
            role = item.get("role") or "user"
            parts = item.get("parts") or []
            texts = []
            for p in parts:
                if isinstance(p, str) and p.strip():
                    texts.append(p)
                elif isinstance(p, dict) and p.get("text"):
                    texts.append(p["text"])
            if texts:
                out.append({"role": role, "parts": texts})
            continue
        role = getattr(item, "role", None) or "user"
        texts = []
        for p in getattr(item, "parts", []) or []:
            text = getattr(p, "text", None)
            if text:
                texts.append(text)
        if texts:
            out.append({"role": role, "parts": texts})
    return out


def _build_system_context():
    today = datetime.date.today()
    month_start = today.replace(day=1)
    week_ago = today - datetime.timedelta(days=7)

    snapshot = {
        "today": today.strftime("%d %B %Y"),
        "errors": [],
    }

    try:
        from stock.models import DailyEntry, TyreItem

        auto_items = list(
            TyreItem.objects.filter(is_active=True).values(
                "id", "tyre", "pattern", "type", "stock", "second_stock",
                "third_stock", "repair_tyre_stock", "rfm_ok_tyre", "on_hold_export",
            )
        )
        auto_totals = TyreItem.objects.filter(is_active=True).aggregate(
            items=Count("id"),
            stock=Sum("stock"),
            second=Sum("second_stock"),
        )
        auto_prod = DailyEntry.objects.filter(
            date__gte=month_start, entry_type="production"
        ).aggregate(qty=Sum("quantity"))
        auto_dispatch = DailyEntry.objects.filter(
            date__gte=month_start, entry_type="dispatch"
        ).aggregate(qty=Sum("quantity"))
        auto_low = list(
            TyreItem.objects.filter(is_active=True, stock__lt=20).values(
                "id", "tyre", "pattern", "type", "stock"
            )[:20]
        )
        snapshot["auto_tyre"] = {
            "totals": auto_totals,
            "month_production": auto_prod.get("qty") or 0,
            "month_dispatch": auto_dispatch.get("qty") or 0,
            "low_stock": auto_low,
            "items": auto_items[:60],
        }
    except Exception as e:
        snapshot["errors"].append(f"auto_tyre: {e}")

    try:
        from cycletyres.models import CycleTyreEntry, CycleTyreItem

        ct_items = list(
            CycleTyreItem.objects.filter(is_active=True).values(
                "id", "size", "box_type", "material", "brand",
                "stock", "second_stock", "rfm_stock", "rejected_stock",
            )
        )
        ct_totals = CycleTyreItem.objects.filter(is_active=True).aggregate(
            items=Count("id"),
            stock=Sum("stock"),
            second=Sum("second_stock"),
            rfm=Sum("rfm_stock"),
        )
        ct_prod = CycleTyreEntry.objects.filter(
            date__gte=month_start, entry_type="production"
        ).aggregate(qty=Sum("quantity"))
        ct_sale = CycleTyreEntry.objects.filter(
            date__gte=month_start, entry_type="sale"
        ).aggregate(qty=Sum("quantity"))
        ct_low = list(
            CycleTyreItem.objects.filter(is_active=True, stock__lt=30).values(
                "id", "size", "box_type", "brand", "stock"
            )[:25]
        )
        snapshot["cycle_tyre"] = {
            "totals": ct_totals,
            "month_production": ct_prod.get("qty") or 0,
            "month_sale": ct_sale.get("qty") or 0,
            "low_stock": ct_low,
            "items": ct_items[:80],
        }
    except Exception as e:
        snapshot["errors"].append(f"cycle_tyre: {e}")

    try:
        from cycletube.models import CycleTubeEntry, CycleTubeItem

        tube_items = list(
            CycleTubeItem.objects.filter(is_active=True).values(
                "id", "size", "type", "brand", "stock", "rfm_stock",
            )
        )
        tube_totals = CycleTubeItem.objects.filter(is_active=True).aggregate(
            items=Count("id"),
            stock=Sum("stock"),
            rfm=Sum("rfm_stock"),
        )
        tube_prod = CycleTubeEntry.objects.filter(
            date__gte=month_start, entry_type="production"
        ).aggregate(qty=Sum("quantity"))
        tube_sale = CycleTubeEntry.objects.filter(
            date__gte=month_start, entry_type="sale"
        ).aggregate(qty=Sum("quantity"))
        snapshot["cycle_tube"] = {
            "totals": tube_totals,
            "month_production": tube_prod.get("qty") or 0,
            "month_sale": tube_sale.get("qty") or 0,
            "items": tube_items[:60],
        }
    except Exception as e:
        snapshot["errors"].append(f"cycle_tube: {e}")

    try:
        from orders.models import Order, OrderItem, Party

        parties = list(Party.objects.all().values("id", "name")[:80])
        orders = list(
            Order.objects.select_related("party", "user")
            .order_by("-date", "-id")[:25]
            .values("id", "date", "status", "deadline", "notes", "party__name", "user__username")
        )
        pending = Order.objects.filter(status="pending").count()
        overdue = Order.objects.filter(
            status="pending", deadline__lt=today
        ).count()
        recent_items = []
        for oi in (
            OrderItem.objects.select_related(
                "order", "order__party", "tyre_item", "tube_item", "cycle_tyre_item"
            )
            .order_by("-id")[:40]
        ):
            recent_items.append({
                "order_id": oi.order_id,
                "party": oi.order.party.name if oi.order and oi.order.party else "",
                "category": oi.category,
                "item": oi.item_display,
                "qty": oi.quantity,
                "price": float(oi.price or 0),
            })
        snapshot["orders"] = {
            "party_count": Party.objects.count(),
            "pending": pending,
            "overdue": overdue,
            "parties": parties,
            "recent_orders": orders,
            "recent_order_items": recent_items,
        }
    except Exception as e:
        snapshot["errors"].append(f"orders: {e}")

    try:
        from tallysync.models import TallyInvoice

        since = today - datetime.timedelta(days=365)
        tally_qs = TallyInvoice.objects.filter(voucher_date__gte=since)
        month_agg = tally_qs.filter(voucher_date__gte=month_start).aggregate(
            invoices=Count("id"),
            total=Sum("total_value"),
            taxable=Sum("taxable_value"),
        )
        week_agg = tally_qs.filter(voucher_date__gte=week_ago).aggregate(
            invoices=Count("id"),
            total=Sum("total_value"),
        )
        tally_map = defaultdict(lambda: {"invoices": 0, "total": Decimal("0")})
        for inv in tally_qs.only("party_name", "total_value"):
            pname = (inv.party_name or "").strip()
            if pname:
                tally_map[pname]["invoices"] += 1
                tally_map[pname]["total"] += inv.total_value or 0
        tally_parties = [
            {"party": k, "invoices": v["invoices"], "total": float(v["total"])}
            for k, v in sorted(
                tally_map.items(), key=lambda x: x[1]["total"], reverse=True
            )[:30]
        ]
        recent_inv = list(
            TallyInvoice.objects.order_by("-voucher_date", "-id")[:15].values(
                "voucher_number", "voucher_date", "party_name", "total_value",
                "taxable_value", "cgst", "sgst", "igst",
            )
        )
        snapshot["tally"] = {
            "this_month": month_agg,
            "last_7_days": week_agg,
            "top_parties": tally_parties,
            "recent_invoices": recent_inv,
        }
    except Exception as e:
        snapshot["errors"].append(f"tally: {e}")

    try:
        from hrms.models import Employee

        employees = list(
            Employee.objects.filter(status="Active")
            .select_related("department")
            .values(
                "id", "employee_code", "name", "designation",
                "department__name", "employee_type", "basic_salary",
            )
        )
        snapshot["hrms"] = {
            "active_count": len(employees),
            "employees": employees,
        }
    except Exception as e:
        snapshot["errors"].append(f"hrms: {e}")

    try:
        from django.contrib.auth.models import User

        snapshot["users"] = list(
            User.objects.filter(is_active=True).values("id", "username", "is_superuser")
        )
    except Exception as e:
        snapshot["errors"].append(f"users: {e}")

    return f"""You are RADHU AI — the ERP assistant for Radhu Industries (cycle tyre & tube manufacturing, Kannauj, Uttar Pradesh, India).
Today: {snapshot['today']}

LIVE ERP SNAPSHOT (JSON):
{_dumps(snapshot)}

RULES:
- Answer using THIS snapshot first. If data is missing, say so clearly instead of inventing numbers.
- Cover Auto Tyre, Cycle Tyre, Cycle Tube, Orders, Tally billing/GST, HRMS.
- Match the user's language (Hindi, English, or Hinglish).
- Be concise and practical. Use Indian number style (₹, lakhs, crores).
- For low stock, pending/overdue orders, and this-month billing, give a short actionable summary.
- If a file is uploaded (Excel/CSV/image), analyse it. If the user wants those rows added to ERP, propose import_items or import_production (max 80 rows). Never set clear_existing.
- You CAN propose ERP write actions. The user must confirm in the UI before anything is saved.
- When the user wants to add/delete/import/production/sale/dispatch/adjust, end your reply with ONE fenced block:

```radhu_action
{"actions":[{"action":"add_item","module":"cycle_tyre","size":"26x1.75","box_type":"BOX","material":"Nylon","brand":"RADHU"}]}
```

Allowed action: add_item, delete_item, add_production, add_sale, add_dispatch, add_adjustment, import_items, import_production.
Allowed module: cycle_tyre, cycle_tube, auto_tyre.
For add_item cycle_tyre need size, box_type, material, brand. cycle_tube need size, type, brand. auto_tyre need tyre, pattern, type.
For production/sale use item_id from snapshot when possible, else size+brand.
delete_item deactivates items that have history. Never invent IDs.
Do not propose HR, users, Tally mappings, or wiping all production.
If it is only a question, do NOT output a radhu_action block.
- Never invent invoice numbers, stock qty, or employee salaries that are not in the snapshot.
"""


def _get_system_context():
    now = time.time()
    if _CONTEXT_CACHE["text"] and (now - _CONTEXT_CACHE["built_at"]) < CONTEXT_TTL_SECONDS:
        return _CONTEXT_CACHE["text"]
    try:
        text = _build_system_context()
    except Exception as e:
        text = (
            "You are RADHU AI, ERP assistant for Radhu Industries. "
            f"Live data could not be loaded ({e}). Answer generally and ask the user to retry."
        )
    _CONTEXT_CACHE["built_at"] = now
    _CONTEXT_CACHE["text"] = text
    return text


def _parse_upload(uploaded_file):
    fname = (uploaded_file.name or "").lower()
    file_bytes = uploaded_file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        return None, f"\n[File: {uploaded_file.name}] Too large. Max 8 MB.", None

    parts = []
    note = ""
    table = None

    if fname.endswith((".xlsx", ".xls")):
        try:
            import openpyxl

            wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
            sheets = []
            for ws in wb.worksheets[:4]:
                rows = [list(row) for row in ws.iter_rows(values_only=True, max_row=80)]
                sheets.append({"sheet": ws.title, "rows": rows[:80]})
                if table is None and rows:
                    table = rows[:81]
            note = f"\n[Excel: {uploaded_file.name}]\n{_dumps(sheets)}"
        except Exception as fe:
            note = f"\n[File: {uploaded_file.name}] Could not parse Excel: {fe}"

    elif fname.endswith(".csv"):
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            rows = list(csv.reader(StringIO(text)))[:81]
            table = rows
            note = f"\n[CSV: {uploaded_file.name}]\n{_dumps(rows)}"
        except Exception as fe:
            note = f"\n[File: {uploaded_file.name}] CSV parse error: {fe}"

    elif fname.endswith((".jpg", ".jpeg", ".png", ".webp")):
        import base64

        mime = (
            "image/jpeg" if fname.endswith((".jpg", ".jpeg"))
            else "image/png" if fname.endswith(".png")
            else "image/webp"
        )
        parts.append({
            "inline_data": {
                "mime_type": mime,
                "data": base64.b64encode(file_bytes).decode(),
            }
        })
        note = f"\n[Image uploaded: {uploaded_file.name}]"

    elif fname.endswith((".txt", ".json")):
        note = f"\n[File: {uploaded_file.name}]\n{file_bytes.decode('utf-8', errors='replace')[:8000]}"
    else:
        note = f"\n[File uploaded: {uploaded_file.name}] Unsupported type — use Excel, CSV, image, txt, or JSON."

    return parts, note, table


def _send_gemini(history, parts):
    import google.generativeai as genai

    config = _get_effective_ai_config()
    api_key = config["api_key"]
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set. Please enter your API key in Django Admin under 'AI Configuration & API Keys'.")

    genai.configure(api_key=api_key)
    system = _get_system_context()
    if config["extra_instructions"]:
        system += f"\n\nEXTRA BUSINESS RULES (from Admin):\n{config['extra_instructions']}"

    safe_history = _history_for_gemini(history)

    # Build model priority order based on admin selection
    models_to_try = [config["primary_model"]]
    if config["fallback_model"] and config["fallback_model"] not in models_to_try:
        models_to_try.append(config["fallback_model"])
    for default_m in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
        if default_m not in models_to_try:
            models_to_try.append(default_m)

    last_error = None
    for model_name in models_to_try:
        try:
            generation_config = {
                "temperature": config["temperature"],
            }
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system,
                generation_config=generation_config,
            )
            chat = model.start_chat(history=safe_history)
            response = chat.send_message(parts)
            stored = _history_for_gemini(chat.history)
            return response.text, stored, model_name
        except Exception as e:
            last_error = e
            continue
    raise last_error or RuntimeError("No Gemini model available")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def ai_agent_chat(request):
    config = _get_effective_ai_config()
    if not config["is_enabled"]:
        return Response(
            {
                "error": "AI Assistant is currently disabled in Django Admin.",
                "reply": None,
            },
            status=503,
        )

    if not config["api_key"]:
        return Response(
            {
                "error": "Gemini API Key not configured. Please add it in Django Admin (/admin/) under 'AI Configuration & API Keys'.",
                "reply": None,
            },
            status=503,
        )

    user = request.user
    session_key = request.data.get("session_id") or f"user_{user.id}"
    reset = str(request.data.get("reset", "false")).lower() == "true"
    user_message = (request.data.get("message") or "").strip()
    uploaded_file = request.FILES.get("file")

    if reset:
        _CHAT_SESSIONS.pop(session_key, None)
        return Response({
            "reply": "Chat history cleared. Kaise help kar sakta hoon?",
            "session_id": session_key,
        })

    if not user_message and not uploaded_file:
        return Response({"error": "Please send a message or upload a file."}, status=400)

    try:
        extra_parts, file_note, table = ([], "", None)
        if uploaded_file:
            extra_parts, file_note, table = _parse_upload(uploaded_file)

        full_message = (user_message + (file_note or "")).strip() or (
            f"Uploaded: {uploaded_file.name}" if uploaded_file else ""
        )
        parts = list(extra_parts or [])
        parts.append(full_message)

        history = _CHAT_SESSIONS.get(session_key, [])
        reply_text, stored, model_used = _send_gemini(history, parts)
        _CHAT_SESSIONS[session_key] = stored[-40:]

        clean_reply, raw_actions = extract_actions_from_reply(reply_text)
        if not raw_actions and table:
            from .actions import table_to_import_actions
            raw_actions = table_to_import_actions(table, user_message)
            if raw_actions and not clean_reply:
                clean_reply = "Sheet padh li. Neeche preview hai — Confirm se ERP mein save hoga."
        proposed, action_errors = store_proposed_actions(user, session_key, raw_actions) if raw_actions else ([], [])
        if action_errors:
            extra = "\n\nKuch actions propose nahi ho sake:\n- " + "\n- ".join(action_errors[:8])
            clean_reply = (clean_reply or reply_text) + extra
        if proposed:
            clean_reply = (clean_reply or "Neeche confirm karke ERP mein save hoga.") + "\n\nConfirm dabane se pehle kuch save nahi hota."

        return Response({
            "reply": clean_reply or reply_text,
            "session_id": session_key,
            "model": model_used,
            "history_length": len(_CHAT_SESSIONS[session_key]),
            "proposed_actions": proposed,
        })
    except Exception as e:
        return Response(
            {"error": f"Gemini error: {str(e)}", "reply": None},
            status=500,
        )


def _get_owned_proposal(request, proposal_id, token):
    from .models import AiAuditLog

    log = AiAuditLog.objects.filter(pk=proposal_id, confirm_token=token).first()
    if not log:
        return None, Response({"error": "Proposal not found."}, status=404)
    if log.user_id != request.user.id and not request.user.is_superuser:
        return None, Response({"error": "Not allowed."}, status=403)
    if log.status != AiAuditLog.STATUS_PROPOSED:
        return None, Response({"error": f"Already {log.status}."}, status=400)
    if log.expires_at and timezone.now() > log.expires_at:
        log.status = AiAuditLog.STATUS_EXPIRED
        log.save(update_fields=["status"])
        return None, Response({"error": "Proposal expired. Ask AI again."}, status=400)
    return log, None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_action_confirm(request):
    from .actions import execute_action
    from .models import AiAuditLog

    proposal_id = request.data.get("id")
    token = request.data.get("token")
    confirm_text = (request.data.get("confirm_text") or "").strip()
    if not proposal_id or not token:
        return Response({"error": "id and token required."}, status=400)

    log, err = _get_owned_proposal(request, proposal_id, token)
    if err:
        return err

    if log.action_type == "delete_item" and confirm_text.upper() != "DELETE":
        return Response({
            "error": "Delete ke liye confirm_text mein DELETE type karo.",
        }, status=400)

    log.status = AiAuditLog.STATUS_CONFIRMED
    log.approved_by = request.user
    log.save(update_fields=["status", "approved_by"])

    try:
        result = execute_action(log.action_type, log.module, log.payload or {}, request.user)
        log.status = AiAuditLog.STATUS_EXECUTED
        log.result = result
        log.executed_at = timezone.now()
        log.save(update_fields=["status", "result", "executed_at"])
        invalidate_context_cache()
        return Response({
            "ok": True,
            "status": log.status,
            "summary": log.summary,
            "result": result,
        })
    except Exception as e:
        log.status = AiAuditLog.STATUS_FAILED
        log.error_message = str(e)
        log.executed_at = timezone.now()
        log.save(update_fields=["status", "error_message", "executed_at"])
        return Response({
            "ok": False,
            "status": log.status,
            "summary": log.summary,
            "error": str(e),
        }, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_action_reject(request):
    from .models import AiAuditLog

    proposal_id = request.data.get("id")
    token = request.data.get("token")
    if not proposal_id or not token:
        return Response({"error": "id and token required."}, status=400)
    log, err = _get_owned_proposal(request, proposal_id, token)
    if err:
        return err
    log.status = AiAuditLog.STATUS_REJECTED
    log.approved_by = request.user
    log.save(update_fields=["status", "approved_by"])
    return Response({"ok": True, "status": log.status, "summary": log.summary})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_audit_logs(request):
    from .models import AiAuditLog

    qs = AiAuditLog.objects.select_related("user", "approved_by")
    if not request.user.is_superuser:
        qs = qs.filter(user=request.user)
    status_filter = (request.query_params.get("status") or "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)
    logs = []
    for log in qs[:200]:
        logs.append({
            "id": log.id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "executed_at": log.executed_at.isoformat() if log.executed_at else None,
            "user": log.user.username if log.user else None,
            "approved_by": log.approved_by.username if log.approved_by else None,
            "action": log.action_type,
            "module": log.module,
            "status": log.status,
            "risk_level": log.risk_level,
            "summary": log.summary,
            "payload": log.payload,
            "result": log.result,
            "error_message": log.error_message,
        })
    return Response({"logs": logs, "count": len(logs)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_agent_status(request):
    config = _get_effective_ai_config()
    has_key = bool(config["api_key"])
    is_ready = has_key and config["is_enabled"]
    return Response({
        "ready": is_ready,
        "is_enabled": config["is_enabled"],
        "has_key": has_key,
        "model": config["primary_model"],
        "fallback_model": config["fallback_model"],
        "temperature": config["temperature"],
        "message": (
            f"RADHU AI Ready ({config['primary_model']})"
            if is_ready
            else (
                "AI Assistant is disabled in Django Admin."
                if not config["is_enabled"]
                else "GEMINI_API_KEY not configured. Add it in Django Admin (/admin/)."
            )
        ),
        "can_write": True,
        "confirm_required": True,
    })
