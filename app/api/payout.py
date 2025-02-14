from decimal import Decimal

from flask import g, request
from flask import current_app as app

from .. import celery
from ..tasks import make_multipayout 
from ..utils import BaseConverter
from . import api
from ..coin import Coin


@api.post('/calc-tx-fee/<decimal:amount>')
def calc_tx_fee(amount):
    coin_inst = Coin(g.symbol)
    fee = coin_inst.get_transaction_price()
    return {'accounts_num': 1, 'fee': float(fee)}


@api.post('/multipayout')
def multipayout():    
    try:
        payout_list = request.get_json(force=True)
    except Exception as e:
        raise Exception(f"Bad JSON in payout list: {e}")
    if not payout_list:
        raise Exception(f"Payout list is empty!")
    task = (make_multipayout.s(g.symbol, payout_list, 0)).apply_async()
    return{'task_id': task.id}
    

@api.post('/payout/<to>/<decimal:amount>')
def payout(to, amount):
    payout_list = [{ "dest": to, "amount": amount }]
    task = (make_multipayout.s(g.symbol, payout_list, 0)).apply_async()        
    return {'task_id': task.id}


@api.post('/task/<id>')
def get_task(id):
    task = celery.AsyncResult(id)
    if isinstance(task.result, Exception):
        return {'status': task.status, 'result': str(task.result)}
    return {'status': task.status, 'result': task.result}

