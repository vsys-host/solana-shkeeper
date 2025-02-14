from decimal import Decimal
from flask import current_app as app
import time
import json
import copy
import math

from solana.rpc.api import Client
from solana.rpc.api import Keypair
from solana.rpc.api import Pubkey
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID
from solana.rpc.types import TokenAccountOpts
from solders.system_program import TransferParams, transfer
from spl.token.instructions import transfer as spl_token_transfer 
from spl.token.instructions import TransferParams as spl_token_TransferParams
from solders.signature import Signature
from solana.transaction import Transaction
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit

from .crypto import Crypto
from .logging import logger
from .encryption import Encryption
from .config import config,  get_token_address
from .models import Accounts, Wallets, db


def to_sol(amount) -> Decimal:
    """Return amount of lamports in SOL"""
    return Decimal(Decimal(amount) / 1_000_000_000)


def to_lamports(amount) -> int:
    """Return amount of SOL in lamports"""
    return int(Decimal(amount) * 1_000_000_000)


def get_all_accounts():
    """"Return list of all accounts pub_address"""
    account_list = []
    tries = 3
    for i in range(tries):
        try:
            with app.app_context():
                all_account_list = Accounts.query.all()
        except Exception:
            if i < tries - 1: # i is zero indexed
                db.session.rollback()
                continue
            else:
                db.session.rollback()
                raise Exception("There was exception during query to the database, try again later")
        break
    for account in all_account_list:
        account_list.append(account.address)
    return account_list


class Coin (Crypto):
    
    def __init__(self, symbol, init=True):
        if (symbol not in config["TOKENS"][config["CURRENT_SOL_NETWORK"]]
            and symbol != "SOL"):
            raise Exception("Symbol is not accepted")
        self.symbol = symbol        
        self.fullnode = config["FULLNODE_URL"]
        self.client = Client(config['FULLNODE_URL'], timeout = float(config['FULLNODE_TIMEOUT']))
        if symbol in config["TOKENS"][config["CURRENT_SOL_NETWORK"]]:
            self.token_address = config["TOKENS"][config["CURRENT_SOL_NETWORK"]][symbol]["token_address"]

    def is_connected(self):
         return self.client.is_connected()

    def generate_account(self):
        return Keypair()
    
    def get_account_info_json_parsed(self, pub_key):
        self.client.get_account_info_json_parsed(pub_key).value

    def get_latest_blockhash(self):
        return self.client.get_latest_blockhash().value

    def get_slot(self):
        return int(self.client.get_slot().value)

    def get_block(self, slot, encoding='json', max_supported_transaction_version=0 ):
        return self.client.get_block(int(slot), encoding, max_supported_transaction_version).value

    def get_blocks(self, start_slot, end_slot):
        return self.client.get_blocks(int(start_slot), int(end_slot)).value

    def get_block_time(self, block_number):
        return int(self.client.get_block_time(int(block_number)).value)

    def get_signatures_for_address(self, pub_address, before=None, until=None, limit=None, commitment=None):
        return self.client.get_signatures_for_address(Pubkey.from_string(pub_address), before, until, limit, commitment)

    def get_transaction(self, tx_sig, encoding='json', commitment=None, max_supported_transaction_version=0):
        if isinstance(tx_sig, str):
            tx_sig = Signature.from_string(tx_sig)
        return self.client.get_transaction(tx_sig, encoding, commitment, max_supported_transaction_version).value

    def get_multiple_accounts(self, pubkeys, commitment=None, encoding='base64', data_slice=None):
        return self.client.get_multiple_accounts(pubkeys, commitment, encoding, data_slice).value

    def get_rent_amount(self) -> Decimal: 
        """Return min amount of rent to create an ATA in SOL"""
        min_balance = int(self.client.get_minimum_balance_for_rent_exemption(config['ATA_ACCOUNT_SIZE']).value)
        min_balance = to_sol(min_balance)
        return min_balance
    
    def parse_transaction(self, txid) -> list:
        "Return list of related transactions details for SHKeeper"
        if self.symbol == "SOL":
            related_transactions = []
            transaction = self.get_transaction(txid)
            trx = json.loads(transaction.to_json())
            slot = int(trx['slot'])
           # tx_id = str(trx["transaction"]["signatures"][0])
            account_keys = trx["transaction"]["message"]["accountKeys"]
           # instructions = trx["transaction"]["message"]["instructions"]
            pre_balances =  trx["meta"]["preBalances"]
            fee = trx["meta"]["fee"]
            post_balances =  trx["meta"]["postBalances"]
            if trx["meta"]["err"] is None:
                error = False
            else:
                error = True
            diff_balances = []
            for i in range(len(pre_balances)):
                diff_balances.append(int(post_balances[i]) - int(pre_balances[i]))
            list_accounts = get_all_accounts()
            addr_indexes = []   
            confirmations =  int(self.get_slot() - slot)
            for i in range(len(account_keys)):
                if account_keys[i] in list_accounts:
                    addr_indexes.append(i)
            if len(addr_indexes) == 1:
                address = account_keys[addr_indexes[0]]
                amount = to_sol(abs(diff_balances[addr_indexes[0]]))
                if diff_balances[addr_indexes[0]] > 0:
                    category = "receive"
                elif diff_balances[addr_indexes[0]] + fee == 0:
                    category = "internal" # paying token transaction fee 
                else:
                    category = "send"
                related_transactions.append([address, amount, confirmations, category])
            else:
                if (len(addr_indexes) == 2 and 
                    (diff_balances[0] + diff_balances[1] + fee) == 0):
                    category = "internal"
                    address = account_keys[1]
                    amount = to_sol(abs(diff_balances[1]))
                    related_transactions.append([address, amount, confirmations, category])
                else:
                    for i in addr_indexes:
                        if diff_balances[i] > 0:
                            category = "receive"
                        elif diff_balances[i] < 0:
                            category = "send"
                        else:
                            category = "token_transaction"
                            related_transactions.append([account_keys[i], to_sol(abs(diff_balances[i])), confirmations, category])
            logger.warning(f"Related transactions -> {related_transactions}")
            return related_transactions
        else:
            # Checking token transaction
            related_transactions = []
            list_accounts = get_all_accounts()
            transaction = self.get_transaction(txid)
            transaction_json = json.loads(transaction.to_json())
            slot = int(transaction_json['slot'])
            confirmations =  int(self.get_slot() - slot)
            pre_token_balances =  transaction_json["meta"]["preTokenBalances"]
            post_token_balances =  transaction_json["meta"]["postTokenBalances"]
            # Internal transaction case (from one-time account to the fee-deposit account)
            if ((len(post_token_balances) == 2)
                and
                ((post_token_balances[0]['owner'] in list_accounts and
                post_token_balances[1]['owner'] in list_accounts) 
                and
                ((post_token_balances[0]['mint'] == self.token_address and
                post_token_balances[1]['mint'] == self.token_address)))):
                cur_acc_index = post_token_balances[0]["accountIndex"]
                cur_post_balance = int(post_token_balances[0]["uiTokenAmount"]["amount"])
                cur_pre_balance = 0
                for pre_balance in pre_token_balances: # token balance can not be in pre_token_balances
                    if cur_acc_index == pre_balance["accountIndex"]:
                        cur_pre_balance = int(pre_balance["uiTokenAmount"]["amount"])
                        diff_balance = cur_post_balance - cur_pre_balance
                        category = "internal"
                related_transactions.append([post_token_balances[0]['owner'], self.to_ui_amount(abs(diff_balance)), confirmations, category])
                logger.warning(f"Related transactions -> {related_transactions}")
            else:   
                for post_balance in post_token_balances:
                    if (post_balance['owner'] in list_accounts and 
                        post_balance["mint"] == self.token_address):
                            cur_acc_index = post_balance["accountIndex"]
                            cur_post_balance = int(post_balance["uiTokenAmount"]["amount"])
                            cur_pre_balance = 0
                            for pre_balance in pre_token_balances: # token balance can not be in pre_token_balances
                                if cur_acc_index == pre_balance["accountIndex"]:
                                    cur_pre_balance = int(pre_balance["uiTokenAmount"]["amount"])
                            diff_balance = cur_post_balance - cur_pre_balance
                            if diff_balance > 0:
                                category = "receive"
                            elif diff_balance == 0:
                                category = "internal_creating_token_account"
                            else:
                                category = "send"
                            related_transactions.append([post_balance['owner'], self.to_ui_amount(abs(diff_balance)), confirmations, category])
                logger.warning(f"Related transactions -> {related_transactions}")
            return related_transactions

    def set_fee_deposit_account(self):
        """Create a fee-deposit account"""
        account = self.generate_account()
        pub_address = str(account.pubkey())
        secret = str(account.to_json())
        crypto_str = "SOL"
        e = Encryption
        logger.warning(f'Saving wallet {pub_address} to DB')
        try:
            with app.app_context():
                db.session.add(Wallets(pub_address = pub_address, 
                                        priv_key = e.encrypt(secret),
                                        type = "fee_deposit",
                                        ))
                db.session.add(Accounts(address = pub_address, 
                                             crypto = crypto_str,
                                             amount = 0,
                                             type = "fee_deposit",
                                             ))
                db.session.commit()
                db.session.close()
                db.engine.dispose() 
        finally:
            with app.app_context():
                db.session.remove()
                db.engine.dispose() 
        logger.info(f'Created fee-deposit account and added to DB')

    def get_fee_deposit_account_address(self) -> str:
        """Return a fee-deposit account address"""
        try:
            pd = Accounts.query.filter_by(type = "fee_deposit").first()
        except Exception:
            db.session.rollback()
            raise Exception("There was exception during query to the database, try again later")
        if not pd:
            from .tasks import create_fee_deposit_account
            create_fee_deposit_account.delay()
            time.sleep(10)
        pd = Accounts.query.filter_by(type = "fee_deposit").first()
        return pd.address

    def get_fee_deposit_coin_balance(self) -> Decimal:
        address = self.get_fee_deposit_account_address()
        return self.get_account_coin_balance(address)

    def get_fee_deposit_token_balance(self) -> Decimal:
        address = self.get_fee_deposit_account_address()
        return self.get_account_token_balance(address)

    def to_ui_amount(self, amount) -> Decimal:
        "Return UI amount of tokens (e.g. 0.451) from the smalest token part"
        token_decimals = self.get_token_decimals()
        ui_amount = Decimal(Decimal(amount) / 10**token_decimals)
        return ui_amount
    
    def to_raw_amount(self, amount) -> int:
        "Return raw amount of tokens in the smalest tokens part (e.g. 451000)"
        token_decimals = self.get_token_decimals()
        raw_amount = int(amount * 10**token_decimals)
        return raw_amount

    def get_account_coin_balance(self, address) -> Decimal:
        """Return coin account balance in SOL"""
        amount = to_sol(Decimal(self.client.get_balance(Pubkey.from_string(address)).value))
        return amount

    def get_token_decimals(self) -> int:
        """Return number of token decimals from token public address"""
        address = get_token_address(self.symbol)
        pub_key = Pubkey.from_string(address)
        info = json.loads(self.client.get_account_info_json_parsed(pub_key).value.to_json())
        decimals = int(info['data']['parsed']['info']['decimals'])
        return decimals

    def get_token_account_by_owner(self, owner_address) -> str:
        """Return token obj one-time address (ATA) by owner public one-time address """
        owner_pub_key = Pubkey.from_string(owner_address)
        token_mint_key = Pubkey.from_string(get_token_address(self.symbol))
        account_opts = TokenAccountOpts(mint=token_mint_key)
        result_array = self.client.get_token_accounts_by_owner_json_parsed(owner_pub_key, account_opts).value
        if len(result_array) == 0:
            account_token_address = ''
        else:
            json_address = json.loads(result_array[0].to_json())
            account_token_address = json_address["pubkey"]
        return account_token_address

    def create_associated_token_account(self, owner_address) -> str:
        """Create associated token account for owner address"""
        owner_key = Pubkey.from_string(owner_address)
        token_pub_key = Pubkey.from_string(get_token_address(self.symbol))
        fee_payer = Keypair.from_seed(self.get_secret_from_address(self.get_fee_deposit_account_address())[:32])
        token_inst = Token(self.client, token_pub_key, token_pub_key, fee_payer)
        new_address = token_inst.create_associated_token_account(owner_key)
        return new_address
        
    def get_account_token_balance(self, owner_address) -> Decimal:
        """Return obj token balance by owner public address in UI form (e.g. 0.342 USDC)"""
        owner_pub_key = Pubkey.from_string(owner_address)
        token_mint_key = Pubkey.from_string(get_token_address(self.symbol))
        account_opts = TokenAccountOpts(mint=token_mint_key)
        result_array = self.client.get_token_accounts_by_owner_json_parsed(owner_pub_key, account_opts).value
        if len(result_array) == 0:
            ui_amount = Decimal(0)
        else:
            json_address = json.loads(result_array[0].to_json())
            amount = int(json_address["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"])
            decimals_number = int(json_address["account"]["data"]["parsed"]["info"]["tokenAmount"]["decimals"])
            # use decimals from json to minimize requests to the fullnode, also self.to_ui_amount() can be used
            ui_amount = Decimal(Decimal(amount) / 10 ** decimals_number) 
        return ui_amount

    def make_multipayout(self, payout_list, fee,) -> list:
        """Send cryto to recepients from payout list"""
        payout_results = []
        if self.symbol == "SOL":
            #prioritization fee is calculated by multiplying its compute unit limit by the compute unit price (measured in micro-lamports).
            multipayout_fee = self.get_transaction_price()
            multipayout_amount = Decimal(0)
            max_transfers = config['MAX_SOL_TRANSFERS_IN_TRANSACTION']
            num_of_transaction = math.ceil(len(payout_list) / max_transfers)
            for payout in payout_list:
                multipayout_amount = multipayout_amount + Decimal(payout['amount'])
            have_crypto = self.get_fee_deposit_coin_balance()
            if have_crypto < (multipayout_amount + (multipayout_fee * num_of_transaction)):
                 raise Exception(f"Have not enough crypto on fee account, need {multipayout_amount + (multipayout_fee * num_of_transaction)} have {have_crypto}")
            sender_keypair = Keypair.from_seed(self.get_secret_from_address(self.get_fee_deposit_account_address())[:32])
            # there is a limit of trasfers in one transaction, dividing the payout_list to separete transactions if len(payout_list) > MAX_SOL_TRANSFERS_IN_TRANSACTION
            transfer_list = []
            for k in range(num_of_transaction):
                if (len(payout_list) - (k * max_transfers)) > max_transfers:
                    transfer_list.append(max_transfers)
                else:
                    if len(payout_list) > max_transfers:
                        transfer_list.append(len(payout_list) - max_transfers)
                    else:
                        transfer_list.append(len(payout_list))

            for i in range(num_of_transaction):
                transaction = Transaction()
                transaction.fee_payer = sender_keypair.pubkey()

                if config['COMPUTE_UNIT_LIMIT'] > 0:
                    transaction.add(set_compute_unit_limit(config['COMPUTE_UNIT_LIMIT']))
                if config['COMPUTE_UNIT_PRICE'] > 0:
                    transaction.add(set_compute_unit_price(config['COMPUTE_UNIT_PRICE']))
    
                # for payout in payout_list:
                for j in range(transfer_list[i]):
                    amount = int(to_lamports(Decimal(payout_list[i * max_transfers + j]['amount'])))
                    transaction.add(transfer(TransferParams(
                        from_pubkey=sender_keypair.pubkey(),
                        to_pubkey=Pubkey.from_string(payout_list[i * max_transfers + j]['dest']),
                        lamports=amount,
                        )))           
                result = self.client.send_transaction(transaction, sender_keypair).to_json()
                logger.warning(f"Result of transaction {result}")
                signature = json.loads(result)['result']
                for j in range(transfer_list[i]):
                # for payout in payout_list:
                    payout_results.append({
                            "dest": payout_list[i * max_transfers + j]['dest'],
                            "amount": float(payout_list[i * max_transfers + j]['amount']),
                            "status": "success",
                            "txids": [signature],
                        })
            return payout_results
        else:
            # Token multipayout
            # Check if enough crypto for multipayout
            multipayout_token_amount = Decimal(0)
            max_transfers = config['MAX_TOKEN_TRANSFERS_IN_TRANSACTION']
            num_of_transaction = math.ceil(len(payout_list) / max_transfers)
            for payout in payout_list:
                multipayout_token_amount = multipayout_token_amount + Decimal(payout['amount'])
            have_tokens = self.get_fee_deposit_token_balance()
            if have_tokens < (multipayout_token_amount):
                 raise Exception(f"Have not enough tokens on fee-deposit account, need {multipayout_token_amount} have {have_tokens}")
            # Check if enough SOL to pay transaction fee
            multipayout_token_fee = 0
            for payout in payout_list:
                multipayout_token_fee = multipayout_token_fee + self.get_token_transaction_price(payout['dest'])
            have_sol = self.get_fee_deposit_coin_balance()
            if have_sol < (multipayout_token_fee):
                 raise Exception(f"Have not enough SOL on fee-deposit account to pay transaction fee, need {multipayout_token_fee * num_of_transaction} have {have_sol}")
            token_payout_list = copy.deepcopy(payout_list)
            # Check if associated token account exist for address, if not - create it and change in payout_list
            for payout in token_payout_list:
                associated_token_account = self.get_token_account_by_owner(payout['dest'])
                if not associated_token_account:
                    logger.warning(f"There is not ATA for {payout['dest']}, creating")
                    owner_key = Pubkey.from_string(payout['dest'])
                    token_pub_key = Pubkey.from_string(get_token_address(self.symbol))
                    fee_payer = Keypair.from_seed(self.get_secret_from_address(self.get_fee_deposit_account_address())[:32])
                    token_inst = Token(self.client, token_pub_key, token_pub_key, fee_payer)
                    new_address_pubkey = token_inst.create_associated_token_account(owner_key)
                    new_address = str(new_address_pubkey)
                    logger.warning(f"Created new ATA {new_address} for account {payout['dest']}")
                    payout['dest'] = new_address
                else:
                    payout['dest'] = associated_token_account
            source_pub = Pubkey.from_string(self.get_token_account_by_owner(self.get_fee_deposit_account_address()))
            owner_pair = Keypair.from_seed(self.get_secret_from_address(self.get_fee_deposit_account_address())[:32])
            fee_payer = owner_pair
            token_pub_key = Pubkey.from_string(get_token_address(self.symbol))
            # there is a limit of trasfers in one transaction, dividing the token_payout_list to separete transactions if len(token_payout_list) > MAX_TOKEN_TRANSFERS_IN_TRANSACTION
            transfer_list = []
            for k in range(num_of_transaction):
                if (len(token_payout_list) - (k * max_transfers)) > max_transfers:
                    transfer_list.append(max_transfers)
                else:
                    if len(token_payout_list) > max_transfers:
                        transfer_list.append(len(token_payout_list) - max_transfers)
                    else:
                        transfer_list.append(len(token_payout_list))
            for i in range(num_of_transaction):
                token_transaction = Transaction(fee_payer=fee_payer.pubkey())
                if config['COMPUTE_UNIT_LIMIT'] > 0:
                    token_transaction.add(set_compute_unit_limit(config['COMPUTE_UNIT_LIMIT']))
                if config['COMPUTE_UNIT_PRICE'] > 0:
                    token_transaction.add(set_compute_unit_price(config['COMPUTE_UNIT_PRICE']))

                for j in range(transfer_list[i]):
                    dest_pub = Pubkey.from_string(token_payout_list[i * max_transfers + j]['dest'])
                    ui_amount = token_payout_list[i * max_transfers + j]['amount']
                    amount = self.to_raw_amount(ui_amount)
                    token_transaction.add(spl_token_transfer(spl_token_TransferParams(
                                           source=source_pub, 
                                           dest=dest_pub, 
                                           owner=owner_pair.pubkey(), 
                                           program_id = TOKEN_PROGRAM_ID,
                                           amount=amount
                                       )))
                result = self.client.send_transaction(token_transaction, fee_payer, owner_pair)
                txid = str(result.value)
                for j in range(transfer_list[i]):
                    payout_results.append({
                            "dest": payout_list[i * max_transfers + j]['dest'],
                            "amount": float(payout_list[i * max_transfers + j]['amount']),
                            "status": "success",
                            "txids": [txid],
                        })
            return payout_results

    def drain_account(self, account, destination) -> list:
        """Send all available crypto from account to destination"""
        drain_results = []
        if self.symbol == "SOL":
            transfer_fee = to_lamports(self.get_coin_transaction_price())
            sol_ui_amount = self.get_account_coin_balance(account)
            if sol_ui_amount < config['MIN_TRANSFER_THRESHOLD']:
                logger.warning(f"Account amount {sol_ui_amount} is below MIN_TRANSFER_THRESHOLD {config['MIN_TRANSFER_THRESHOLD']}, skip draining")
                return False
            amount = int(to_lamports(sol_ui_amount) - transfer_fee)
            sender_keypair = Keypair.from_seed(self.get_secret_from_address(account)[:32])
            transaction = Transaction()
            transaction.fee_payer = sender_keypair.pubkey()
            if config['COMPUTE_UNIT_LIMIT'] > 0:
                transaction.add(set_compute_unit_limit(config['COMPUTE_UNIT_LIMIT']))
            if config['COMPUTE_UNIT_PRICE'] > 0:
                transaction.add(set_compute_unit_price(config['COMPUTE_UNIT_PRICE']))
            logger.warning(f'Draining {amount} lamports from {account} to {destination}')
            transaction.add(transfer(TransferParams(
                from_pubkey=sender_keypair.pubkey(),
                to_pubkey=Pubkey.from_string(destination),
                lamports=amount,
                )))

            result = self.client.send_transaction(transaction, sender_keypair).to_json()
            logger.warning(f"Result of transaction {result}")
            signature = json.loads(result)['result']
            drain_results.append({
                    "dest": destination,
                    "amount": float(to_sol(amount)),
                    "status": "success",
                    "txids": [signature],
                })
            return drain_results
        else:
            # Token drain
            ui_amount = self.get_account_token_balance(account)
            if ui_amount < config['MIN_TOKEN_TRANSFER_THRESHOLD']:
                logger.warning(f"Account amount {ui_amount} is below MIN_TOKEN_TRANSFER_THRESHOLD {config['MIN_TOKEN_TRANSFER_THRESHOLD']}, skip draining")
                return False
            coin_amount = self.get_account_coin_balance(self.get_fee_deposit_account_address())
            drain_fee = self.get_token_transaction_price(destination)
            if drain_fee > coin_amount - self.get_rent_amount():
                logger.warning("There is not enough SOL on fee-deposit account to pay drain fee, skip draining")
                return False
            # Check if associated token account exist for address, if not - create it and change in payout_list
            associated_token_account = self.get_token_account_by_owner(destination)
            if not associated_token_account:
                owner_key = Pubkey.from_string(destination)
                token_pub_key = Pubkey.from_string(get_token_address(self.symbol))
                fee_payer = Keypair.from_seed(self.get_secret_from_address(self.get_fee_deposit_account_address())[:32])
                token_inst = Token(self.client, token_pub_key, token_pub_key, fee_payer)
                new_dest_address = str(token_inst.create_associated_token_account(owner_key))
            else:
                new_dest_address = associated_token_account
            source_pub = Pubkey.from_string(self.get_token_account_by_owner(account))
            dest_pub = Pubkey.from_string(new_dest_address)
            owner_pair = Keypair.from_seed(self.get_secret_from_address(account)[:32])
            token_pub_key = Pubkey.from_string(get_token_address(self.symbol))
            amount = self.to_raw_amount(ui_amount)
            fee_payer = Keypair.from_seed(self.get_secret_from_address(self.get_fee_deposit_account_address())[:32])
            token_transaction = Transaction(fee_payer=fee_payer.pubkey())
            if config['COMPUTE_UNIT_LIMIT'] > 0:
                token_transaction.add(set_compute_unit_limit(config['COMPUTE_UNIT_LIMIT']))
            if config['COMPUTE_UNIT_PRICE'] > 0:
                token_transaction.add(set_compute_unit_price(config['COMPUTE_UNIT_PRICE']))
            token_transaction.add(spl_token_transfer(spl_token_TransferParams(
                                   source=source_pub, 
                                   dest=dest_pub, 
                                   owner=owner_pair.pubkey(), 
                                   program_id = TOKEN_PROGRAM_ID,
                                   amount=amount
                               )))
            result = self.client.send_transaction(token_transaction, fee_payer, owner_pair)
            txid = str(result.value)
            drain_results.append({
                    "dest": destination,
                    "amount": float(ui_amount),
                    "status": "success",
                    "txids": [txid],
                })
            return drain_results
   
    def get_secret_from_address(self, address) -> list:
        """Return a secret of address"""
        tries = 3
        for i in range(tries):
            try:
                pd = Wallets.query.filter_by(pub_address = address).first()
            except Exception:
                if i < tries - 1: # i is zero indexed
                    db.session.rollback()
                    continue
                else:
                    db.session.rollback()
                    raise Exception("There was exception during query to the database, try again later")
            break
        secret = str(Encryption.decrypt(pd.priv_key))
        secret = json.loads(secret)
        return secret

    def create_regular_wallet(self) -> str:
        """Create a regular one-time wallet"""
        account = self.generate_account()
        pub_address = str(account.pubkey())
        secret = str(account.to_json())
        crypto_str = self.symbol
        e = Encryption
        logger.warning(f'Saving wallet {pub_address} to DB')
        try:
            with app.app_context():
                db.session.add(Wallets(pub_address = pub_address, 
                                        priv_key = e.encrypt(secret),
                                        type = "regular",
                                        ))
                db.session.add(Accounts(address = pub_address, 
                                             crypto = crypto_str,
                                             amount = 0,
                                             type = "regular",
                                             ))
                db.session.commit()
                db.session.close()
                db.engine.dispose() 
        finally:
            with app.app_context():
                db.session.remove()
                db.engine.dispose() 
        logger.info(f'Created one-time account and added to DB')
        return pub_address

    def get_dump(self) -> dict:
        """Return dict of pub_address: secret of all accounts"""
        logger.warning('Start dumping wallets')
        all_wallets = {}
        address_list = get_all_accounts()
        for address in address_list:
            all_wallets.update({address: {'public_address': address,
                                          'secret': self.get_secret_from_address(address)}})
        return all_wallets

    def get_coin_transaction_price(self) -> Decimal:
        """Return the transaction fee amount in SOL"""
        #prioritization fee is calculated by multiplying its compute unit limit by the compute unit price (measured in micro-lamports).
        transfer_fee = int((config['COMPUTE_UNIT_LIMIT'] * config['COMPUTE_UNIT_PRICE'] / 1_000_000) + config['BASE_TX_FEE'])
        return  to_sol(transfer_fee)

    def get_token_transaction_price(self, dest_address="") -> Decimal:
        """Return amount of SOL should be payed to make token transaction to dest_address"""
        if not dest_address:
            fee = self.get_coin_transaction_price() + self.get_rent_amount()
            return fee
        pub_key = Pubkey.from_string(dest_address)
        account_info = self.get_account_info_json_parsed(pub_key)
        dest_is_regular_acc = False
        if account_info is None:
            # empty regular account
            dest_is_regular_acc = True
        else:
            account_info_json = json.loads(account_info.to_json())
            if account_info_json['owner'] == '11111111111111111111111111111111':
                # regular account with balance
                dest_is_regular_acc = True
            else:
                dest_mint_address = account_info_json['data']['parsed']['info']['mint']
                if dest_mint_address == self.token_address:
                    # dest_address is ATA for right token
                    fee = self.get_coin_transaction_price()
                    return fee
                else:
                    raise Exception("Address is ATA for another token, cannot transfer to it") 
        if dest_is_regular_acc:
            ata_address = self.get_token_account_by_owner(dest_address)
            if not ata_address:
                fee = self.get_coin_transaction_price() + self.get_rent_amount()
                return fee
            else:
                fee = self.get_coin_transaction_price()
                return fee
    
    def get_transaction_price(self):
        if self.symbol == "SOL":
            return self.get_coin_transaction_price()
        else:
            return self.get_token_transaction_price()

    def get_account_balance_from_db(self, address) -> Decimal: 
        """"Return balance from DB, can be outdated"""
        try:
            pd = Accounts.query.filter_by(crypto = self.symbol, address = address).first()
        except Exception:
            db.session.rollback()
            raise Exception("There was exception during query to the database, try again later") 
        if not pd:  
            raise Exception(f"There is no account {address} related with {self.symbol} crypto in database") 
        else:
            return pd.amount

    def get_account_balance_from_fullnode(self, address) -> Decimal: 
        """Return account balance from fullnode based on symbol"""
        if self.symbol in config["TOKENS"][config["CURRENT_SOL_NETWORK"]]:
            return self.get_account_token_balance(address)
        else:
            return self.get_account_coin_balance(address)

    def check_address(self, address) -> bool:
        try:
            sol_addr = Pubkey.from_string(address)
        except:
            return False
        if sol_addr.is_on_curve() and  sol_addr.LENGTH == 32:
            return True
        else:
            return False

    def get_all_token_transfers(self, from_block, to_block) -> list:
        pass

    def get_all_token_dict(self) -> dict:
        """Return confirmed token addresses for current blockchain in dict address: symbol"""
        token_addresses ={}
        for symbol in config["TOKENS"][config["CURRENT_SOL_NETWORK"]]:
            token_addresses[config["TOKENS"][config["CURRENT_SOL_NETWORK"]][symbol]['token_address']] = symbol
        return token_addresses

    def get_transaction_symbols(self, transaction_json) -> list: 
        """Return transaction related symbols """
        list_accounts = get_all_accounts()
        symbols = []
        pre_token_balances =  transaction_json["meta"]["preTokenBalances"]
        post_token_balances =  transaction_json["meta"]["postTokenBalances"]
        symbols.append("SOL")
        if len(post_token_balances) != 0 or len(pre_token_balances) != 0:
            token_dict = self.get_all_token_dict()
            for balance in post_token_balances:
                if (balance['owner'] in list_accounts and 
                    balance["mint"] in token_dict.keys()):
                    symbols.append(token_dict[balance["mint"]])
        return symbols

