from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TransactionViewSet, CategoryViewSet, TagViewSet

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transactions')
# Rotas auxiliares para dependências
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'tags', TagViewSet, basename='tags')

urlpatterns = [
    path('', include(router.urls)),
]
