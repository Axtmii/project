
from django.contrib.auth.models import AbstractUser
from django.db import models
from prison_core.models import Jail
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


    full_name = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    id_proof = models.ImageField(upload_to="id_proofs/", blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


class Blacklist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    reason = models.TextField()
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='blacklisted_by')

    def __str__(self):
        return f"{self.user.username} - Blacklisted"