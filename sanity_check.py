#!/usr/bin/env python3
import os, socket, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST, PORT = "127.0.0.1", 5000
SERVER = ROOT / "server" / "run-server"

class Fail(Exception): pass

class Client:
    def __init__(self, name):
        self.name = name
        self.s = socket.create_connection((HOST, PORT), timeout=2)
        self.s.settimeout(0.2)
        self.buf = b""
    def send(self, msg): self.s.sendall((msg + "\n").encode())
    def fragments(self, pieces):
        for p in pieces:
            self.s.sendall(p.encode()); time.sleep(.03)
    def recv(self, timeout=2):
        end = time.time() + timeout
        while time.time() < end:
            if b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                return line.rstrip(b"\r").decode()
            try:
                d = self.s.recv(4096)
                if not d: raise Fail(f"{self.name}: server closed connection")
                self.buf += d
            except socket.timeout: pass
        raise Fail(f"{self.name}: timeout waiting for response")
    def expect(self, msg):
        got = self.recv()
        if got != msg: raise Fail(f"{self.name}: expected {msg!r}, got {got!r}")
    def close(self):
        try: self.s.close()
        except OSError: pass

def wait_for_server(proc):
    end = time.time() + 3
    while time.time() < end:
        if proc.poll() is not None:
            raise Fail("server exited during startup")
        try:
            s = socket.create_connection((HOST, PORT), timeout=.2)
            s.close(); return
        except OSError: time.sleep(.05)
    raise Fail("server did not start listening on 127.0.0.1:5000")

def check_launchers():
    paths = [ROOT/"server"/"run-server", ROOT/"client"/"run-trader", ROOT/"client"/"run-market-data"]
    for p in paths:
        if not p.is_file(): raise Fail(f"missing required launcher: {p}")
        if not os.access(p, os.X_OK): raise Fail(f"launcher not executable: {p}")
    print("PASS 1: required launchers exist and are executable")

def main():
    check_launchers()
    proc = subprocess.Popen([str(SERVER), HOST, str(PORT)], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    clients = []
    try:
        wait_for_server(proc); print("Server started")

        a = Client("alice"); clients.append(a); a.send("LOGIN alice"); a.expect("OK")
        print("PASS 2: basic TCP connection + LOGIN")

        f = Client("framing"); clients.append(f)
        f.fragments(["LOG", "IN frame", "d_user\n"]); f.expect("OK")
        print("PASS 3: fragmented TCP message reconstructed")

        zq = Client("zero_qty"); clients.append(zq); zq.send("LOGIN zero_qty"); zq.expect("OK")
        zq.send("BUY JNST 0 100")
        if not zq.recv().startswith("ERROR"): raise Fail("zero quantity was accepted")
        zp = Client("zero_price"); clients.append(zp); zp.send("LOGIN zero_price"); zp.expect("OK")
        zp.send("BUY JNST 1 0")
        if not zp.recv().startswith("ERROR"): raise Fail("zero price was accepted")
        print("PASS 4: zero quantity/price rejected")

        md = Client("md"); clients.append(md); md.send("SUBSCRIBE JNST"); md.expect("OK")
        md.send("BUY JNST 1 100")
        if not md.recv().startswith("ERROR"): raise Fail("market-data client placed order")
        a.send("SUBSCRIBE JNST")
        if not a.recv().startswith("ERROR"): raise Fail("trader subscribed to market data")
        print("PASS 5: role restrictions")

        seller = Client("seller"); clients.append(seller); seller.send("LOGIN seller"); seller.expect("OK")
        a.send("BUY IMCT 5 200"); acc = a.recv()
        if not acc.startswith("ORDER_ACCEPTED "): raise Fail("BUY not accepted")
        seller.send("SELL IMCT 5 200"); acc = seller.recv()
        if not acc.startswith("ORDER_ACCEPTED "): raise Fail("SELL not accepted")
        a.expect("BOUGHT IMCT 5 200"); seller.expect("SOLD IMCT 5 200")
        print("PASS 6: matching + BOUGHT/SOLD")

        b = Client("buyer2"); s = Client("seller2"); md2 = Client("md2")
        clients += [b,s,md2]
        b.send("LOGIN buyer2"); b.expect("OK"); s.send("LOGIN seller2"); s.expect("OK")
        md2.send("SUBSCRIBE JNST"); md2.expect("OK")
        b.send("BUY JNST 10 333"); acc=b.recv()
        if not acc.startswith("ORDER_ACCEPTED "): raise Fail("partial-fill BUY not accepted")
        s.send("SELL JNST 4 333"); acc=s.recv()
        if not acc.startswith("ORDER_ACCEPTED "): raise Fail("partial-fill SELL not accepted")
        b.expect("BOUGHT JNST 4 333"); s.expect("SOLD JNST 4 333"); md2.expect("TRADE JNST 4 333")
        s.send("SELL JNST 6 333"); acc=s.recv()
        if not acc.startswith("ORDER_ACCEPTED "): raise Fail("second SELL not accepted")
        b.expect("BOUGHT JNST 6 333"); s.expect("SOLD JNST 6 333"); md2.expect("TRADE JNST 6 333")
        print("PASS 7: partial fills + market-data TRADE")

        c = Client("canceler"); clients.append(c); c.send("LOGIN canceler"); c.expect("OK")
        c.send("BUY IMCT 7 999"); acc=c.recv()
        if not acc.startswith("ORDER_ACCEPTED "): raise Fail("unmatched order not accepted")
        oid=acc.split()[1]; c.send("CANCEL "+oid); c.expect("ORDER_CANCELLED "+oid)
        print("PASS 8: CANCEL")

        ps = Client("persistent_seller"); clients.append(ps); ps.send("LOGIN persistent_seller"); ps.expect("OK")
        ps.send("SELL IMCT 3 777"); acc=ps.recv()
        if not acc.startswith("ORDER_ACCEPTED "): raise Fail("persistent SELL not accepted")
        ps.close(); clients.remove(ps)
        lb = Client("later_buyer"); clients.append(lb); lb.send("LOGIN later_buyer"); lb.expect("OK")
        lb.send("BUY IMCT 3 777"); acc=lb.recv()
        if not acc.startswith("ORDER_ACCEPTED "): raise Fail("later BUY not accepted")
        lb.expect("BOUGHT IMCT 3 777")
        print("PASS 9: orders survive trader disconnect")

        idle=[]
        for i in range(10): idle.append(Client(f"idle{i}"))
        time.sleep(.2)
        for x in idle: x.close()
        clients.extend(idle)
        print("PASS 10: 10 simultaneous idle connections")

        print("\nALL SANITY TESTS PASSED")
    except Exception as e:
        print("\nFAIL:", e)
        sys.exit(1)
    finally:
        for c in clients: c.close()
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired: proc.kill()

if __name__ == "__main__": main()
