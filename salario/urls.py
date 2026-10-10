from django.urls import path

from . import views

urlpatterns = [
    path('salary/models/', views.SalaryModelsView.as_view(), name='salary-models'),
    path('salary/plan/', views.SalaryPlanView.as_view(), name='salary-plan'),
    path('salary/simulate/', views.SalarySimulateView.as_view(), name='salary-simulate'),
    path('salary/pending/', views.SalaryPendingView.as_view(), name='salary-pending'),
    path('salary/divisions/preview/', views.SalaryDivisionPreviewView.as_view(), name='salary-division-preview'),
    path('salary/divisions/', views.SalaryDivisionsView.as_view(), name='salary-divisions'),
    path('salary/divisions/<uuid:pk>/', views.SalaryDivisionDetailView.as_view(), name='salary-division-detail'),
    path('salary/divisions/<uuid:pk>/undo/', views.SalaryDivisionUndoView.as_view(), name='salary-division-undo'),
]
