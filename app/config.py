import os
from decimal import Decimal

config = {
    'FULLNODE_URL': os.environ.get('FULLNODE_URL', 'http://solana:8545'),
    'FULLNODE_TIMEOUT': os.environ.get('FULLNODE_TIMEOUT', '60'),
    'CHECK_NEW_BLOCK_EVERY_SECONDS': os.environ.get('CHECK_NEW_BLOCK_EVERY_SECONDS',2),
    'EVENTS_MAX_THREADS_NUMBER': int(os.environ.get('EVENTS_MAX_THREADS_NUMBER', 10)),
    'EVENTS_MIN_DIFF_TO_RUN_PARALLEL': int(os.environ.get('EVENTS_MIN_DIFF_TO_RUN_PARALLEL', 30)), #min difference between last checked block and last block
    'CURRENT_SOL_NETWORK': os.environ.get('CURRENT_SOL_NETWORK','devnet'),
    'TOKENS': {
        'main': {
            'SOLANA-USDT': {
                'token_address': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
            },
            'SOLANA-USDC': {
                'token_address': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            },
            'SOLANA-PYUSD': {
                'token_address': '2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo',
            },
        },
        'devnet': {
            'SOLANA-USDT': {
                'token_address': 'GCRaxtuxSybvBCYtwT45DCNm2sXP4SKrowhQ1TPabE1', # https://solana-faucet-dev.euroe.com/
            },
            'SOLANA-USDC': {
                'token_address': 'Gh9ZwEmdLJ8DscKNTkTqPbNwLNNBjuSzaG9Vp2KGtKJr', # https://spl-token-faucet.com/
            },
            'SOLANA-PYUSD': {
                'token_address': 'CXk2AMBfi3TwaEL2468s6zP8xq9NxTXjp9gjMgzeUynM', # https://faucet.paxos.com/
            },
        },
    },   
    'DEBUG': os.environ.get('DEBUG', False),
    'LOGGING_LEVEL': os.environ.get('LOGGING_LEVEL', 'INFO'),
    'SQLALCHEMY_DATABASE_URI' : os.environ.get('SQLALCHEMY_DATABASE_URI', "mariadb+pymysql://root:shkeeper@mariadb/solana-shkeeper?charset=utf8mb4"),
    'UPDATE_TOKEN_BALANCES_EVERY_SECONDS': int(os.environ.get('UPDATE_TOKEN_BALANCES_EVERY_SECONDS', 3600)),
    'API_USERNAME': os.environ.get('SOL_USERNAME', 'shkeeper'),
    'API_PASSWORD': os.environ.get('SOL_PASSWORD', 'shkeeper'),
    'SHKEEPER_KEY': os.environ.get('SHKEEPER_BACKEND_KEY', 'shkeeper'),
    'SHKEEPER_HOST': os.environ.get('SHKEEPER_HOST', 'shkeeper:5000'),
    'REDIS_HOST': os.environ.get('REDIS_HOST', 'localhost'),
    'BASE_TX_FEE':  int(os.environ.get('BASE_TX_FEE', '5000')), # in lamports
    'ATA_ACCOUNT_SIZE':  int(os.environ.get('ATA_ACCOUNT_SIZE', '165')), # in bytes
    'COMPUTE_UNIT_LIMIT': int(os.environ.get('COMPUTE_UNIT_LIMIT', '1000000')), # prioritization fee is calculated by multiplying its compute unit limit by the compute unit price (measured in micro-lamports).
    'COMPUTE_UNIT_PRICE':  int(os.environ.get('COMPUTE_UNIT_PRICE', '1000')),  # in micro-lamports
    'LAST_BLOCK_LOCKED': os.environ.get('LAST_BLOCK_LOCKED', 'TRUE'),
    'MIN_TRANSFER_THRESHOLD': Decimal(os.environ.get('MIN_TRANSFER_THRESHOLD', '0.002')), # in SOL
    'MIN_TOKEN_TRANSFER_THRESHOLD': Decimal(os.environ.get('MIN_TOKEN_TRANSFER_THRESHOLD', '0.5')),
    'MAX_SOL_TRANSFERS_IN_TRANSACTION': int(os.environ.get('MAX_SOL_TRANSFERS_IN_TRANSACTION', 50)), # limit of transfers in one transaction (https://solana.com/uk/docs/core/transactions)
    'MAX_TOKEN_TRANSFERS_IN_TRANSACTION': int(os.environ.get('MAX_TOKEN_TRANSFERS_IN_TRANSACTION', 55)), 
}


def get_token_address(symbol):
    return config["TOKENS"][config["CURRENT_SOL_NETWORK"]][symbol]["token_address"]
