import requests
import prometheus_client
from prometheus_client import generate_latest, Info, Gauge


from . import metrics_blueprint
from ..config import config
from ..models import Settings, db
from ..coin import Coin


prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)


def get_latest_release(name):
    if name == 'solana':
        url = 'https://api.github.com/repos/anza-xyz/agave/releases/latest'
    else:
        return False
    data = requests.get(url).json()
    version = data["tag_name"].split('v')[1]
    info = { key:data[key] for key in ["name", "tag_name", "published_at"] }
    info['version'] = version
    return info


def get_all_metrics():
    inst = Coin("SOL")
    last_slot = inst.get_slot()
    if last_slot:
        response = {}
        last_fullnode_block_number = int(last_slot)
        response['last_fullnode_block_number'] = last_fullnode_block_number
        response['last_fullnode_block_timestamp'] = inst.get_block_time(last_slot)
        solana_version = inst.client.get_version().value.solana_core
        response['solana_version'] = solana_version
        pd = Settings.query.filter_by(name = 'last_block').first()
        last_checked_block_number = int(pd.value)
        response['solana_wallet_last_block'] = last_checked_block_number
        response['solana_wallet_last_block_timestamp'] = inst.get_block_time(last_checked_block_number)
        response['solana_fullnode_status'] = 1
        return response
    else:
        response['solana_fullnode_status'] = 0
        return response

solana_last_release = Info(
    'solana_last_release',
    'Version of the latest release from https://github.com/anza-xyz/agave/releases'
)

solana_last_release.info(get_latest_release('solana'))
solana_fullnode_version = Info('solana_fullnode_version', 'Current solana version in use')
solana_fullnode_status = Gauge('solana_fullnode_status', 'Connection status to solana fullnode')
solana_fullnode_last_block = Gauge('solana_fullnode_last_block', 'Last block loaded to the fullnode', )
solana_wallet_last_block = Gauge('solana_wallet_last_block', 'Last checked block ') 
solana_fullnode_last_block_timestamp = Gauge('solana_fullnode_last_block_timestamp', 'Last block timestamp loaded to the fullnode', )
solana_wallet_last_block_timestamp = Gauge('solana_wallet_last_block_timestamp', 'Last checked block timestamp')


@metrics_blueprint.get("/metrics")
def get_metrics():
    response = get_all_metrics()
    if response['solana_fullnode_status'] == 1:
        solana_fullnode_version.info({'version': response['solana_version']})
        solana_fullnode_last_block.set(response['last_fullnode_block_number'])
        solana_fullnode_last_block_timestamp.set(response['last_fullnode_block_timestamp'])
        solana_wallet_last_block.set(response['solana_wallet_last_block'])
        solana_wallet_last_block_timestamp.set(response['solana_wallet_last_block_timestamp'])
        solana_fullnode_status.set(response['solana_fullnode_status'])
    else:
        solana_fullnode_status.set(response['solana_fullnode_status'])

    return generate_latest().decode()