"""
Daily Snapshot Email — Radhu ERP
Sends a professional HTML email summary every night with:
  • Cycle Tyre, Cycle Tube, Auto Tyre stock totals
  • Today's production / sales counts
  • Top 10 items by stock
  • Any low-stock alerts
"""
import datetime
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.db.models import Sum, Count
from django.conf import settings


class Command(BaseCommand):
    help = "Send daily stock snapshot email"

    def handle(self, *args, **options):
        from stock.models import TyreItem, DailyEntry
        from cycletyres.models import CycleTyreItem, CycleTyreEntry
        from cycletube.models import CycleTubeItem, CycleTubeEntry

        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        report_date = yesterday  # report is for yesterday since cron runs at night

        # ── Auto Tyre ──────────────────────────────────────────
        auto_items = TyreItem.objects.all()
        auto_total_stock = sum(i.stock for i in auto_items)
        auto_prod_today = (
            DailyEntry.objects.filter(entry_type="production", date=report_date)
            .aggregate(t=Sum("quantity"))["t"]
            or 0
        )
        auto_sale_today = (
            DailyEntry.objects.filter(entry_type="dispatch", date=report_date)
            .aggregate(t=Sum("quantity"))["t"]
            or 0
        )
        auto_top = sorted(auto_items, key=lambda x: x.stock, reverse=True)[:10]

        # ── Cycle Tyre ─────────────────────────────────────────
        ct_items = CycleTyreItem.objects.all()
        ct_total_stock = sum(i.stock for i in ct_items)
        ct_total_2nd = sum(i.second_stock for i in ct_items)
        ct_prod_today = (
            CycleTyreEntry.objects.filter(entry_type="production", date=report_date)
            .aggregate(t=Sum("first_grade"))["t"]
            or 0
        )
        ct_sale_today = (
            CycleTyreEntry.objects.filter(entry_type="sale", date=report_date)
            .aggregate(t=Sum("quantity"))["t"]
            or 0
        )
        ct_curing_today = (
            CycleTyreEntry.objects.filter(entry_type="production", date=report_date)
            .aggregate(t=Sum("all_curing"))["t"]
            or 0
        )
        ct_top = sorted(ct_items, key=lambda x: x.stock, reverse=True)[:10]

        # ── Cycle Tube ─────────────────────────────────────────
        tube_items = CycleTubeItem.objects.all()
        tube_total_stock = sum(i.stock for i in tube_items)
        tube_prod_today = (
            CycleTubeEntry.objects.filter(entry_type="production", date=report_date)
            .aggregate(t=Sum("quantity"))["t"]
            or 0
        )
        tube_sale_today = (
            CycleTubeEntry.objects.filter(entry_type="sale", date=report_date)
            .aggregate(t=Sum("quantity"))["t"]
            or 0
        )
        tube_top = sorted(tube_items, key=lambda x: x.stock, reverse=True)[:10]

        # ── Low Stock Alerts ───────────────────────────────────
        low_ct = [i for i in ct_items if 0 < i.stock < 100]
        low_auto = [i for i in auto_items if 0 < i.stock < 50]

        # ── Build HTML ─────────────────────────────────────────
        html = self._build_html(
            report_date=report_date,
            auto_total_stock=auto_total_stock,
            auto_prod_today=auto_prod_today,
            auto_sale_today=auto_sale_today,
            auto_top=auto_top,
            ct_total_stock=ct_total_stock,
            ct_total_2nd=ct_total_2nd,
            ct_prod_today=ct_prod_today,
            ct_sale_today=ct_sale_today,
            ct_curing_today=ct_curing_today,
            ct_top=ct_top,
            tube_total_stock=tube_total_stock,
            tube_prod_today=tube_prod_today,
            tube_sale_today=tube_sale_today,
            tube_top=tube_top,
            low_ct=low_ct,
            low_auto=low_auto,
        )

        subject = f"📊 Radhu ERP — Daily Snapshot — {report_date.strftime('%d %b %Y')}"
        to = [settings.SNAPSHOT_EMAIL_TO]
        from_email = settings.DEFAULT_FROM_EMAIL

        msg = EmailMultiAlternatives(subject, "Please view in an HTML email client.", from_email, to)
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)

        self.stdout.write(self.style.SUCCESS(f"✅ Snapshot email sent for {report_date} to {to}"))

    # ── HTML Builder ───────────────────────────────────────────
    def _build_html(self, **d):
        def fmt(n):
            return f"{n:,}"

        def item_rows(items, name_fn):
            rows = ""
            for i, item in enumerate(items):
                bg = "#fff" if i % 2 == 0 else "#f8fafc"
                rows += f'<tr style="background:{bg}"><td style="padding:8px 12px;border-bottom:1px solid #eee">{name_fn(item)}</td><td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;font-weight:700">{fmt(item.stock)}</td></tr>'
            return rows

        def alert_rows(items, name_fn):
            rows = ""
            for item in items:
                rows += f'<tr><td style="padding:6px 12px;border-bottom:1px solid #fee2e2">{name_fn(item)}</td><td style="padding:6px 12px;border-bottom:1px solid #fee2e2;text-align:right;font-weight:700;color:#dc2626">{fmt(item.stock)}</td></tr>'
            return rows

        report_date_str = d["report_date"].strftime("%A, %d %B %Y")

        html = f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:#f0f4ff;font-family:Arial,Helvetica,sans-serif">
<div style="max-width:680px;margin:20px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1e40af,#3b82f6);padding:28px 32px;color:#fff">
    <h1 style="margin:0;font-size:22px">📊 Radhu Industries — Daily Snapshot</h1>
    <p style="margin:6px 0 0;opacity:0.85;font-size:14px">{report_date_str}</p>
  </div>

  <div style="padding:24px 32px">

    <!-- Summary Cards -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px">
      <tr>
        <td style="padding:8px">
          <div style="background:#eff6ff;border:2px solid #bfdbfe;border-radius:12px;padding:16px;text-align:center">
            <div style="font-size:12px;color:#3b82f6;font-weight:700;text-transform:uppercase">Cycle Tyre Stock</div>
            <div style="font-size:28px;font-weight:900;color:#1e40af;margin-top:4px">{fmt(d['ct_total_stock'])}</div>
            <div style="font-size:11px;color:#64748b;margin-top:2px">2nd: {fmt(d['ct_total_2nd'])}</div>
          </div>
        </td>
        <td style="padding:8px">
          <div style="background:#f0fdf4;border:2px solid #bbf7d0;border-radius:12px;padding:16px;text-align:center">
            <div style="font-size:12px;color:#16a34a;font-weight:700;text-transform:uppercase">Cycle Tube Stock</div>
            <div style="font-size:28px;font-weight:900;color:#166534;margin-top:4px">{fmt(d['tube_total_stock'])}</div>
          </div>
        </td>
        <td style="padding:8px">
          <div style="background:#fefce8;border:2px solid #fef08a;border-radius:12px;padding:16px;text-align:center">
            <div style="font-size:12px;color:#a16207;font-weight:700;text-transform:uppercase">Auto Tyre Stock</div>
            <div style="font-size:28px;font-weight:900;color:#854d0e;margin-top:4px">{fmt(d['auto_total_stock'])}</div>
          </div>
        </td>
      </tr>
    </table>

    <!-- Today's Activity -->
    <h2 style="font-size:16px;color:#0f172a;margin:20px 0 12px;border-bottom:2px solid #e2e8f0;padding-bottom:8px">📈 Today's Activity</h2>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
      <thead>
        <tr style="background:#1e293b;color:#fff">
          <th style="padding:10px 14px;text-align:left;font-size:12px">CATEGORY</th>
          <th style="padding:10px 14px;text-align:right;font-size:12px">PRODUCTION</th>
          <th style="padding:10px 14px;text-align:right;font-size:12px">SALES</th>
          <th style="padding:10px 14px;text-align:right;font-size:12px">CURING</th>
        </tr>
      </thead>
      <tbody>
        <tr style="background:#fff">
          <td style="padding:10px 14px;font-weight:700">Cycle Tyre</td>
          <td style="padding:10px 14px;text-align:right;font-weight:700;color:#16a34a">{fmt(d['ct_prod_today'])}</td>
          <td style="padding:10px 14px;text-align:right;font-weight:700;color:#dc2626">{fmt(d['ct_sale_today'])}</td>
          <td style="padding:10px 14px;text-align:right;font-weight:600;color:#7c3aed">{fmt(d['ct_curing_today'])}</td>
        </tr>
        <tr style="background:#f8fafc">
          <td style="padding:10px 14px;font-weight:700">Cycle Tube</td>
          <td style="padding:10px 14px;text-align:right;font-weight:700;color:#16a34a">{fmt(d['tube_prod_today'])}</td>
          <td style="padding:10px 14px;text-align:right;font-weight:700;color:#dc2626">{fmt(d['tube_sale_today'])}</td>
          <td style="padding:10px 14px;text-align:right;color:#94a3b8">—</td>
        </tr>
        <tr style="background:#fff">
          <td style="padding:10px 14px;font-weight:700">Auto Tyre</td>
          <td style="padding:10px 14px;text-align:right;font-weight:700;color:#16a34a">{fmt(d['auto_prod_today'])}</td>
          <td style="padding:10px 14px;text-align:right;font-weight:700;color:#dc2626">{fmt(d['auto_sale_today'])}</td>
          <td style="padding:10px 14px;text-align:right;color:#94a3b8">—</td>
        </tr>
      </tbody>
    </table>

    <!-- Top 10 Cycle Tyre -->
    <h2 style="font-size:16px;color:#0f172a;margin:20px 0 12px;border-bottom:2px solid #e2e8f0;padding-bottom:8px">🏆 Top 10 Cycle Tyre Items (by Stock)</h2>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
      <thead><tr style="background:#1e293b;color:#fff"><th style="padding:8px 12px;text-align:left;font-size:12px">ITEM</th><th style="padding:8px 12px;text-align:right;font-size:12px">STOCK</th></tr></thead>
      <tbody>{item_rows(d['ct_top'], lambda i: f"{i.size} {i.material or ''} {i.box_type} {i.brand}")}</tbody>
    </table>

    <!-- Top 10 Auto Tyre -->
    <h2 style="font-size:16px;color:#0f172a;margin:20px 0 12px;border-bottom:2px solid #e2e8f0;padding-bottom:8px">🏆 Top 10 Auto Tyre Items (by Stock)</h2>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
      <thead><tr style="background:#1e293b;color:#fff"><th style="padding:8px 12px;text-align:left;font-size:12px">ITEM</th><th style="padding:8px 12px;text-align:right;font-size:12px">STOCK</th></tr></thead>
      <tbody>{item_rows(d['auto_top'], lambda i: f"{i.tyre} {i.pattern} {i.type}")}</tbody>
    </table>

    <!-- Top 10 Cycle Tube -->
    <h2 style="font-size:16px;color:#0f172a;margin:20px 0 12px;border-bottom:2px solid #e2e8f0;padding-bottom:8px">🏆 Top 10 Cycle Tube Items (by Stock)</h2>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
      <thead><tr style="background:#1e293b;color:#fff"><th style="padding:8px 12px;text-align:left;font-size:12px">ITEM</th><th style="padding:8px 12px;text-align:right;font-size:12px">STOCK</th></tr></thead>
      <tbody>{item_rows(d['tube_top'], lambda i: f"{i.size} {i.type} {i.brand}")}</tbody>
    </table>
"""

        # Low stock alerts
        if d["low_ct"] or d["low_auto"]:
            html += """
    <h2 style="font-size:16px;color:#dc2626;margin:20px 0 12px;border-bottom:2px solid #fecaca;padding-bottom:8px">⚠️ Low Stock Alerts</h2>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;border:1px solid #fecaca;border-radius:10px;overflow:hidden;background:#fef2f2">
      <thead><tr style="background:#991b1b;color:#fff"><th style="padding:8px 12px;text-align:left;font-size:12px">ITEM</th><th style="padding:8px 12px;text-align:right;font-size:12px">STOCK</th></tr></thead>
      <tbody>
"""
            html += alert_rows(d["low_ct"], lambda i: f"CT: {i.size} {i.material or ''} {i.box_type} {i.brand}")
            html += alert_rows(d["low_auto"], lambda i: f"AT: {i.tyre} {i.pattern} {i.type}")
            html += "</tbody></table>"

        html += """
    <!-- Footer -->
    <div style="margin-top:24px;padding:16px;background:#f8fafc;border-radius:10px;text-align:center">
      <p style="margin:0;font-size:12px;color:#94a3b8">Generated automatically by Radhu ERP at """ + datetime.datetime.now().strftime("%I:%M %p IST") + """</p>
      <p style="margin:4px 0 0;font-size:11px;color:#cbd5e1">radhuerp.site</p>
    </div>

  </div>
</div>
</body></html>
"""
        return html
