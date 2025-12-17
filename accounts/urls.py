from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccountViewSet, CreditCardViewSet

router = DefaultRouter()
router.register(r'accounts', AccountViewSet, basename='accounts')
router.register(r'credit-cards', CreditCardViewSet, basename='credit-cards')

urlpatterns = [
    path('', include(router.urls)),
]
