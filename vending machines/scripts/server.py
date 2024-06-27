import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from aiohttp import web
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
from solana.keypair import Keypair
from solana.publickey import PublicKey
import qrcode
from base58 import b58encode, b58decode
from cryptography.fernet import Fernet
import aioredis
from aiolimiter import AsyncLimiter
import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from prometheus_client import Counter, Histogram
from prometheus_async.aio.web import server_stats
import ssl

# Configuration
CONFIG_FILE = os.getenv("CONFIG_FILE", "server_config.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Config:
    def __init__(self, filename: str):
        with open(filename, 'r') as f:
            config = json.load(f)
        self.port: int = config['port']
        self.host: str = config['host']
        self.solana_network: str = config['solana_network']
        self.merchant_wallet: str = config['merchant_wallet']
        self.merchant_private_key: str = config['merchant_private_key']
        self.api_key: str = config['api_key']
        self.redis_url: str = config['redis_url']
        self.encryption_key: bytes = config['encryption_key'].encode()
        self.sentry_dsn: str = config['sentry_dsn']
        self.ssl_cert: str = config['ssl_cert']
        self.ssl_key: str = config['ssl_key']

config = Config(CONFIG_FILE)

# Initialize Sentry
sentry_sdk.init(
    dsn=config.sentry_dsn,
    integrations=[AioHttpIntegration()],
    traces_sample_rate=1.0
)

# Initialize Solana client
solana_client = AsyncClient(config.solana_network)

# Initialize Redis client
redis = aioredis.from_url(config.redis_url, decode_responses=True)

# Initialize Fernet for encryption
fernet = Fernet(config.encryption_key)

# Initialize rate limiter
rate_limiter = AsyncLimiter(10, 1)  # 10 requests per second

# Prometheus metrics
REQUESTS = Counter('server_requests_total', 'Total number of requests', ['endpoint'])
LATENCY = Histogram('server_request_latency_seconds', 'Request latency in seconds', ['endpoint'])

async def generate_payment(request: web.Request) -> web.Response:
    async with LATENCY.labels('generate_payment').time():
        REQUESTS.labels('generate_payment').inc()
        try:
            async with rate_limiter:
                data = await request.json()
                item_price = data['item_price']
                recipient_wallet = data['recipient_wallet']
                item_slot = data['item_slot']

                # Generate a unique memo for this transaction
                memo = b58encode(os.urandom(16)).decode('ascii')

                # Create a Solana payment URL
                payment_url = f"solana:{recipient_wallet}?amount={item_price}&reference={memo}&label=Vending%20Machine&message=Payment%20for%20item%20{item_slot}"

                # Generate QR code
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(payment_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Save QR code
                qr_code_path = f"qr_codes/{memo}.png"
                img.save(qr_code_path)

                # Store transaction details in Redis
                encrypted_details = fernet.encrypt(json.dumps({
                    'item_price': item_price,
                    'recipient_wallet': recipient_wallet,
                    'item_slot': item_slot,
                    'status': 'pending',
                    'created_at': datetime.utcnow().isoformat()
                }).encode())
                await redis.set(f"transaction:{memo}", encrypted_details, ex=3600)  # Expire after 1 hour

                return web.json_response({
                    'payment_url': payment_url,
                    'qr_code_path': qr_code_path,
                    'memo': memo
                })

        except ValueError as ve:
            logger.warning(f"Invalid input: {str(ve)}")
            return web.json_response({'error': 'Invalid input'}, status=400)
        except Exception as e:
            logger.error(f"Error generating payment: {str(e)}", exc_info=True)
            sentry_sdk.capture_exception(e)
            return web.json_response({'error': 'Internal server error'}, status=500)

async def verify_payment(request: web.Request) -> web.Response:
    async with LATENCY.labels('verify_payment').time():
        REQUESTS.labels('verify_payment').inc()
        try:
            async with rate_limiter:
                data = await request.json()
                memo = data['memo']

                # Retrieve transaction details from Redis
                encrypted_details = await redis.get(f"transaction:{memo}")
                if not encrypted_details:
                    return web.json_response({'status': 'not_found'})

                transaction_details = json.loads(fernet.decrypt(encrypted_details))

                # Check for the transaction on the Solana blockchain
                recent_blockhash = await solana_client.is_connected()
                
                # Search for the transaction with the given memo
                transactions = await solana_client.get_signatures_for_address(PublicKey(config.merchant_wallet))
                
                is_verified = False
                for tx in transactions:
                    transaction = await solana_client.get_confirmed_transaction(tx.signature)
                    if transaction and transaction.transaction.message.recent_blockhash == recent_blockhash:
                        # Check if the transaction amount matches the item price and memo
                        if (transaction.transaction.message.instructions[0].data == transaction_details['item_price'] and
                            transaction.transaction.message.instructions[1].data == memo):
                            is_verified = True
                            break

                if is_verified:
                    # Update transaction status in Redis
                    transaction_details['status'] = 'verified'
                    transaction_details['verified_at'] = datetime.utcnow().isoformat()
                    encrypted_details = fernet.encrypt(json.dumps(transaction_details).encode())
                    await redis.set(f"transaction:{memo}", encrypted_details, ex=3600)
                    return web.json_response({'status': 'verified'})
                else:
                    return web.json_response({'status': 'not_verified'})

        except ValueError as ve:
            logger.warning(f"Invalid input: {str(ve)}")
            return web.json_response({'error': 'Invalid input'}, status=400)
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}", exc_info=True)
            sentry_sdk.capture_exception(e)
            return web.json_response({'error': 'Internal server error'}, status=500)

async def get_transaction_status(request: web.Request) -> web.Response:
    async with LATENCY.labels('transaction_status').time():
        REQUESTS.labels('transaction_status').inc()
        try:
            async with rate_limiter:
                memo = request.query.get('memo')
                if not memo:
                    return web.json_response({'error': 'Memo is required'}, status=400)

                encrypted_details = await redis.get(f"transaction:{memo}")
                if not encrypted_details:
                    return web.json_response({'status': 'not_found'})

                transaction_details = json.loads(fernet.decrypt(encrypted_details))
                return web.json_response({'status': transaction_details['status']})

        except Exception as e:
            logger.error(f"Error getting transaction status: {str(e)}", exc_info=True)
            sentry_sdk.capture_exception(e)
            return web.json_response({'error': 'Internal server error'}, status=500)

async def validate_api_key(request: web.Request, handler: callable) -> web.Response:
    if request.headers.get('API-Key') != config.api_key:
        logger.warning(f"Invalid API key attempt from IP: {request.remote}")
        return web.json_response({'error': 'Invalid API key'}, status=401)
    return await handler(request)

async def cleanup_old_transactions() -> None:
    while True:
        try:
            current_time = datetime.utcnow()
            async for key in redis.scan_iter("transaction:*"):
                ttl = await redis.ttl(key)
                if ttl < 0:
                    await redis.delete(key)
            await asyncio.sleep(3600)  # Run every hour
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}", exc_info=True)
            sentry_sdk.capture_exception(e)
            await asyncio.sleep(60)  # Wait a minute before retrying

async def start_background_tasks(app: web.Application) -> None:
    app['cleanup_task'] = asyncio.create_task(cleanup_old_transactions())

async def cleanup_background_tasks(app: web.Application) -> None:
    app['cleanup_task'].cancel()
    await app['cleanup_task']

app = web.Application(middlewares=[server_stats])
app.router.add_post('/generate_payment', lambda r: validate_api_key(r, generate_payment))
app.router.add_post('/verify_payment', lambda r: validate_api_key(r, verify_payment))
app.router.add_get('/transaction_status', lambda r: validate_api_key(r, get_transaction_status))
app.router.add_get('/metrics', server_stats)
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)

if __name__ == '__main__':
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(config.ssl_cert, config.ssl_key)
    web.run_app(app, host=config.host, port=config.port, ssl_context=ssl_context)