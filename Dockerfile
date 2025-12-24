FROM python:3

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fix incorrect program ID in create_associated_token_account for TOKEN_2022_PROGRAM_ID in https://github.com/michaelhly/solana-py v0.36.0

RUN sed -i -e 's/owner, skip_confirmation, self._conn.commitment, recent_blockhash_to_use/owner, skip_confirmation, self._conn.commitment, recent_blockhash_to_use, token_program_id=self.program_id/g' /usr/local/lib/python3.13/site-packages/spl/token/client.py

RUN sed -i -e 's/self, owner: Pubkey, skip_confirmation: bool, commitment: Commitment, recent_blockhash: Blockhash/self, owner: Pubkey, skip_confirmation: bool, commitment: Commitment, recent_blockhash: Blockhash,token_program_id: Pubkey/g' /usr/local/lib/python3.13/site-packages/spl/token/core.py

RUN sed -i -e 's/ix = spl_token.create_associated_token_account(payer=self.payer.pubkey(), owner=owner, mint=self.pubkey)/ix = spl_token.create_associated_token_account(payer=self.payer.pubkey(), owner=owner, mint=self.pubkey,token_program_id=token_program_id)/g' /usr/local/lib/python3.13/site-packages/spl/token/core.py

