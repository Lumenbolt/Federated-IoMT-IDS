import subprocess
import sys
import time
import os
from multiprocessing import Process, Event
from collections import Counter

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

SENSOR_SCRIPT = os.path.join(BASE_DIR, "rts.py")
FEATURES_SCRIPT = os.path.join(BASE_DIR, "rtf.py")
PREPROCESS_SCRIPT = os.path.join(BASE_DIR, "rtc.py")
PREDICT_SCRIPT = os.path.join(BASE_DIR, "rtp.py")
DASHBOARD_SCRIPT = os.path.join(BASE_DIR, "dashboard.py")
PREDICT_LOG = os.path.join(BASE_DIR, "logs/prediction_output.log")
STATUS_FILE = os.path.join(BASE_DIR, "logs/status.txt")
BLOCKED_IPS_FILE = os.path.join(BASE_DIR, "logs/blocked_ips.txt")
ESP32_IP = "192.168.137.250"
INTERFACE = "wlan0"

def get_lan_ip():
    ips = os.popen('hostname -I').read().strip().split()
    valid_ips = [ip for ip in ips if not ip.startswith('169.254.')]
    if valid_ips:
        return valid_ips[0]
    elif ips:
        return ips[0]
    else:
        return '127.0.0.1'

def run_script(script, name, halt_event, log_file=None):
    with open(log_file, "w") if log_file else open(os.devnull, "w") as f:
        proc = subprocess.Popen([sys.executable, script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        while True:
            if halt_event.is_set():
                proc.terminate()
                break
            line = proc.stdout.readline()
            if not line:
                break
            print(f"[{name}] {line}", end='')
            if log_file:
                f.write(line)
                f.flush()

def run_tcpdump(halt_event):
    cmd = [
        "sudo", "tcpdump", "-i", INTERFACE,
        "dst host", get_lan_ip(),
        "-w", os.path.join(BASE_DIR, "logs/esp32_traffic.pcap"),
    ]
    print(f"[TCPDUMP] Starting: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while True:
        if halt_event.is_set():
            proc.terminate()
            break
        line = proc.stdout.readline()
        if not line:
            break
        print(f"[TCPDUMP] {line}", end='')

def run_dashboard():
    subprocess.Popen([sys.executable, DASHBOARD_SCRIPT])

def tail_file(filename, n=1):
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
            return lines[-n:] if len(lines) >= n else lines
    except Exception:
        return [""]

def write_status(status):
    with open(STATUS_FILE, "w") as f:
        f.write(status + "\n")

def block_ip(ip):
    my_ip = get_lan_ip()
    if not ip or ip == my_ip or ip == "127.0.0.1" or ip == "192.168.137.1" or ip == ESP32_IP:
        print(f"[INFO] Skipping IP (not blocking): {ip}")
        return
    print(f"[DEBUG] Blocking IP: {ip}")
    subprocess.run(['sudo', 'iptables', '-I', 'INPUT', '1', '-s', ip, '-j', 'DROP'])
    subprocess.run(['sudo', 'netfilter-persistent', 'save'])
    # Save blocked IP to file
    with open(BLOCKED_IPS_FILE, "a") as f:
        f.write(ip + "\n")
    print(f"[INFO] Blocked and saved IP: {ip}")

def extract_top_attacker_ip_from_last_n_malicious(n=500):
    lines = tail_file(PREDICT_LOG, n)
    ips = []
    for line in lines:
        if "ALERT: Malicious" in line and "src_ip:" in line:
            parts = line.strip().split("src_ip:")
            if len(parts) > 1:
                ip = parts[1].strip().split()[0]
                ips.append(ip)
    exclude = {get_lan_ip(), "127.0.0.1", "192.168.137.1", ESP32_IP}
    ips = [ip for ip in ips if ip and ip not in exclude]
    if not ips:
        return None
    counter = Counter(ips)
    top_ip, count = counter.most_common(1)[0]
    print(f"[DEBUG] Top attacker IP in last {n} malicious: {top_ip} ({count} times)")
    return top_ip

def monitor_for_attack():
    already_blocked = set()
    while True:
        status = "Benign"
        if os.path.exists(PREDICT_LOG):
            pred_lines = tail_file(PREDICT_LOG, n=500)
            # Attack detected: 500 consecutive malicious
            if pred_lines and all("ALERT: Malicious" in l for l in pred_lines) and len(pred_lines) == 500:
                attacker_ip = extract_top_attacker_ip_from_last_n_malicious(n=500)
                if attacker_ip and attacker_ip not in already_blocked:
                    print("[MAIN] Detected sustained attack. Extracting attacker IP...")
                    # 1. RED: Attack detected
                    status = "Halted"
                    write_status(status)
                    print("[MAIN] RED status written. Waiting 3 seconds for dashboard to show red.")
                    time.sleep(3)  # Hold red for 3 seconds

                    # 2. Block attacker and show BLUE
                    block_ip(attacker_ip)
                    already_blocked.add(attacker_ip)
                    status = "Danger averted: attacker blocked"
                    write_status(status)
                    print("[MAIN] BLUE status written. Waiting 4 seconds for dashboard to show blue.")
                    time.sleep(4)  # Hold blue for 4 seconds

                    # 3. GREEN: Benign
                    status = "Benign"
                    write_status(status)
                    print("[MAIN] GREEN status written. Returning to normal monitoring.")
                else:
                    # Already blocked or no attacker found, just show benign
                    status = "Benign"
                    write_status(status)
            else:
                status = "Benign"
                write_status(status)
        time.sleep(0.1)


if __name__ == "__main__":
    lan_ip = get_lan_ip()
    print(f"\n[MAIN] Starting web dashboard at: http://{lan_ip}:8050\n")
    halt_event = Event()
    dashboard_proc = Process(target=run_dashboard)
    dashboard_proc.start()
    time.sleep(2)

    procs = [
        Process(target=run_tcpdump, args=(halt_event,)),
        Process(target=run_script, args=(SENSOR_SCRIPT, "SENSOR", halt_event)),
        Process(target=run_script, args=(FEATURES_SCRIPT, "FEATURES", halt_event)),
        Process(target=run_script, args=(PREPROCESS_SCRIPT, "PREPROCESS", halt_event)),
        Process(target=run_script, args=(PREDICT_SCRIPT, "PREDICT", halt_event, PREDICT_LOG))
    ]
    for p in procs:
        p.start()
        time.sleep(1)

    monitor_for_attack()

    for p in procs:
        p.join()
    dashboard_proc.terminate()
    print("[MAIN] Exited.")
