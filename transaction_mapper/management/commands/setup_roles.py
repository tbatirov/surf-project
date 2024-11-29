from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from transaction_mapper.models import Role, User, Account, UserActivity

class Command(BaseCommand):
    help = 'Set up initial roles and permissions'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating roles and permissions...')
        
        # Create custom permissions
        content_type = ContentType.objects.get_for_model(Account)
        custom_permissions = [
            ('upload_transactions', 'Can upload transactions'),
            ('map_transactions', 'Can map transactions'),
            ('export_reports', 'Can export financial reports'),
        ]
        
        for codename, name in custom_permissions:
            Permission.objects.get_or_create(
                codename=codename,
                name=name,
                content_type=content_type,
            )
        
        # Create roles
        roles = {
            'ADMIN': 'Administrator with full access',
            'ACCOUNTANT': 'Can manage transactions and accounts',
            'ANALYST': 'Can view and analyze data',
            'VIEWER': 'Read-only access'
        }
        
        for role_name, description in roles.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={'description': description}
            )
            if created:
                self.stdout.write(f'Created role: {role_name}')
                
        self.stdout.write('Roles and permissions created successfully!')
        
        # Create superuser if it doesn't exist
        if not User.objects.filter(is_superuser=True).exists():
            self.stdout.write('Creating superuser...')
            admin_role = Role.objects.get(name='ADMIN')
            superuser = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123',  # Change this in production!
                role=admin_role
            )
            self.stdout.write('Superuser created successfully!')
            self.stdout.write('Username: admin')
            self.stdout.write('Password: admin123')
            self.stdout.write('Please change the password immediately after first login!')
