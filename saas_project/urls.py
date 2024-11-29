"""
URL configuration for saas_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.shortcuts import render

import sys
import os
import pandas as pd
from enum import Enum

# Add the project directory to the PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transaction_mapper.chart_of_accounts import TransactionMapper, ChartOfAccounts

class AccountType(Enum):
    ASSET = 1
    LIABILITY = 2
    EQUITY = 3
    REVENUE = 4
    EXPENSE = 5

class Account:
    def __init__(self, account_id, name, account_type):
        self.account_id = account_id
        self.name = name
        self.account_type = account_type

# Updated homepage view to render a template
def homepage(request):
    return render(request, 'homepage.html')

# Views for key pages
def dashboard(request):
    return render(request, 'dashboard.html')

def profile(request):
    return render(request, 'profile.html')

def transaction_management(request):
    return render(request, 'transaction_management.html')

# Store the chart of accounts in memory (in a real app, this would be in a database)
_chart_of_accounts = None

def upload_accounts(request):
    if request.method == 'POST' and request.FILES['accountFile']:
        account_file = request.FILES['accountFile']
        file_type = account_file.name.split('.')[-1]
        if file_type not in ['csv', 'xls', 'xlsx']:
            return HttpResponse("Unsupported file type.")

        # Create a new ChartOfAccounts instance
        global _chart_of_accounts
        _chart_of_accounts = ChartOfAccounts()
        
        try:
            # Load accounts from the uploaded file
            if file_type == 'csv':
                df = pd.read_csv(account_file)
            else:
                df = pd.read_excel(account_file)

            # Normalize column names (remove spaces, convert to lowercase)
            df.columns = df.columns.str.strip().str.lower()

            # Map expected column names to actual column names
            required_columns = {
                'account_code': next((col for col in df.columns if 'code' in col or 'number' in col), None),
                'account_name': next((col for col in df.columns if 'name' in col or 'description' in col), None),
                'account_type': next((col for col in df.columns if 'type' in col), None)
            }

            # Print column mapping for debugging
            print("Found columns:", df.columns.tolist())
            print("Mapped columns:", required_columns)

            # Verify all required columns are found
            missing_columns = [k for k, v in required_columns.items() if v is None]
            if missing_columns:
                return HttpResponse(f"Missing required columns: {missing_columns}. Found columns: {df.columns.tolist()}")

            # Process each row and create Account objects
            for _, row in df.iterrows():
                try:
                    account_type_str = str(row[required_columns['account_type']]).strip().upper()
                    # Map common account type variations
                    account_type_mapping = {
                        'A': 'ASSET', 'ASSETS': 'ASSET',
                        'L': 'LIABILITY', 'LIABILITIES': 'LIABILITY',
                        'E': 'EQUITY',
                        'R': 'REVENUE', 'REVENUES': 'REVENUE', 'INCOME': 'REVENUE',
                        'EX': 'EXPENSE', 'EXPENSES': 'EXPENSE'
                    }
                    account_type = account_type_mapping.get(account_type_str, account_type_str)

                    account = Account(
                        account_id=str(row[required_columns['account_code']]).strip(),
                        name=str(row[required_columns['account_name']]).strip(),
                        account_type=account_type
                    )
                    _chart_of_accounts.add_account(account)
                except Exception as e:
                    print(f"Error processing row: {row}")
                    print(f"Error: {str(e)}")
                    continue

            return HttpResponse(f"Successfully loaded {len(_chart_of_accounts.accounts)} accounts.")
        except Exception as e:
            import traceback
            print("Full error:", traceback.format_exc())
            return HttpResponse(f"Error loading accounts: {str(e)}")
    
    return HttpResponse("Failed to upload accounts.")

def upload_transactions(request):
    if request.method == 'POST' and request.FILES['transactionFile']:
        if _chart_of_accounts is None:
            return HttpResponse("Please upload chart of accounts first.")
            
        transaction_file = request.FILES['transactionFile']
        file_type = transaction_file.name.split('.')[-1]
        if file_type not in ['csv', 'xls', 'xlsx']:
            return HttpResponse("Unsupported file type.")

        # Process the file using TransactionMapper
        transaction_mapper = TransactionMapper(chart_of_accounts=_chart_of_accounts)
        try:
            transactions = transaction_mapper.parse_transactions(transaction_file, file_type)
            results = transaction_mapper.map_transactions_to_accounts(transactions)
            
            # Generate detailed results report
            report = ["<h2>Transaction Mapping Results</h2>"]
            report.append(f"<p>Total Transactions: {len(transactions)}</p>")
            report.append(f"<p>Mapped: {len(results['mapped'])}</p>")
            report.append(f"<p>Unmapped: {len(results['unmapped'])}</p>")
            
            # Show mapped transactions
            if results['mapped']:
                report.append("<h3>Mapped Transactions</h3>")
                report.append("<table border='1'>")
                report.append("<tr><th>Description</th><th>Amount</th><th>Type</th><th>Mapped Account</th><th>Confidence</th></tr>")
                
                # Sort by confidence score
                sorted_transactions = sorted(results['mapped'], 
                                          key=lambda x: float(x.get('mapping_confidence', 0)), 
                                          reverse=True)
                
                for t in sorted_transactions:
                    confidence = float(t.get('mapping_confidence', 0)) * 100
                    color = 'green' if confidence >= 70 else 'orange' if confidence >= 40 else 'red'
                    
                    report.append(
                        f"<tr>"
                        f"<td>{t.get('description', '')}</td>"
                        f"<td>{t.get('amount', 0):.2f}</td>"
                        f"<td>{t.get('transaction_type', '')}</td>"
                        f"<td>{t.get('mapped_account_name', '')}</td>"
                        f"<td style='color: {color}'>{confidence:.1f}%</td>"
                        f"</tr>"
                    )
                report.append("</table>")
                
                # Show confidence distribution
                confidence_ranges = {
                    'High (>70%)': len([t for t in results['mapped'] if float(t.get('mapping_confidence', 0)) > 0.7]),
                    'Medium (40-70%)': len([t for t in results['mapped'] if 0.4 <= float(t.get('mapping_confidence', 0)) <= 0.7]),
                    'Low (<40%)': len([t for t in results['mapped'] if float(t.get('mapping_confidence', 0)) < 0.4])
                }
                
                report.append("<h3>Confidence Distribution</h3>")
                report.append("<ul>")
                for range_name, count in confidence_ranges.items():
                    report.append(f"<li>{range_name}: {count} transactions</li>")
                report.append("</ul>")
            
            # Show unmapped transactions
            if results['unmapped']:
                report.append("<h3>Unmapped Transactions</h3>")
                report.append("<table border='1'>")
                report.append("<tr><th>Description</th><th>Amount</th><th>Type</th><th>Confidence</th></tr>")
                for t in results['unmapped']:
                    report.append(
                        f"<tr>"
                        f"<td>{t.get('description', '')}</td>"
                        f"<td>{t.get('amount', 0):.2f}</td>"
                        f"<td>{t.get('transaction_type', '')}</td>"
                        f"<td>{float(t.get('mapping_confidence', 0)) * 100:.1f}%</td>"
                        f"</tr>"
                    )
                report.append("</table>")
            
            return HttpResponse("\n".join(report))
        except Exception as e:
            import traceback
            print("Full error:", traceback.format_exc())
            return HttpResponse(f"Error processing transactions: {str(e)}")

    return HttpResponse("Failed to upload transactions.")

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('transaction_mapper.urls')),  # Include our app URLs
    
    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='transaction_mapper/auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='transaction_mapper/auth/password_change.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='transaction_mapper/auth/password_change_done.html'), name='password_change_done'),
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='transaction_mapper/auth/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='transaction_mapper/auth/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='transaction_mapper/auth/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='transaction_mapper/auth/password_reset_complete.html'), name='password_reset_complete'),
]
