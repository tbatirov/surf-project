from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from ..models import Transaction, Account
from ..decorators import role_required
import pandas as pd
from decimal import Decimal, InvalidOperation
import logging
import uuid

logger = logging.getLogger(__name__)

@login_required
def transaction_view(request):
    """Transaction listing and filtering view"""
    # Get filter parameters
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    sort = request.GET.get('sort', '-date')

    # Base queryset
    transactions = Transaction.objects.all()

    # Apply filters
    if status:
        transactions = transactions.filter(status=status)
    if search:
        transactions = transactions.filter(
            Q(description__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(transaction_id__icontains=search)
        )
    if date_from:
        transactions = transactions.filter(date__gte=date_from)
    if date_to:
        transactions = transactions.filter(date__lte=date_to)

    # Apply sorting
    transactions = transactions.order_by(sort)

    # Get statistics
    total_transactions = Transaction.objects.count()
    pending_count = Transaction.objects.filter(status='PENDING').count()
    mapped_count = Transaction.objects.filter(status='MAPPED').count()
    verified_count = Transaction.objects.filter(status='VERIFIED').count()

    context = {
        'title': 'Transactions',
        'transactions': transactions,
        'total_transactions': total_transactions,
        'pending_count': pending_count,
        'mapped_count': mapped_count,
        'verified_count': verified_count,
        'status_filter': status,
        'search_query': search,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'transaction_mapper/transactions.html', context)

@login_required
@role_required(['ADMIN', 'ACCOUNTANT'])
def map_transaction(request, transaction_id):
    """Map a transaction to an account"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    transaction = get_object_or_404(Transaction, transaction_id=transaction_id)
    account_id = request.POST.get('account_id')
    notes = request.POST.get('notes', '')
    
    if not account_id:
        return JsonResponse({'error': 'Account ID is required'}, status=400)

    try:
        account = Account.objects.get(account_id=account_id)
        transaction.map_to_account(account, request.user, notes)
        return JsonResponse({
            'status': 'success',
            'message': 'Transaction mapped successfully'
        })
    except Account.DoesNotExist:
        return JsonResponse({'error': 'Invalid account ID'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@role_required(['ADMIN', 'ACCOUNTANT'])
def verify_transaction(request, transaction_id):
    """Verify a transaction mapping"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    transaction = get_object_or_404(Transaction, transaction_id=transaction_id)
    transaction.verify_mapping(request.user)
    return JsonResponse({
        'status': 'success',
        'message': 'Transaction verified successfully'
    })

@login_required
@role_required(['ADMIN', 'ACCOUNTANT'])
def reject_transaction(request, transaction_id):
    """Reject a transaction mapping"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    transaction = get_object_or_404(Transaction, transaction_id=transaction_id)
    reason = request.POST.get('reason', '')
    transaction.reject_mapping(request.user, reason)
    return JsonResponse({
        'status': 'success',
        'message': 'Transaction rejected successfully'
    })

@login_required
@role_required(['ADMIN', 'ACCOUNTANT'])
@csrf_exempt
def upload_transactions(request):
    """Handle transaction file upload"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        logger.info(f"Upload request received - Method: {request.method}, User: {request.user.username}, Role: {request.user.role.name if request.user.role else 'No Role'}")
        
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        file = request.FILES['file']
        if not file.name.endswith('.csv'):
            return JsonResponse({'error': 'Only CSV files are allowed'}, status=400)
        
        try:
            # Try reading with different encodings and delimiters
            try:
                df = pd.read_csv(file, encoding='utf-8')
            except:
                try:
                    df = pd.read_csv(file, encoding='utf-8-sig')
                except:
                    # If both fail, try to read the file manually to debug
                    content = file.read().decode('utf-8-sig')
                    logger.info(f"File content start: {content[:200]}")
                    
                    # Split the content into lines and parse manually
                    lines = content.split('\n')
                    if len(lines) > 0:
                        # Get headers from first line
                        headers = [h.strip() for h in lines[0].split(',')]
                        logger.info(f"Parsed headers: {headers}")
                        
                        # Create DataFrame with proper headers
                        if len(lines) > 1:
                            data = [line.split(',') for line in lines[1:] if line.strip()]
                            df = pd.DataFrame(data, columns=headers)
                        else:
                            df = pd.DataFrame(columns=headers)
            
            # Print original columns for debugging
            logger.info(f"Original columns: {list(df.columns)}")
            
            # Convert column names to match our internal names
            column_mapping = {
                'Transaction_ID': 'transaction_id',
                'Date': 'date',
                'Time': 'time',
                'Description': 'description',
                'Account_Number': 'account',
                'Customer_Name': 'customer_name',
                'Transaction_Type': 'transaction_type',
                'Amount': 'amount'
            }
            
            # Rename columns using the exact mapping
            df = df.rename(columns=column_mapping)
            
            # Print mapped columns for debugging
            logger.info(f"Mapped columns: {list(df.columns)}")
            
            # Required columns check
            required_columns = ['date', 'description', 'amount', 'transaction_type']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return JsonResponse({
                    'error': f'Missing required columns: {", ".join(missing_columns)}. Found columns: {", ".join(df.columns)}'
                }, status=400)
                
        except Exception as e:
            logger.error(f"Error reading CSV: {str(e)}")
            return JsonResponse({
                'error': f'Error reading CSV file: {str(e)}'
            }, status=400)
        
        success_count = 0
        error_rows = []
        
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Basic data validation
                    if pd.isna(row['date']) or pd.isna(row['description']) or pd.isna(row['amount']):
                        raise ValidationError('Missing required fields')
                    
                    # Create transaction with validated data
                    trans_data = {
                        'transaction_id': str(row.get('transaction_id', uuid.uuid4())),
                        'date': pd.to_datetime(row['date']).date(),
                        'description': str(row['description']).strip(),
                        'amount': Decimal(str(row['amount']).strip().replace(',', '')),
                        'transaction_type': str(row['transaction_type']).strip().upper(),
                        'uploaded_by': request.user,
                        'status': 'PENDING'
                    }
                    
                    # Add optional fields if present
                    if 'time' in row and pd.notna(row['time']):
                        trans_data['time'] = pd.to_datetime(row['time']).time()
                    if 'customer_name' in row and pd.notna(row['customer_name']):
                        trans_data['customer_name'] = str(row['customer_name'])
                    if 'account' in row and pd.notna(row['account']):
                        try:
                            account = Account.objects.get(account_id=str(row['account']))
                            trans_data['account'] = account
                        except Account.DoesNotExist:
                            logger.warning(f"Account {row['account']} not found for transaction in row {index + 2}")
                    
                    trans = Transaction(**trans_data)
                    trans.full_clean()
                    trans.save()
                    success_count += 1
                    
                except (ValidationError, ValueError, InvalidOperation) as e:
                    error_rows.append({
                        'row': index + 2,  # Add 2 to account for 0-based index and header row
                        'error': str(e)
                    })
                    logger.error(f"Row {index + 2} error details: {str(e)}")
                    continue
        
        response_data = {
            'success_count': success_count,
            'error_count': len(error_rows),
            'errors': error_rows
        }
        
        if success_count > 0:
            messages.success(request, f'Successfully imported {success_count} transactions.')
        if error_rows:
            messages.warning(request, f'Failed to import {len(error_rows)} transactions. Check the response for details.')
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Transaction upload error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def delete_all_transactions(request):
    """Delete all transactions from the system"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        with transaction.atomic():
            # Delete all transactions
            count = Transaction.objects.all().delete()[0]
            logger.info(f"Deleted {count} transactions")
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully deleted {count} transactions'
            })
            
    except Exception as e:
        error_msg = f'Error deleting transactions: {str(e)}'
        logger.error(error_msg)
        return JsonResponse({'error': error_msg}, status=500)
