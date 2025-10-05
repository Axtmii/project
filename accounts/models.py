from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from prison_core.models import Jail
from prison_core.models import Prisoner
import re

class User(AbstractUser):
    ROLE_CHOICES = [
        ("family", "Family Visitor"),
        ("visitor", "Other Visitor"),
        ("security", "Gate Security"),
        ("admin", "Prison Admin"),
    ]
    
    RELATIONSHIP_CHOICES = [
        ("father", "Father"),
        ("mother", "Mother"),
        ("spouse", "Spouse/Husband/Wife"),
        ("son", "Son"),
        ("daughter", "Daughter"),
        ("brother", "Brother"),
        ("sister", "Sister"),
        ("grandfather", "Grandfather"),
        ("grandmother", "Grandmother"),
        ("uncle", "Uncle"),
        ("aunt", "Aunt"),
        ("cousin", "Cousin"),
        ("nephew", "Nephew"),
        ("niece", "Niece"),
        ("son_in_law", "Son-in-law"),
        ("daughter_in_law", "Daughter-in-law"),
        ("father_in_law", "Father-in-law"),
        ("mother_in_law", "Mother-in-law"),
        ("other", "Other Relative"),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="visitor")
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    is_family_member = models.BooleanField(default=False)
    jail = models.ForeignKey(Jail, on_delete=models.SET_NULL, null=True, blank=True)

    # Personal Information
    full_name = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Identity Information
    id_proof = models.ImageField(upload_to="id_proofs/", blank=True, null=True)
    aadhar_number = models.CharField(
        max_length=12,
        unique=True,
        blank=True,
        null=True,
        help_text="12-digit Aadhar number (only accepted ID proof)",
        verbose_name="Aadhar Card Number"
    )
    
    phone_number = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        help_text="10-digit Indian mobile number"
    )
    
    # NEW: Prisoner Relationship Fields
    related_prisoner = models.ForeignKey(
        Prisoner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='family_members',
        help_text="Select the prisoner you are related to",
        verbose_name="Related Prisoner"
    )
    
    relationship_to_prisoner = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        blank=True,
        null=True,
        help_text="Your relationship to the prisoner",
        verbose_name="Relationship to Prisoner"
    )
    
    # Family Connection Fields (for connecting with other family members)
    primary_family_member = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='family_members',
        help_text="Primary family member who can authorize emergency visits"
    )
    
    relationship_to_primary = models.CharField(
        max_length=20, 
        choices=RELATIONSHIP_CHOICES,
        blank=True,
        null=True,
        help_text="Your relationship to the primary family member"
    )
    
    # Emergency visit authorization
    can_authorize_emergency_visits = models.BooleanField(
        default=False,
        help_text="Can this user authorize emergency visits for family members"
    )

    def clean(self):
        super().clean()
        
        # Validate Aadhar number for visitors and family members
        if self.role in ['visitor', 'family'] and self.aadhar_number:
            if not self.is_valid_aadhar(self.aadhar_number):
                raise ValidationError({
                    'aadhar_number': 'Invalid Aadhar number. Must be 12 digits and cannot start with 0 or 1.'
                })
        
        # Family member validation
        if self.primary_family_member and not self.relationship_to_primary:
            raise ValidationError({
                'relationship_to_primary': 'Please specify your relationship to the primary family member.'
            })
        
        # Prisoner relationship validation
        if self.role == 'family' and self.related_prisoner and not self.relationship_to_prisoner:
            raise ValidationError({
                'relationship_to_prisoner': 'Please specify your relationship to the prisoner.'
            })

    @staticmethod
    def is_valid_aadhar(aadhar_number):
        """Validate Aadhar number format"""
        if not aadhar_number:
            return False
        
        aadhar_clean = re.sub(r'[\s-]', '', str(aadhar_number))
        
        if not re.match(r'^\d{12}$', aadhar_clean):
            return False
        
        if aadhar_clean[0] in ['0', '1']:
            return False
        
        return True

    def get_formatted_aadhar(self):
        """Return formatted Aadhar number (XXXX XXXX XXXX)"""
        if self.aadhar_number:
            clean_aadhar = re.sub(r'[\s-]', '', str(self.aadhar_number))
            if len(clean_aadhar) == 12:
                return f"{clean_aadhar[:4]} {clean_aadhar[4:8]} {clean_aadhar[8:]}"
        return self.aadhar_number

    def get_masked_aadhar(self):
        """Return masked Aadhar number for security (XXXX XXXX 1234)"""
        if self.aadhar_number:
            clean_aadhar = re.sub(r'[\s-]', '', str(self.aadhar_number))
            if len(clean_aadhar) == 12:
                return f"XXXX XXXX {clean_aadhar[8:]}"
        return "XXXX XXXX XXXX"

    @property
    def has_valid_aadhar(self):
        """Check if user has valid Aadhar identification"""
        return bool(self.aadhar_number and len(re.sub(r'[\s-]', '', str(self.aadhar_number))) == 12)
    
    def can_request_emergency_visit(self, prisoner=None):
        """Check if user can request emergency visit"""
        if self.role != 'family':
            return False
        
        # Check if this user has authorization or is authorized by primary family member
        if self.can_authorize_emergency_visits:
            return True
        
        if self.primary_family_member and self.primary_family_member.can_authorize_emergency_visits:
            return True
        
        return False

    def get_family_members(self):
        """Get all family members connected to this user"""
        family_members = []
        
        # If this is a primary family member, get all connected members
        if self.can_authorize_emergency_visits:
            family_members.extend(self.family_members.all())
        
        # If this user has a primary family member, get all siblings
        if self.primary_family_member:
            family_members.append(self.primary_family_member)
            family_members.extend(
                self.primary_family_member.family_members.exclude(id=self.id)
            )
        
        return family_members

    def __str__(self):
        """Display format: ID + Name for better search and identification"""
        if self.full_name:
            return f"#{self.id} - {self.full_name}"
        else:
            return f"#{self.id} - {self.username}"
    
    def get_display_name_with_id(self):
        """Get display name with ID for forms"""
        if self.full_name:
            return f"#{self.id} - {self.full_name} ({self.username})"
        else:
            return f"#{self.id} - {self.username}"
    
    def get_family_display_name(self):
        """Enhanced display for family member selection with searchable info"""
        if self.full_name:
            display = f"#{self.id} - {self.full_name}"
        else:
            display = f"#{self.id} - {self.username}"
        
        # Add role info
        display += f" ({self.get_role_display()})"
        
        # Add additional info for family members
        if self.can_authorize_emergency_visits:
            display += " [Emergency Authorizer]"
        
        # Add phone number for better identification
        if self.phone_number:
            display += f" • {self.phone_number}"
            
        return display

# Keep existing Blacklist model unchanged
class Blacklist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='blacklist')
    reason = models.TextField()
    blacklisted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_blacklists')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Blacklisted"
