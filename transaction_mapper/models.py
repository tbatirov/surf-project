from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid

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
            self.user_permissions.clear()
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

class Account(models.Model):
    """Chart of accounts model"""
    account_id = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20)
    parent_account = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_accounts')

    def __str__(self):
        return f"{self.account_id} - {self.name}"

    class Meta:
        ordering = ['account_id']
        verbose_name = _('account')
        verbose_name_plural = _('accounts')

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
    customer_name = models.CharField(max_length=100, null=True, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Double-entry accounting fields
    debit_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='debit_transactions',
        help_text='Account to be debited'
    )
    credit_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='credit_transactions',
        help_text='Account to be credited'
    )
    
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
            models.Index(fields=['debit_account']),
            models.Index(fields=['credit_account']),
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

    def map_accounts(self, debit_account, credit_account, user, notes='', confidence=1.0):
        """Map transaction to debit and credit accounts"""
        self.debit_account = debit_account
        self.credit_account = credit_account
        self.mapped_by = user
        self.mapped_at = timezone.now()
        self.mapping_notes = notes
        self.confidence_score = confidence
        self.status = 'MAPPED'
        self.save()

    def verify_mapping(self, user):
        """Verify the current mapping"""
        if not self.debit_account or not self.credit_account:
            raise ValidationError('Cannot verify transaction without both debit and credit accounts')
        self.status = 'VERIFIED'
        self.save()

    def reject_mapping(self, user, reason=''):
        """Reject the current mapping"""
        self.status = 'REJECTED'
        self.mapping_notes = f"Rejected: {reason}"
        self.debit_account = None
        self.credit_account = None
        self.save()

    def __str__(self):
        return f"{self.date} - {self.description} ({self.amount})"
