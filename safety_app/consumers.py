# safety_app/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Alert, LocationTrack, AuditLog
from decimal import Decimal
from datetime import datetime

class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.alert_group_name = f'alert_{self.user.id}'
        
        # Join alert group
        await self.channel_layer.group_add(
            self.alert_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to alert system'
        }))

    async def disconnect(self, close_code):
        # Leave alert group
        if hasattr(self, 'alert_group_name'):
            await self.channel_layer.group_discard(
                self.alert_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'location_update':
            await self.handle_location_update(data)
        elif message_type == 'alert_trigger':
            await self.handle_alert_trigger(data)
        elif message_type == 'alert_cancel':
            await self.handle_alert_cancel(data)
        elif message_type == 'safe_word_check':
            await self.handle_safe_word_check(data)

    async def handle_location_update(self, data):
        """Handle incoming location updates from the client"""
        alert_id = data.get('alert_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        accuracy = data.get('accuracy')
        
        if not all([alert_id, latitude, longitude]):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Missing required location data'
            }))
            return
        
        # Save location track
        location_data = await self.save_location_track(
            alert_id, latitude, longitude, accuracy,
            data.get('altitude'), data.get('speed'), data.get('heading')
        )
        
        if location_data:
            # Broadcast to monitoring group
            monitor_group = f'monitor_{alert_id}'
            await self.channel_layer.group_send(
                monitor_group,
                {
                    'type': 'location_broadcast',
                    'location': location_data
                }
            )
            
            # Send confirmation back to user
            await self.send(text_data=json.dumps({
                'type': 'location_saved',
                'data': location_data
            }))

    async def handle_alert_trigger(self, data):
        """Handle alert trigger from client"""
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        trigger_method = data.get('trigger_method', 'panic_button')
        
        alert_data = await self.create_alert(
            latitude, longitude, trigger_method,
            data.get('user_agent'), data.get('ip_address')
        )
        
        if alert_data:
            await self.send(text_data=json.dumps({
                'type': 'alert_triggered',
                'alert': alert_data
            }))

    async def handle_alert_cancel(self, data):
        """Handle alert cancellation"""
        alert_id = data.get('alert_id')
        reason = data.get('reason', '')
        
        success = await self.cancel_alert(alert_id, reason)
        
        await self.send(text_data=json.dumps({
            'type': 'alert_cancelled' if success else 'error',
            'message': 'Alert cancelled successfully' if success else 'Failed to cancel alert',
            'alert_id': alert_id
        }))

    async def handle_safe_word_check(self, data):
        """Verify safe word for alert cancellation"""
        alert_id = data.get('alert_id')
        safe_word = data.get('safe_word')
        
        is_valid = await self.verify_safe_word(alert_id, safe_word)
        
        await self.send(text_data=json.dumps({
            'type': 'safe_word_result',
            'valid': is_valid,
            'alert_id': alert_id
        }))

    # Database operations
    @database_sync_to_async
    def save_location_track(self, alert_id, lat, lon, accuracy, altitude, speed, heading):
        try:
            alert = Alert.objects.get(alert_id=alert_id, user=self.user)
            
            # Check if location is in safe zone
            is_in_safe_zone, nearest_zone = self.check_safe_zone(lat, lon)
            
            track = LocationTrack.objects.create(
                alert=alert,
                latitude=Decimal(str(lat)),
                longitude=Decimal(str(lon)),
                accuracy=accuracy,
                altitude=altitude,
                speed=speed,
                heading=heading,
                is_in_safe_zone=is_in_safe_zone,
                nearest_safe_zone=nearest_zone
            )
            
            # Create audit log
            AuditLog.objects.create(
                user=self.user,
                alert=alert,
                action='LOCATION_UPDATED',
                description=f'Location updated: ({lat}, {lon})',
                metadata={'accuracy': accuracy, 'in_safe_zone': is_in_safe_zone}
            )
            
            return {
                'id': track.id,
                'latitude': float(track.latitude),
                'longitude': float(track.longitude),
                'accuracy': track.accuracy,
                'timestamp': track.timestamp.isoformat(),
                'is_in_safe_zone': track.is_in_safe_zone
            }
        except Exception as e:
            print(f"Error saving location: {e}")
            return None

    @database_sync_to_async
    def create_alert(self, lat, lon, trigger_method, user_agent, ip_address):
        try:
            alert = Alert.objects.create(
                user=self.user,
                status='TRIGGERED',
                trigger_method=trigger_method,
                initial_latitude=Decimal(str(lat)) if lat else None,
                initial_longitude=Decimal(str(lon)) if lon else None,
                user_agent=user_agent,
                ip_address=ip_address
            )
            
            # Update user profile
            profile = self.user.profile
            profile.is_active_alert = True
            profile.save()
            
            # Create audit log
            AuditLog.objects.create(
                user=self.user,
                alert=alert,
                action='ALERT_TRIGGERED',
                description=f'Alert triggered via {trigger_method}',
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={'latitude': lat, 'longitude': lon}
            )
            
            return {
                'alert_id': str(alert.alert_id),
                'status': alert.status,
                'triggered_at': alert.triggered_at.isoformat()
            }
        except Exception as e:
            print(f"Error creating alert: {e}")
            return None

    @database_sync_to_async
    def cancel_alert(self, alert_id, reason):
        try:
            alert = Alert.objects.get(alert_id=alert_id, user=self.user)
            alert.status = 'CANCELLED'
            alert.cancelled_at = datetime.now()
            alert.cancellation_reason = reason
            alert.save()
            
            # Update user profile
            profile = self.user.profile
            profile.is_active_alert = False
            profile.save()
            
            # Create audit log
            AuditLog.objects.create(
                user=self.user,
                alert=alert,
                action='ALERT_CANCELLED',
                description=f'Alert cancelled: {reason}',
                metadata={'cancellation_reason': reason}
            )
            
            return True
        except Exception as e:
            print(f"Error cancelling alert: {e}")
            return False

    @database_sync_to_async
    def verify_safe_word(self, alert_id, safe_word):
        try:
            alert = Alert.objects.get(alert_id=alert_id, user=self.user)
            profile = self.user.profile
            
            alert.safe_word_attempted = True
            
            if profile.safe_word and profile.safe_word.lower() == safe_word.lower():
                alert.safe_word_success = True
                alert.save()
                return True
            else:
                alert.save()
                return False
        except Exception as e:
            print(f"Error verifying safe word: {e}")
            return False

    def check_safe_zone(self, lat, lon):
        """Check if coordinates are within any safe zone using Haversine formula"""
        from math import radians, sin, cos, sqrt, atan2
        
        safe_zones = self.user.safe_zones.filter(is_active=True)
        
        for zone in safe_zones:
            # Haversine formula
            R = 6371000  # Earth's radius in meters
            
            lat1 = radians(float(lat))
            lon1 = radians(float(lon))
            lat2 = radians(float(zone.latitude))
            lon2 = radians(float(zone.longitude))
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            distance = R * c
            
            if distance <= zone.radius_meters:
                return True, zone
        
        return False, None

    # Receive from channel layer
    async def location_broadcast(self, event):
        """Broadcast location updates to monitoring clients"""
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'location': event['location']
        }))


class MonitorConsumer(AsyncWebsocketConsumer):
    """Consumer for monitoring active alerts"""
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.alert_id = self.scope['url_route']['kwargs']['alert_id']
        self.monitor_group_name = f'monitor_{self.alert_id}'
        
        # Verify user has permission to monitor this alert
        can_monitor = await self.verify_monitor_permission()
        
        if not can_monitor:
            await self.close()
            return
        
        # Join monitoring group
        await self.channel_layer.group_add(
            self.monitor_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current alert status
        alert_data = await self.get_alert_data()
        await self.send(text_data=json.dumps({
            'type': 'alert_status',
            'alert': alert_data
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'monitor_group_name'):
            await self.channel_layer.group_discard(
                self.monitor_group_name,
                self.channel_name
            )

    @database_sync_to_async
    def verify_monitor_permission(self):
        """Check if user can monitor this alert (is emergency contact or alert owner)"""
        try:
            alert = Alert.objects.get(alert_id=self.alert_id)
            
            # Owner can always monitor
            if alert.user == self.user:
                return True
            
            # Check if user is an emergency contact
            is_contact = alert.user.emergency_contacts.filter(
                email=self.user.email
            ).exists()
            
            return is_contact
        except:
            return False

    @database_sync_to_async
    def get_alert_data(self):
        try:
            alert = Alert.objects.get(alert_id=self.alert_id)
            latest_location = alert.location_tracks.first()
            
            return {
                'alert_id': str(alert.alert_id),
                'status': alert.status,
                'triggered_at': alert.triggered_at.isoformat(),
                'user': alert.user.get_full_name() or alert.user.username,
                'latest_location': {
                    'latitude': float(latest_location.latitude),
                    'longitude': float(latest_location.longitude),
                    'timestamp': latest_location.timestamp.isoformat()
                } if latest_location else None
            }
        except:
            return None

    async def location_broadcast(self, event):
        """Receive location broadcast from alert consumer"""
        await self.send(text_data=json.dumps(event))