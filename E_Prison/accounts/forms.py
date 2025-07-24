from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class UserRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = [
            'username', 'full_name', 'email', 'address',
            'password1', 'password2', 'profile_photo', 'id_proof', 'is_family_member'
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        # Automatically assign role
        if self.cleaned_data.get("is_family_member"):
            user.role = "family"
        else:
            user.role = "visitor"
        if commit:
            user.save()
        return user
