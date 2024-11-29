# Transaction Mapping Tool

## Overview
This Transaction Mapping Tool provides a flexible system for managing financial accounts and transactions, allowing for sophisticated categorization and analysis.

## Features
- Hierarchical Chart of Accounts
- Automatic Transaction Categorization
- Flexible Mapping Rules
- Financial Reporting

## Quick Start

### Installation
```bash
pip install -r requirements.txt
```

### Basic Usage
```python
from chart_of_accounts import ChartOfAccounts, Account, AccountType
from transaction_mapper import TransactionMapper, Transaction
from datetime import datetime

# Create Chart of Accounts
coa = ChartOfAccounts()

# Add Accounts
salary_income = Account('1001', 'Salary Income', AccountType.REVENUE)
coa.add_account(salary_income)

# Create Transaction Mapper
mapper = TransactionMapper(coa)

# Add Mapping Rule
mapper.add_mapping_rule(
    'salary_rule', 
    {'description': 'Monthly Salary'}, 
    '1001'
)

# Create and Categorize Transaction
transaction = Transaction(
    transaction_id='TX001',
    date=datetime.now(),
    description='Monthly Salary',
    amount=5000.00
)
mapper.categorize_transaction(transaction)

# Generate Financial Report
report = mapper.generate_financial_report()
print(report)
```

## Key Components
- `Account`: Represents a single account with hierarchical support
- `Transaction`: Represents a financial transaction
- `TransactionMapper`: Manages transaction categorization and analysis

## Contributing
1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License
MIT License
