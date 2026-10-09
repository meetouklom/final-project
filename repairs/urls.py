from django.urls import path
from . import views

urlpatterns = [
    path('comments/', views.comment_management, name='comment_management'),
    path('comments/<int:pk>/reply/', views.reply_from_comment_management, name='comment_management_reply'),
    path('new/', views.create_request, name='repair_create'),
    path('<int:pk>/', views.request_detail, name='repair_detail'),
    path('<int:pk>/comments/', views.add_repair_comment, name='repair_comment'),
    path('<int:pk>/rating/', views.rate_repair, name='repair_rating'),
    path('<int:pk>/analyze/', views.analyze_repair, name='repair_ai_analyze'),
    path('<int:pk>/update/', views.update_request, name='repair_update'),
    path('<int:pk>/delete/', views.delete_request, name='repair_delete'),
]
