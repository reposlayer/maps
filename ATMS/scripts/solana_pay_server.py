import os
import time
import requests
from flask import Flask, request, jsonify, render_template
from flask_httpauth import HTTPBasicAuth
from solana.publickey import PublicKey
from solana.rpc.api import Client
from solana.transaction import Transaction, TransactionInstruction
from solana.rpc.commitment import Confirmed
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Initialize Solana client
client = Client("https://api.mainnet-beta.solana.com")

# Initialize Flask app and authentication
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
auth = HTTPBasicAuth()

# Setup logging
logging.basicConfig(filename='atm.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment variables
RECEIVER_ADDRESS = os.getenv('ATM_PUBLIC_KEY')
BASIC_AUTH_USERNAME = os.getenv('BASIC_AUTH_USERNAME')
BASIC_AUTH_PASSWORD = os.getenv('BASIC_AUTH_PASSWORD')

# User authentication
@auth.verify_password
def verify_password(username, password):
    if username == BASIC_AUTH_USERNAME and password == BASIC_AUTH_PASSWORD:
        return username

@app.route('/generate_qr', methods=['GET'])
@auth.login_required
def generate_qr():
    try:
        amount = request.args.get('amount')
        if not amount:
            return jsonify({"error": "Amount is required"}), 400

        # Generate Solana Pay URL
        solana_pay_url = f"solana:{RECEIVER_ADDRESS}?amount={amount}&label=ATM%20Payment&message=Payment%20for%20services"

        logging.info(f'Generated QR for amount: {amount} SOL')
        return render_template('qr_code.html', solana_pay_url=solana_pay_url)
    except Exception as e:
        logging.error(f'Error generating QR: {e}')
        return jsonify({"error": "Internal server error"}), 500

@app.route('/check_payment', methods=['POST'])
@auth.login_required
def check_payment():
    try:
        data = request.get_json()
        amount = data.get('amount')
        if not amount:
            return jsonify({"error": "Amount is required"}), 400

        amount_lamports = int(float(amount) * 1e9)

        # Check for recent transactions
        response = client.get_confirmed_signature_for_address2(PublicKey(RECEIVER_ADDRESS), limit=10, commitment=Confirmed)
        for tx in response['result']:
            tx_details = client.get_confirmed_transaction(tx['signature'], commitment=Confirmed)
            pre_balances = tx_details['result']['meta']['preBalances']
            post_balances = tx_details['result']['meta']['postBalances']

            if (post_balances[0] - pre_balances[0]) >= amount_lamports:
                logging.info(f'Payment received: {amount} SOL')
                return jsonify({"status": "Payment received"}), 200

        logging.info('Payment not received')
        return jsonify({"status": "Payment not received"}), 404
    except Exception as e:
        logging.error(f'Error checking payment: {e}')
        return jsonify({"error": "Internal server error"}), 500

@app.route('/webhook', methods=['POST'])
@auth.login_required
def webhook():
    try:
        data = request.get_json()
        # Process webhook data
        logging.info(f'Webhook received: {data}')
        return jsonify({"status": "Webhook received"}), 200
    except Exception as e:
        logging.error(f'Error in webhook: {e}')
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
