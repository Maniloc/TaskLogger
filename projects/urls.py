from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('projects/<int:project_pk>/tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/quick-add/', views.quick_add, name='quick_add'),
    path('report/', views.report, name='report'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('admin-panel/user/<int:user_id>/', views.admin_user_detail, name='admin_user_detail'),
]
