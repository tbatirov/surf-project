from django.apps import AppConfig

class TransactionMapperConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transaction_mapper'
    
    def ready(self):
        """
        Initialize app-specific configurations when Django starts.
        This is where we can import signal handlers or perform other initialization.
        """
        import transaction_mapper.signals  # Import signal handlers
