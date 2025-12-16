from django.contrib import admin
from .models import (
    UserProfile, EmergencyContact, SafeZone,
    Alert, LocationTrack, DispatchLog, AuditLog
)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'is_active_alert']
    search_fields = ['user__username', 'phone_number']

@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'relationship', 'user', 'priority', 'is_active']
    list_filter = ['is_active', 'priority']
    search_fields = ['name', 'user__username']

@admin.register(SafeZone)
class SafeZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'latitude', 'longitude', 'radius_meters']
    search_fields = ['name', 'user__username']

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['alert_id', 'user', 'status', 'triggered_at']
    list_filter = ['status', 'triggered_at']
    search_fields = ['user__username', 'alert_id']
    readonly_fields = ['alert_id']

@admin.register(LocationTrack)
class LocationTrackAdmin(admin.ModelAdmin):
    list_display = ['alert', 'latitude', 'longitude', 'timestamp']
    list_filter = ['timestamp']

@admin.register(DispatchLog)
class DispatchLogAdmin(admin.ModelAdmin):
    list_display = ['alert', 'contact', 'channel', 'status', 'sent_at']
    list_filter = ['channel', 'status']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__username', 'description']