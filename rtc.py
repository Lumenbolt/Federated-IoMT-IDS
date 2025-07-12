import pandas as pd
import numpy as np
import time
import os
from sklearn.preprocessing import StandardScaler

INPUT_CSV = 'logs/network_features.csv'
OUTPUT_CSV = 'logs/network_features_preprocessed.csv'

last_row = 0

print("[PREPROCESS] Waiting for network_features.csv to be created and filled...")
while not (os.path.exists(INPUT_CSV) and os.path.getsize(INPUT_CSV) > 0):
    time.sleep(1)

while True:
    try:
        df = pd.read_csv(INPUT_CSV, on_bad_lines='skip')  # pandas >=1.3
    except Exception as e:
        print(f"[PREPROCESS] Error reading {INPUT_CSV}: {e}")
        time.sleep(1)
        continue

    if len(df) > last_row:
        new_rows = df.iloc[last_row:]
        new_rows = new_rows.fillna(0)

        numeric_cols = new_rows.select_dtypes(include=[np.number]).columns
        non_numeric_cols = [col for col in new_rows.columns if col not in numeric_cols]

        scaler = StandardScaler()
        scaled_numeric = scaler.fit_transform(new_rows[numeric_cols])

        new_rows_scaled = pd.concat(
            [new_rows[non_numeric_cols].reset_index(drop=True),
             pd.DataFrame(scaled_numeric, columns=numeric_cols)],
            axis=1
        )
        new_rows_scaled = new_rows_scaled.fillna(0)

        if os.path.exists(OUTPUT_CSV) and os.path.getsize(OUTPUT_CSV) > 0:
            new_rows_scaled.to_csv(OUTPUT_CSV, mode='a', header=False, index=False)
        else:
            new_rows_scaled.to_csv(OUTPUT_CSV, mode='w', header=True, index=False)
        print(f"[PREPROCESS] Appended {len(new_rows_scaled)} new rows to {OUTPUT_CSV}")

        last_row = len(df)
    time.sleep(1)
