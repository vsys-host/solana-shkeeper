from abc import ABC, abstractmethod 
from decimal import Decimal


class Crypto(ABC):

    def __init__(self, symbol, init=True):
        self.symbol = symbol        
        self.fullnode = None
        self.client = None
        self.token_address = None
        self.abi = None
        self.contract = None
        
    @abstractmethod
    def set_fee_deposit_account(self):
        pass

    @abstractmethod
    def get_fee_deposit_account_address(self) -> str:
        pass
    
    @abstractmethod
    def get_fee_deposit_coin_balance(self) -> Decimal:
        pass
    
    @abstractmethod
    def get_fee_deposit_token_balance(self) -> Decimal:
        pass
    
    @abstractmethod
    def get_account_coin_balance(self) -> Decimal:
        pass
    
    @abstractmethod
    def get_account_token_balance(self) -> Decimal:
        pass
    
    @abstractmethod
    def make_multipayout(self, payout_list, fee,) -> list:
        pass
    
    @abstractmethod
    def drain_account(self, account, destination) -> list:
        pass
       
    @abstractmethod
    def get_secret_from_address(self, address) -> str:
        pass
    
    @abstractmethod
    def create_regular_wallet(self) -> str:
        pass
       
    @abstractmethod     
    def get_dump(self) -> dict:
        pass
    
    @abstractmethod
    def get_coin_transaction_price(self) -> Decimal:
        pass
    
    @abstractmethod
    def get_token_transaction_price(self) -> Decimal:
        pass
    
    @abstractmethod
    def get_account_balance_from_db(self, address) -> Decimal: 
        pass
    
    @abstractmethod
    def get_account_balance_from_fullnode(self, address) -> Decimal: 
        pass
    
    @abstractmethod
    def check_address(self, address) -> bool:
        pass
    
    @abstractmethod
    def get_all_token_transfers(self, from_block, to_block) -> list:
        pass

    @abstractmethod
    def parse_transaction(self, txid) -> list:
        pass
