from flask import Flask, request, jsonify
from solana.rpc.api import Client
from solana_pay import create_payment_url
import qrcode
import os

app = Flask(__name__)
client = Client("https://api.mainnet-beta.solana.com")

# Directory to store QR codes
QR_CODE_DIR = 'qr_codes'
os.makedirs(QR_CODE_DIR, exist_ok=True)

@app.route('/generate_payment', methods=['POST'])
def generate_payment():
    data = request.json
    item_price = data['item_price']
    recipient_wallet = data['recipient_wallet']
    item_slot = data.get('item_slot', '')

    # Create a unique memo for the transaction
    memo = os.urandom(16).hex()

    # Create the payment request payload
    payment_request = {
        "recipient": recipient_wallet,
        "amount": item_price,
        "label": "Necta Vending",
        "message": f"Purchase at Necta Vending - Slot {item_slot}",
        "memo": memo
    }

    # Generate the payment URL using SolanaPay
    payment_url = create_payment_url(payment_request)

    # Generate a QR code from the payment URL
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(payment_url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    qr_code_path = os.path.join(QR_CODE_DIR, f'{memo}.png')
    img.save(qr_code_path)

    return jsonify({"payment_url": payment_url, "qr_code_path": qr_code_path, "memo": memo})

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    data = request.json
    memo = data['memo']

    # Query recent transactions to find the one with the correct memo
    result = client.get_signatures_for_address('YOUR_SOLANA_WALLET_ADDRESS', limit=10)

    for signature_info in result['result']:
        transaction = client.get_confirmed_transaction(signature_info['signature'])
        if transaction['result']:
            for instruction in transaction['result']['transaction']['message']['instructions']:
                if 'data' in instruction and memo in instruction['data']:
                    return jsonify({"status": "verified"})

    return jsonify({"status": "not_verified"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
