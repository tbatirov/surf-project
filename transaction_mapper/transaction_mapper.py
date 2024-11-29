from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from .chart_of_accounts import Account, ChartOfAccounts, AccountType
import nltk

@dataclass
class Transaction:
    """Represents a single financial transaction."""
    transaction_id: str
    date: datetime
    description: str
    amount: float
    account: Optional[Account] = None
    tags: Dict[str, str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}

class TransactionMapper:
    """Maps transactions to appropriate accounts and provides analysis."""
    def __init__(self, chart_of_accounts: ChartOfAccounts):
        self.chart_of_accounts = chart_of_accounts
        self.transactions: Dict[str, Transaction] = {}
        self.mapping_rules: Dict[str, Dict[str, Any]] = {}
        nltk.download('punkt')  # Ensure NLTK resources are available

    def add_mapping_rule(
        self, 
        rule_name: str, 
        conditions: Dict[str, Any], 
        target_account_id: str
    ):
        """
        Add a mapping rule for automatic transaction categorization.
        
        :param rule_name: Unique name for the rule
        :param conditions: Dictionary of conditions to match against transaction attributes
        :param target_account_id: Account ID to map matching transactions to
        """
        self.mapping_rules[rule_name] = {
            'conditions': conditions,
            'target_account_id': target_account_id
        }

    def match_transaction(self, transaction: Transaction) -> Optional[Account]:
        """
        Attempt to match a transaction to an account based on mapping rules.
        
        :param transaction: Transaction to match
        :return: Matched account or None
        """
        for rule in self.mapping_rules.values():
            conditions = rule['conditions']
            match = all(
                getattr(transaction, key, None) == value 
                for key, value in conditions.items()
            )
            
            if match:
                return self.chart_of_accounts.get_account(rule['target_account_id'])
        
        return None

    def analyze_transaction_context(self, transaction: Transaction):
        """
        Analyze the transaction description to identify potential account matches.

        :param transaction: Transaction to analyze
        """
        tokens = nltk.word_tokenize(transaction.description)
        potential_accounts = []

        for account in self.chart_of_accounts.accounts.values():
            if any(token.lower() in account.name.lower() for token in tokens):
                potential_accounts.append(account)

        return potential_accounts

    def apply_bookkeeping_rules(self, transaction: Transaction, is_credit: bool):
        """
        Apply bookkeeping rules to determine the debit or credit of a transaction.

        :param transaction: Transaction to apply rules to
        :param is_credit: Boolean indicating if the transaction is a credit
        """
        if is_credit:
            transaction.amount = -abs(transaction.amount)  # Credits are negative
        else:
            transaction.amount = abs(transaction.amount)  # Debits are positive

    def categorize_transaction(self, transaction: Transaction, is_credit: bool):
        """
        Categorize a transaction by matching it to an account and applying bookkeeping rules.

        :param transaction: Transaction to categorize
        :param is_credit: Boolean indicating if the transaction is a credit
        """
        matched_account = self.match_transaction(transaction)
        if matched_account:
            transaction.account = matched_account
        else:
            potential_accounts = self.analyze_transaction_context(transaction)
            if potential_accounts:
                # For simplicity, choose the first match
                transaction.account = potential_accounts[0]

        self.apply_bookkeeping_rules(transaction, is_credit)
        self.transactions[transaction.transaction_id] = transaction

    def get_account_balance(self, account_id: str) -> float:
        """
        Calculate the total balance for a specific account.
        
        :param account_id: Account ID to calculate balance for
        :return: Total balance
        """
        return sum(
            t.amount for t in self.transactions.values() 
            if t.account and t.account.account_id == account_id
        )

    def generate_financial_report(self) -> Dict[AccountType, float]:
        """
        Generate a summary report of transactions by account type.
        
        :return: Dictionary of total amounts by account type
        """
        report = {account_type: 0.0 for account_type in AccountType}
        
        for transaction in self.transactions.values():
            if transaction.account:
                report[transaction.account.account_type] += transaction.amount
        
        return report
