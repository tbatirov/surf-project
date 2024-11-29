from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from transaction_mapper.models import Role

User = get_user_model()

ADMIN_PERMISSIONS = [
    'add_user', 'change_user', 'delete_user', 'view_user',
    'add_role', 'change_role', 'delete_role', 'view_role',
    'add_account', 'change_account', 'delete_account', 'view_account',
    'add_transaction', 'change_transaction', 'delete_transaction', 'view_transaction',
    'upload_transactions', 'map_transactions', 'export_reports'
]

class Command(BaseCommand):
    help = 'Creates a superuser and default roles'

    def handle(self, *args, **kwargs):
        if not User.objects.filter(username='admin').exists():
            # Create admin role if it doesn't exist
            admin_role, _ = Role.objects.get_or_create(
                name='ADMIN',
                defaults={
                    'description': 'Administrator role with full access',
                    'permissions': ADMIN_PERMISSIONS
                }
            )

            # Create superuser
            admin = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
            admin.role = admin_role
            admin.save()

            self.stdout.write(self.style.SUCCESS('Successfully created superuser'))
