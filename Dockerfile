FROM python:3

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i '258i\        token_program_id = None,' /usr/local/lib/python3.13/site-packages/spl/token/client.py
RUN sed -i -e 's/owner, skip_confirmation, self._conn.commitment/owner, skip_confirmation, self._conn.commitment, token_program_id/g' /usr/local/lib/python3.13/site-packages/spl/token/client.py

RUN sed -i '197i\        token_program_id: Pubkey,' /usr/local/lib/python3.13/site-packages/spl/token/core.py
RUN sed -i -e 's/spl_token.create_associated_token_account(payer=self.payer.pubkey(), owner=owner, mint=self.pubkey)/spl_token.create_associated_token_account(payer=self.payer.pubkey(), owner=owner, mint=self.pubkey, token_program_id=token_program_id)/g' /usr/local/lib/python3.13/site-packages/spl/token/core.py

RUN sed -i -e 's/def create_associated_token_account(payer: Pubkey, owner: Pubkey, mint: Pubkey) -> Instruction:/def create_associated_token_account(payer: Pubkey, owner: Pubkey, mint: Pubkey, token_program_id: Pubkey) -> Instruction:/g' /usr/local/lib/python3.13/site-packages/spl/token/instructions.py
RUN sed -i -e 's/pubkey=TOKEN_PROGRAM_ID/pubkey=token_program_id/g' /usr/local/lib/python3.13/site-packages/spl/token/instructions.py

RUN sed -i -e 's/associated_token_address = get_associated_token_address(owner, mint)/associated_token_address = get_associated_token_address(owner, mint, token_program_id)/g' /usr/local/lib/python3.13/site-packages/spl/token/instructions.py
RUN sed -i -e 's/def get_associated_token_address(owner: Pubkey, mint: Pubkey) -> Pubkey:/def get_associated_token_address(owner: Pubkey, mint: Pubkey, token_program_id: Pubkey) -> Pubkey:/g' /usr/local/lib/python3.13/site-packages/spl/token/instructions.py
RUN sed -i -e 's/        seeds=\[bytes(owner), bytes(TOKEN_PROGRAM_ID), bytes(mint)\],/        seeds=\[bytes(owner), bytes(token_program_id), bytes(mint)\],/g' /usr/local/lib/python3.13/site-packages/spl/token/instructions.py


