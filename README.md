# Assignment 2: The Socket Exchange

## Overview
This project is a simplified trading exchange implemented using TCP sockets in a FreeBSD environment. It consists of a central Exchange Server that concurrently handles multiple Trader Clients (who can submit and cancel orders) and Market-Data Clients (who receive real-time trade notifications). 

The main server uses a single-threaded I/O multiplexing approach with `select()` and non-blocking sockets to efficiently manage concurrency, connection states, and network backpressure.

---

## 1. Programming Language and Runtime
* **Language:** Python 3
* **Runtime Environment:** FreeBSD (Tested, self-contained, and perfectly reproducible on the provided FreeBSD VM environment).
* **Dependencies:** Only standard Python 3 system libraries are used (e.g., `socket`, `select`, `sys`). No external packages are required.

## 2. Project Files
* `src/server.py` - The main Exchange Server script.
* `src/trader.py` - The Trader Client application.
* `src/market_data.py` - The Market-Data Client application.
* `src/common.py` - Shared utilities, protocol constants, and the `LineBuffer` implementation for TCP message framing.
* `src/experiment.py` - The automated script used to conduct the 8 networking experiments.
* `src/server_bonus.py` - Scalable server utilizing `kqueue()` and dual IP binding for the 70,000 connection bonus.
* `bonus/generator.py` - Bulk client generator script used to spawn the 70,000 connections.

## 3. Build and Preparation
Because this implementation is written entirely in Python, there is no compilation, linking, or build step required. The source code is ready to execute directly from the terminal. 

## 4. How to Start the Exchange Server
To start the Exchange Server, open a terminal in the root directory of the project and execute:
```bash
python3 src/server.py
```
The server will immediately start running and listen for incoming TCP connections on `127.0.0.1` (localhost) at port `5000`.

## 5. How to Start the Clients

### Trader Client
To start a Trader Client, open a separate terminal window and execute:
```bash
python3 src/trader.py
```
*(Once connected, you can type commands directly into the terminal, such as `LOGIN <username>`, `BUY <instrument> <qty> <price>`, or `CANCEL <order_id>`, followed by the Enter key).*

### Market-Data Client
To start a Market-Data Client, open a separate terminal window and execute:
```bash
python3 src/market_data.py
```
*(Once connected, type `SUBSCRIBE <instrument>` followed by the Enter key to begin receiving real-time market updates).*

## 6. Running the Experiments
To reproduce the experiments documented in the report, execute the experiment script from the root directory with the corresponding experiment number (1-8). For example, to run Experiment 5:
```bash
python3 src/experiment.py 5
```
*(You will need to use a second terminal window to run diagnostic tools like `netstat`, `sockstat`, or `tcpdump` to observe the network states as detailed in the report).*

## 7. Configuration Required & Submission Independence
* **No standard external configuration is required.** 
* You do not need to set any environment variables, modify system files, or install external software for the base assignment.
* The system is entirely self-contained and hardcoded to bind to `127.0.0.1` and port `5000` to guarantee reproducible behavior in the FreeBSD grading environment.
* Please ensure that port `5000` is completely free/available before starting the server.

---

## 8. Bonus: Connection Scalability (70,000 Connections)
This project includes the implementation for the Bonus section, demonstrating the ability to maintain 70,000 concurrent idle connections. This was achieved by replacing `select()` with `kqueue()` and binding to both IPv4 and IPv6 to bypass the ephemeral port limits.

### Kernel Configuration Required
To reproduce the 70,000 connections without crashing the FreeBSD kernel, the file descriptor and socket limits must be temporarily increased. Run the following commands as `root` (or using `sudo`) **before** starting the server:

```bash
sudo sysctl kern.maxfiles=200000
sudo sysctl kern.maxfilesperproc=200000
sudo sysctl kern.ipc.maxsockets=300000
```

### How to Run the Bonus
1. **Start the scalable server:**
   Open a terminal and start the server that utilizes `kqueue` and dual IP binding:
   ```bash
   python3 src/server_bonus.py
   ```

2. **Start the bulk connection generator:**
   Open a separate terminal and run the client generation script to spawn 70,000 connections:
   ```bash
   python3 bonus/generator.py
   ```
```