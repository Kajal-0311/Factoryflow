from django.urls import path
from apps.payments import views

app_name = 'payments'

urlpatterns = [
    path('', views.payment_list, name='payment_list'),
    path('new/', views.create_payment, name='create_payment'),
    path('ageing/', views.ageing_report_view, name='ageing_report'),
]
