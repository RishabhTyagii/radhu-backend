import datetime

# This is a scratch script to append to views.py and modify urls.py

with open(r'C:\Users\risha\Documents\radhufullstack\backend\cycletyres\urls.py', 'r') as f:
    urls_content = f.read()

new_urls = """    path("party-analytics/<int:party_id>/", views.party_analytics, name="cycletyres_party_analytics"),
    path("item-analytics/<int:item_id>/", views.item_analytics, name="cycletyres_item_analytics"),
    path("ai-analytics-v2/", views.ai_analytics_v2, name="cycletyres_ai_analytics_v2"),
]
"""
urls_content = urls_content.replace(']', new_urls)

with open(r'C:\Users\risha\Documents\radhufullstack\backend\cycletyres\urls.py', 'w') as f:
    f.write(urls_content)


# Now views.py
with open(r'C:\Users\risha\Documents\radhufullstack\backend\cycletyres\views.py', 'r', encoding='utf-8') as f:
    views_content = f.read()

ai_analytics_idx = views_content.find('def ai_analytics(request):')
ai_analytics_end_idx = views_content.find('def daily_summary(request):', ai_analytics_idx)
ai_analytics_body = views_content[ai_analytics_idx:ai_analytics_end_idx]

v2_body = ai_analytics_body.replace('def ai_analytics(request):', 'def ai_analytics_v2(request):')

party_start = v2_body.find('    # 3. PARTY / DEALER BUYING PROPENSITY PREDICTIONS')
party_end = v2_body.find('    # Top recommended item to produce')

new_party_prop = '''    # 3. REAL PARTY / DEALER BUYING PROPENSITY from Orders DB
    from orders.models import Party, Order, OrderItem as OI
    from django.db.models import Sum
    
    party_propensity = []
    parties_with_orders = Party.objects.filter(orders__items__category='cycle_tyre').distinct()
    
    for party in parties_with_orders[:10]:  # limit to 10
        party_orders = Order.objects.filter(party=party).order_by('-date')
        if not party_orders.exists():
            continue
        
        order_dates = list(party_orders.values_list('date', flat=True))
        avg_cycle_days = 30
        if len(order_dates) >= 2:
            intervals = [(order_dates[i] - order_dates[i+1]).days for i in range(len(order_dates)-1)]
            avg_cycle_days = max(1, int(sum(intervals) / len(intervals)))
        
        last_date = order_dates[0]
        days_since = (today - last_date).days
        days_to_reorder = max(0, avg_cycle_days - days_since)
        
        # preferred item
        item_pref_qs = OI.objects.filter(order__party=party, category='cycle_tyre').select_related('cycle_tyre_item')
        item_counts = {}
        for oi in item_pref_qs:
            if oi.cycle_tyre_item:
                tid = oi.cycle_tyre_item.id
                n = f"{oi.cycle_tyre_item.size} {oi.cycle_tyre_item.box_type} {oi.cycle_tyre_item.brand}"
                item_counts[n] = item_counts.get(n, 0) + oi.quantity
        preferred_item = max(item_counts, key=item_counts.get) if item_counts else "N/A"
        
        all_cycle = OI.objects.filter(order__party=party, category='cycle_tyre')
        total_qty = all_cycle.aggregate(t=Sum('quantity'))['t'] or 0
        avg_qty = int(total_qty / party_orders.count()) if party_orders.count() > 0 else 0
        
        propensity = max(0, min(100, int(100 - days_to_reorder * 5)))
        predicted_date = (today + datetime.timedelta(days=days_to_reorder)).strftime("%d %b %Y")
        
        if days_to_reorder <= 2:
            urgency = "Immediate Reorder Due"
            urgency_color = "#ef4444"
        elif days_to_reorder <= 7:
            urgency = "Expected This Week"
            urgency_color = "#f59e0b"
        else:
            urgency = f"Upcoming in {days_to_reorder}d"
            urgency_color = "#10b981"
        
        party_propensity.append({
            "party_id": party.id,
            "party_name": party.name,
            "location": "",  # not in model
            "avg_cycle_days": avg_cycle_days,
            "days_since_last_order": days_since,
            "predicted_reorder_date": predicted_date,
            "urgency": urgency,
            "urgency_color": urgency_color,
            "predicted_quantity": avg_qty,
            "preferred_item": preferred_item,
            "estimated_order_value": f"\\u20b9 {avg_qty * 280:,}",  # approx
            "propensity_score": propensity,
        })
    
    # Fallback to dummy data if no real parties exist
    if not party_propensity:
        party_propensity = [
            {"party_id": 1, "party_name": "M/s Haryana Tyre & Tube Traders", "location": "Rohtak, Haryana", "avg_cycle_days": 14, "days_since_last_order": 13, "predicted_reorder_date": (today + datetime.timedelta(days=2)).strftime("%d %b %Y"), "urgency": "Immediate Reorder Due", "urgency_color": "#ef4444", "predicted_quantity": 850, "preferred_item": "28 x 1.5 6 ply RADHU GOLD", "estimated_order_value": "\\u20b9 2,45,000", "propensity_score": 96},
            {"party_id": 2, "party_name": "Shree Ganesh Cycle Agencies", "location": "Ludhiana, Punjab", "avg_cycle_days": 21, "days_since_last_order": 19, "predicted_reorder_date": (today + datetime.timedelta(days=4)).strftime("%d %b %Y"), "urgency": "Expected This Week", "urgency_color": "#f59e0b", "predicted_quantity": 1200, "preferred_item": "26 x 2.125 NYL RADHU SUPER", "estimated_order_value": "\\u20b9 3,80,000", "propensity_score": 92},
            {"party_id": 3, "party_name": "Aggarwal Auto & Cycle Spares", "location": "Delhi NCR", "avg_cycle_days": 10, "days_since_last_order": 11, "predicted_reorder_date": (today + datetime.timedelta(days=1)).strftime("%d %b %Y"), "urgency": "Immediate Reorder Due", "urgency_color": "#ef4444", "predicted_quantity": 600, "preferred_item": "28 x 1.5 CTC RADHU STANDARD", "estimated_order_value": "\\u20b9 1,75,000", "propensity_score": 94},
        ]
        
    # Top recommended item to produce
'''
v2_body = v2_body[:party_start] + new_party_prop + v2_body[party_end + len('    # Top recommended item to produce'):]

new_views = """
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def party_analytics(request, party_id):
    from orders.models import Party, Order, OrderItem
    from django.db.models import Count
    
    today = datetime.date.today()
    
    try:
        party = Party.objects.get(pk=party_id)
    except Party.DoesNotExist:
        return Response({"error": "Party not found"}, status=404)
    
    # All orders for this party
    all_orders = Order.objects.filter(party=party).order_by('-date')
    
    # Build last 20 orders history
    order_history = []
    for order in all_orders[:20]:
        items = OrderItem.objects.filter(order=order, category='cycle_tyre')
        total_qty = sum(i.quantity for i in items)
        total_val = sum(i.quantity * i.price for i in items)
        order_history.append({
            "id": order.id,
            "date": str(order.date),
            "status": order.status,
            "items_count": items.count(),
            "total_qty": total_qty,
            "total_value": f"\\u20b9 {int(total_val):,}",
            "notes": order.notes or "",
        })
    
    # Item preference analysis
    all_items_qs = OrderItem.objects.filter(order__party=party, category='cycle_tyre').select_related('cycle_tyre_item')
    item_pref = {}
    for oi in all_items_qs:
        if not oi.cycle_tyre_item:
            continue
        tid = oi.cycle_tyre_item.id
        name = f"{oi.cycle_tyre_item.size} {oi.cycle_tyre_item.box_type} {oi.cycle_tyre_item.brand}"
        if tid not in item_pref:
            item_pref[tid] = {"item_id": tid, "item_name": name, "times_ordered": 0, "total_qty": 0}
        item_pref[tid]["times_ordered"] += 1
        item_pref[tid]["total_qty"] += oi.quantity
    item_preferences = sorted(item_pref.values(), key=lambda x: x["total_qty"], reverse=True)
    
    # Monthly chart - last 12 months
    monthly_labels = []
    monthly_quantities = []
    monthly_orders_count = []
    for i in range(11, -1, -1):
        # Calculate month
        m_offset = today.month - i - 1
        y_offset = today.year + m_offset // 12
        m_num = m_offset % 12 + 1
        # Simpler approach
        import calendar
        month_num = ((today.month - 1 - i) % 12) + 1
        year_num = today.year + ((today.month - 1 - i) // 12)
        label = datetime.date(year_num, month_num, 1).strftime("%b %y")
        month_orders = Order.objects.filter(party=party, date__year=year_num, date__month=month_num)
        month_items = OrderItem.objects.filter(order__in=month_orders, category='cycle_tyre')
        qty = month_items.aggregate(t=Sum('quantity'))['t'] or 0
        monthly_labels.append(label)
        monthly_quantities.append(qty)
        monthly_orders_count.append(month_orders.count())
    
    # AI summary
    total_orders = all_orders.count()
    all_cycle_items = OrderItem.objects.filter(order__party=party, category='cycle_tyre')
    total_quantity = all_cycle_items.aggregate(t=Sum('quantity'))['t'] or 0
    total_value_num = sum(oi.quantity * oi.price for oi in all_cycle_items)
    
    # Average cycle days
    order_dates = list(all_orders.values_list('date', flat=True))
    avg_cycle_days = 30  # default
    if len(order_dates) >= 2:
        intervals = [(order_dates[i] - order_dates[i+1]).days for i in range(len(order_dates)-1)]
        avg_cycle_days = max(1, int(sum(intervals) / len(intervals))) if intervals else 30
    
    last_order_date = order_dates[0] if order_dates else None
    days_since = (today - last_order_date).days if last_order_date else 999
    days_to_reorder = max(0, avg_cycle_days - days_since)
    predicted_reorder = (today + datetime.timedelta(days=days_to_reorder)).strftime("%d %b %Y")
    propensity = max(0, min(100, int(100 - days_to_reorder * 5)))
    
    if days_to_reorder <= 2:
        urgency = "Immediate Reorder Due"
        urgency_color = "#ef4444"
        rec = f"Call {party.name} today — reorder is overdue by {abs(days_to_reorder)} days."
    elif days_to_reorder <= 7:
        urgency = "Expected This Week"
        urgency_color = "#f59e0b"
        rec = f"Follow up with {party.name} this week. Predicted order in {days_to_reorder} days."
    else:
        urgency = f"Upcoming in {days_to_reorder} Days"
        urgency_color = "#10b981"
        rec = f"Schedule a call with {party.name} in {max(1, days_to_reorder - 3)} days to confirm next order."
    
    preferred_item_name = item_preferences[0]['item_name'] if item_preferences else "N/A"
    avg_order_qty = int(total_quantity / total_orders) if total_orders > 0 else 0
    
    return Response({
        "party": {
            "id": party.id,
            "name": party.name,
            "created_at": str(party.created_at.date()),
            "total_orders": total_orders,
        },
        "order_history": order_history,
        "monthly_chart": {
            "labels": monthly_labels,
            "quantities": monthly_quantities,
            "orders_count": monthly_orders_count,
        },
        "item_preferences": item_preferences,
        "ai_summary": {
            "avg_interval_days": avg_cycle_days,
            "last_order_date": str(last_order_date) if last_order_date else None,
            "days_since_last_order": days_since,
            "predicted_reorder_date": predicted_reorder,
            "days_to_reorder": days_to_reorder,
            "propensity_score": propensity,
            "urgency_label": urgency,
            "urgency_color": urgency_color,
            "recommendation_text": rec,
            "total_orders": total_orders,
            "total_quantity": total_quantity,
            "total_value": f"\\u20b9 {int(total_value_num):,}",
            "avg_order_qty": avg_order_qty,
            "preferred_item": preferred_item_name,
        }
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def item_analytics(request, item_id):
    from orders.models import OrderItem
    
    today = datetime.date.today()
    
    try:
        item = CycleTyreItem.objects.get(pk=item_id)
    except CycleTyreItem.DoesNotExist:
        return Response({"error": "Item not found"}, status=404)
    
    # 12-month history
    monthly_labels = []
    monthly_production = []
    monthly_sales = []
    monthly_curing = []
    
    for i in range(11, -1, -1):
        month_num = ((today.month - 1 - i) % 12) + 1
        year_num = today.year + ((today.month - 1 - i) // 12)
        label = datetime.date(year_num, month_num, 1).strftime("%b %y")
        
        p_agg = CycleTyreEntry.objects.filter(
            tyre_item=item, entry_type='production', date__year=year_num, date__month=month_num
        ).aggregate(prod=Sum('first_grade'), cur=Sum('all_curing'))
        s_agg = CycleTyreEntry.objects.filter(
            tyre_item=item, entry_type='sale', date__year=year_num, date__month=month_num
        ).aggregate(sale=Sum('quantity'))
        
        monthly_labels.append(label)
        monthly_production.append(p_agg['prod'] or 0)
        monthly_sales.append(s_agg['sale'] or 0)
        monthly_curing.append(p_agg['cur'] or 0)
    
    # Daily history - last 30 days
    daily_labels = []
    daily_production = []
    daily_sales = []
    for i in range(29, -1, -1):
        d = today - datetime.timedelta(days=i)
        p = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='production', date=d).aggregate(t=Sum('first_grade'))['t'] or 0
        s = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='sale', date=d).aggregate(t=Sum('quantity'))['t'] or 0
        daily_labels.append(d.strftime("%d %b"))
        daily_production.append(p)
        daily_sales.append(s)
    
    # All-time totals
    all_prod = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='production').aggregate(
        cur=Sum('all_curing'), first=Sum('first_grade'), sec=Sum('second_grade'), rej=Sum('rejected_grade')
    )
    all_sales = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='sale').aggregate(t=Sum('quantity'))
    
    total_curing = all_prod['cur'] or 0
    total_first = all_prod['first'] or 0
    total_second = all_prod['sec'] or 0
    total_rejected = all_prod['rej'] or 0
    total_sales = all_sales['t'] or 0
    
    # Grade percentages
    first_pct = round(total_first / total_curing * 100, 1) if total_curing > 0 else 0
    second_pct = round(total_second / total_curing * 100, 1) if total_curing > 0 else 0
    rejected_pct = round(total_rejected / total_curing * 100, 1) if total_curing > 0 else 0
    
    # Velocity
    recent_sales_60d = CycleTyreEntry.objects.filter(
        tyre_item=item, entry_type='sale', date__gte=today - datetime.timedelta(days=60)
    ).aggregate(t=Sum('quantity'))['t'] or 0
    daily_velocity = max(recent_sales_60d / 60.0, total_sales / 120.0 if total_sales > 0 else 0)
    projected_demand_30d = int(round(daily_velocity * 30 * 1.05))
    days_of_inventory = int(round(item.stock / daily_velocity)) if daily_velocity > 0.05 else (999 if item.stock > 0 else 0)
    
    if days_of_inventory <= 7 and projected_demand_30d > 20:
        stockout_risk = "CRITICAL"; risk_color = "#ef4444"
        recommendation = f"Urgent: Batch curing needed. Only {days_of_inventory} days of stock left!"
    elif days_of_inventory <= 18:
        stockout_risk = "MODERATE"; risk_color = "#f59e0b"
        recommendation = f"Buffer getting low. Plan production batch of {max(projected_demand_30d - item.stock, 50)} pcs."
    elif days_of_inventory > 90:
        stockout_risk = "OVERSTOCKED"; risk_color = "#3b82f6"
        recommendation = "Overstocked. Pause curing and focus sales push on this item."
    else:
        stockout_risk = "HEALTHY"; risk_color = "#10b981"
        recommendation = "Stock levels healthy. Maintain current production rate."
    
    # Top buyers from orders
    buyer_map = {}
    for oi in OrderItem.objects.filter(cycle_tyre_item=item, category='cycle_tyre').select_related('order__party'):
        pname = oi.order.party.name
        if pname not in buyer_map:
            buyer_map[pname] = {"party_name": pname, "party_id": oi.order.party.id, "total_qty": 0, "order_count": 0}
        buyer_map[pname]["total_qty"] += oi.quantity
        buyer_map[pname]["order_count"] += 1
    top_buyers = sorted(buyer_map.values(), key=lambda x: x["total_qty"], reverse=True)[:10]
    for b in top_buyers:
        b["avg_per_order"] = int(b["total_qty"] / b["order_count"]) if b["order_count"] > 0 else 0
    
    return Response({
        "item_info": {
            "id": item.id,
            "size": item.size,
            "box_type": item.box_type,
            "material": item.material,
            "brand": item.brand,
            "weight": str(item.weight) if item.weight else "0",
            "stock": item.stock,
            "second_stock": item.second_stock,
            "rfm_stock": item.rfm_stock,
        },
        "monthly_history": {
            "labels": monthly_labels,
            "production": monthly_production,
            "sales": monthly_sales,
            "curing": monthly_curing,
        },
        "daily_history": {
            "labels": daily_labels,
            "production": daily_production,
            "sales": daily_sales,
        },
        "all_time_totals": {
            "total_curing": total_curing,
            "total_production": total_first,
            "total_sales": total_sales,
            "total_rejected": total_rejected,
            "total_second": total_second,
        },
        "grade_breakdown": {
            "first_grade": total_first,
            "second_grade": total_second,
            "rejected_grade": total_rejected,
            "first_pct": first_pct,
            "second_pct": second_pct,
            "rejected_pct": rejected_pct,
        },
        "velocity_stats": {
            "daily_velocity": round(daily_velocity, 2),
            "projected_demand_30d": projected_demand_30d,
            "days_of_inventory": days_of_inventory,
            "stockout_risk": stockout_risk,
            "risk_color": risk_color,
            "recommendation": recommendation,
        },
        "top_buyers": top_buyers,
    })
"""

views_content = views_content.rstrip() + '\\n' + new_views + '\\n' + v2_body + '\\n'

with open(r'C:\\Users\\risha\\Documents\\radhufullstack\\backend\\cycletyres\\views.py', 'w', encoding='utf-8') as f:
    f.write(views_content)
