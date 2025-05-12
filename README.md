# cs438-exchange

## Overview

This exchange system implements a matching engine and order book that can handle various types of orders and execute trades according to price-time priority. The system is designed to be efficient and thread-safe, making it suitable for high-frequency trading applications.

## Features

- Price-time priority matching algorithm
- Support for new orders, modifications, and cancellations
- Trade execution with counterparty tracking
- Network-ready server implementation
- High-performance epoll-based server architecture
- Docker containerization for easy deployment

## Project Structure

- `src/MatchingEngine/`: Core matching engine that processes order commands
- `src/OrderBook/`: Order book implementation for tracking bids and asks
- `src/Server/`: Network server implementation
- `src/Wire/`: Protocol and serialization code
- `src/Printer/`: Output formatting utilities
- `network/`: Network simulation environment for testing
- `tests/`: Unit and end-to-end tests

## Network Simulation

The project includes a software-defined network (SDN) simulation environment in the `/network` directory:

```bash
# Start the network simulation
cd network
docker compose up -d

# View network topology
# Open http://localhost:8000/sdn_controller/graph in a browser

# Stop the simulation
docker compose down
```