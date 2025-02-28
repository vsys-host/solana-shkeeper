from typing import NamedTuple, List
from solana.rpc.api import Pubkey



class PYUSDTransferParams(NamedTuple):
    """Transfer token transaction params."""

    program_id: Pubkey
    """SPL Token program account."""
    source: Pubkey
    """Source account."""
    dest: Pubkey
    """Destination account."""
    owner: Pubkey
    """Owner of the source account."""
    mint: Pubkey
    """Mint of the token."""
    decimals: int
    """Decimals of the token."""
    amount: int
    """Number of tokens to transfer."""
    signers: List[Pubkey] = []
    """Signing accounts if `owner` is a multiSig."""