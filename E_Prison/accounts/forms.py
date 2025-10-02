from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from .models import User
from prison_core.models import Prisoner  # Import Prisoner model
import re

class PrisonerChoiceField(forms.ModelChoiceField):
    """Custom ModelChoiceField for prisoner selection with ID + Name display"""
    
    def label_from_instance(self, obj):
        """Custom display format showing Prisoner ID + Name + Prison"""
        return f"#{obj.prisoner_id} - {obj.first_name} {obj.last_name} | {obj.jail.name if obj.jail else 'No Jail Assigned'}"

class FamilyMemberChoiceField(forms.ModelChoiceField):
    """Custom ModelChoiceField for family member selection with ID + Name display"""
    
    def label_from_instance(self, obj):
        """Custom display format showing ID + Name + Additional info"""
        return obj.get_family_display_name()

class UserRegisterForm(UserCreationForm):
    """Enhanced registration form with family and prisoner relationship support"""
    
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        help_text="Enter your 10-digit Indian mobile number",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 10-digit mobile number'
        })
    )
    
    aadhar_number = forms.CharField(
        max_length=14,
        required=True,
        help_text="Enter your 12-digit Aadhar card number (only accepted ID proof)",
        label="Aadhar Card Number",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 12-digit Aadhar number',
            'maxlength': '14',
            'pattern': r'[0-9\s]{12,14}',
            'title': 'Enter valid 12-digit Aadhar number'
        })
    )
    
    profile_photo = forms.ImageField(
        required=False,
        help_text="Upload a clear, recent photo of your face",
        label="Profile Photo",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    
    # Prisoner relationship fields
    related_prisoner = PrisonerChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="-- Select prisoner you are related to (Optional) --",
        help_text="Select if you are a family member visiting a specific prisoner",
        widget=forms.Select(attrs={'class': 'form-select select2-prisoner-search'})
    )
    
    relationship_to_prisoner = forms.ChoiceField(
        choices=[('', '-- Select Relationship --')] + User.RELATIONSHIP_CHOICES,
        required=False,
        help_text="Your relationship to the selected prisoner",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Family relationship fields
    primary_family_member = FamilyMemberChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="-- Select Primary Family Member (Optional) --",
        help_text="Select if you want to connect to an existing family member",
        widget=forms.Select(attrs={'class': 'form-select select2-family-search'})
    )
    
    relationship_to_primary = forms.ChoiceField(
        choices=[('', '-- Select Relationship --')] + User.RELATIONSHIP_CHOICES,
        required=False,
        help_text="Your relationship to the selected family member",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    can_authorize_emergency = forms.BooleanField(
        required=False,
        label="I can authorize emergency visits for family members",
        help_text="Check this if you want to be able to authorize emergency visits",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'username', 'full_name', 'email', 'phone_number', 'address', 
            'profile_photo', 'aadhar_number', 'id_proof', 'is_family_member',
            'related_prisoner', 'relationship_to_prisoner',
            'primary_family_member', 'relationship_to_primary', 'can_authorize_emergency'
        )
        
        labels = {
            'full_name': 'Full Name',
            'email': 'Email Address',
            'phone_number': 'Phone Number',
            'profile_photo': 'Profile Photo',
            'aadhar_number': 'Aadhar Card Number',
            'id_proof': 'Aadhar Card Image',
            'is_family_member': 'I am an immediate family member of an inmate',
            'related_prisoner': 'Related Prisoner',
            'relationship_to_prisoner': 'Relationship to Prisoner'
        }

        help_texts = {
            'username': 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
            'profile_photo': 'Upload a clear, recent photo of your face for identification.',
            'id_proof': 'Upload clear photo of your Aadhar card (Required for security)',
            'aadhar_number': 'Only Aadhar card is accepted as valid ID proof',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set queryset for prisoners (all prisoners - removed status filter)
        self.fields['related_prisoner'].queryset = Prisoner.objects.all().select_related('jail').order_by('prisoner_id')
        
        # Set queryset for primary family member (only users who can authorize)
        self.fields['primary_family_member'].queryset = User.objects.filter(
            role='family',
            can_authorize_emergency_visits=True
        ).order_by('id')
        
        for field_name, field in self.fields.items():
            if field_name == 'is_family_member':
                field.widget.attrs.update({'class': 'form-check-input'})
            elif field_name == 'can_authorize_emergency':
                field.widget.attrs.update({'class': 'form-check-input'})
            elif field_name in ['primary_family_member', 'relationship_to_primary', 'related_prisoner', 'relationship_to_prisoner']:
                # Already set in field definition
                pass
            elif field_name == 'aadhar_number':
                # Already set in field definition
                pass
            elif field_name == 'phone_number':
                # Already set in field definition
                pass
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
            if image.size > 3 * 1024 * 1024:  # 3MB
                raise ValidationError("Profile photo size should be less than 3MB.")
            
            if not image.content_type.startswith('image/'):
                raise ValidationError("Only image files are allowed for profile photo.")
        
        return image

    def clean_aadhar_number(self):
        """Validate Aadhar number with proper space handling"""
        aadhar_number = self.cleaned_data.get('aadhar_number')
        
        if not aadhar_number:
            raise ValidationError("Aadhar number is required.")
        
        # Remove spaces for validation
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
        
        return aadhar_clean

    def clean_phone_number(self):
        """Validate Indian phone number format"""
        phone_number = self.cleaned_data.get('phone_number')
        
        if not phone_number:
            return phone_number
        
        phone_clean = re.sub(r'[\s\-\+\(\)]', '', phone_number)
        
        if not re.match(r'^[6-9]\d{9}$', phone_clean):
            raise ValidationError("Enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.")
        
        return phone_clean

    def clean_id_proof(self):
        """Validate Aadhar card image upload"""
        image = self.cleaned_data.get('id_proof')
        
        if image:
            if image.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError("Aadhar card image size should be less than 5MB.")
            
            if not image.content_type.startswith('image/'):
                raise ValidationError("Only image files are allowed for Aadhar card.")
        
        return image

    def clean(self):
        """Cross-field validation for family and prisoner relationships"""
        cleaned_data = super().clean()
        primary_family_member = cleaned_data.get('primary_family_member')
        relationship_to_primary = cleaned_data.get('relationship_to_primary')
        related_prisoner = cleaned_data.get('related_prisoner')
        relationship_to_prisoner = cleaned_data.get('relationship_to_prisoner')
        is_family_member = cleaned_data.get('is_family_member')
        can_authorize = cleaned_data.get('can_authorize_emergency')
        
        # If primary family member is selected, relationship is required
        if primary_family_member and not relationship_to_primary:
            raise ValidationError({
                'relationship_to_primary': 'Please specify your relationship to the selected family member.'
            })
        
        # If prisoner is selected, relationship is required
        if related_prisoner and not relationship_to_prisoner:
            raise ValidationError({
                'relationship_to_prisoner': 'Please specify your relationship to the selected prisoner.'
            })
        
        # If related to prisoner or connecting to family, set as family member
        if related_prisoner or primary_family_member or can_authorize:
            cleaned_data['is_family_member'] = True
        
        return cleaned_data

    def save(self, commit=True):
        """Save with enhanced family and prisoner relationship logic"""
        user = super().save(commit=False)
        
        # Set basic fields
        user.phone_number = self.cleaned_data.get('phone_number', '')
        user.aadhar_number = self.cleaned_data['aadhar_number']
        
        # Set prisoner relationship fields
        user.related_prisoner = self.cleaned_data.get('related_prisoner')
        user.relationship_to_prisoner = self.cleaned_data.get('relationship_to_prisoner')
        
        # Set family relationship fields
        user.primary_family_member = self.cleaned_data.get('primary_family_member')
        user.relationship_to_primary = self.cleaned_data.get('relationship_to_primary')
        user.can_authorize_emergency_visits = self.cleaned_data.get('can_authorize_emergency', False)
        
        # Set role based on family member status
        if (self.cleaned_data.get('is_family_member') or user.primary_family_member or 
            user.can_authorize_emergency_visits or user.related_prisoner):
            user.role = 'family'
            user.is_family_member = True
        else:
            user.role = 'visitor'
            user.is_family_member = False
        
        if commit:
            user.save()
        
        return user

class VisitorRegistrationForm(UserCreationForm):
    """Enhanced visitor registration form with prisoner and family relationship support"""
    
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
        required=False,
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
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text="Upload a clear, recent photo of your face",
        label="Profile Photo"
    )
    
    aadhar_number = forms.CharField(
        max_length=14,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 12-digit Aadhar number',
            'maxlength': '14',
            'pattern': r'[0-9\s]{12,14}',
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
    
    # Prisoner relationship fields
    related_prisoner = PrisonerChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="-- Select prisoner you are related to (Optional) --",
        help_text="Select if you are a family member visiting a specific prisoner",
        widget=forms.Select(attrs={'class': 'form-select select2-prisoner-search'})
    )
    
    relationship_to_prisoner = forms.ChoiceField(
        choices=[('', '-- Select Relationship --')] + User.RELATIONSHIP_CHOICES,
        required=False,
        help_text="Your relationship to the selected prisoner",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Family relationship fields
    primary_family_member = FamilyMemberChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="-- Select Primary Family Member (Optional) --",
        help_text="Select if you want to connect to an existing family member",
        widget=forms.Select(attrs={'class': 'form-select select2-family-search'})
    )
    
    relationship_to_primary = forms.ChoiceField(
        choices=[('', '-- Select Relationship --')] + User.RELATIONSHIP_CHOICES,
        required=False,
        help_text="Your relationship to the selected family member",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    can_authorize_emergency = forms.BooleanField(
        required=False,
        label="I can authorize emergency visits for family members",
        help_text="Check this if you want to be able to authorize emergency visits",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = (
            'username', 'first_name', 'last_name', 'email', 'phone_number', 
            'address', 'profile_photo', 'role', 'aadhar_number', 'id_proof',
            'related_prisoner', 'relationship_to_prisoner',
            'primary_family_member', 'relationship_to_primary', 'can_authorize_emergency',
            'password1', 'password2'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set queryset for prisoners (all prisoners)
        self.fields['related_prisoner'].queryset = Prisoner.objects.all().select_related('jail').order_by('prisoner_id')
        
        # Set queryset for primary family member
        self.fields['primary_family_member'].queryset = User.objects.filter(
            role='family',
            can_authorize_emergency_visits=True
        ).order_by('id')

    def clean_aadhar_number(self):
        """Validate Aadhar number with space handling"""
        aadhar_number = self.cleaned_data.get('aadhar_number')
        
        if not aadhar_number:
            raise ValidationError("Aadhar number is required.")
        
        aadhar_clean = re.sub(r'\s', '', aadhar_number)
        
        if not re.match(r'^\d{12}$', aadhar_clean):
            raise ValidationError("Aadhar number must be exactly 12 digits.")
        
        if aadhar_clean[0] in ['0', '1']:
            raise ValidationError("Invalid Aadhar number. Aadhar numbers cannot start with 0 or 1.")
        
        existing_user = User.objects.filter(aadhar_number=aadhar_clean)
        if self.instance and self.instance.pk:
            existing_user = existing_user.exclude(pk=self.instance.pk)
        
        if existing_user.exists():
            raise ValidationError("This Aadhar number is already registered.")
        
        return aadhar_clean

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

    def clean(self):
        """Cross-field validation for prisoner and family relationships"""
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        primary_family_member = cleaned_data.get('primary_family_member')
        relationship_to_primary = cleaned_data.get('relationship_to_primary')
        related_prisoner = cleaned_data.get('related_prisoner')
        relationship_to_prisoner = cleaned_data.get('relationship_to_prisoner')
        can_authorize = cleaned_data.get('can_authorize_emergency')
        
        # Family member specific validations
        if role == 'family':
            # If primary family member is selected, relationship is required
            if primary_family_member and not relationship_to_primary:
                raise ValidationError({
                    'relationship_to_primary': 'Please specify your relationship to the selected family member.'
                })
        
        # If prisoner is selected, relationship is required
        if related_prisoner and not relationship_to_prisoner:
            raise ValidationError({
                'relationship_to_prisoner': 'Please specify your relationship to the selected prisoner.'
            })
        
        # If relationship to prisoner is specified, role should be family
        if relationship_to_prisoner and role != 'family':
            cleaned_data['role'] = 'family'  # Auto-set to family
        
        return cleaned_data

    def save(self, commit=True):
        """Save with prisoner and family relationship logic"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.full_name = f"{self.cleaned_data['first_name']} {self.cleaned_data['last_name']}"
        user.phone_number = self.cleaned_data.get('phone_number', '')
        user.address = self.cleaned_data['address']
        user.aadhar_number = self.cleaned_data['aadhar_number']
        user.role = self.cleaned_data['role']
        
        # Set prisoner relationship fields
        user.related_prisoner = self.cleaned_data.get('related_prisoner')
        user.relationship_to_prisoner = self.cleaned_data.get('relationship_to_prisoner')
        
        # Set family relationship fields
        user.primary_family_member = self.cleaned_data.get('primary_family_member')
        user.relationship_to_primary = self.cleaned_data.get('relationship_to_primary')
        user.can_authorize_emergency_visits = self.cleaned_data.get('can_authorize_emergency', False)
        
        # Set family member flag
        if (self.cleaned_data['role'] == 'family' or user.related_prisoner or 
            user.primary_family_member or user.can_authorize_emergency_visits):
            user.is_family_member = True
        
        if commit:
            user.save()
        
        return user

class UserProfileForm(forms.ModelForm):
    """Form for editing user profile information with searchable prisoner and family selection"""
    
    # Enhanced searchable prisoner selection field
    related_prisoner = PrisonerChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="-- Search and select a prisoner --",
        help_text="Type to search by prisoner ID or name",
        widget=forms.Select(attrs={
            'class': 'form-select select2-prisoner-search',
            'data-placeholder': 'Search by prisoner ID or name...',
            'data-allow-clear': 'true'
        })
    )
    
    # Enhanced searchable primary family member field
    primary_family_member = FamilyMemberChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="-- Search and select a family member --",
        help_text="Type to search by ID or name (e.g., '#123' or 'John')",
        widget=forms.Select(attrs={
            'class': 'form-select select2-family-search',
            'data-placeholder': 'Search by ID (#123) or name...',
            'data-allow-clear': 'true'
        })
    )
    
    class Meta:
        model = User
        fields = [
            'full_name', 'email', 'phone_number', 'address', 
            'profile_photo', 'aadhar_number', 'id_proof',
            'related_prisoner', 'relationship_to_prisoner',
            'primary_family_member', 'relationship_to_primary'
        ]
        
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your full name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your email address'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '10-digit mobile number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter your complete address'
            }),
            'profile_photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'aadhar_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'XXXX XXXX XXXX',
                'maxlength': '12'
            }),
            'id_proof': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'relationship_to_prisoner': forms.Select(attrs={
                'class': 'form-select'
            }),
            'relationship_to_primary': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        
        # Set queryset for prisoners (all prisoners - no status filter)
        self.fields['related_prisoner'].queryset = Prisoner.objects.all().select_related('jail').order_by('prisoner_id')
        
        # Set queryset for family members who can authorize emergency visits
        self.fields['primary_family_member'].queryset = User.objects.filter(
            role='family',
            can_authorize_emergency_visits=True
        ).exclude(id=user.id if user else None).order_by('id')
        
        # Enhanced help text
        self.fields['related_prisoner'].help_text = "Search by typing prisoner ID or name to find the inmate you are related to"
        self.fields['primary_family_member'].help_text = "Search by typing ID number (e.g., '123') or name (e.g., 'John') to find family members"
        self.fields['aadhar_number'].help_text = "12-digit Aadhar number (required for family members)"
    
    def clean_aadhar_number(self):
        aadhar = self.cleaned_data.get('aadhar_number')
        if aadhar:
            # Remove spaces and validate
            aadhar_clean = re.sub(r'[\s-]', '', str(aadhar))
            if not User.is_valid_aadhar(aadhar_clean):
                raise forms.ValidationError("Invalid Aadhar number format.")
            
            # Check for duplicates (exclude current user)
            existing = User.objects.filter(aadhar_number=aadhar_clean)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError("This Aadhar number is already registered.")
            
            return aadhar_clean
        return aadhar
    
    def clean(self):
        cleaned_data = super().clean()
        primary_family_member = cleaned_data.get('primary_family_member')
        relationship_to_primary = cleaned_data.get('relationship_to_primary')
        related_prisoner = cleaned_data.get('related_prisoner')
        relationship_to_prisoner = cleaned_data.get('relationship_to_prisoner')
        
        # If primary family member is selected, relationship is required
        if primary_family_member and not relationship_to_primary:
            raise forms.ValidationError({
                'relationship_to_primary': 'Please specify your relationship to the selected family member.'
            })
        
        # If prisoner is selected, relationship is required
        if related_prisoner and not relationship_to_prisoner:
            raise forms.ValidationError({
                'relationship_to_prisoner': 'Please specify your relationship to the selected prisoner.'
            })
        
        return cleaned_data

class FamilyAuthorizationForm(forms.ModelForm):
    """Form for setting family authorization settings"""
    
    class Meta:
        model = User
        fields = ['can_authorize_emergency_visits']
        
        widgets = {
            'can_authorize_emergency_visits': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['can_authorize_emergency_visits'].help_text = (
            "Check this if you want to authorize emergency visits for your family members"
        )

class StaffCreationForm(forms.ModelForm):
    """Form for creating staff members"""
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
