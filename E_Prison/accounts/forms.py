
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class UserRegisterForm(UserCreationForm):
    """
    A form for creating new users. It inherits from Django's UserCreationForm
    to get password validation and hashing automatically.
    """
    class Meta(UserCreationForm.Meta):
        model = User
        # Define the fields to be displayed on the registration form, in order.
        fields = (
            'username', 
            'full_name', 
            'email', 
            'address', 
            'profile_photo', 
            'id_proof', 
            'is_family_member'
        )
        
        # Add user-friendly labels that will appear on the form
        labels = {
            'full_name': 'Full Name',
            'email': 'Email Address',
            'id_proof': 'ID Proof (Aadhar, Driving License, etc.)',
            'is_family_member': 'I am an immediate family member of the inmate'
        }

        # Add help text to guide the user
        help_texts = {
            'username': 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
            'profile_photo': 'Optional. A clear, recent photo of your face.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This loop adds the correct Bootstrap CSS classes to each form field's widget.
        for field_name, field in self.fields.items():
            if field_name == 'is_family_member':
                # Special styling for the checkbox
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                # General styling for all other input fields
                field.widget.attrs.update({'class': 'form-control'})
