
from flask import current_app, g

from .. import events
from ..config import config
from ..models import Settings
from ..coin import Coin, get_all_accounts
from . import api
from app import create_app

app = create_app()
app.app_context().push()


@api.post("/generate-address")
def generate_new_address(): 
    inst = Coin(g.symbol)
    address = inst.create_regular_wallet()
    return {'status': 'success', 'address': address}


@api.post('/balance')
def get_balance():
    crypto_str = str(g.symbol)   
    inst = Coin(crypto_str)

    if crypto_str == "SOL":
        balance = inst.get_fee_deposit_coin_balance()
    elif crypto_str in config['TOKENS'][config["CURRENT_SOL_NETWORK"]]:
        balance = inst.get_fee_deposit_token_balance()
    else:
        return {'status': 'error', 'msg': 'token is not defined in config'}
    return {'status': 'success', 'balance': balance}


@api.post('/status')
def get_status():
    with app.app_context():
        pd = Settings.query.filter_by(name = 'last_block').first()
    
    last_checked_block_number = int(pd.value)
    inst = Coin("SOL")
    timestamp = inst.get_block_time(last_checked_block_number)
    return {'status': 'success', 'last_block_timestamp': timestamp}


@api.post('/transaction/<txid>')
def get_transaction(txid):
    inst = Coin(g.symbol)
    return inst.parse_transaction(txid)


@api.post('/dump')
def dump():
    w = Coin("SOL")
    all_wallets = w.get_dump()
    return all_wallets


@api.post('/fee-deposit-account')
def get_fee_deposit_account():
    coin_instance = Coin(g.symbol)
    return {'account': coin_instance.get_fee_deposit_account_address(), 
            'balance': coin_instance.get_fee_deposit_coin_balance()}
 

@api.post('/get_all_addresses')
def get_all_addresses():
    all_addresses_list = get_all_accounts()    
    return all_addresses_list


    
