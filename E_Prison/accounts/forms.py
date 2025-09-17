from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User
import re

class UserRegisterForm(UserCreationForm):
    """
    CORRECTED: Form that matches your exact User model structure
    """
    
    # These fields exist in your model, so we can use them directly
    phone_number = forms.CharField(
        max_length=15,
        required=False,  # Model allows blank=True
        help_text="Enter your 10-digit Indian mobile number"
    )
    
    aadhar_number = forms.CharField(
        max_length=14,  # FIXED: Allow for formatted input with spaces (12 digits + 2 spaces)
        required=True,  # Make required for new registrations
        help_text="Enter your 12-digit Aadhar card number (only accepted ID proof)",
        label="Aadhar Card Number"
    )
    
    profile_photo = forms.ImageField(
        required=False,  # Model allows blank=True
        help_text="Upload a clear, recent photo of your face",
        label="Profile Photo"
    )
    
    class Meta(UserCreationForm.Meta):
        model = User
        # ✅ All these fields exist in your User model
        fields = (
            'username', 
            'full_name', 
            'email',
            'phone_number',
            'address', 
            'profile_photo',
            'aadhar_number',
            'id_proof',
            'is_family_member'
        )
        
        labels = {
            'full_name': 'Full Name',
            'email': 'Email Address',
            'phone_number': 'Phone Number',
            'profile_photo': 'Profile Photo',
            'aadhar_number': 'Aadhar Card Number',
            'id_proof': 'Aadhar Card Image',
            'is_family_member': 'I am an immediate family member of an inmate'
        }

        help_texts = {
            'username': 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
            'profile_photo': 'Upload a clear, recent photo of your face for identification.',
            'id_proof': 'Upload clear photo of your Aadhar card (Required for security)',
            'aadhar_number': 'Only Aadhar card is accepted as valid ID proof',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            if field_name == 'is_family_member':
                field.widget.attrs.update({'class': 'form-check-input'})
            elif field_name == 'aadhar_number':
                field.widget.attrs.update({
                    'class': 'form-control',
                    'placeholder': 'Enter 12-digit Aadhar number',
                    'maxlength': '14',  # FIXED: Allow formatted input
                    'pattern': r'[0-9\s]{12,14}',  # FIXED: Simplified pattern
                    'title': 'Enter valid 12-digit Aadhar number'
                })
            elif field_name == 'phone_number':
                field.widget.attrs.update({
                    'class': 'form-control',
                    'placeholder': 'Enter 10-digit mobile number'
                })
            elif field_name in ['id_proof', 'profile_photo']:
                field.widget.attrs.update({
                    'class': 'form-control',
                    'accept': 'image/*'
                })
            else:
                field.widget.attrs.update({'class': 'form-control'})

    def clean_profile_photo(self):
        """Validate profile photo upload"""
        image = self.cleaned_data.get('profile_photo')
        
        if image:
            # Check file size (max 3MB for profile photos)
            if image.size > 3 * 1024 * 1024:  # 3MB
                raise ValidationError("Profile photo size should be less than 3MB.")
            
            # Check file format
            if not image.content_type.startswith('image/'):
                raise ValidationError("Only image files are allowed for profile photo.")
        
        return image

    def clean_aadhar_number(self):
        """FIXED: Validate Aadhar number with proper space handling"""
        aadhar_number = self.cleaned_data.get('aadhar_number')
        
        if not aadhar_number:
            raise ValidationError("Aadhar number is required.")
        
        # FIXED: Remove spaces for validation
        aadhar_clean = re.sub(r'\s', '', aadhar_number)
        
        # Validate format (exactly 12 digits)
        if not re.match(r'^\d{12}$', aadhar_clean):
            raise ValidationError("Aadhar number must be exactly 12 digits.")
        
        # Check if starts with 0 or 1 (invalid Aadhar numbers)
        if aadhar_clean[0] in ['0', '1']:
            raise ValidationError("Invalid Aadhar number. Aadhar numbers cannot start with 0 or 1.")
        
        # Check for duplicate Aadhar numbers
        existing_user = User.objects.filter(aadhar_number=aadhar_clean)
        if self.instance and self.instance.pk:
            existing_user = existing_user.exclude(pk=self.instance.pk)
        
        if existing_user.exists():
            raise ValidationError("This Aadhar number is already registered.")
        
        return aadhar_clean  # Return clean digits only for storage

    def clean_phone_number(self):
        """Validate Indian phone number format"""
        phone_number = self.cleaned_data.get('phone_number')
        
        if not phone_number:
            return phone_number  # Allow empty since model allows blank
        
        # Remove spaces and special characters
        phone_clean = re.sub(r'[\s\-\+\(\)]', '', phone_number)
        
        # Validate Indian phone number format
        if not re.match(r'^[6-9]\d{9}$', phone_clean):
            raise ValidationError("Enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.")
        
        return phone_clean

    def clean_id_proof(self):
        """Validate Aadhar card image upload"""
        image = self.cleaned_data.get('id_proof')
        
        if image:
            # Check file size (max 5MB for document images)
            if image.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError("Aadhar card image size should be less than 5MB.")
            
            # Check file format
            if not image.content_type.startswith('image/'):
                raise ValidationError("Only image files are allowed for Aadhar card.")
        
        return image

    def save(self, commit=True):
        """✅ CORRECTED: All these fields exist in your User model"""
        user = super().save(commit=False)
        
        # ✅ These fields all exist in your User model
        user.phone_number = self.cleaned_data.get('phone_number', '')
        user.aadhar_number = self.cleaned_data['aadhar_number']
        
        # Set role based on family member status
        if self.cleaned_data.get('is_family_member'):
            user.role = 'family'
            user.is_family_member = True
        else:
            user.role = 'visitor'
            user.is_family_member = False
        
        if commit:
            user.save()
        
        return user

class VisitorRegistrationForm(UserCreationForm):
    """
    ✅ CORRECTED: Enhanced visitor registration form matching your User model
    """
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your first name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your last name'
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )
    
    phone_number = forms.CharField(
        max_length=15,
        required=False,  # Model allows blank
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your phone number'
        })
    )
    
    address = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full address',
            'rows': 3
        })
    )
    
    profile_photo = forms.ImageField(
        required=False,  # Model allows blank
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text="Upload a clear, recent photo of your face",
        label="Profile Photo"
    )
    
    aadhar_number = forms.CharField(
        max_length=14,  # FIXED: Allow for formatted input with spaces
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 12-digit Aadhar number',
            'maxlength': '14',  # FIXED: HTML maxlength
            'pattern': r'[0-9\s]{12,14}',  # FIXED: Simplified pattern
            'title': 'Enter valid 12-digit Aadhar number'
        }),
        help_text="Enter your 12-digit Aadhar card number (only accepted ID proof)"
    )
    
    id_proof = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text="Upload clear photo of your Aadhar card",
        label="Aadhar Card Image"
    )
    
    VISITOR_ROLE_CHOICES = [
        ('visitor', 'General Visitor'),
        ('family', 'Family Member'),
    ]
    
    role = forms.ChoiceField(
        choices=VISITOR_ROLE_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    class Meta:
        model = User
        fields = (
            'username', 'first_name', 'last_name', 'email', 'phone_number', 
            'address', 'profile_photo', 'role', 'aadhar_number', 'id_proof',
            'password1', 'password2'
        )

    def clean_aadhar_number(self):
        """FIXED: Use proper Aadhar validation with space handling"""
        aadhar_number = self.cleaned_data.get('aadhar_number')
        
        if not aadhar_number:
            raise ValidationError("Aadhar number is required.")
        
        # FIXED: Remove spaces for validation
        aadhar_clean = re.sub(r'\s', '', aadhar_number)
        
        # Validate format (exactly 12 digits)
        if not re.match(r'^\d{12}$', aadhar_clean):
            raise ValidationError("Aadhar number must be exactly 12 digits.")
        
        # Check if starts with 0 or 1 (invalid Aadhar numbers)
        if aadhar_clean[0] in ['0', '1']:
            raise ValidationError("Invalid Aadhar number. Aadhar numbers cannot start with 0 or 1.")
        
        # Check for duplicates
        existing_user = User.objects.filter(aadhar_number=aadhar_clean)
        if self.instance and self.instance.pk:
            existing_user = existing_user.exclude(pk=self.instance.pk)
        
        if existing_user.exists():
            raise ValidationError("This Aadhar number is already registered.")
        
        return aadhar_clean  # Return clean digits only for storage

    def clean_phone_number(self):
        """Validate phone number"""
        phone_number = self.cleaned_data.get('phone_number')
        
        if not phone_number:
            return phone_number
        
        phone_clean = re.sub(r'[\s\-\+\(\)]', '', phone_number)
        
        if not re.match(r'^[6-9]\d{9}$', phone_clean):
            raise ValidationError("Enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.")
        
        return phone_clean

    def clean_id_proof(self):
        """Validate Aadhar card image"""
        image = self.cleaned_data.get('id_proof')
        
        if not image:
            raise ValidationError("Aadhar card image is required for registration.")
        
        if image.size > 5 * 1024 * 1024:
            raise ValidationError("Aadhar card image size should be less than 5MB.")
        
        if not image.content_type.startswith('image/'):
            raise ValidationError("Only image files are allowed for Aadhar card.")
        
        return image

    def clean_profile_photo(self):
        """Validate profile photo"""
        image = self.cleaned_data.get('profile_photo')
        
        if image:
            if image.size > 3 * 1024 * 1024:  # 3MB
                raise ValidationError("Profile photo size should be less than 3MB.")
            
            if not image.content_type.startswith('image/'):
                raise ValidationError("Only image files are allowed for profile photo.")
        
        return image

    def save(self, commit=True):
        """✅ CORRECTED: Save with your exact User model fields"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.full_name = f"{self.cleaned_data['first_name']} {self.cleaned_data['last_name']}"
        user.phone_number = self.cleaned_data.get('phone_number', '')
        user.address = self.cleaned_data['address']
        user.aadhar_number = self.cleaned_data['aadhar_number']
        user.role = self.cleaned_data['role']
        
        if self.cleaned_data['role'] == 'family':
            user.is_family_member = True
        
        if commit:
            user.save()
        
        return user

class StaffCreationForm(forms.ModelForm):
    """
    ✅ This form looks correct for your User model
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), 
        help_text="Set a temporary password for the new staff member.",
        min_length=8
    )

    class Meta:
        model = User
        fields = ['username', 'full_name', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
        
        self.fields['username'].widget.attrs.update({'placeholder': 'Enter username'})
        self.fields['full_name'].widget.attrs.update({'placeholder': 'Enter full name'})
        self.fields['password'].widget.attrs.update({'placeholder': 'Enter temporary password'})

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.role = 'security'
        user.is_staff = True
        
        if commit:
            user.save()
        return user
