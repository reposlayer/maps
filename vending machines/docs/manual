Table of Contents

    Introduction
    System Overview
    Getting Started
        Setting Up the Backend Server
        Setting Up the Vending Machine Client
    Using the Vending Machine
        Selecting an Item
        Making a Payment
        Verifying Payment and Dispensing
    Maintenance and Troubleshooting
        Regular Maintenance
        Troubleshooting Common Issues
    Advanced Configuration
    Security Best Practices
    Frequently Asked Questions (FAQs)
    Support and Contact Information

Introduction

Welcome to Snacktastic SolanaVend! This user manual provides comprehensive instructions on how to set up, use, maintain, and troubleshoot the vending machine integrated with SolanaPay. The system allows users to make payments using Solana cryptocurrency and enjoy a seamless vending experience.
System Overview

Snacktastic SolanaVend consists of two main components:

    Backend Server: Manages payment request generation, QR code generation, and transaction verification.
    Vending Machine Client: Interacts with the backend server to generate payment requests, display QR codes, verify payments, and dispense items.

Getting Started
Setting Up the Backend Server
Requirements

    A server with Python 3.x installed.
    Internet connectivity.
    The following Python libraries: Flask, Solana, QRCode, Requests.

Installation Steps

    Install Python Libraries:

    bash

pip install flask solana qrcode[pil] requests

Create the Server Script:
Save the following script as server.py:

python

    from flask import Flask, request, jsonify
    from solana.rpc.api import Client
    from solana_pay import create_payment_url
    import qrcode
    import os

    app = Flask(__name__)
    client = Client("https://api.mainnet-beta.solana.com")

    @app.route('/generate_payment', methods=['POST'])
    def generate_payment():
        data = request.json
        item_price = data['item_price']
        recipient_wallet = data['recipient_wallet']
        
        memo = os.urandom(16).hex()

        payment_request = {
            "recipient": recipient_wallet,
            "amount": item_price,
            "label": "Necta Vending",
            "message": "Purchase at Necta Vending",
            "memo": memo
        }
        
        payment_url = create_payment_url(payment_request)
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(payment_url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        qr_code_path = f'qr_codes/{memo}.png'
        img.save(qr_code_path)

        return jsonify({"payment_url": payment_url, "qr_code_path": qr_code_path, "memo": memo})

    @app.route('/verify_payment', methods=['POST'])
    def verify_payment_status():
        data = request.json
        memo = data['memo']
        
        result = client.get_signatures_for_address('YOUR_SOLANA_WALLET_ADDRESS', limit=10)
        
        for signature_info in result['result']:
            transaction = client.get_confirmed_transaction(signature_info['signature'])
            for instruction in transaction['result']['transaction']['message']['instructions']:
                if 'data' in instruction and memo in instruction['data']:
                    return jsonify({"status": "verified"})
        
        return jsonify({"status": "not_verified"}), 404

    if __name__ == '__main__':
        os.makedirs('qr_codes', exist_ok=True)
        app.run(host='0.0.0.0', port=5000)

Running the Server

    Start the Server:

    bash

    python server.py

    Verify Server Running: Ensure the server is running by accessing http://your-server-ip:5000 from a browser or using a tool like curl.

Setting Up the Vending Machine Client
Requirements

    A vending machine with Python 3.x installed.
    Internet connectivity.
    The Requests library for Python.

Installation Steps

    Install Python Libraries:

    bash

pip install requests

Create the Client Script:
Save the following script as vending_machine.py:

python

    import requests
    import time

    SERVER_URL = "http://your-server-ip:5000"

    def get_payment_url(item_price):
        url = f"{SERVER_URL}/generate_payment"
        payload = {
            "item_price": item_price,
            "recipient_wallet": "YOUR_SOLANA_WALLET_ADDRESS"
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            print(f"Payment URL: {data['payment_url']}")
            print(f"QR Code saved at: {data['qr_code_path']}")
            return data['memo']
        except requests.RequestException as e:
            print(f"Error generating payment URL: {e}")
            return None

    def verify_payment(memo):
        url = f"{SERVER_URL}/verify_payment"
        payload = {"memo": memo}
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            if result['status'] == "verified":
                print("Payment verified")
                return True
            else:
                print("Payment not found or not confirmed")
                return False
        except requests.RequestException as e:
            print(f"Error verifying payment: {e}")
            return False

    def main():
        items = {
            "A1": 0.5,
            "A2": 0.75,
            "A3": 1.0,
            "B1": 1.25,
            "B2": 1.5,
            "B3": 2.0
        }

        while True:
            print("Available items:")
            for slot, price in items.items():
                print(f"Slot: {slot}, Price: {price} SOL")

            selected_slot = input("Select an item slot (e.g., A1): ").strip().upper()
            if selected_slot not in items:
                print("Invalid slot selected. Try again.")
                continue

            item_price = items[selected_slot]
            print(f"Selected item price: {item_price} SOL")

            memo = get_payment_url(item_price)
            if not memo:
                continue

            print("Scan the QR code with your Solana wallet to make the payment.")

            payment_verified = False
            for _ in range(12):
                time.sleep(5)
                if verify_payment(memo):
                    payment_verified = True
                    break

            if payment_verified:
                print(f"Dispensing item from slot {selected_slot}...")
                time.sleep(3)
                print("Item dispensed.")
            else:
                print("Payment verification failed.")

            time.sleep(5)

    if __name__ == '__main__':
        main()

Running the Client Script

    Start the Client Script:

    bash

    python vending_machine.py

Using the Vending Machine
Selecting an Item

    Item Selection:
        On the vending machine interface, the user is presented with a list of available items and their corresponding slots.
        The user selects an item by entering the slot number (e.g., A1).

Making a Payment

    Payment URL Generation:
        Upon item selection, the client script requests a payment URL and QR code from the backend server.
        The user scans the QR code with their Solana wallet to initiate the payment.

Verifying Payment and Dispensing

    Payment Verification:
        The system continuously polls the backend server to verify the transaction status using the memo identifier.
        Once the payment is verified, the vending machine dispenses the selected item.
        If the payment is not verified within a minute, the transaction is marked as failed.

Maintenance and Troubleshooting
Regular Maintenance

    Check System Updates: Regularly check for updates to the backend server and client script to ensure compatibility and security.
    Monitor Performance: Use monitoring tools to track system performance and identify potential issues.

Troubleshooting Common Issues

    Payment Verification Fails:
        Ensure the backend server is running and accessible.
        Check the Solana blockchain for the transaction status.
    QR Code Not Displayed:
        Verify the connection between the vending machine and the backend server.
        Check for errors in the client script.