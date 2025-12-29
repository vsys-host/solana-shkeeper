FROM python:3.13

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fix some solana RPC nodes reply to avoid solders.SerdeJSONError

RUN sed -i '96i\    raw = raw.replace("\\\"readonly\\\":null", "\\\"readonly\\\":[]")' /usr/local/lib/python3.13/site-packages/solana/rpc/providers/core.py
RUN sed -i '97i\    raw = raw.replace("\\\"writable\\\":null", "\\\"writable\\\":[]")' /usr/local/lib/python3.13/site-packages/solana/rpc/providers/core.py
