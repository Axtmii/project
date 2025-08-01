from django.db import models





from django.db import models
from accounts.models import User
from prison_core.models import Prisoner

# Add this entire class to the file
class Visit(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    VISIT_TYPE_CHOICES = [
        ('REGULAR', 'Regular Visit'),
        ('EMERGENCY', 'Emergency Visit'),
    ]
    
    visit_type = models.CharField(
        max_length=10, 
        choices=VISIT_TYPE_CHOICES, 
        default='REGULAR'
    )
    visitor = models.ForeignKey(User, on_delete=models.CASCADE)
    prisoner = models.ForeignKey(Prisoner, on_delete=models.CASCADE)
    visit_date = models.DateField()
    visit_time_slot = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    qr_code = models.ImageField(upload_to='visit_qrcodes/', blank=True, null=True)
    check_in_time = models.DateTimeField(blank=True, null=True)
    check_out_time = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Visit by {self.visitor.username} for {self.prisoner.prisoner_id}"
# Create your models here.
from accounts.models import User

class EmergencyAlert(models.Model):
    message = models.TextField()
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Alert: {self.message[:50]}"