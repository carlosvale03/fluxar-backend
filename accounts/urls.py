from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccountViewSet, CreditCardViewSet, CreditCardInvoiceViewSet

router = DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'credit-cards', CreditCardViewSet)
router.register(r'invoices', CreditCardInvoiceViewSet, basename='invoices')

urlpatterns = [
    path('', include(router.urls)),
]
