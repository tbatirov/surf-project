from django.core.management.base import BaseCommand
from transaction_mapper.models import User, Role

class Command(BaseCommand):
    help = 'Fix user roles by assigning ADMIN role to superusers'

    def handle(self, *args, **kwargs):
        self.stdout.write('Fixing user roles...')
        
        # Get or create ADMIN role
        admin_role, created = Role.objects.get_or_create(
            name='ADMIN',
            defaults={'description': 'Administrator with full access'}
        )
        if created:
            self.stdout.write('Created ADMIN role')
        
        # Fix superuser roles
        superusers = User.objects.filter(is_superuser=True)
        for user in superusers:
            if not user.role:
                user.role = admin_role
                user.save()
                self.stdout.write(f'Assigned ADMIN role to {user.username}')
            else:
                self.stdout.write(f'User {user.username} already has role: {user.role.name}')
        
        self.stdout.write('User roles fixed successfully!')
