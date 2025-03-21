import decimal
import time
import copy
import requests

from celery.utils.log import get_task_logger
import requests as rq

from . import celery
from .config import config
from .models import Accounts, db
from .coin import Coin, get_all_accounts
from .utils import skip_if_running

logger = get_task_logger(__name__)


@celery.task()
def make_multipayout(symbol, payout_list, fee):
    coint_inst = Coin(symbol)
    for transfer in payout_list:
        if not coint_inst.check_address(transfer['dest']):
            raise Exception(f"Bad destination address in {transfer}")
        try:
            transfer['amount'] = decimal.Decimal(transfer['amount'])
        except Exception as e:
            raise Exception(f"Bad amount in {transfer}: {e}")
        if transfer['amount'] <= 0:
            raise Exception(f"Payout amount should be a positive number: {transfer}")
    payout_results = coint_inst.make_multipayout(payout_list, fee)
    post_payout_results.delay(payout_results, symbol)
    return payout_results    


@celery.task()
def post_payout_results(data, symbol):
    while True:
        try:
            return requests.post(
                f'http://{config["SHKEEPER_HOST"]}/api/v1/payoutnotify/{symbol}',
                headers={'X-Shkeeper-Backend-Key': config['SHKEEPER_KEY']},
                json=data,
            )
        except Exception as e:
            logger.exception(f'Shkeeper payout notification failed: {e}')
            time.sleep(10)


@celery.task()
def refresh_balances():
    updated = 0

    refresh_inst = Coin("SOL")

    try:
        from app import create_app
        app = create_app()
        app.app_context().push()

        list_acccounts = get_all_accounts()
        for account in list_acccounts:
            try:
                pd = Accounts.query.filter_by(address = account).first()
            except Exception:
                db.session.rollback()
                raise Exception("There was exception during query to the database, try again later")

            acc_balance = decimal.Decimal(refresh_inst.get_account_coin_balance(account))

            if Accounts.query.filter_by(address = account, crypto = "SOL").first():
                pd = Accounts.query.filter_by(address = account, crypto = "SOL").first()            
                pd.amount = decimal.Decimal(acc_balance)                     
                with app.app_context():
                    db.session.add(pd)
                    db.session.commit()
                    db.session.close()
            
            have_tokens = False
                
            for token in config['TOKENS'][config["CURRENT_SOL_NETWORK"]]:
                token_instance = Coin(token)
                if Accounts.query.filter_by(address = account, crypto = token).first():
                    pd = Accounts.query.filter_by(address = account, crypto = token).first()
                    balance = token_instance.get_account_balance_from_fullnode(account)
                    pd.amount = balance
                    
                    with app.app_context():
                        db.session.add(pd)
                        db.session.commit() 
                        db.session.close()  
                    if balance >= decimal.Decimal(config['MIN_TOKEN_TRANSFER_THRESHOLD']):
                        have_tokens = copy.deepcopy(token)
                    
            if have_tokens in config['TOKENS'][config["CURRENT_SOL_NETWORK"]].keys():
                drain_account.delay(have_tokens, account) 
            else:
                if acc_balance >= decimal.Decimal(config['MIN_TRANSFER_THRESHOLD']):
                    drain_account.delay("SOL", account)        
    
            updated = updated + 1                
    
            with app.app_context():
                db.session.add(pd)
                db.session.commit()
                db.session.close()
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()  
 
    return updated


@celery.task(bind=True)
@skip_if_running
def drain_account(self, symbol, account):
    logger.warning(f"Start draining from account {account} crypto {symbol}")
    inst = Coin(symbol)
    destination = inst.get_fee_deposit_account_address()
    if destination == account:
        logger.warning("Fee-deposit account, skip draining")
        return False
    results = inst.drain_account(account, destination)
    return results


@celery.task(bind=True)
@skip_if_running
def create_fee_deposit_account(self):
    logger.warning("Creating fee-deposit account")
    inst = Coin("SOL")
    inst.set_fee_deposit_account()    
    return True
        

@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Update cached account balances
    sender.add_periodic_task(int(config['UPDATE_TOKEN_BALANCES_EVERY_SECONDS']), refresh_balances.s())


