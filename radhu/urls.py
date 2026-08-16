from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/stock/', include('stock.urls')),
    path('api/cycletube/', include('cycletube.urls')),
    path('api/cycletyres/', include('cycletyres.urls')),
    path('api/tallysync/', include('tallysync.urls')),
    path('tallysync/', include('tallysync.urls')),  # For webhook compatibility with http://.../tallysync/webhook/
    path('api/hrms/', include('hrms.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/accounts/', include('accounts.urls')),
]
