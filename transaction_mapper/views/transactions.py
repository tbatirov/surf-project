from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
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

    # Base queryset with select_related to avoid N+1 queries
    transactions = Transaction.objects.select_related('mapped_account', 'uploaded_by', 'mapped_by')

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

    # Get accounts for mapping
    accounts = Account.objects.all().order_by('name')

    # Get statistics using efficient aggregation
    stats = Transaction.objects.aggregate(
        total_transactions=Count('transaction_id'),
        mapped_transactions=Count('transaction_id', filter=Q(status='MAPPED')),
        pending_transactions=Count('transaction_id', filter=Q(status='PENDING')),
        verified_transactions=Count('transaction_id', filter=Q(status='VERIFIED'))
    )

    # Pagination
    paginator = Paginator(transactions, 50)  # Show 50 transactions per page
    page = request.GET.get('page', 1)
    try:
        transactions = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        transactions = paginator.page(1)

    context = {
        'transactions': transactions,
        'accounts': accounts,
        'total_transactions': stats['total_transactions'],
        'mapped_transactions': stats['mapped_transactions'],
        'pending_transactions': stats['pending_transactions'],
        'verified_transactions': stats['verified_transactions'],
        'selected_status': status,
        'search_query': search,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort,
        'filters': {
            'status': status,
            'search': search,
            'date_from': date_from,
            'date_to': date_to,
            'sort': sort
        }
    }

    return render(request, 'transaction_mapper/transactions.html', context)

@login_required
@role_required(['ADMIN', 'ACCOUNTANT'])
def map_transaction(request, transaction_id=None):
    """Map a transaction or all transactions using AI"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        map_all = request.POST.get('map_all') == 'true'
        use_ai = request.POST.get('use_ai', 'true') == 'true'

        if map_all:
            # Map all unmapped transactions
            pending_count = Transaction.objects.filter(status='PENDING').count()
            if pending_count == 0:
                return JsonResponse({'error': 'No pending transactions found'}, status=400)

            # Get all accounts for AI context
            all_accounts = list(Account.objects.all().values('account_id', 'name', 'account_type'))
            if not all_accounts:
                return JsonResponse({'error': 'No accounts found in the system'}, status=400)

            # Process in smaller batches
            BATCH_SIZE = 50
            total_mapped = 0
            total_errors = 0
            error_details = []

            for offset in range(0, pending_count, BATCH_SIZE):
                try:
                    with transaction.atomic():
                        # Get batch of transactions with select_for_update to prevent concurrent modifications
                        batch = Transaction.objects.select_for_update(skip_locked=True).filter(
                            status='PENDING'
                        )[offset:offset + BATCH_SIZE]

                        batch_data = []
                        for trans in batch:
                            try:
                                # Prepare transaction data for AI
                                batch_data.append({
                                    'transaction_id': trans.transaction_id,
                                    'description': trans.description,
                                    'amount': str(trans.amount),
                                    'customer_name': trans.customer_name,
                                    'transaction_type': trans.transaction_type,
                                    'date': trans.date.strftime('%Y-%m-%d')
                                })
                            except Exception as e:
                                logger.error(f"Error preparing transaction {trans.transaction_id}: {str(e)}")
                                error_details.append({
                                    'transaction_id': trans.transaction_id,
                                    'error': f"Data preparation error: {str(e)}"
                                })
                                total_errors += 1
                                continue

                        if not batch_data:
                            continue

                        try:
                            # TODO: Replace with actual AI mapping call
                            # This is where you'll call your AI service to get account mappings
                            # Example:
                            # ai_mappings = ai_service.map_transactions(batch_data, all_accounts)
                            
                            # Placeholder AI logic (replace with actual implementation)
                            for trans in batch:
                                try:
                                    best_account = None
                                    highest_confidence = 0
                                    
                                    for account in all_accounts:
                                        # Simple word matching (replace with actual AI logic)
                                        confidence = 0
                                        desc_lower = trans.description.lower()
                                        account_name_lower = account['name'].lower()
                                        
                                        if account_name_lower in desc_lower:
                                            confidence = 0.9
                                        elif any(word in desc_lower for word in account_name_lower.split()):
                                            confidence = 0.7
                                        
                                        if confidence > highest_confidence:
                                            highest_confidence = confidence
                                            best_account = account

                                    if best_account and highest_confidence > 0.5:
                                        account_obj = Account.objects.get(account_id=best_account['account_id'])
                                        trans.map_to_account(
                                            account=account_obj,
                                            user=request.user,
                                            notes=f'Mapped via AI (confidence: {highest_confidence:.2f})',
                                            confidence=highest_confidence
                                        )
                                        total_mapped += 1
                                    else:
                                        error_details.append({
                                            'transaction_id': trans.transaction_id,
                                            'error': 'No suitable account found with sufficient confidence'
                                        })
                                        total_errors += 1
                                except Exception as e:
                                    logger.error(f"Error mapping transaction {trans.transaction_id}: {str(e)}")
                                    error_details.append({
                                        'transaction_id': trans.transaction_id,
                                        'error': f"Mapping error: {str(e)}"
                                    })
                                    total_errors += 1

                        except Exception as e:
                            logger.error(f"Batch AI mapping error: {str(e)}")
                            error_details.append({
                                'batch': f"offset={offset}",
                                'error': f"AI service error: {str(e)}"
                            })
                            total_errors += len(batch_data)
                            continue

                except Exception as e:
                    logger.error(f"Batch processing error at offset {offset}: {str(e)}")
                    error_details.append({
                        'batch': f"offset={offset}",
                        'error': f"Batch processing error: {str(e)}"
                    })
                    total_errors += BATCH_SIZE
                    continue

            response_data = {
                'success': True,
                'total_processed': pending_count,
                'total_mapped': total_mapped,
                'total_errors': total_errors,
                'error_details': error_details[:10] if error_details else []  # Limit error details in response
            }

            if total_mapped == 0:
                response_data['warning'] = 'No transactions could be mapped successfully'

            return JsonResponse(response_data)

        else:
            # Single transaction mapping
            if not transaction_id:
                return JsonResponse({'error': 'Transaction ID is required'}, status=400)

            try:
                # Use select_for_update to prevent concurrent modifications
                transaction_obj = Transaction.objects.select_for_update().get(transaction_id=transaction_id)
            except Transaction.DoesNotExist:
                return JsonResponse({'error': 'Transaction not found'}, status=404)

            # Check if transaction is already mapped
            if transaction_obj.status != 'PENDING':
                return JsonResponse({'error': 'Transaction is already mapped or verified'}, status=400)

            # Get the account ID from request if provided (for manual mapping)
            account_id = request.POST.get('account_id')
            
            if account_id:
                # Manual mapping
                try:
                    account = Account.objects.get(account_id=account_id)
                except Account.DoesNotExist:
                    return JsonResponse({'error': 'Account not found'}, status=404)
                
                transaction_obj.map_to_account(
                    account=account,
                    user=request.user,
                    notes='Mapped manually',
                    confidence=1.0
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Transaction mapped successfully'
                })
            else:
                # AI mapping for single transaction
                all_accounts = list(Account.objects.all().values('account_id', 'name', 'account_type'))
                if not all_accounts:
                    return JsonResponse({'error': 'No accounts found in the system'}, status=400)

                # TODO: Replace with actual AI mapping call
                # Placeholder logic (same as batch processing)
                best_account = None
                highest_confidence = 0
                
                for account in all_accounts:
                    confidence = 0
                    desc_lower = transaction_obj.description.lower()
                    account_name_lower = account['name'].lower()
                    
                    if account_name_lower in desc_lower:
                        confidence = 0.9
                    elif any(word in desc_lower for word in account_name_lower.split()):
                        confidence = 0.7
                    
                    if confidence > highest_confidence:
                        highest_confidence = confidence
                        best_account = account

                if best_account and highest_confidence > 0.5:
                    account_obj = Account.objects.get(account_id=best_account['account_id'])
                    transaction_obj.map_to_account(
                        account=account_obj,
                        user=request.user,
                        notes=f'Mapped via AI (confidence: {highest_confidence:.2f})',
                        confidence=highest_confidence
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Transaction mapped successfully',
                        'account': {
                            'id': account_obj.account_id,
                            'name': account_obj.name,
                            'confidence': highest_confidence
                        }
                    })
                else:
                    return JsonResponse({
                        'error': 'No suitable account found with sufficient confidence',
                        'suggestion': 'Please map this transaction manually'
                    }, status=400)

    except Exception as e:
        logger.error(f"Error in map_transaction: {str(e)}")
        return JsonResponse({
            'error': 'An unexpected error occurred while mapping transactions',
            'details': str(e)
        }, status=500)

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
        logger.info(f"Upload request received from user: {request.user.username}")
        
        if 'file' not in request.FILES:
            logger.warning("No file found in request")
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        file = request.FILES['file']
        logger.info(f"Received file: {file.name}, size: {file.size} bytes")
        
        # Validate file size (10MB limit)
        if file.size > 10 * 1024 * 1024:
            logger.warning(f"File too large: {file.size} bytes")
            return JsonResponse({'error': 'File size exceeds 10MB limit'}, status=400)
        
        # Validate file type
        if not file.name.lower().endswith('.csv'):
            logger.warning(f"Invalid file type: {file.name}")
            return JsonResponse({'error': 'Only CSV files are allowed'}, status=400)
        
        # Read and validate file content
        try:
            # Try different encodings
            df = None
            encoding_errors = []
            
            for encoding in ['utf-8', 'utf-8-sig', 'latin1', 'iso-8859-1']:
                try:
                    logger.info(f"Trying to read file with {encoding} encoding")
                    # First, try to read a small chunk to validate structure
                    chunk = file.read(1024).decode(encoding)
                    file.seek(0)
                    
                    # Validate CSV structure
                    lines = [line.strip() for line in chunk.split('\n') if line.strip()]
                    if not lines:
                        logger.warning("File appears to be empty")
                        return JsonResponse({'error': 'File appears to be empty'}, status=400)
                    
                    # Parse headers
                    headers = [h.strip().lower() for h in lines[0].split(',')]
                    logger.info(f"Found headers: {headers}")
                    
                    # Check required columns
                    required_columns = ['date', 'description', 'amount']
                    missing_columns = [col for col in required_columns if col not in headers]
                    
                    if missing_columns:
                        logger.warning(f"Missing required columns: {missing_columns}")
                        return JsonResponse({
                            'error': f'Missing required columns: {", ".join(missing_columns)}',
                            'found_columns': headers
                        }, status=400)
                    
                    # Try to read the full file
                    df = pd.read_csv(file, encoding=encoding)
                    logger.info(f"Successfully read file with {encoding} encoding")
                    break
                    
                except UnicodeDecodeError as e:
                    encoding_errors.append(f"{encoding}: {str(e)}")
                    file.seek(0)
                    continue
                except Exception as e:
                    logger.error(f"Error reading file with {encoding} encoding: {str(e)}")
                    return JsonResponse({
                        'error': f'Error reading CSV file: {str(e)}'
                    }, status=400)
            
            if df is None:
                logger.error(f"Failed to read file with any encoding. Errors: {encoding_errors}")
                return JsonResponse({
                    'error': 'Unable to read the CSV file. Please ensure it is properly encoded (UTF-8).'
                }, status=400)
            
            # Process the data
            success_count = 0
            error_rows = []
            transactions_to_create = []
            
            # Process in batches
            BATCH_SIZE = 100
            total_rows = len(df)
            logger.info(f"Processing {total_rows} rows in batches of {BATCH_SIZE}")
            
            for index, row in df.iterrows():
                try:
                    # Basic data validation
                    if pd.isna(row['date']) or pd.isna(row['description']) or pd.isna(row['amount']):
                        error_rows.append({
                            'row': index + 2,
                            'error': 'Missing required fields'
                        })
                        continue
                    
                    # Validate and parse date
                    try:
                        parsed_date = pd.to_datetime(row['date']).date()
                    except Exception as e:
                        error_rows.append({
                            'row': index + 2,
                            'error': f'Invalid date format: {row["date"]}'
                        })
                        continue
                    
                    # Validate and parse amount
                    try:
                        amount = Decimal(str(row['amount']).strip().replace(',', ''))
                    except Exception as e:
                        error_rows.append({
                            'row': index + 2,
                            'error': f'Invalid amount format: {row["amount"]}'
                        })
                        continue
                    
                    # Create transaction object
                    trans_data = {
                        'transaction_id': str(row.get('transaction_id', uuid.uuid4())),
                        'date': parsed_date,
                        'description': str(row['description']).strip()[:255],
                        'amount': amount,
                        'transaction_type': str(row.get('transaction_type', 'OTHER')).strip().upper()[:50],
                        'uploaded_by': request.user,
                        'status': 'PENDING'
                    }
                    
                    # Add optional fields if present
                    if 'time' in row and pd.notna(row['time']):
                        try:
                            trans_data['time'] = pd.to_datetime(row['time']).time()
                        except:
                            logger.warning(f"Invalid time format in row {index + 2}: {row['time']}")
                    
                    if 'customer_name' in row and pd.notna(row['customer_name']):
                        trans_data['customer_name'] = str(row['customer_name'])[:100]
                    
                    if 'account' in row and pd.notna(row['account']):
                        try:
                            account = Account.objects.get(account_id=str(row['account']))
                            trans_data['account'] = account
                        except Account.DoesNotExist:
                            logger.warning(f"Account {row['account']} not found for row {index + 2}")
                    
                    # Validate transaction
                    trans = Transaction(**trans_data)
                    trans.full_clean()
                    transactions_to_create.append(trans)
                    
                    # Process in batches
                    if len(transactions_to_create) >= BATCH_SIZE:
                        with transaction.atomic():
                            Transaction.objects.bulk_create(transactions_to_create)
                            success_count += len(transactions_to_create)
                            logger.info(f"Created batch of {len(transactions_to_create)} transactions")
                        transactions_to_create = []
                    
                except Exception as e:
                    logger.error(f"Error processing row {index + 2}: {str(e)}")
                    error_rows.append({
                        'row': index + 2,
                        'error': str(e)
                    })
                    continue
            
            # Process remaining transactions
            if transactions_to_create:
                with transaction.atomic():
                    Transaction.objects.bulk_create(transactions_to_create)
                    success_count += len(transactions_to_create)
                    logger.info(f"Created final batch of {len(transactions_to_create)} transactions")
            
            logger.info(f"Upload complete. {success_count} transactions created, {len(error_rows)} errors")
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully processed {success_count} transactions',
                'total_rows': total_rows,
                'success_count': success_count,
                'error_count': len(error_rows),
                'errors': error_rows[:10] if error_rows else []
            })
            
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}")
            return JsonResponse({
                'error': f'Error processing CSV file: {str(e)}'
            }, status=400)
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return JsonResponse({
            'error': 'An error occurred while processing the file',
            'details': str(e)
        }, status=500)

@login_required
@role_required(['ADMIN'])  # Only admins should be able to delete all transactions
def delete_all_transactions(request):
    """Delete all transactions from the system"""
    if request.method != 'POST':
        logger.warning(f"Delete transactions attempted with {request.method} method by user {request.user.username}")
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        logger.info(f"Starting transaction deletion by user {request.user.username}")
        
        # Get initial count
        initial_count = Transaction.objects.count()
        logger.info(f"Found {initial_count} transactions to delete")
        
        # Delete transactions in smaller batches to avoid database lock
        batch_size = 100
        deleted_count = 0
        
        while True:
            with transaction.atomic():
                # Get a batch of transactions
                batch = Transaction.objects.all()[:batch_size]
                if not batch.exists():
                    break
                    
                # Delete the batch
                batch_ids = list(batch.values_list('transaction_id', flat=True))
                Transaction.objects.filter(transaction_id__in=batch_ids).delete()
                deleted_count += len(batch_ids)
                logger.info(f"Deleted batch of {len(batch_ids)} transactions")
        
        logger.info(f"Deleted {deleted_count} transactions successfully")
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {deleted_count} transactions'
        })
            
    except Exception as e:
        error_msg = f'Error deleting transactions: {str(e)}'
        logger.error(f"{error_msg}. User: {request.user.username}")
        return JsonResponse({'error': error_msg}, status=500)
