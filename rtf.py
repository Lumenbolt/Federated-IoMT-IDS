import subprocess
import time
import os
import csv

fields = [
    'ip.src',  # Must be first for logging
    'http.content_length', 'http.request', 'http.response.code', 'http.response_number', 'http.time',
    'tcp.analysis.initial_rtt', 'tcp.connection.fin', 'tcp.connection.syn', 'tcp.connection.synack',
    'tcp.flags.cwr', 'tcp.flags.fin', 'tcp.flags.res', 'tcp.flags.syn',
    'tcp.flags.urg', 'tcp.urgent_pointer', 'ip.frag_offset', 'eth.dst.ig', 'eth.src.ig', 'eth.src.lg',
    'eth.src_not_group', 'arp.isannouncement'
]

pcap_file = "logs/esp32_traffic.pcap"
output_csv = "logs/network_features.csv"

while not os.path.exists(pcap_file) or os.path.getsize(pcap_file) == 0:
    print("[FEATURES] Waiting for esp32_traffic.pcap to be created and filled...")
    time.sleep(1)

while True:
    cmd = [
        "tshark", "-r", pcap_file, "-T", "fields"
    ]
    for field in fields:
        cmd += ["-e", field]
    cmd += ["-E", "header=y", "-E", "separator=,", "-E", "quote=d"]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    lines = result.stdout.strip().split('\n')
    if not lines or len(lines) < 2:
        print("[FEATURES] No data yet.")
        time.sleep(1)
        continue

    tmp_output_csv = output_csv + ".tmp"
    with open(tmp_output_csv, "w", newline='') as f:
        writer = csv.writer(f)
        header = lines[0].split(',')
        writer.writerow(header)
        for line in lines[1:]:
            row = [x.strip('"') for x in line.split(',')]
            if not row or len(row) < 1:
                continue
            writer.writerow(row)
    os.replace(tmp_output_csv, output_csv)  # atomic move

    print("[FEATURES] Extracted features to network_features.csv")
    time.sleep(1)
