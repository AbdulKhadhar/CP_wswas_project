# safety_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import (
    UserProfile, EmergencyContact, SafeZone, 
    Alert, LocationTrack, DispatchLog, AuditLog
)
from .forms import (
    UserProfileForm, EmergencyContactForm, 
    SafeZoneForm, UserRegistrationForm
)
from .services import AlertService, DispatchService
import json


# Authentication Views
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create user profile
            UserProfile.objects.create(
                user=user,
                phone_number=form.cleaned_data.get('phone_number'),
                safe_word=form.cleaned_data.get('safe_word')
            )
            
            # Log user in
            login(request, user)
            
            # Create audit log
            AuditLog.objects.create(
                user=user,
                action='USER_LOGIN',
                description='User registered and logged in',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, 'Registration successful! Please add emergency contacts.')
            return redirect('contacts')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Create audit log
            AuditLog.objects.create(
                user=user,
                action='USER_LOGIN',
                description='User logged in',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'registration/login.html')


@login_required
def logout_view(request):
    # Create audit log
    AuditLog.objects.create(
        user=request.user,
        action='USER_LOGOUT',
        description='User logged out',
        ip_address=get_client_ip(request)
    )
    
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('login')


# Dashboard Views
@login_required
def dashboard_view(request):
    # Get or create profile
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'phone_number': ''}
    )
    
    active_alert = Alert.objects.filter(
        user=request.user,
        status__in=['TRIGGERED', 'PENDING_CANCEL', 'DISPATCHED']
    ).first()
    
    recent_alerts = Alert.objects.filter(user=request.user).order_by('-triggered_at')[:5]
    emergency_contacts = request.user.emergency_contacts.filter(is_active=True)
    safe_zones = request.user.safe_zones.filter(is_active=True)
    
    context = {
        'profile': profile,
        'active_alert': active_alert,
        'recent_alerts': recent_alerts,
        'emergency_contacts': emergency_contacts,
        'safe_zones': safe_zones,
        'contacts_count': emergency_contacts.count(),
        'safe_zones_count': safe_zones.count(),
    }
    
    return render(request, 'safety_app/dashboard.html', context)


# Emergency Contact Views
@login_required
def contacts_view(request):
    contacts = request.user.emergency_contacts.all().order_by('priority')
    
    if request.method == 'POST':
        form = EmergencyContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.user = request.user
            contact.save()
            
            # Create audit log
            AuditLog.objects.create(
                user=request.user,
                action='CONTACT_ADDED',
                description=f'Added emergency contact: {contact.name}',
                metadata={'contact_id': contact.id}
            )
            
            messages.success(request, f'Emergency contact {contact.name} added successfully.')
            return redirect('contacts')
    else:
        form = EmergencyContactForm()
    
    context = {
        'contacts': contacts,
        'form': form
    }
    return render(request, 'safety_app/contacts.html', context)


@login_required
def contact_edit_view(request, contact_id):
    contact = get_object_or_404(EmergencyContact, id=contact_id, user=request.user)
    
    if request.method == 'POST':
        form = EmergencyContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            
            # Create audit log
            AuditLog.objects.create(
                user=request.user,
                action='CONTACT_MODIFIED',
                description=f'Modified emergency contact: {contact.name}',
                metadata={'contact_id': contact.id}
            )
            
            messages.success(request, 'Contact updated successfully.')
            return redirect('contacts')
    else:
        form = EmergencyContactForm(instance=contact)
    
    return render(request, 'safety_app/contact_edit.html', {'form': form, 'contact': contact})


@login_required
def contact_delete_view(request, contact_id):
    contact = get_object_or_404(EmergencyContact, id=contact_id, user=request.user)
    
    if request.method == 'POST':
        contact_name = contact.name
        contact.delete()
        
        messages.success(request, f'Contact {contact_name} deleted successfully.')
        return redirect('contacts')
    
    return render(request, 'safety_app/contact_confirm_delete.html', {'contact': contact})


# Safe Zone Views
@login_required
def safe_zones_view(request):
    zones = request.user.safe_zones.all()
    
    if request.method == 'POST':
        form = SafeZoneForm(request.POST)
        if form.is_valid():
            zone = form.save(commit=False)
            zone.user = request.user
            zone.save()
            
            # Create audit log
            AuditLog.objects.create(
                user=request.user,
                action='SAFE_ZONE_CREATED',
                description=f'Created safe zone: {zone.name}',
                metadata={'zone_id': zone.id}
            )
            
            messages.success(request, f'Safe zone {zone.name} created successfully.')
            return redirect('safe_zones')
    else:
        form = SafeZoneForm()
    
    context = {
        'zones': zones,
        'form': form
    }
    return render(request, 'safety_app/safe_zones.html', context)


# Alert Views
@login_required
def alert_panel_view(request):
    """Main alert trigger panel"""
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'phone_number': ''}
    )
    
    active_alert = Alert.objects.filter(
        user=request.user,
        status__in=['TRIGGERED', 'PENDING_CANCEL', 'DISPATCHED']
    ).first()
    
    context = {
        'profile': profile,
        'active_alert': active_alert,
        'has_contacts': request.user.emergency_contacts.filter(is_active=True).exists()
    }
    
    return render(request, 'safety_app/alert_panel.html', context)


@login_required
@require_http_methods(["POST"])
def trigger_alert_view(request):
    """API endpoint to trigger an alert"""
    try:
        data = json.loads(request.body)
        
        # Check if user already has active alert
        active_alert = Alert.objects.filter(
            user=request.user,
            status__in=['TRIGGERED', 'PENDING_CANCEL', 'DISPATCHED']
        ).first()
        
        if active_alert:
            return JsonResponse({
                'success': False,
                'message': 'You already have an active alert',
                'alert_id': str(active_alert.alert_id)
            }, status=400)
        
        # Create alert using AlertService
        alert_service = AlertService()
        alert = alert_service.create_alert(
            user=request.user,
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            trigger_method=data.get('trigger_method', 'panic_button'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'alert_id': str(alert.alert_id),
            'status': alert.status,
            'message': 'Alert triggered successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def cancel_alert_view(request):
    """API endpoint to cancel an alert"""
    try:
        data = json.loads(request.body)
        alert_id = data.get('alert_id')
        reason = data.get('reason', 'User cancelled')
        
        alert = get_object_or_404(Alert, alert_id=alert_id, user=request.user)
        
        alert_service = AlertService()
        success = alert_service.cancel_alert(alert, reason)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Alert cancelled successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Failed to cancel alert'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def dispatch_alert_view(request):
    """API endpoint to dispatch alert to contacts"""
    try:
        data = json.loads(request.body)
        alert_id = data.get('alert_id')
        
        alert = get_object_or_404(Alert, alert_id=alert_id, user=request.user)
        
        if alert.status != 'TRIGGERED':
            return JsonResponse({
                'success': False,
                'message': 'Alert cannot be dispatched in current status'
            }, status=400)
        
        # Dispatch alert using DispatchService
        dispatch_service = DispatchService()
        result = dispatch_service.dispatch_alert(alert)
        
        return JsonResponse({
            'success': True,
            'contacts_notified': result['contacts_notified'],
            'dispatch_logs': result['dispatch_logs']
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
def alert_history_view(request):
    """View alert history"""
    alerts = Alert.objects.filter(user=request.user).order_by('-triggered_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        alerts = alerts.filter(status=status_filter)
    
    context = {
        'alerts': alerts,
        'status_filter': status_filter
    }
    
    return render(request, 'safety_app/alert_history.html', context)


@login_required
def alert_detail_view(request, alert_id):
    """Detailed view of a specific alert"""
    alert = get_object_or_404(Alert, alert_id=alert_id, user=request.user)
    location_tracks = alert.location_tracks.all()
    dispatch_logs = alert.dispatch_logs.all()
    audit_logs = alert.audit_logs.all()
    
    context = {
        'alert': alert,
        'location_tracks': location_tracks,
        'dispatch_logs': dispatch_logs,
        'audit_logs': audit_logs
    }
    
    return render(request, 'safety_app/alert_detail.html', context)


@login_required
def monitor_alert_view(request, alert_id):
    """Real-time monitoring view for active alerts"""
    alert = get_object_or_404(Alert, alert_id=alert_id, user=request.user)
    
    context = {
        'alert': alert
    }
    
    return render(request, 'safety_app/monitor_alert.html', context)


# Profile Views
@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'phone_number': ''}
    )
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)
    
    context = {
        'form': form,
        'profile': profile
    }
    
    return render(request, 'safety_app/profile.html', context)


# Utility Functions
def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip