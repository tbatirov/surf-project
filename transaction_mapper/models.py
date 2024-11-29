from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import uuid
from django.db.models import functions
from django.utils import timezone

class Role(models.Model):
    """Role model for user permissions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('role')
        verbose_name_plural = _('roles')
        ordering = ['name']

class User(AbstractUser):
    """Custom user model with role-based permissions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Override groups to add related_name
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='transaction_mapper_users',
        related_query_name='transaction_mapper_user',
    )

    # Override user_permissions to add related_name
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='transaction_mapper_users',
        related_query_name='transaction_mapper_user',
    )

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.role:
            self.update_user_permissions()

    def update_user_permissions(self):
        """Update user permissions based on their role"""
        if self.role:
            # Clear existing user permissions
            self.user_permissions.clear()
            
            # Add role-specific permissions
            role_permissions = self.role.permissions
            for perm_codename in role_permissions:
                try:
                    perm = Permission.objects.get(codename=perm_codename)
                    self.user_permissions.add(perm)
                except Permission.DoesNotExist:
                    pass

    def has_module_perms(self, app_label):
        """Check if user has any permissions for the app"""
        return self.is_active and (self.is_superuser or bool(self.user_permissions.filter(content_type__app_label=app_label).exists()))

    def has_perm(self, perm, obj=None):
        """Check if user has a specific permission"""
        if self.is_active and self.is_superuser:
            return True
        return self.user_permissions.filter(codename=perm.split('.')[-1]).exists()

class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    department = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    notification_preferences = models.JSONField(default=dict)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class UserActivity(models.Model):
    """Track user activities for audit purposes"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    activity_type = models.CharField(max_length=50)
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'User Activities'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.username} - {self.activity_type} - {self.created_at}"

class Account(models.Model):
    account_id = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20)
    parent_account = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_accounts')

    def __str__(self):
        return f"{self.account_id} - {self.name}"

class Transaction(models.Model):
    """Transaction model for financial records"""
    TRANSACTION_TYPES = [
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Mapping'),
        ('MAPPED', 'Mapped'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]

    transaction_id = models.CharField(max_length=50, primary_key=True)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    description = models.TextField()
    account = models.ForeignKey(
        Account, 
        on_delete=models.CASCADE, 
        related_name='transactions',
        null=True,  
        blank=True
    )
    customer_name = models.CharField(max_length=100, null=True, blank=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Upload tracking
    uploaded_by = models.ForeignKey(
        User,  
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_transactions'
    )
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    # Mapping fields
    mapped_account = models.ForeignKey(
        Account, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='mapped_transactions'
    )
    mapped_by = models.ForeignKey(
        User,  
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mapped_transactions'
    )
    mapped_at = models.DateTimeField(null=True, blank=True)
    mapping_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    confidence_score = models.FloatField(default=0.0)
    is_recurring = models.BooleanField(default=False)
    tags = models.JSONField(default=list, null=True, blank=True)
        
    class Meta:
        ordering = ['-date', '-time']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['customer_name']),
            models.Index(fields=['transaction_type']),
        ]

    def clean(self):
        super().clean()
        if self.tags is None:
            self.tags = []
            
        if not isinstance(self.tags, list):
            raise ValidationError({'tags': 'Tags must be a list'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def map_to_account(self, account, user, notes='', confidence=1.0):
        """Map this transaction to a specific account"""
        from django.utils import timezone
        self.mapped_account = account
        self.mapped_by = user
        self.mapped_at = timezone.now()
        self.mapping_notes = notes
        self.confidence_score = confidence
        self.status = 'MAPPED'
        self.save()

    def verify_mapping(self, user):
        """Verify the current mapping"""
        self.status = 'VERIFIED'
        self.save()

    def reject_mapping(self, user, reason=''):
        """Reject the current mapping"""
        self.status = 'REJECTED'
        self.mapping_notes = f"Rejected: {reason}"
        self.save()

    def __str__(self):
        return f"{self.date} - {self.description} ({self.amount})"
