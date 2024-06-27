import requests
import time
import logging
import asyncio
import json
from pymdb import MDBInterface, MDBDevice
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

# Configuration
CONFIG_FILE = "config.json"

@dataclass
class Config:
    server_url: str
    mdb_port: str
    api_key: str
    solana_wallet_address: str
    payment_verification_timeout: int
    payment_verification_interval: int

    @classmethod
    def load_from_file(cls, filename: str) -> 'Config':
        with open(filename, 'r') as f:
            config_data = json.load(f)
        return cls(**config_data)

config = Config.load_from_file(CONFIG_FILE)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Item:
    slot: str
    price: float
    name: str
    quantity: int

class PaymentGateway(ABC):
    @abstractmethod
    async def get_payment_url(self, item: Item) -> Optional[str]:
        pass

    @abstractmethod
    async def verify_payment(self, memo: str) -> bool:
        pass

class SolanaPaymentGateway(PaymentGateway):
    def __init__(self, config: Config):
        self.config = config

    async def get_payment_url(self, item: Item) -> Optional[str]:
        url = f"{self.config.server_url}/generate_payment"
        headers = {"API-Key": self.config.api_key}
        payload = {
            "item_price": item.price,
            "recipient_wallet": self.config.solana_wallet_address,
            "item_slot": item.slot
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.info(f"Payment URL: {data['payment_url']}")
                    logger.info(f"QR Code saved at: {data['qr_code_path']}")
                    return data['memo']
        except aiohttp.ClientError as e:
            logger.error(f"Error generating payment URL: {e}")
            return None

    async def verify_payment(self, memo: str) -> bool:
        url = f"{self.config.server_url}/verify_payment"
        headers = {"API-Key": self.config.api_key}
        payload = {"memo": memo}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    result = await response.json()
                    if result['status'] == "verified":
                        logger.info("Payment verified")
                        return True
                    else:
                        logger.info("Payment not found or not confirmed")
                        return False
        except aiohttp.ClientError as e:
            logger.error(f"Error verifying payment: {e}")
            return False

class Inventory:
    def __init__(self, items: Dict[str, Item]):
        self.items = items

    def get_item(self, slot: str) -> Optional[Item]:
        return self.items.get(slot)

    def update_quantity(self, slot: str, quantity: int):
        if slot in self.items:
            self.items[slot].quantity = quantity

    def list_items(self) -> List[Item]:
        return list(self.items.values())

class VendingMachine:
    def __init__(self, config: Config, inventory: Inventory, payment_gateway: PaymentGateway):
        self.config = config
        self.inventory = inventory
        self.payment_gateway = payment_gateway
        self.mdb_interface = MDBInterface(config.mdb_port)
        self.mdb_device = MDBDevice(self.mdb_interface)

    async def dispense_item(self, slot: str) -> bool:
        try:
            self.mdb_device.vend_request(slot)
            logger.info(f"Dispensing item from slot {slot}...")
            await asyncio.sleep(3)  # Simulate item dispensing delay
            logger.info("Item dispensed.")
            return True
        except Exception as e:
            logger.error(f"Error dispensing item: {e}")
            return False

    async def process_transaction(self, item: Item) -> bool:
        memo = await self.payment_gateway.get_payment_url(item)
        if not memo:
            return False

        logger.info("Scan the QR code with your Solana wallet to make the payment.")
        
        start_time = time.time()
        while time.time() - start_time < self.config.payment_verification_timeout:
            if await self.payment_gateway.verify_payment(memo):
                if await self.dispense_item(item.slot):
                    self.inventory.update_quantity(item.slot, item.quantity - 1)
                    return True
                return False
            await asyncio.sleep(self.config.payment_verification_interval)
        
        logger.warning("Payment verification timed out.")
        return False

    async def run(self):
        while True:
            self.display_items()
            selected_slot = input("Select an item slot (e.g., A1) or 'q' to quit: ").strip().upper()
            
            if selected_slot == 'Q':
                logger.info("Exiting the vending machine program.")
                break
            
            item = self.inventory.get_item(selected_slot)
            if not item:
                logger.warning("Invalid slot selected. Try again.")
                continue

            if item.quantity <= 0:
                logger.warning(f"Item {item.name} is out of stock.")
                continue

            logger.info(f"Selected item: {item.name}, Price: {item.price} SOL")
            
            if await self.process_transaction(item):
                logger.info("Transaction completed successfully.")
            else:
                logger.warning("Transaction failed. Please try again.")
            
            await asyncio.sleep(5)

    def display_items(self):
        logger.info("\nAvailable items:")
        for item in self.inventory.list_items():
            if item.quantity > 0:
                logger.info(f"Slot: {item.slot}, Name: {item.name}, Price: {item.price} SOL, Quantity: {item.quantity}")

async def main():
    config = Config.load_from_file(CONFIG_FILE)
    inventory = Inventory({
        "A1": Item("A1", 0.5, "Cola", 10),
        "A2": Item("A2", 0.75, "Water", 15),
        "A3": Item("A3", 1.0, "Energy Drink", 8),
        "B1": Item("B1", 1.25, "Chips", 12),
        "B2": Item("B2", 1.5, "Chocolate Bar", 20),
        "B3": Item("B3", 2.0, "Sandwich", 5)
    })
    payment_gateway = SolanaPaymentGateway(config)
    vending_machine = VendingMachine(config, inventory, payment_gateway)
    await vending_machine.run()

if __name__ == '__main__':
    asyncio.run(main())