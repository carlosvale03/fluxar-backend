from django.urls import path

from . import views

urlpatterns = [
    path('salary/models/', views.SalaryModelsView.as_view(), name='salary-models'),
    path('salary/plan/', views.SalaryPlanView.as_view(), name='salary-plan'),
    path('salary/simulate/', views.SalarySimulateView.as_view(), name='salary-simulate'),
]
