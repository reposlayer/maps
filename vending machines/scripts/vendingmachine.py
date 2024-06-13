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
