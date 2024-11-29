import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saas_project.settings')
django.setup()

from transaction_mapper.models import User, Role

def create_superuser():
    # Create admin role if it doesn't exist
    admin_role, _ = Role.objects.get_or_create(
        name='ADMIN',
        defaults={
            'description': 'Administrator role with full access'
        }
    )
    
    # Create superuser
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123',
            role=admin_role
        )
        print("Superuser created successfully!")
    else:
        print("Superuser already exists.")

if __name__ == '__main__':
    create_superuser()
