from django.urls import path
from apps.bom import views

app_name = 'bom'

urlpatterns = [
    path('', views.bom_list, name='bom_list'),
    path('<int:pk>/', views.bom_detail, name='bom_detail'),
    path('api/requirements/<int:product_id>/', views.api_calculate_requirements, name='api_requirements'),
]
