from django.db import models
from django.contrib.auth.models import User

PAGES_MAP = {
    'Home': [
        ('home', 'Home Page'),
    ],
    'Auto Tyre': [
        ('dashboard', 'Dashboard'),
        ('add_tyre', 'Add Tyre Item'),
        ('add_production', 'Add Production'),
        ('add_dispatch', 'Add Dispatch'),
        ('add_adjustment', 'Add Adjustment'),
        ('entries_log', 'Entries Log'),
        ('monthly_report', 'Monthly Report'),
        ('production_sheet', 'Production Sheet'),
        ('daily_summary', 'Daily Summary'),
    ],
    'Cycle Tube': [
        ('tube_dashboard', 'Dashboard'),
        ('tube_add_item', 'Add Tube Item'),
        ('tube_add_production', 'Add Production'),
        ('tube_add_sale', 'Add Dispatch'),
        ('tube_add_adjustment', 'Add Adjustment'),
        ('tube_entries_log', 'Entries Log'),
        ('tube_monthly_report', 'Monthly Report'),
        ('tube_production_summary', 'Production Summary'),
    ],
    'Cycle Tyre': [
        ('cycletyre_dashboard', 'Dashboard'),
        ('cycletyre_add_item', 'Add Tyre Item'),
        ('cycletyre_add_production', 'Add Production'),
        ('cycletyre_add_sale', 'Add Dispatch'),
        ('cycletyre_add_adjustment', 'Add Adjustment'),
        ('cycletyre_entries_log', 'Entries Log'),
        ('cycletyre_monthly_report', 'Monthly Report'),
        ('cycletyre_daily_summary', 'Daily Summary'),
    ],
    'HRMS': [
        ('hr_dashboard', 'Dashboard'),
        ('employee_list', 'Employees'),
        ('attendance_list', 'Attendance Register'),
        ('bulk_attendance', 'Bulk Attendance'),
        ('production_list', 'Production'),
        ('salary_list', 'Salary'),
    ],
    'Tally Sync': [
        ('tally_sales_summary', 'Sales Summary'),
        ('tally_mapping_list', 'Item Mapping'),
        ('tally_sync_log', 'Sync Logs'),
        ('tally_map_pending_item', 'Map Pending Items'),
    ],
    'Orders': [
        ('my_orders', 'My Orders'),
        ('create_order', 'Create Order'),
        ('order_detail', 'View Order Detail'),
        ('import_orders', 'Import Orders'),
    ],
    'Admin': [
        ('admin_orders', 'View All Orders'),
        ('manage_users', 'Manage Users'),
        ('create_user', 'Create User'),
        ('edit_user', 'Edit User'),
    ],
    'RADHU AI': [
        ('ai_agent', 'AI Agent Chat'),
        ('ai_audit_log', 'AI Audit Log'),
    ],
}


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    allowed_pages = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.user.username
