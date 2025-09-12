from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from prison_core.models import Jail
import re

class User(AbstractUser):
    ROLE_CHOICES = [
        ("family", "Family Visitor"),
        ("visitor", "Other Visitor"),
        ("security", "Gate Security"),
        ("admin", "Prison Admin"),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="visitor")
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    is_family_member = models.BooleanField(default=False)
    jail = models.ForeignKey(Jail, on_delete=models.SET_NULL, null=True, blank=True)

    # Your existing fields
    full_name = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # UPDATED: Replace id_proof with Aadhar-specific fields
    id_proof = models.ImageField(upload_to="id_proofs/", blank=True, null=True)  # Keep for backward compatibility
    
    # NEW: Aadhar-only ID proof system
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

    def clean(self):
        super().clean()
        
        # Validate Aadhar number for visitors and family members
        if self.role in ['visitor', 'family'] and self.aadhar_number:
            if not self.is_valid_aadhar(self.aadhar_number):
                raise ValidationError({
                    'aadhar_number': 'Invalid Aadhar number. Must be 12 digits and cannot start with 0 or 1.'
                })

    @staticmethod
    def is_valid_aadhar(aadhar_number):
        """Validate Aadhar number format"""
        if not aadhar_number:
            return False
        
        # Remove spaces and hyphens
        aadhar_clean = re.sub(r'[\s-]', '', str(aadhar_number))
        
        # Check if it's exactly 12 digits
        if not re.match(r'^\d{12}$', aadhar_clean):
            return False
        
        # Aadhar numbers don't start with 0 or 1
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

    def __str__(self):
        return f"{self.username} ({self.role})"

class Blacklist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='blacklist')
    reason = models.TextField()
    
    # --- Your existing field ---
    blacklisted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_blacklists')
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Blacklisted"
