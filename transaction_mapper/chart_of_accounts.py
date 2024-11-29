from enum import Enum
from typing import Dict, List, Optional, Tuple
import pandas as pd
import spacy
import numpy as np
from datetime import datetime
from difflib import SequenceMatcher

class AccountType(Enum):
    """Enumeration of standard account types."""
    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    REVENUE = "Revenue"
    EXPENSE = "Expense"

class Account:
    """Represents a single account in the chart of accounts."""
    def __init__(
        self, 
        account_id: str, 
        name: str, 
        account_type: AccountType, 
        parent_account: Optional['Account'] = None
    ):
        self.account_id = account_id
        self.name = name
        self.account_type = account_type
        self.parent_account = parent_account
        self.sub_accounts: List[Account] = []
        self.transactions: List[Dict] = []  # Store transactions for this account
        
    def add_transaction(self, transaction: Dict):
        """Add a transaction to this account."""
        self.transactions.append(transaction)
        
    def get_balance(self) -> float:
        """Calculate the current balance of this account."""
        balance = 0.0
        for transaction in self.transactions:
            if transaction['transaction_type'].upper() in ['CREDIT', 'CR']:
                balance += transaction['amount']
            else:  # DEBIT or DR
                balance -= transaction['amount']
        return balance

    def add_sub_account(self, sub_account: 'Account'):
        """Add a sub-account to this account."""
        self.sub_accounts.append(sub_account)
        sub_account.parent_account = self

    def __repr__(self):
        return f"Account(id={self.account_id}, name={self.name}, type={self.account_type})"

class ChartOfAccounts:
    """Manages the entire chart of accounts."""
    def __init__(self):
        self.accounts: Dict[str, Account] = {}

    def add_account(self, account: Account):
        """Add an account to the chart of accounts."""
        self.accounts[account.account_id] = account

    def get_account(self, account_id: str) -> Optional[Account]:
        """Retrieve an account by its ID."""
        return self.accounts.get(account_id)

    def list_accounts_by_type(self, account_type: AccountType) -> List[Account]:
        """List all accounts of a specific type."""
        return [
            account for account in self.accounts.values() 
            if account.account_type == account_type
        ]

    def load_from_file(self, file_path: str, file_type: str = 'csv'):
        """
        Load accounts from a file (CSV or Excel) and populate the chart of accounts.

        :param file_path: Path to the file containing account data
        :param file_type: Type of file ('csv' or 'excel')
        """
        if file_type == 'csv':
            df = pd.read_csv(file_path)
        elif file_type == 'excel':
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file type. Use 'csv' or 'excel'.")

        for _, row in df.iterrows():
            account = Account(
                account_id=row['account_code'],
                name=row['account_name'],
                account_type=AccountType[row['account_type'].upper()]
            )
            self.add_account(account)

    def upload_accounts(self, file_path: str, file_type: str = 'csv'):
        """
        Upload accounts from a file (CSV or Excel) and populate the chart of accounts.

        :param file_path: Path to the file containing account data
        :param file_type: Type of file ('csv' or 'excel')
        """
        if file_type == 'csv':
            df = pd.read_csv(file_path)
        elif file_type == 'excel':
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file type")

        for _, row in df.iterrows():
            account_type = AccountType[row['type'].upper()]
            account = Account(
                account_id=row['accounting_code'],
                name=row['accounting_name'],
                account_type=account_type
            )
            # Assuming sign_convention is used for additional logic, if needed
            self.add_account(account)

class TransactionMapper:
    def __init__(self, chart_of_accounts):
        self.chart_of_accounts = chart_of_accounts
        # Load English language model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # If model not found, download it
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
            self.nlp = spacy.load("en_core_web_sm")
        
        # Create lookup dictionaries for accounts
        self.account_vectors = {}
        self.section_accounts = {}  # Accounts ending in '00'
        self.regular_accounts = {}  # All other accounts
        self.transaction_patterns = {}  # Store patterns from previous mappings
        
        for account in self.chart_of_accounts.accounts.values():
            # Process account name with spaCy
            doc = self.nlp(account.name.lower())
            self.account_vectors[account.account_id] = doc.vector
            
            # Separate section accounts (ending in '00') from regular accounts
            if account.account_id.endswith('00'):
                self.section_accounts[account.account_id] = account
            else:
                self.regular_accounts[account.account_id] = account

    def calculate_similarity(self, vec1, vec2):
        """Calculate cosine similarity between two vectors"""
        if vec1 is None or vec2 is None:
            return 0.0
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return np.dot(vec1, vec2) / (norm1 * norm2)

    def extract_transaction_features(self, transaction: Dict) -> Dict:
        """Extract relevant features from a transaction for matching"""
        features = {
            'description_doc': self.nlp(transaction['description'].lower()),
            'amount': float(transaction['amount']),
            'transaction_type': transaction['transaction_type'].upper(),
            'date': datetime.strptime(transaction['date'], '%Y-%m-%d') if isinstance(transaction['date'], str) else transaction['date'],
            'customer_name': transaction.get('customer_name', '').lower()
        }
        
        # Extract key entities from description
        entities = []
        for ent in features['description_doc'].ents:
            entities.append({
                'text': ent.text,
                'label': ent.label_
            })
        features['entities'] = entities
        
        return features

    def find_matching_pattern(self, features: Dict) -> Tuple[Optional[str], float]:
        """Find if transaction matches any known patterns"""
        best_match = None
        best_score = 0.0
        
        for pattern_key, pattern in self.transaction_patterns.items():
            score = 0.0
            
            # Compare description similarity
            desc_similarity = self.calculate_similarity(
                features['description_doc'].vector,
                pattern['description_vector']
            )
            score += desc_similarity * 0.4  # 40% weight for description
            
            # Compare amount similarity (exact match gets bonus)
            amount_diff = abs(features['amount'] - pattern['amount'])
            amount_score = 1.0 if amount_diff == 0 else 1.0 / (1.0 + amount_diff)
            score += amount_score * 0.3  # 30% weight for amount
            
            # Compare transaction type (exact match required)
            if features['transaction_type'] == pattern['transaction_type']:
                score += 0.2  # 20% weight for transaction type
            
            # Compare customer name if available
            if pattern.get('customer_name') and features.get('customer_name'):
                if pattern['customer_name'] == features['customer_name']:
                    score += 0.1  # 10% weight for customer match
            
            if score > best_score:
                best_score = score
                best_match = pattern['account_id']
        
        return best_match, best_score

    def find_best_account_match(self, transaction: Dict) -> Tuple[str, float]:
        """
        Find the best matching account for a transaction using NLP and context.
        Returns tuple of (account_id, confidence_score)
        """
        features = self.extract_transaction_features(transaction)
        
        # Check for matching patterns first
        pattern_match, pattern_score = self.find_matching_pattern(features)
        if pattern_score > 0.8:  # High confidence pattern match
            return pattern_match, pattern_score
        
        best_match = None
        best_score = 0.0
        
        # Try matching against all accounts
        for account_id, account in self.regular_accounts.items():
            score = 0.0
            
            # Description similarity (40% weight)
            desc_similarity = self.calculate_similarity(
                features['description_doc'].vector,
                self.account_vectors[account_id]
            )
            score += desc_similarity * 0.4
            
            # Account type compatibility (30% weight)
            account_type = account.account_type
            if features['transaction_type'] == 'DEBIT':
                if account_type in [AccountType.ASSET, AccountType.EXPENSE]:
                    score += 0.3
            else:  # CREDIT
                if account_type in [AccountType.LIABILITY, AccountType.EQUITY, AccountType.REVENUE]:
                    score += 0.3
            
            # Entity matching (20% weight)
            for entity in features['entities']:
                if entity['text'].lower() in account.name.lower():
                    score += 0.2
                    break
            
            # Historical transaction similarity (10% weight)
            if account.transactions:
                similar_amounts = sum(1 for t in account.transactions 
                                   if abs(float(t['amount']) - features['amount']) < 0.01)
                score += min(similar_amounts / len(account.transactions), 1.0) * 0.1
            
            if score > best_score:
                best_score = score
                best_match = account_id
        
        # If no good match found in regular accounts, try section accounts
        if best_score < 0.5:
            for account_id, account in self.section_accounts.items():
                score = 0.0
                
                # Description similarity (50% weight)
                desc_similarity = self.calculate_similarity(
                    features['description_doc'].vector,
                    self.account_vectors[account_id]
                )
                score += desc_similarity * 0.5
                
                # Account type compatibility (50% weight)
                account_type = account.account_type
                if features['transaction_type'] == 'DEBIT':
                    if account_type in [AccountType.ASSET, AccountType.EXPENSE]:
                        score += 0.5
                else:  # CREDIT
                    if account_type in [AccountType.LIABILITY, AccountType.EQUITY, AccountType.REVENUE]:
                        score += 0.5
                
                if score > best_score:
                    best_score = score
                    best_match = account_id
        
        return best_match, best_score

    def learn_from_mapping(self, transaction: Dict, account_id: str):
        """Learn from a verified transaction mapping"""
        features = self.extract_transaction_features(transaction)
        pattern_key = f"{transaction['description']}_{account_id}"
        
        self.transaction_patterns[pattern_key] = {
            'description_vector': features['description_doc'].vector,
            'amount': features['amount'],
            'transaction_type': features['transaction_type'],
            'customer_name': features.get('customer_name'),
            'account_id': account_id
        }

    def map_transactions_to_accounts(self, transactions: List[Dict]) -> List[Dict]:
        """Map transactions to accounts using NLP similarity and context"""
        mapped_transactions = []
        
        for transaction in transactions:
            account_id, confidence = self.find_best_account_match(transaction)
            
            mapped_transaction = transaction.copy()
            mapped_transaction.update({
                'mapped_account_id': account_id,
                'confidence_score': confidence,
                'status': 'MAPPED' if confidence > 0.7 else 'PENDING'
            })
            
            mapped_transactions.append(mapped_transaction)
        
        return mapped_transactions

    def parse_transactions(self, file_path_or_buffer, file_type: str) -> List[Dict]:
        """Parse transaction file and return list of transaction dictionaries"""
        if file_type.lower() == 'csv':
            df = pd.read_csv(file_path_or_buffer)
        elif file_type.lower() in ['xlsx', 'excel']:
            df = pd.read_excel(file_path_or_buffer)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        # Expected column headers (case-insensitive)
        expected_headers = {
            'transactionid': 'transaction_id',
            'date': 'date',
            'time': 'time',
            'description': 'description',
            'accountnumber': 'account',
            'customername': 'customer_name',
            'transactiontype': 'transaction_type',
            'amount': 'amount'
        }

        # Convert actual column names to lowercase and remove underscores for comparison
        df.columns = df.columns.str.lower().str.replace('_', '')

        # Create a mapping from actual column names to model field names
        column_mapping = {}
        for col in df.columns:
            if col in expected_headers:
                column_mapping[col] = expected_headers[col]

        # Rename columns using the mapping
        df = df.rename(columns=column_mapping)

        # Required columns that must be present
        required_columns = ['date', 'description', 'amount', 'transaction_type']
        
        # Check for missing required columns
        missing_required = [col for col in required_columns if col not in df.columns]
        if missing_required:
            raise ValueError(f"Missing required columns: {', '.join(missing_required)}")

        # Convert DataFrame to list of dictionaries
        transactions = df.to_dict('records')

        # Clean and validate transactions
        for transaction in transactions:
            # Clean amount
            if isinstance(transaction['amount'], str):
                transaction['amount'] = self.clean_amount(transaction['amount'])

            # Format date
            if isinstance(transaction['date'], str):
                transaction['date'] = pd.to_datetime(transaction['date']).date()
            
            # Format time
            if pd.notnull(transaction['time']):
                if isinstance(transaction['time'], str):
                    transaction['time'] = pd.to_datetime(transaction['time']).time()
                elif isinstance(transaction['time'], pd.Timestamp):
                    transaction['time'] = transaction['time'].time()

            # Ensure transaction type is standardized
            transaction['transaction_type'] = str(transaction['transaction_type']).strip().upper()
            if transaction['transaction_type'] in ['DR', 'D']:
                transaction['transaction_type'] = 'DEBIT'
            elif transaction['transaction_type'] in ['CR', 'C']:
                transaction['transaction_type'] = 'CREDIT'
            
            if transaction['transaction_type'] not in ['DEBIT', 'CREDIT']:
                raise ValueError(f"Invalid transaction type: {transaction['transaction_type']}")

            # Convert empty strings to None for optional fields
            for field in ['customer_name', 'account']:
                if transaction.get(field) == '':
                    transaction[field] = None

        return transactions

    @staticmethod
    def clean_amount(amount_str: str) -> float:
        """Clean and convert amount string to float"""
        # Remove currency symbols and commas
        amount_str = ''.join(c for c in amount_str if c.isdigit() or c in '.-')
        return float(amount_str)
