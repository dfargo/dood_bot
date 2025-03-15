# dood_bot: Cross-Chain Bridge Event Listener

This repository contains `dood_bot`, a sophisticated Python-based service designed to simulate a critical component of a cross-chain bridge: the event listener, also known as an oracle or relayer. It actively listens for specific events on a source blockchain and relays the event data to a destination chain's API endpoint.

This script is built with resilience and modularity in mind, showcasing architectural patterns suitable for production-grade decentralized applications.

## Concept

A cross-chain bridge allows users to transfer assets or data from one blockchain (the source chain) to another (the destination chain). A typical lock-and-mint bridge works as follows:

1.  A user locks tokens in a smart contract on the source chain.
2.  This action emits an event (e.g., `BridgeDepositInitiated`).
3.  Off-chain services, known as oracles or relayers, listen for this event.
4.  Upon detecting the event, the oracle verifies it and submits a transaction to a smart contract on the destination chain.
5.  The destination chain contract verifies the oracle's message and mints an equivalent amount of wrapped tokens for the user.

`dood_bot` plays the role of the oracle (step 3 and 4). It connects to a source chain's RPC node, filters for specific deposit events, and then makes an API call to a mock relayer service, simulating the process of initiating the transaction on the destination chain.

## Code Architecture

The script is designed with a clear separation of concerns, organized into several distinct classes:

*   **`ChainConnector`**: This class is responsible for all direct interactions with the source blockchain. It uses the `web3.py` library to establish a connection to a JSON-RPC endpoint, load a smart contract's ABI, and provide a clean interface for querying the chain and creating event filters.

*   **`DestinationChainOracle`**: This class simulates the relayer component. In this implementation, instead of signing and sending a real blockchain transaction, it uses the `requests` library to make a secure HTTP POST request to a configured API endpoint. This modular design allows it to be easily replaced with a true on-chain transaction handler.

*   **`EventListenerService`**: This is the main orchestrator. It ties the `ChainConnector` and `DestinationChainOracle` together. Its primary responsibility is to run the main event-listening loop. It polls the blockchain for new events, handles event processing, manages retry logic for relaying, and implements robust error handling and reconnection mechanisms to ensure the service is resilient and long-running.

*   **Main Execution Block**: The `main()` function at the end of the script is the entry point. It handles loading configuration from a `.env` file (using `python-dotenv`), validates the configuration, instantiates the necessary classes, and starts the `EventListenerService`.

### Interaction Flow

```
+-----------------------+
| main()                |
| (Load .env config)    |
+-----------+-----------+
            |
            v
+-----------+-----------+
| EventListenerService  |
| (Orchestrator)        |
+-----------+-----------+
     |            ^
     | creates    | processes events
     v            |
+----+------------+----+     sends      +------------------------+
| ChainConnector      +--------------->| DestinationChainOracle |
| (Source Chain via   |     event      | (Relayer via API)      |
|  web3.py)           |     data       +------------------------+
+---------------------+
```

## How it Works

1.  **Configuration**: The service starts by loading necessary parameters from a `.env` file. This includes the source chain's RPC URL, the bridge contract's address, and the destination API's endpoint and key.

2.  **Connection**: The `ChainConnector` establishes a connection to the source chain's RPC endpoint using `web3.py`. It verifies the connection and prepares a contract object using the provided address and ABI.

3.  **Event Filtering**: The `EventListenerService` creates a persistent event filter on the bridge contract, specifically targeting the `BridgeDepositInitiated` event. The filter is set to start from the latest block.

4.  **Polling Loop**: The service enters an infinite `while` loop. In each iteration, it queries the event filter for any new event logs that have been created since the last poll.

5.  **Event Processing**: When a new event is detected, the `_process_event` method is triggered. It parses the event data, extracting key information like the user's address, the token address, the amount, and the destination chain ID.

6.  **Relaying**: The parsed event data is passed to the `DestinationChainOracle`. The oracle constructs a JSON payload and sends it via an HTTP POST request to the configured destination API endpoint.

7.  **Resilience**: 
    *   **API Retries**: If the API call to the destination relayer fails, the service will retry the request with an exponential backoff strategy.
    *   **RPC Errors**: If the connection to the source chain's RPC node is lost, the main loop's `try...except` block catches the exception. The service will wait for a moment and then attempt to reconnect and recreate the event filter, ensuring it can recover from temporary network issues.

## Usage Example

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd dood_bot
    ```

2.  **Create a virtual environment and install dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Create a `.env` file** in the root of the project and populate it with your configuration. You can use a service like [Infura](https://infura.io) or [Alchemy](https://www.alchemy.com) to get an RPC URL. For the destination API, you can use a mock service like [Beeceptor](https://beeceptor.com) to see the incoming requests.

    **`.env` file example:**
    ```env
    # RPC URL for the source blockchain (e.g., Ethereum Sepolia testnet)
    SOURCE_CHAIN_RPC_URL="https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID"

    # Address of the deployed bridge smart contract on the source chain
    BRIDGE_CONTRACT_ADDRESS="0x1234567890123456789012345678901234567890"

    # Endpoint for the destination chain's relayer/oracle service
    DESTINATION_API_ENDPOINT="https://your-mock-api.free.beeceptor.com/relay"

    # A secret key for authenticating with the destination API
    DESTINATION_API_KEY="your-secret-api-key"
    ```

4.  **Run the script:**
    ```bash
    python script.py
    ```

The service will start, connect to the RPC, and begin listening for events. All activities and errors will be logged to the console and to a file named `dood_bot_listener.log`.