import socket
import sys
import time
import subprocess
import resource

def get_server_pid():
    try:
        # Use pgrep to find the server_bonus.py process
        output = subprocess.check_output(['pgrep', '-f', 'server_bonus.py']).decode().strip()
        pids = output.split('\n')
        for pid in pids:
            if pid:
                return int(pid)
    except:
        pass
    return None

def take_measurements(server_pid, current_connections):
    # 1. Server memory & CPU
    try:
        ps_out = subprocess.check_output(['ps', '-o', '%cpu,rss', '-p', str(server_pid)]).decode().strip().split('\n')
        if len(ps_out) > 1:
            cpu, rss = ps_out[1].split()
            memory = f"{int(rss) / 1024:.2f} MB"
        else:
            cpu, memory = "N/A", "N/A"
    except:
        cpu, memory = "N/A", "N/A"

    # 2. Open FDs for server
    try:
        procstat_out = subprocess.check_output(['procstat', '-f', str(server_pid)]).decode().strip().split('\n')
        server_fds = str(len(procstat_out) - 1) # Subtract 1 for the header line
    except:
        server_fds = "N/A"

    # 3. System-wide FDs
    try:
        sys_fds = subprocess.check_output(['sysctl', '-n', 'kern.openfiles']).decode().strip()
    except:
        sys_fds = "N/A"

    # 4. Socket usage / limit
    try:
        sock_usage = subprocess.check_output(['sysctl', '-n', 'kern.ipc.numopensockets']).decode().strip()
        sock_limit = subprocess.check_output(['sysctl', '-n', 'kern.ipc.maxsockets']).decode().strip()
        socket_buffer = f"{sock_usage}/{sock_limit}"
    except:
        socket_buffer = "N/A"

    return [str(current_connections), memory, cpu, server_fds, sys_fds, socket_buffer, str(current_connections)]

def run_experiment(host, base_port):
    server_pid = get_server_pid()
    if not server_pid:
        print("Could not find running server_bonus.py. Make sure it is running in another terminal.")
        return

    print(f"Found server_bonus.py running with PID: {server_pid}")
    
    # Increase fd limits for this script to hold 70k connections
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
        print(f"Maximized client file descriptor limit to: {hard}")
    except Exception as e:
        print(f"Warning: Could not automatically increase file descriptor limit: {e}")

    connections = []
    
    targets = [10000, 20000, 30000, 40000, 50000, 60000, 70000]
    
    print("\nStarting experiment...")
    print(f"{'Idle Conns':<10} | {'Server Mem':<12} | {'Server CPU':<10} | {'Server FDs':<10} | {'System FDs':<10} | {'Socket Usage/Limit':<18} | {'Max Conns'}")
    print("-" * 105)

    for target in targets:
        to_create = target - len(connections)
        
        # Create connections up to the target
        for _ in range(to_create):
            i = len(connections)
            target_host = host if (i % 2 == 0) else "::1"
            af_type = socket.AF_INET if (i % 2 == 0) else socket.AF_INET6
            
            s = None
            retries = 0
            while retries < 5:
                try:
                    s = socket.socket(af_type, socket.SOCK_STREAM)
                    s.connect((target_host, base_port))
                    connections.append(s)
                    break
                except OSError as e:
                    if s is not None:
                        s.close()
                    if e.errno in (54, 61, 104):
                        retries += 1
                        time.sleep(0.05)
                        continue
                    else:
                        print(f"Error creating connection #{i + 1}: {e}")
                        break
            if retries >= 5:
                print(f"Max retries reached at connection #{i + 1}")
                break
        
        # Wait a moment for things to stabilize
        time.sleep(2)
        
        # Take measurements and print row
        metrics = take_measurements(server_pid, len(connections))
        print(f"{metrics[0]:<10} | {metrics[1]:<12} | {metrics[2]:<10} | {metrics[3]:<10} | {metrics[4]:<10} | {metrics[5]:<18} | {metrics[6]}")

        # If we failed to reach the target, stop the experiment
        if len(connections) < target:
            print("Failed to reach target connections. Stopping experiment.")
            break

    print("-" * 105)
    print("Experiment complete! Check the table above for your assignment.")
    print("Press Ctrl-C to close connections and exit.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nClosing connections...")
    finally:
        for s in connections:
            try:
                s.close()
            except:
                pass
        print("Done.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python experiment.py <host> <port>")
        sys.exit(1)
        
    h = sys.argv[1]
    p = int(sys.argv[2])
    run_experiment(h, p)
