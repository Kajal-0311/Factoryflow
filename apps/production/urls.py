from django.urls import path
from apps.production import views

app_name = 'production'

urlpatterns = [
    path('', views.run_list, name='run_list'),
    path('new/', views.create_run, name='create_run'),
    path('<int:pk>/', views.run_detail, name='run_detail'),
]
