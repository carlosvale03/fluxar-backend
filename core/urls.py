from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/', include('accounts.urls')),
    path('api/', include('transactions.urls')),
    path('api/', include('budgets.urls')),
    path('api/', include('reports.urls')),
    path('api/', include('data_exchange.urls')),
    path('api/', include('goals.urls')),
]
