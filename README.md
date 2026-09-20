# Assignment 2: The Socket Exchange

## Overview

This project is a simplified trading exchange implemented using TCP sockets. It consists of a central Exchange Server that concurrently handles multiple Trader Clients (who can submit and cancel orders) and Market-Data Clients (who receive real-time trade notifications).

The main server uses a single-threaded I/O multiplexing approach with `select()` and non-blocking sockets to efficiently manage concurrency, connection states, and network backpressure.

---

## 1. Development Environment and Setup

This implementation was developed, tested, and is fully reproducible in a FreeBSD virtual machine.

- **Operating System:** FreeBSD 14.4-RELEASE (or later compatible release).
- **Virtualization:** VirtualBox (for x86-64) or UTM / VMware Fusion (for Apple Silicon ARM64).
- **VM Specifications:** A configuration of 2 CPU cores and at least 2 GB RAM is sufficient. No graphical/X Window environment is required.
- **Network Configuration:** The Exchange Server, Trader Clients, and Market-Data Clients are designed to run as separate processes within the _same_ FreeBSD VM. All TCP communication routes through the loopback network interface (`127.0.0.1`).
- **Software Prerequisites:** Python 3 is required. If not already present on the FreeBSD VM, install it as root using `pkg install python3`.

## 2. Programming Language and Runtime

- **Language:** Python 3
- **Dependencies:** Only standard Python 3 system libraries are used (e.g., `socket`, `select`, `sys`). No external packages or `pip` installations are required.

## 3. Project Files

- `src/server.py` - The main Exchange Server script.
- `src/trader.py` - The Trader Client application.
- `src/market_data.py` - The Market-Data Client application.
- `src/common.py` - Shared utilities, protocol constants, and the `LineBuffer` implementation.
- `src/experiment.py` - The automated script used to conduct the 8 networking experiments.
- `src/server_bonus.py` - Scalable server utilizing `kqueue()` and dual IP binding for the bonus.
- `src/bonus/generator.py` - Bulk client generator script used to spawn the 70,000 connections.
- `server/run-server` & `client/run-*` - Executable wrapper scripts to launch the system.

## 4. Build and Preparation

Because this implementation is written entirely in Python, there is no `Makefile`, compilation, or build step required. The source code is ready to execute directly from the terminal.

## 5. How to Start the Exchange Server

To start the Exchange Server, open a terminal in the root directory of the project and execute the wrapper script:

```bash
./server/run-server
```

The server will immediately start running and listen for incoming TCP connections on `127.0.0.1` (localhost) at port `5000`.

## 6. How to Start the Clients

### Trader Client

To start a Trader Client, open a separate terminal window and execute:

```bash
./client/run-trader
```

_(Once connected, you can type commands directly into the terminal, such as `LOGIN <username>`, `BUY <instrument> <qty> <price>`, or `CANCEL <order_id>`, followed by the Enter key)._

### Market-Data Client

To start a Market-Data Client, open a separate terminal window and execute:

```bash
./client/run-market-data
```

_(Once connected, type `SUBSCRIBE <instrument>` followed by the Enter key to begin receiving real-time market updates)._

## 7. Running the Experiments

To reproduce the network observations documented in the report, you will need two separate terminal windows open in your FreeBSD environment.

**Terminal 1 (Action)** is used to run the automated experiment script from the root folder.  
**Terminal 2 (Diagnostic)** is used to run diagnostic tools (`netstat`, `sockstat`, `tcpdump`) to observe the network states.

### Experiment 1: Listening and Connected Sockets

- **Terminal 1:** Run `python3 src/experiment.py 1` (this starts the server and connects one client).
- **Terminal 2:** Run `sockstat -4 -P tcp | grep 5000`
- **What to observe:** You will see two entries. One socket is in the `LISTEN` state bound to `*:5000`, and the other is a connected socket showing both the local and foreign addresses representing the established client connection.

### Experiment 2: Observing TCP Connection States

- **Terminal 1:** Run `python3 src/experiment.py 2`
- **Terminal 2:** Run `netstat -an -p tcp | grep 5000` repeatedly (or use a `while true` loop).
- **What to observe:** You will see the connection transition to the `ESTABLISHED` state. Once Terminal 1 resumes and the client closes, running the `netstat` command again will show that the `ESTABLISHED` connection has disappeared, but the `LISTEN` socket remains active.

### Experiment 3: TCP as a Byte Stream

- **Terminal 1:** Run `python3 src/experiment.py 3`
- **Terminal 2:** _(No network tool required for this step)._
- **What to observe:** Look at the output in Terminal 1. The client sends one application message fragmented across 4 separate TCP writes (6, 10, 7, 1 bytes). The server output proves it correctly buffers and reconstitutes the single message using the newline (`\n`) delimiter.

### Experiment 4: One Client Should Not Stall the Others

- **Terminal 1:** Run `python3 src/experiment.py 4`
- **Terminal 2:** Run `netstat -an -p tcp | grep 5000`
- **What to observe:** In Terminal 2, you will see two `ESTABLISHED` connections. In Terminal 1, the output proves that even though Client 1 sent a partial message and stalled, Client 2 was able to connect and receive an `OK` response instantly (elapsed time ~0.000s), proving the server uses non-blocking `select()` multiplexing.

### Experiment 5: Multiple Simultaneous Connections

- **Terminal 1:** Run `python3 src/experiment.py 5` (connects 5 clients, 3 send data, 2 idle).
- **Terminal 2:** Run `netstat -an | grep 5000`
- **What to observe:** Look at the **Recv-Q** (Receive Queue) column. You will explicitly see exactly three active connections holding unread bytes in their `Recv-Q` (e.g., a value of `3`), while the other two idle connections maintain a `Recv-Q` of `0`.

### Experiment 6: Abrupt Client Termination

- **Terminal 2 (Start this FIRST):** Run `sudo tcpdump -i lo0 port 5000`. Leave it running to capture network packets.
- **Terminal 1:** Run `python3 src/experiment.py 6`
- **What to observe:** In Terminal 2's packet capture, look for the TCP flags. During Part A (orderly shutdown), you will see `Flags [F.]` representing a FIN packet. During Part B (abrupt termination where the process is killed), you will explicitly see `Flags [R.]` representing an RST (Reset) packet sent by the OS.

### Experiment 7: Slow Receiver and Backpressure

- **Terminal 1:** Run `python3 src/experiment.py 7`
- **Terminal 2:** Run the following loop to monitor the queues continuously:  
  `while true; do netstat -an | grep 5000; sleep 0.5; done`
- **What to observe:** In Terminal 2, watch the queue columns. You will first see the slow client's `Recv-Q` rapidly filling up (e.g., growing from 187 to 306). Once that buffer is full (Zero Window), you will observe the Exchange Server's `Send-Q` for that specific connection begin to back up as it safely buffers the output via non-blocking I/O.

### Experiment 8: Unexpected Client Disconnection

- **Terminal 1:** Run `python3 src/experiment.py 8`
- **Terminal 2:** Run the following loop to monitor the stuck data:  
  `while true; do netstat -an | grep 5000; sleep 0.5; done`
- **What to observe:** In Terminal 2, you will see that the connection remains stuck in the `ESTABLISHED` state because no FIN/RST was received. However, you will explicitly observe unacknowledged data getting trapped in the server's **Send-Q** (e.g., values accumulating like 17, 35, 37 bytes) as the server repeatedly attempts to retransmit TCP packets to the dead client.

## 8. Configuration Required & Submission Independence

- **No standard external configuration is required.**
- You do not need to set any environment variables, modify system files, or install external software for the base assignment.
- The system is entirely self-contained and hardcoded to bind to `127.0.0.1` and port `5000` to guarantee reproducible behavior in the FreeBSD grading environment.
- Please ensure that port `5000` is completely free/available before starting the server.

---

## 9. Bonus: Connection Scalability (70,000 Connections)

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
   python3 src/bonus/generator.py
   ```

```

```
