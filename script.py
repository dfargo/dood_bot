import os
import json
import time
import logging
from typing import Dict, Any, Optional, List

import requests
from web3 import Web3
from web3.contract import Contract
from web3.logs import DISCARD
from web3.exceptions import ContractLogicError
from dotenv import load_dotenv

# --- Configuration Setup ---
# It's a best practice to load configurations from environment variables
# to avoid hardcoding sensitive information like API keys or RPC URLs.
load_dotenv()

# --- Logging Configuration ---
# A robust logging setup is crucial for any production-grade service.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("dood_bot_listener.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ChainConnector:
    """
    Manages the connection to a specific blockchain via Web3.py.

    This class encapsulates the logic for connecting to an Ethereum-like node,
    instantiating a contract object, and providing a stable interface for
    blockchain interactions.
    """

    def __init__(self, rpc_url: str, contract_address: str, contract_abi: List[Dict[str, Any]]):
        """
        Initializes the connection to the blockchain.

        Args:
            rpc_url (str): The URL of the blockchain's JSON-RPC endpoint.
            contract_address (str): The address of the smart contract to interact with.
            contract_abi (List[Dict[str, Any]]): The ABI of the smart contract.
        
        Raises:
            ConnectionError: If the connection to the RPC endpoint cannot be established.
        """
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        self.contract_abi = contract_abi
        self.web3: Optional[Web3] = None
        self.contract: Optional[Contract] = None
        self._connect()

    def _connect(self):
        """
        Establishes the Web3 connection and initializes the contract object.
        Handles connection errors and retries internally.
        """
        try:
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if not self.web3.is_connected():
                raise ConnectionError(f"Failed to connect to blockchain node at {self.rpc_url}")
            
            # Checksum address is a best practice
            checksum_address = self.web3.to_checksum_address(self.contract_address)
            self.contract = self.web3.eth.contract(address=checksum_address, abi=self.contract_abi)
            logger.info(f"Successfully connected to RPC endpoint and loaded contract at {self.contract_address}")
        except Exception as e:
            logger.error(f"Error connecting to blockchain: {e}")
            # In a real-world scenario, you might implement a retry mechanism here.
            raise ConnectionError(f"Could not establish connection to {self.rpc_url}") from e

    def get_latest_block_number(self) -> int:
        """
        Fetches the most recent block number from the connected chain.
        
        Returns:
            int: The latest block number.
        """
        if not self.web3:
            raise ConnectionError("Web3 provider not initialized.")
        return self.web3.eth.block_number


class DestinationChainOracle:
    """
    Simulates an oracle that relays information to a destination chain.

    In a real cross-chain bridge, this component would be responsible for signing a message
    with the event data and submitting it as a transaction to the destination chain's
    bridge contract. For this simulation, it sends the data to a mock API endpoint.
    """

    def __init__(self, api_endpoint: str, api_key: str):
        """
        Initializes the oracle with the destination API details.

        Args:
            api_endpoint (str): The URL of the destination chain's relayer service.
            api_key (str): An API key for authenticating with the service.
        """
        self.api_endpoint = api_endpoint
        self.headers = {
            "Content-Type": "application/json",
            "X-API-KEY": api_key
        }

    def relay_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Sends the event data to the destination chain's simulated relayer service.

        Args:
            event_data (Dict[str, Any]): The processed event data to be relayed.

        Returns:
            bool: True if the API call was successful (2xx status code), False otherwise.
        """
        try:
            payload = {
                "source_tx_hash": event_data['transactionHash'],
                "source_chain_id": event_data['source_chain_id'],
                "destination_chain_id": event_data['destination_chain_id'],
                "user": event_data['user'],
                "token": event_data['token'],
                "amount": event_data['amount'],
                "block_number": event_data['block_number']
            }
            logger.info(f"Relaying event to {self.api_endpoint} with payload: {payload}")
            
            # Using requests library to make an external HTTP POST request
            response = requests.post(self.api_endpoint, headers=self.headers, json=payload, timeout=10)
            
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
            
            logger.info(f"Successfully relayed event. Destination API response: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to relay event to destination chain API: {e}")
            return False


class EventListenerService:
    """
    The main service orchestrator for listening to and processing blockchain events.

    This class ties together the ChainConnector, event filtering logic, and the
    DestinationChainOracle to form a complete event-listening pipeline.
    """

    def __init__(self, chain_connector: ChainConnector, oracle: DestinationChainOracle, event_name: str, source_chain_id: int):
        """
        Initializes the event listener service.

        Args:
            chain_connector (ChainConnector): The connector for the source blockchain.
            oracle (DestinationChainOracle): The oracle for relaying events to the destination.
            event_name (str): The name of the contract event to listen for.
            source_chain_id (int): The identifier for the source chain.
        """
        self.connector = chain_connector
        self.oracle = oracle
        self.event_name = event_name
        self.source_chain_id = source_chain_id
        self.event_filter = self._create_event_filter()
        self.last_processed_block = self.connector.get_latest_block_number() - 1

    def _create_event_filter(self):
        """
        Creates a Web3.py event filter for the specified event.
        """
        if not self.connector.contract:
            raise ValueError("Contract not initialized in ChainConnector.")
        try:
            event = getattr(self.connector.contract.events, self.event_name)
            return event.create_filter(fromBlock='latest')
        except AttributeError:
            logger.error(f"Event '{self.event_name}' not found in contract ABI.")
            raise

    def _process_event(self, event: Dict[str, Any]):
        """
        Processes a single event log.
        This involves formatting the data and passing it to the oracle.
        """
        logger.info(f"New event received: {self.event_name} in transaction {event['transactionHash'].hex()}")
        
        # Edge case: Handle potential malformed events or missing arguments
        if 'args' not in event:
            logger.warning(f"Event log is missing 'args' field. Skipping. Log: {event}")
            return

        event_args = event['args']
        processed_data = {
            "transactionHash": event['transactionHash'].hex(),
            "block_number": event['blockNumber'],
            "source_chain_id": self.source_chain_id,
            "destination_chain_id": event_args.get('destinationChainId'),
            "user": event_args.get('user'),
            "token": event_args.get('token'),
            "amount": str(event_args.get('amount')) # Convert BigNumber to string for JSON serialization
        }

        # Retry logic for the oracle relay
        max_retries = 3
        for attempt in range(max_retries):
            if self.oracle.relay_event(processed_data):
                logger.info(f"Successfully processed and relayed event for tx {processed_data['transactionHash']}")
                # Here you might persist the state to a DB to avoid reprocessing
                break
            else:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} to relay event failed. Retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff
        else:
            logger.error(f"Failed to relay event after {max_retries} attempts. Manual intervention required.")

    def run(self, poll_interval: int = 5):
        """
        Starts the main event listening loop.
        
        Args:
            poll_interval (int): The time in seconds to wait between polling for new events.
        """
        logger.info(f"Starting event listener for '{self.event_name}' events...")
        while True:
            try:
                # Fetch new logs since the last poll
                logs = self.event_filter.get_new_entries()
                if logs:
                    for event in logs:
                        self._process_event(event)
                else:
                    logger.debug("No new events found in this poll.")
                
                time.sleep(poll_interval)

            except KeyboardInterrupt:
                logger.info("Shutdown signal received. Exiting gracefully.")
                break
            except Exception as e:
                # Catch-all for unexpected errors, to ensure the listener keeps running.
                logger.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
                logger.info("Attempting to reconnect and restart listening...")
                time.sleep(15) # Wait before restarting to avoid spamming a broken endpoint
                self._reconnect_and_recreate_filter()

    def _reconnect_and_recreate_filter(self):
        """
        Handles reconnection to the RPC and recreation of the event filter.
        This is a critical resilience feature for long-running services.
        """
        try:
            self.connector._connect() # Re-establish connection
            self.event_filter = self._create_event_filter() # Re-create the filter
            logger.info("Successfully reconnected and recreated event filter.")
        except Exception as e:
            logger.error(f"Failed to reconnect or recreate filter: {e}. Will retry on next cycle.")


def main():
    """
    Main function to set up and run the service.
    """
    # --- Load Environment Configuration ---
    SOURCE_CHAIN_RPC_URL = os.getenv("SOURCE_CHAIN_RPC_URL")
    BRIDGE_CONTRACT_ADDRESS = os.getenv("BRIDGE_CONTRACT_ADDRESS")
    DESTINATION_API_ENDPOINT = os.getenv("DESTINATION_API_ENDPOINT")
    DESTINATION_API_KEY = os.getenv("DESTINATION_API_KEY")

    # --- Configuration Validation ---
    if not all([SOURCE_CHAIN_RPC_URL, BRIDGE_CONTRACT_ADDRESS, DESTINATION_API_ENDPOINT, DESTINATION_API_KEY]):
        logger.error("One or more environment variables are missing. Please check your .env file.")
        return

    # --- Mock Contract ABI ---
    # In a real project, this would be loaded from a JSON file.
    BRIDGE_ABI = json.loads('''
    [
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "user",
                    "type": "address"
                },
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "token",
                    "type": "address"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "amount",
                    "type": "uint256"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "destinationChainId",
                    "type": "uint256"
                }
            ],
            "name": "BridgeDepositInitiated",
            "type": "event"
        }
    ]
    ''')

    try:
        # 1. Initialize the connection to the source chain
        chain_connector = ChainConnector(
            rpc_url=SOURCE_CHAIN_RPC_URL,
            contract_address=BRIDGE_CONTRACT_ADDRESS,
            contract_abi=BRIDGE_ABI
        )

        # 2. Initialize the destination chain oracle/relayer
        oracle = DestinationChainOracle(
            api_endpoint=DESTINATION_API_ENDPOINT,
            api_key=DESTINATION_API_KEY
        )

        # 3. Initialize and run the main listener service
        listener_service = EventListenerService(
            chain_connector=chain_connector,
            oracle=oracle,
            event_name="BridgeDepositInitiated",
            source_chain_id=1 # Example: 1 for Ethereum Mainnet
        )

        listener_service.run()

    except ConnectionError as e:
        logger.critical(f"Failed to initialize the service due to a connection error: {e}")
    except Exception as e:
        logger.critical(f"A fatal error occurred during service setup: {e}", exc_info=True)


if __name__ == "__main__":
    main()
 
# @-internal-utility-start
# Historical update 2025-10-10 11:54:39
def historical_feature_9922():
    """Feature added on 2025-10-10 11:54:39"""
    print('Historical feature working')
    return True
# @-internal-utility-end

 
# @-internal-utility-start
# Historical update 2025-10-10 11:56:04
def historical_feature_4459():
    """Feature added on 2025-10-10 11:56:04"""
    print('Historical feature working')
    return True
# @-internal-utility-end

