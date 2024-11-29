from django.urls import path
from .views.dashboard import dashboard_view
from .views.profile import profile_view
from .views.transactions import transaction_view, upload_transactions, delete_all_transactions, map_transaction, verify_transaction, reject_transaction
from .views.users import user_management_view, register_view
from .views.accounts import accounts_view, upload_accounts, delete_all_accounts

app_name = 'transaction_mapper'

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('profile/', profile_view, name='profile'),
    path('transactions/', transaction_view, name='transactions'),
    path('transactions/upload/', upload_transactions, name='upload_transactions'),
    path('transactions/delete-all/', delete_all_transactions, name='delete_all_transactions'),
    path('transactions/map/', map_transaction, name='map_transaction'),
    path('transactions/verify/', verify_transaction, name='verify_transaction'),
    path('transactions/reject/', reject_transaction, name='reject_transaction'),
    path('users/', user_management_view, name='user_management'),
    path('register/', register_view, name='register'),
    path('accounts/', accounts_view, name='accounts'),
    path('accounts/upload/', upload_accounts, name='upload_accounts'),
    path('accounts/delete-all/', delete_all_accounts, name='delete_all_accounts'),
]
