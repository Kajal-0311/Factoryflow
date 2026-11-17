from django.urls import path
from apps.reports import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_hub, name='report_hub'),
    path('<str:report_id>/', views.view_report, name='view_report'),
]
