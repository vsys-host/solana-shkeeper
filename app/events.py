from concurrent.futures import ThreadPoolExecutor
import time
import json

from .models import Settings, db
from .config import config
from .logging import logger
from .coin import Coin, get_all_accounts


def log_loop(last_checked_block, check_interval):
    from .tasks import walletnotify_shkeeper, drain_account
    from app import create_app
    app = create_app()
    app.app_context().push()

    coin = Coin("SOL")

    while True:       
        last_block = coin.get_slot()
        if last_checked_block == '' or last_checked_block is None:
            last_checked_block = last_block	
        blocks_list = coin.get_blocks(last_checked_block, last_block)
        our_addresses = set(get_all_accounts()) 
        if last_checked_block > last_block:
            logger.exception(f'Last checked block {last_checked_block} is bigger than last block {last_block} in blockchain')
        elif len(blocks_list) > int(config['EVENTS_MIN_DIFF_TO_RUN_PARALLEL']):
            def check_in_parallel(block):
                buf = coin.get_block(block)
                for transaction in buf.transactions:
                    symbols = []
                    for address in transaction.transaction.message.account_keys:
                        if str(address) in our_addresses:
                            logger.warning("Found related transaction")
                            transaction_json = json.loads(transaction.to_json())
                            logger.warning(transaction_json) 
                            # check if amount of transactions is 0, if yes the do not notify about this trx
                            pre_coin_balances =  transaction_json["meta"]["preBalances"]
                            post_coin_balances =  transaction_json["meta"]["postBalances"]
                            diff_balances = []
                            for i in range(len(pre_coin_balances)):
                                diff_balances.append(int(post_coin_balances[i]) - int(pre_coin_balances[i]))
                            for i in range(len(transaction.transaction.message.account_keys)):
                                if address == transaction.transaction.message.account_keys[i]:
                                    logger.warning(f"Address {address} in address_keys")
                                    if diff_balances[i] > 0 or diff_balances[i] < 0:
                                        logger.warning(f"Balance difference is not zero: {diff_balances[i]} notify")
                                        symbols.append("SOL")
                                        if diff_balances[i] > 0:
                                            drain_account.delay('SOL', str(address))
                                    else:
                                        logger.warning(f"Balance difference is {diff_balances[i]} skip it")
                    for balance in transaction.meta.post_token_balances:
                        if str(balance.owner) in our_addresses:
                            logger.warning("Found related transaction")
                            transaction_json = json.loads(transaction.to_json())
                            logger.warning(transaction_json) 
                            pre_token_balances =  transaction_json["meta"]["preTokenBalances"]
                            post_token_balances =  transaction_json["meta"]["postTokenBalances"]
                            if len(post_token_balances) != 0 or len(pre_token_balances) != 0:
                                token_dict = coin.get_all_token_dict()
                                for balance in post_token_balances:
                                    if (balance['owner'] in our_addresses and 
                                        balance["mint"] in token_dict.keys()):
                                        symbols.append(token_dict[balance["mint"]])
                                        drain_account.delay(token_dict[balance["mint"]], balance['owner'])
                    symbols_set = set(symbols)
                    for symbol in symbols_set:
                        walletnotify_shkeeper.delay(symbol, transaction_json['transaction']['signatures'][0])
                return 1
            with ThreadPoolExecutor(max_workers=config['EVENTS_MAX_THREADS_NUMBER']) as executor:
                try:
                    for j in range((len(blocks_list) - 1) // int(config['EVENTS_MAX_THREADS_NUMBER'])):
                        blocks = []
                        for i in range(int(config['EVENTS_MAX_THREADS_NUMBER'])):
                            blocks.append(blocks_list[1 + i + (j * int(config['EVENTS_MAX_THREADS_NUMBER']))])
                        start_time = time.time()
                        logger.warning(f'Working on {blocks[0]} - {blocks[-1]}')
                        results = list(executor.map(check_in_parallel, blocks))
                        logger.warning(f'Block chunk {blocks[0]} - {blocks[-1]} processed for {time.time() - start_time} seconds')
                        if results and all(results):
                            last_checked_block = blocks[-1] #last_checked_block = blocks[-1]
                            pd = Settings.query.filter_by(name = "last_block").first()
                            pd.value = last_checked_block
                            with app.app_context():
                                db.session.add(pd)
                                db.session.commit()
                                db.session.close()
                        else:
                            logger.warning(f"Some blocks failed, retrying chunk {blocks[0]} - {blocks[-1]}")
                except Exception as e:
                    sleep_sec = 6
                    logger.warning(f"Exception in main block scanner loop: {e}")
                    logger.warning(f"Waiting {sleep_sec} seconds before retry.")
                    time.sleep(sleep_sec)
        else:
            logger.warning("Waiting for a new slots")
            time.sleep(check_interval)


def events_listener():

    from app import create_app

    app = create_app()
    app.app_context().push()
    coin_inst = Coin("SOL")
    if (not Settings.query.filter_by(name = "last_block").first()) and (config['LAST_BLOCK_LOCKED'].lower() != 'true'):
        logger.warning("Changing last_block to a last block on a fullnode, because cannot get it in DB")
        with app.app_context():
            db.session.add(Settings(name = "last_block", 
                                    value = coin_inst.get_slot()))
            db.session.commit()
            db.session.close() 
            db.session.remove()
            db.engine.dispose()
    
    while True:
        try:
            pd = Settings.query.filter_by(name = "last_block").first()
            last_checked_block = int(pd.value)
            log_loop(last_checked_block, int(config["CHECK_NEW_BLOCK_EVERY_SECONDS"]))
        except BaseException as e:
            sleep_sec = 60
            logger.exception(f"Exception in main block scanner loop: {e}")
            logger.warning(f"Waiting {sleep_sec} seconds before retry.")           
            time.sleep(sleep_sec)


