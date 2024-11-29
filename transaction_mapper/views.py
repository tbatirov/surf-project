from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
import pandas as pd
from .models import Transaction, Role
from .decorators import role_required

@ensure_csrf_cookie
@login_required
def transactions_view(request):
    """View for displaying the transactions page."""
    transactions = Transaction.objects.all()
    return render(request, 'transaction_mapper/transactions.html', {
        'transactions': transactions
    })

@login_required
@role_required(['ADMIN', 'ACCOUNTANT'])
def upload_transactions(request):
    """Handle transaction file upload."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
    
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file was uploaded'}, status=400)
    
    file = request.FILES['file']
    
    # Validate file extension
    if not file.name.endswith(('.csv', '.xlsx', '.xls')):
        return JsonResponse({
            'error': 'Invalid file format. Please upload a CSV or Excel file.'
        }, status=400)
    
    try:
        # Read the file based on its extension
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Validate required columns
        required_columns = ['date', 'description', 'amount', 'category']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return JsonResponse({
                'error': f'Missing required columns: {", ".join(missing_columns)}'
            }, status=400)
        
        # Process transactions
        success_count = 0
        errors = []
        
        for _, row in df.iterrows():
            try:
                Transaction.objects.create(
                    date=row['date'],
                    description=row['description'],
                    amount=row['amount'],
                    category=row['category'],
                    uploaded_by=request.user
                )
                success_count += 1
            except Exception as e:
                errors.append(f"Error in row {_ + 2}: {str(e)}")
        
        # Prepare response message
        message = f"Successfully uploaded {success_count} transactions."
        if errors:
            message += f"\n{len(errors)} errors occurred."
            return JsonResponse({
                'message': message,
                'errors': errors
            }, status=207)  # 207 Multi-Status
        
        return JsonResponse({'message': message})
    
    except Exception as e:
        return JsonResponse({
            'error': f'Error processing file: {str(e)}'
        }, status=400)

@login_required
@role_required(['ADMIN'])
def delete_all_transactions(request):
    """Delete all transactions."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
    
    try:
        count = Transaction.objects.all().delete()[0]
        return JsonResponse({
            'message': f'Successfully deleted {count} transactions'
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Error deleting transactions: {str(e)}'
        }, status=400)
