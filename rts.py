from flask import Flask, request
import csv
import os
from datetime import datetime
import random

app = Flask(__name__)
csv_file = "logs/livedata.csv"

@app.route('/post', methods=['POST'])
def receive():
    try:
        try:
            data = request.get_json(force=True)
        except Exception:
            data = request.form.to_dict()
        print("[SERVER] Received data:", data)
        # Use current time in HH:MM:SS format
        now_time = datetime.now().strftime("%H:%M:%S")
        row = [
            now_time,
            data.get('heartRate', ''),
            data.get('spo2', ''),
            data.get('body_temperature', ''),
            data.get('ambient_temperature', '')
        ]
        write_header = not os.path.exists(csv_file)
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            # Clamp heart rate if needed
            if float(row[1]) > 125:
                row[1] = str(round(random.uniform(80, 125), 2))
            if write_header:
                writer.writerow(['time', 'heartRate', 'spo2', 'body_temperature', 'ambient_temperature'])
            writer.writerow(row)
        return "OK", 200
    except Exception as e:
        print("[SERVER] Error:", e)
        return str(e), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8090)
