from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import User, UserProfile, UserActivity

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when a new User is created"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    instance.profile.save()

@receiver([post_save, post_delete], sender=User)
def log_user_changes(sender, instance, created=None, **kwargs):
    """Log user creation and deletion"""
    if created:
        activity_type = 'USER_CREATED'
        description = f'User {instance.username} was created'
    elif 'signal' in kwargs and kwargs['signal'] == post_delete:
        activity_type = 'USER_DELETED'
        description = f'User {instance.username} was deleted'
    else:
        activity_type = 'USER_UPDATED'
        description = f'User {instance.username} was updated'
    
    # Create activity log
    UserActivity.objects.create(
        user=instance,
        activity_type=activity_type,
        description=description,
        ip_address='system'  # System-generated event
    )
