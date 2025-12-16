# safety_app/services.py
from django.utils import timezone
from django.conf import settings
from .models import Alert, AuditLog, DispatchLog, EmergencyContact
from decimal import Decimal
from datetime import timedelta


class AlertService:
    """Service for managing alert lifecycle"""
    
    def create_alert(self, user, latitude, longitude, trigger_method, user_agent=None, ip_address=None):
        """Create a new alert"""
        alert = Alert.objects.create(
            user=user,
            status='TRIGGERED',
            trigger_method=trigger_method,
            initial_latitude=Decimal(str(latitude)) if latitude else None,
            initial_longitude=Decimal(str(longitude)) if longitude else None,
            user_agent=user_agent,
            ip_address=ip_address,
            cancellation_timer_started=timezone.now()
        )
        
        # Update user profile
        profile = user.profile
        profile.is_active_alert = True
        profile.save()
        
        # Create audit log
        AuditLog.objects.create(
            user=user,
            alert=alert,
            action='ALERT_TRIGGERED',
            description=f'Alert triggered via {trigger_method}',
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                'latitude': str(latitude) if latitude else None,
                'longitude': str(longitude) if longitude else None,
                'trigger_method': trigger_method
            }
        )
        
        return alert
    
    def cancel_alert(self, alert, reason=''):
        """Cancel an active alert"""
        if alert.status not in ['TRIGGERED', 'PENDING_CANCEL', 'DISPATCHED']:
            return False
        
        alert.status = 'CANCELLED'
        alert.cancelled_at = timezone.now()
        alert.cancellation_reason = reason
        alert.save()
        
        # Update user profile
        profile = alert.user.profile
        profile.is_active_alert = False
        profile.save()
        
        # Create audit log
        AuditLog.objects.create(
            user=alert.user,
            alert=alert,
            action='ALERT_CANCELLED',
            description=f'Alert cancelled: {reason}',
            metadata={'cancellation_reason': reason}
        )
        
        return True
    
    def resolve_alert(self, alert, notes=''):
        """Resolve an alert"""
        alert.status = 'RESOLVED'
        alert.resolved_at = timezone.now()
        alert.resolution_notes = notes
        alert.save()
        
        # Update user profile
        profile = alert.user.profile
        profile.is_active_alert = False
        profile.save()
        
        # Create audit log
        AuditLog.objects.create(
            user=alert.user,
            alert=alert,
            action='ALERT_RESOLVED',
            description=f'Alert resolved: {notes}',
            metadata={'resolution_notes': notes}
        )
        
        return True
    
    def check_timeout(self, alert):
        """Check if alert cancellation timer has expired"""
        if not alert.cancellation_timer_started:
            return False
        
        timeout_seconds = getattr(settings, 'ALERT_CANCELLATION_TIMEOUT', 120)
        elapsed = (timezone.now() - alert.cancellation_timer_started).total_seconds()
        
        if elapsed >= timeout_seconds and alert.status == 'TRIGGERED':
            # Timer expired - auto-dispatch
            alert.status = 'PENDING_CANCEL'
            alert.save()
            return True
        
        return False
    
    def verify_safe_word(self, alert, safe_word):
        """Verify safe word for alert cancellation"""
        profile = alert.user.profile
        
        alert.safe_word_attempted = True
        
        if profile.safe_word and profile.safe_word.lower() == safe_word.lower():
            alert.safe_word_success = True
            alert.save()
            return True
        else:
            alert.save()
            return False


class DispatchService:
    """Service for dispatching alerts to emergency contacts"""
    
    def dispatch_alert(self, alert):
        """Dispatch alert to all active emergency contacts"""
        contacts = alert.user.emergency_contacts.filter(is_active=True).order_by('priority')
        
        if not contacts.exists():
            return {
                'success': False,
                'message': 'No active emergency contacts found',
                'contacts_notified': 0,
                'dispatch_logs': []
            }
        
        dispatch_logs = []
        contacts_notified = 0
        
        for contact in contacts:
            # Dispatch via SMS
            sms_log = self._send_sms(alert, contact)
            dispatch_logs.append(sms_log)
            
            # Dispatch via Email
            email_log = self._send_email(alert, contact)
            dispatch_logs.append(email_log)
            
            contacts_notified += 1
        
        # Update alert status
        alert.status = 'DISPATCHED'
        alert.dispatched_at = timezone.now()
        alert.contacts_notified = contacts_notified
        alert.save()
        
        # Create audit log
        AuditLog.objects.create(
            user=alert.user,
            alert=alert,
            action='ALERT_DISPATCHED',
            description=f'Alert dispatched to {contacts_notified} contacts',
            metadata={
                'contacts_notified': contacts_notified,
                'dispatch_channels': ['SMS', 'EMAIL']
            }
        )
        
        return {
            'success': True,
            'contacts_notified': contacts_notified,
            'dispatch_logs': [
                {
                    'contact': log.contact.name,
                    'channel': log.channel,
                    'status': log.status
                } for log in dispatch_logs
            ]
        }
    
    def _send_sms(self, alert, contact):
        """Simulate SMS dispatch"""
        message = self._generate_sms_message(alert, contact)
        
        # Create dispatch log (simulated)
        log = DispatchLog.objects.create(
            alert=alert,
            contact=contact,
            channel='SMS',
            status='SIMULATED',
            message_content=message,
            sent_at=timezone.now()
        )
        
        return log
    
    def _send_email(self, alert, contact):
        """Simulate email dispatch"""
        message = self._generate_email_message(alert, contact)
        
        # Create dispatch log (simulated)
        log = DispatchLog.objects.create(
            alert=alert,
            contact=contact,
            channel='EMAIL',
            status='SIMULATED',
            message_content=message,
            sent_at=timezone.now()
        )
        
        return log
    
    def _generate_sms_message(self, alert, contact):
        """Generate SMS message content"""
        user = alert.user
        location_url = self._generate_maps_url(
            alert.initial_latitude, 
            alert.initial_longitude
        )
        
        message = f"""🚨 EMERGENCY ALERT 🚨

{user.get_full_name() or user.username} has triggered an emergency alert!

Time: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}
Location: {location_url}

Monitor live tracking: {self._generate_monitor_url(alert)}

This is an automated message from Women Safety Web Alert System."""
        
        return message
    
    def _generate_email_message(self, alert, contact):
        """Generate email message content"""
        user = alert.user
        location_url = self._generate_maps_url(
            alert.initial_latitude, 
            alert.initial_longitude
        )
        monitor_url = self._generate_monitor_url(alert)
        
        message = f"""Dear {contact.name},

This is an EMERGENCY ALERT from the Women Safety Web Alert System.

{user.get_full_name() or user.username} has triggered an emergency alert and you are listed as an emergency contact.

ALERT DETAILS:
- User: {user.get_full_name() or user.username}
- Trigger Time: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}
- Trigger Method: {alert.trigger_method}
- Alert ID: {alert.alert_id}

LOCATION INFORMATION:
Current Location: {location_url}

REAL-TIME TRACKING:
You can monitor the user's real-time location here:
{monitor_url}

WHAT TO DO:
1. Try to contact {user.first_name} immediately
2. If you cannot reach them, consider contacting local authorities
3. Use the tracking link above to monitor their location

This is an automated alert. Please respond immediately.

---
Women Safety Web Alert System
Emergency Response Protocol"""
        
        return message
    
    def _generate_maps_url(self, latitude, longitude):
        """Generate Google Maps URL for location"""
        if latitude and longitude:
            return f"https://www.google.com/maps?q={latitude},{longitude}"
        return "Location not available"
    
    def _generate_monitor_url(self, alert):
        """Generate monitoring URL"""
        # In production, this would be the full domain
        return f"http://localhost:8000/alert/monitor/{alert.alert_id}/"


class GeoSpatialService:
    """Service for geo-spatial calculations"""
    
    @staticmethod
    def haversine_distance(lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        Returns distance in meters
        """
        from math import radians, sin, cos, sqrt, atan2
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [
            float(lat1), float(lon1), 
            float(lat2), float(lon2)
        ])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        # Earth's radius in meters
        R = 6371000
        distance = R * c
        
        return distance
    
    @staticmethod
    def is_in_safe_zone(user, latitude, longitude):
        """
        Check if coordinates are within any of user's safe zones
        Returns (is_safe, nearest_zone, distance)
        """
        safe_zones = user.safe_zones.filter(is_active=True)
        
        nearest_zone = None
        min_distance = float('inf')
        
        for zone in safe_zones:
            distance = GeoSpatialService.haversine_distance(
                latitude, longitude,
                zone.latitude, zone.longitude
            )
            
            if distance < min_distance:
                min_distance = distance
                nearest_zone = zone
            
            if distance <= zone.radius_meters:
                return True, zone, distance
        
        return False, nearest_zone, min_distance
    
    @staticmethod
    def get_address_from_coordinates(latitude, longitude):
        """
        Reverse geocode coordinates to get address
        (This would use a geocoding service in production)
        """
        # Placeholder - would integrate with geocoding API
        return f"Location: {latitude}, {longitude}"