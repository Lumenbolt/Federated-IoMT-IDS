import pandas as pd
import numpy as np
import tensorflow as tf
import time
import os

MODEL_PATH = 'dbn_iomt_ids.h5'
CSV_PATH = 'logs/network_features_preprocessed.csv'
LOG_PATH = 'logs/prediction_output.log'
BLOCKED_IPS_FILE = 'logs/blocked_ips.txt'

last_row = 0

def get_blocked_ips():
    if not os.path.exists(BLOCKED_IPS_FILE):
        return set()
    with open(BLOCKED_IPS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

model = tf.keras.models.load_model(MODEL_PATH)
print("Model loaded.")

with open(LOG_PATH, "a") as logf:
    while True:
        try:
            df = pd.read_csv(CSV_PATH)
        except (pd.errors.EmptyDataError, FileNotFoundError):
            time.sleep(1)
            continue
        except Exception as e:
            msg = f"[PREDICT] Error reading {CSV_PATH}: {e}"
            print(msg)
            logf.write(msg + "\n")
            logf.flush()
            time.sleep(1)
            continue

        if len(df) < last_row:
            print("[PREDICT] Input file truncated, resetting last_row to 0.")
            last_row = 0

        blocked_ips = get_blocked_ips()

        if len(df) > last_row:
            new_rows = df.iloc[last_row:]
            src_ips = new_rows.iloc[:, 0].astype(str).tolist()
            features = new_rows.iloc[:, 1:]
            X = features.apply(pd.to_numeric, errors='coerce').fillna(0).to_numpy(dtype=np.float32)
            if not np.any(X):
                last_row = len(df)
                time.sleep(1)
                continue
            preds = model.predict(X, verbose=0)
            for i, pred in enumerate(preds):
                is_malicious = int(np.argmax(pred))
                row_number = last_row + i + 1
                src_ip = src_ips[i]
                if src_ip in blocked_ips:
                    # Skip predicting/logging for blocked IPs
                    continue
                out = ""
                if is_malicious:
                    out = f"Row {row_number}: ALERT: Malicious traffic detected! src_ip: {src_ip}"
                else:
                    out = f"Row {row_number}: Normal traffic src_ip: {src_ip}"
                print(out)
                logf.write(out + "\n")
                logf.flush()
            last_row = len(df)
        time.sleep(1)
