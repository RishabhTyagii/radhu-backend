from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.ai_agent_chat, name='ai_chat'),
    path('status/', views.ai_agent_status, name='ai_status'),
    path('actions/confirm/', views.ai_action_confirm, name='ai_action_confirm'),
    path('actions/reject/', views.ai_action_reject, name='ai_action_reject'),
    path('logs/', views.ai_audit_logs, name='ai_audit_logs'),
]
