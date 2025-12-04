from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import api_views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('stock/', views.stock_dashboard, name='stock_dashboard'),
    # API endpoints
    path('api/product/<int:product_id>/stock-history/', api_views.product_stock_history, name='product_stock_history'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_add, name='product_add'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),
    path('products/<int:product_id>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:product_id>/delete/', views.product_delete, name='product_delete'),
    path('products/<int:product_id>/movement/add/', views.movement_add, name='movement_add'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('analytics/sales-report/', views.sales_report, name='sales_report'),
    path('analytics/products/', views.product_analytics, name='product_analytics'),
    path('documentation/', views.documentation, name='documentation'),
    path('advertising/', views.advertising_dashboard, name='advertising_dashboard'),
    path('advertising/campaigns/', views.campaign_list, name='campaign_list'),
    path('advertising/campaigns/add/', views.campaign_create, name='campaign_create'),
    path('advertising/campaigns/<int:campaign_id>/', views.campaign_detail, name='campaign_detail'),
    path('advertising/campaigns/<int:campaign_id>/edit/', views.campaign_edit, name='campaign_edit'),
    path('advertising/campaigns/<int:campaign_id>/delete/', views.campaign_delete, name='campaign_delete'),
    path('advertising/analytics/', views.advertising_analytics, name='advertising_analytics'),
    path('advertising/goals/', views.campaign_goals, name='campaign_goals'),
    path('advertising/goals/add/', views.goal_create, name='goal_create'),
    path('advertising/goals/<int:goal_id>/', views.goal_detail, name='goal_detail'),
    path('advertising/goals/<int:goal_id>/edit/', views.goal_edit, name='goal_edit'),
    path('advertising/goals/<int:goal_id>/update-progress/', views.goal_update_progress, name='goal_update_progress'),
    path('advertising/goals/<int:goal_id>/archive/', views.goal_archive, name='goal_archive'),
    path('advertising/goals/<int:goal_id>/reactivate/', views.goal_reactivate, name='goal_reactivate'),
    path('advertising/goals/<int:goal_id>/delete/', views.goal_delete, name='goal_delete'),
    path('positions/', views.position_tracking, name='position_tracking'),
    path('keyword/<int:keyword_id>/delete/', views.delete_keyword, name='delete_keyword'),
    path('keyword/<int:keyword_id>/history/', views.keyword_history, name='keyword_history'),
    
    # API
    path('api/keyword/<int:keyword_id>/history/', views.api_keyword_history, name='api_keyword_history'),
    path('api/keywords-by-product/<int:product_id>/', views.api_keywords_by_product, name='api_keywords_by_product'),
]
