from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from ..models import Account, Transaction
import pandas as pd
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def accounts_view(request):
    """View for listing and managing chart of accounts"""
    accounts = Account.objects.all()
    context = {
        'title': 'Chart of Accounts',
        'accounts': accounts,
    }
    return render(request, 'transaction_mapper/accounts.html', context)

@login_required
def delete_all_accounts(request):
    """Delete all accounts from the system"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        with transaction.atomic():
            # First check if any transactions are mapped
            mapped_transactions = Transaction.objects.filter(mapped_account__isnull=False).exists()
            if mapped_transactions:
                return JsonResponse({
                    'error': 'Cannot delete accounts while transactions are mapped to them. Please unmap all transactions first.'
                }, status=400)
            
            # Delete all accounts
            count = Account.objects.all().delete()[0]
            logger.info(f"Deleted {count} accounts")
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully deleted {count} accounts'
            })
            
    except Exception as e:
        error_msg = f'Error deleting accounts: {str(e)}'
        logger.error(error_msg)
        return JsonResponse({'error': error_msg}, status=500)

@login_required
def upload_accounts(request):
    """Handle chart of accounts file upload"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    
    file = request.FILES['file']
    logger.info(f"Processing file upload: {file.name}")
    
    # Check file extension
    if not file.name.endswith(('.csv', '.xlsx')):
        return JsonResponse({'error': 'Invalid file format. Please upload a CSV or Excel file.'}, status=400)
    
    try:
        # Read file based on extension
        try:
            if file.name.endswith('.csv'):
                # Read CSV with accounting_code as string to preserve leading zeros
                df = pd.read_csv(file, dtype={'accounting_code': str})
            else:
                # Read Excel with accounting_code as string
                df = pd.read_excel(file, dtype={'accounting_code': str})
            
            logger.info(f"Successfully read file with {len(df)} rows")
            logger.info(f"Columns found in file: {list(df.columns)}")
            
            # Check for BOM in column names and strip if present
            df.columns = df.columns.str.replace('\ufeff', '')
            df.columns = df.columns.str.strip().str.lower()
            
            logger.info(f"Cleaned columns: {list(df.columns)}")
            
            # Map file columns to model fields
            column_mapping = {
                'accounting_code': 'account_id',
                'accounting_name': 'name',
                'account_type': 'account_type'
            }
            
            # Rename columns to match model fields
            df = df.rename(columns=column_mapping)
            
            # Ensure account_id is string and preserve leading zeros
            df['account_id'] = df['account_id'].astype(str).str.strip()
            
            # Add leading zeros if needed (assuming 4-digit codes)
            df['account_id'] = df['account_id'].str.zfill(4)
            
            logger.info(f"Sample of processed account IDs: {df['account_id'].head().tolist()}")
            
            # Validate required columns after mapping
            required_columns = ['account_id', 'name', 'account_type']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                error_msg = f'Missing required columns: {", ".join(missing_columns)}. Please ensure your file has these columns: {", ".join(column_mapping.keys())}'
                logger.error(error_msg)
                return JsonResponse({'error': error_msg}, status=400)
            
            # Process accounts
            accounts_created = 0
            accounts_updated = 0
            errors = []
            
            # Use transaction.atomic to ensure all-or-nothing operation
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Clean and validate data
                        account_data = {
                            'name': str(row['name']).strip(),
                            'account_type': str(row['account_type']).strip(),
                        }
                        
                        # Handle parent account if present
                        if 'parent_account' in row and pd.notna(row['parent_account']):
                            parent_id = str(row['parent_account']).strip()
                            try:
                                parent_account = Account.objects.get(account_id=parent_id)
                                account_data['parent_account'] = parent_account
                            except Account.DoesNotExist:
                                errors.append(f"Parent account {parent_id} not found for account {row['account_id']}")
                                continue
                        
                        # Create or update account
                        account, created = Account.objects.update_or_create(
                            account_id=str(row['account_id']).strip(),
                            defaults=account_data
                        )
                        
                        if created:
                            accounts_created += 1
                            logger.info(f"Created account: {account.account_id}")
                        else:
                            accounts_updated += 1
                            logger.info(f"Updated account: {account.account_id}")
                            
                    except Exception as e:
                        error_msg = f"Error processing row {index + 1} (account_id: {row.get('account_id', 'unknown')}): {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
            
            response_data = {
                'success': True,
                'accounts_created': accounts_created,
                'accounts_updated': accounts_updated,
                'errors': errors
            }
            logger.info(f"Upload completed: {accounts_created} created, {accounts_updated} updated, {len(errors)} errors")
            return JsonResponse(response_data)
            
        except Exception as e:
            error_msg = f'Error processing file: {str(e)}'
            logger.error(error_msg)
            return JsonResponse({'error': error_msg}, status=400)

    except Exception as e:
        error_msg = f'Error processing file: {str(e)}'
        logger.error(error_msg)
        return JsonResponse({'error': error_msg}, status=400)
