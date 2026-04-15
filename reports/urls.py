from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReportViewSet, FocusedMonitorViewSet

router = DefaultRouter()
router.register(r'reports', ReportViewSet, basename='reports')
router.register(r'focused-monitors', FocusedMonitorViewSet, basename='focused-monitors')

urlpatterns = [
    path('', include(router.urls)),
]
