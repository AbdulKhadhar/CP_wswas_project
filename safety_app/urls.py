from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    
    # Emergency Contacts
    path('contacts/', views.contacts_view, name='contacts'),
    path('contacts/<int:contact_id>/edit/', views.contact_edit_view, name='contact_edit'),
    path('contacts/<int:contact_id>/delete/', views.contact_delete_view, name='contact_delete'),
    
    # Safe Zones
    path('safe-zones/', views.safe_zones_view, name='safe_zones'),
    
    # Alert Management
    path('alert/panel/', views.alert_panel_view, name='alert_panel'),
    path('alert/trigger/', views.trigger_alert_view, name='trigger_alert'),
    path('alert/cancel/', views.cancel_alert_view, name='cancel_alert'),
    path('alert/dispatch/', views.dispatch_alert_view, name='dispatch_alert'),
    path('alert/history/', views.alert_history_view, name='alert_history'),
    path('alert/<uuid:alert_id>/', views.alert_detail_view, name='alert_detail'),
    path('alert/monitor/<uuid:alert_id>/', views.monitor_alert_view, name='monitor_alert'),
]