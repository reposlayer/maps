import requests
import time
from pymdb import MDBInterface, MDBDevice

SERVER_URL = "http://your-server-ip:5000"
MDB_PORT = "/dev/ttyUSB0"  # Example port, update as needed
API_KEY = "your_secure_api_key"  # Set your API key here

# Initialize MDB interface
mdb_interface = MDBInterface(MDB_PORT)
mdb_device = MDBDevice(mdb_interface)

def get_payment_url(item_price, item_slot):
    url = f"{SERVER_URL}/generate_payment"
    headers = {"API-Key": API_KEY}
    payload = {
        "item_price": item_price,
        "recipient_wallet": "YOUR_SOLANA_WALLET_ADDRESS",
        "item_slot": item_slot
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
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
    headers = {"API-Key": API_KEY}
    payload = {"memo": memo}
    try:
        response = requests.post(url, json=payload, headers=headers)
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

def dispense_item(slot):
    try:
        # Select and vend the item from the specified slot
        mdb_device.vend_request(slot)
        print(f"Dispensing item from slot {slot}...")
        time.sleep(3)  # Simulate item dispensing delay
        print("Item dispensed.")
    except Exception as e:
        print(f"Error dispensing item: {e}")

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
        print("\nAvailable items:")
        for slot, price in items.items():
            print(f"Slot: {slot}, Price: {price} SOL")

        selected_slot = input("Select an item slot (e.g., A1): ").strip().upper()
        if selected_slot not in items:
            print("Invalid slot selected. Try again.")
            continue

        item_price = items[selected_slot]
        print(f"Selected item price: {item_price} SOL")

        memo = get_payment_url(item_price, selected_slot)
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
            dispense_item(selected_slot)
        else:
            print("Payment verification failed. Please try again.")

        time.sleep(5)

if __name__ == '__main__':
    main()
