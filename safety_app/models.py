# safety_app/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Enter valid phone number")]
    )
    emergency_keyword = models.CharField(max_length=50, blank=True, null=True)
    safe_word = models.CharField(max_length=50, blank=True, null=True)
    is_active_alert = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Profile"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class EmergencyContact(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emergency_contacts')
    name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=50)
    phone_number = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Enter valid phone number")]
    )
    email = models.EmailField()
    priority = models.IntegerField(default=1, help_text="1 is highest priority")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.relationship}) - {self.user.username}"

    class Meta:
        verbose_name = "Emergency Contact"
        verbose_name_plural = "Emergency Contacts"
        ordering = ['priority', 'name']


class SafeZone(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='safe_zones')
    name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_meters = models.IntegerField(default=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.user.username}"

    class Meta:
        verbose_name = "Safe Zone"
        verbose_name_plural = "Safe Zones"


class Alert(models.Model):
    STATUS_CHOICES = [
        ('TRIGGERED', 'Triggered'),
        ('PENDING_CANCEL', 'Pending Cancellation'),
        ('CANCELLED', 'Cancelled'),
        ('DISPATCHED', 'Dispatched'),
        ('RESOLVED', 'Resolved'),
        ('TIMEOUT', 'Timeout'),
    ]

    alert_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TRIGGERED')
    
    # Trigger Information
    triggered_at = models.DateTimeField(auto_now_add=True)
    trigger_method = models.CharField(max_length=50, default='panic_button')
    
    # Location Information
    initial_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    initial_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    initial_accuracy = models.FloatField(null=True, blank=True)
    
    # Cancellation Information
    cancellation_timer_started = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    
    # Dispatch Information
    dispatched_at = models.DateTimeField(null=True, blank=True)
    contacts_notified = models.IntegerField(default=0)
    
    # Resolution Information
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, null=True)
    
    # Safe Word Validation
    safe_word_attempted = models.BooleanField(default=False)
    safe_word_success = models.BooleanField(default=False)
    
    # Metadata
    user_agent = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Alert {self.alert_id} - {self.user.username} - {self.status}"

    class Meta:
        verbose_name = "Alert"
        verbose_name_plural = "Alerts"
        ordering = ['-triggered_at']


class LocationTrack(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='location_tracks')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_in_safe_zone = models.BooleanField(default=False)
    nearest_safe_zone = models.ForeignKey(SafeZone, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Track {self.alert.alert_id} at {self.timestamp}"

    class Meta:
        verbose_name = "Location Track"
        verbose_name_plural = "Location Tracks"
        ordering = ['-timestamp']


class DispatchLog(models.Model):
    CHANNEL_CHOICES = [
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('PUSH', 'Push Notification'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('SIMULATED', 'Simulated'),
    ]

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='dispatch_logs')
    contact = models.ForeignKey(EmergencyContact, on_delete=models.CASCADE)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    message_content = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.channel} to {self.contact.name} - {self.status}"

    class Meta:
        verbose_name = "Dispatch Log"
        verbose_name_plural = "Dispatch Logs"
        ordering = ['-created_at']


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('ALERT_TRIGGERED', 'Alert Triggered'),
        ('ALERT_CANCELLED', 'Alert Cancelled'),
        ('ALERT_DISPATCHED', 'Alert Dispatched'),
        ('ALERT_RESOLVED', 'Alert Resolved'),
        ('LOCATION_UPDATED', 'Location Updated'),
        ('CONTACT_ADDED', 'Contact Added'),
        ('CONTACT_MODIFIED', 'Contact Modified'),
        ('SAFE_ZONE_CREATED', 'Safe Zone Created'),
        ('SAFE_ZONE_MODIFIED', 'Safe Zone Modified'),
        ('USER_LOGIN', 'User Login'),
        ('USER_LOGOUT', 'User Logout'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.action} - {self.user.username} at {self.timestamp}"

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ['-timestamp']