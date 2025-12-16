# safety_app/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile, EmergencyContact, SafeZone


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        help_text='Enter phone number with country code',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+919876543210'})
    )
    safe_word = forms.CharField(
        max_length=50,
        required=False,
        help_text='Optional: A secret word to cancel alerts',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already registered.')
        return email


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'emergency_keyword', 'safe_word']
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_keyword': forms.TextInput(attrs={'class': 'form-control'}),
            'safe_word': forms.PasswordInput(attrs={'class': 'form-control'}, render_value=True),
        }
        help_texts = {
            'emergency_keyword': 'A keyword to trigger alert via text',
            'safe_word': 'Secret word to cancel alerts',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Update user fields
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            profile.save()
        
        return profile


class EmergencyContactForm(forms.ModelForm):
    class Meta:
        model = EmergencyContact
        fields = ['name', 'relationship', 'phone_number', 'email', 'priority', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contact Name'
            }),
            'relationship': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Mother, Friend, Spouse'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '10'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        help_texts = {
            'priority': '1 is highest priority (will be contacted first)',
            'is_active': 'Uncheck to temporarily disable notifications to this contact'
        }


class SafeZoneForm(forms.ModelForm):
    class Meta:
        model = SafeZone
        fields = ['name', 'latitude', 'longitude', 'radius_meters', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Home, Office, School'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': '0.000000'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': '0.000000'
            }),
            'radius_meters': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '50',
                'max': '5000',
                'placeholder': '500'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        help_texts = {
            'latitude': 'Decimal degrees (e.g., 40.7128)',
            'longitude': 'Decimal degrees (e.g., -74.0060)',
            'radius_meters': 'Safe zone radius in meters (50-5000)',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        lat = cleaned_data.get('latitude')
        lon = cleaned_data.get('longitude')
        
        if lat and (lat < -90 or lat > 90):
            raise forms.ValidationError('Latitude must be between -90 and 90')
        
        if lon and (lon < -180 or lon > 180):
            raise forms.ValidationError('Longitude must be between -180 and 180')
        
        return cleaned_data