from django.urls import path
from apps.billing import views

app_name = 'billing'

urlpatterns = [
    path('', views.invoice_list, name='invoice_list'),
    path('<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('<int:pk>/pdf/', views.download_pdf_invoice, name='download_pdf'),
    path('<int:pk>/credit-note/', views.issue_credit_note, name='issue_credit_note'),
    path('credit-notes/', views.credit_note_list, name='credit_note_list'),
]
