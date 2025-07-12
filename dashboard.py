from flask import Flask, render_template_string, jsonify
import pandas as pd
import os

app = Flask(__name__)

@app.route('/')
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>IoMT Sensor and IDS Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f8f8f8; }
        .container { display: flex; justify-content: space-between; margin: 40px; }
        .sensor, .status { width: 45%; padding: 30px; background: #fff; border-radius: 12px; box-shadow: 0 0 10px #ccc; }
        .sensor h2, .status h2 { text-align: center; margin-bottom: 20px; }
        .reading { font-size: 2em; margin-bottom: 20px; }
        .hr { color: #1976d2; }
        .spo2 { color: #43a047; }
        .bodytemp { color: #e65100; }
        .ambtemp { color: #0097a7; }
        .time { color: #555; }
        .benign { color: green; font-size: 2.2em; text-align: center; font-weight: bold; margin-top: 60px;}
        .malicious { color: red; font-size: 2.2em; text-align: center; font-weight: bold; margin-top: 60px; animation: blink 1s linear infinite; letter-spacing: 2px; }
        .averted { color: #1565c0; background: #e3f2fd; font-size: 2.2em; text-align: center; font-weight: bold; margin-top: 60px; animation: blinkblue 1s linear infinite; letter-spacing: 2px; }
        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0.1; }
        }
        @keyframes blinkblue {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0.1; }
        }
        #sound-alert-row { text-align:center; margin-bottom: 10px; }
        #sound-alert-checkbox { width: 22px; height: 22px; vertical-align: middle; }
        label[for="sound-alert-checkbox"] { font-size: 1.2em; vertical-align: middle; margin-left: 8px; }
        #blocked-ips-box {
            width: 100%;
            max-width: 600px;
            margin: 40px auto 0 auto;
            background: #e3f2fd;
            border: 1.5px solid #1565c0;
            border-radius: 8px;
            padding: 14px 20px;
            font-size: 1.1em;
            display: none;
            transition: max-height 0.4s;
            overflow-y: auto;
            max-height: 300px;
        }
        #blocked-ips-btn {
            display: block;
            margin: 0 auto;
            margin-top: 30px;
            background: #1565c0;
            color: #fff;
            border: none;
            border-radius: 6px;
            padding: 10px 24px;
            font-size: 1.1em;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h1 style="text-align:center; margin-bottom:30px;">IoMT Sensor and IDS Dashboard</h1>
    <div id="sound-alert-row">
        <input type="checkbox" id="sound-alert-checkbox">
        <label for="sound-alert-checkbox">Enable sound alerts</label>
    </div>
    <div class="container">
        <div class="sensor">
            <h2>Sensor Readings</h2>
            <div class="reading time" id="time">Time: --</div>
            <div class="reading hr" id="hr">Heart Rate: -- bpm</div>
            <div class="reading spo2" id="spo2">SpO₂: -- %</div>
            <div class="reading bodytemp" id="bodytemp">Body Temp: -- °C</div>
            <div class="reading ambtemp" id="ambtemp">Ambient Temp: -- °C</div>
        </div>
        <div class="status">
            <h2>Network Status</h2>
            <div id="status" class="benign">Benign (Normal Traffic)</div>
        </div>
    </div>
    <button id="blocked-ips-btn" onclick="toggleBlockedIps()">Show Blocked Devices</button>
    <div id="blocked-ips-box"></div>
    <audio id="alert-audio" src="/static/alert.mp3" style="display:none;"></audio>
    <audio id="blocked-audio" src="/static/blocked.mp3" style="display:none;"></audio>
    <script>
        let lastStatus = "Normal";
        let soundEnabled = false;
        let soundInterval = null;
        let avertedTimeout = null;
        let attackOngoing = false;
        let bluePlayed = false;

        const checkbox = document.getElementById('sound-alert-checkbox');
        checkbox.addEventListener('change', function() {
            soundEnabled = checkbox.checked;
            if (!soundEnabled && soundInterval) {
                clearInterval(soundInterval);
                soundInterval = null;
            }
        });

        function playAlertSoundLoop() {
            var audio = document.getElementById("alert-audio");
            if (soundInterval) return; // Already looping
            audio.currentTime = 0;
            audio.play();
            soundInterval = setInterval(function() {
                audio.currentTime = 0;
                audio.play();
            }, 2000);
        }

        function stopAlertSoundLoop() {
            if (soundInterval) {
                clearInterval(soundInterval);
                soundInterval = null;
            }
            var audio = document.getElementById("alert-audio");
            audio.pause();
            audio.currentTime = 0;
        }

        function playBlockedSoundOnce() {
            var audio = document.getElementById("blocked-audio");
            audio.currentTime = 0;
            audio.play();
        }

        function showAvertedStatus() {
            let statusDiv = document.getElementById('status');
            statusDiv.textContent = "DANGER AVERTED: ATTACKER BLOCKED";
            statusDiv.className = "averted";
            stopAlertSoundLoop();
            if (!bluePlayed) {
                playBlockedSoundOnce();
                bluePlayed = true;
            }
            if (avertedTimeout) clearTimeout(avertedTimeout);
            avertedTimeout = setTimeout(() => {
                statusDiv.textContent = "Benign (Normal Traffic)";
                statusDiv.className = "benign";
                bluePlayed = false;
            }, 4000); // Show blue for 4 seconds then green
        }

        function updateBlockedIps() {
            fetch('/blocked_ips')
                .then(r => r.json())
                .then(data => {
                    let box = document.getElementById('blocked-ips-box');
                    if (data.length === 0) {
                        box.innerHTML = "<i>No devices have been blocked yet.</i>";
                    } else {
                        box.innerHTML = "<b>Blocked Devices:</b><br>" +
                            data.map(ip => "<span style='color:#1565c0'>" + ip + "</span>").join("<br>");
                    }
                });
        }

        function toggleBlockedIps() {
            let box = document.getElementById('blocked-ips-box');
            let btn = document.getElementById('blocked-ips-btn');
            if (box.style.display === "block") {
                box.style.display = "none";
                btn.textContent = "Show Blocked Devices";
            } else {
                updateBlockedIps();
                box.style.display = "block";
                btn.textContent = "Hide Blocked Devices";
            }
        }

        function updateDashboard() {
            fetch('/status')
                .then(r => r.text())
                .then(status => {
                    status = status.trim();
                    let statusDiv = document.getElementById('status');
                    if (status === "Halted") {
                        statusDiv.textContent = "ALERT! MALICIOUS ATTACK DETECTED! BLOCKING DEVICE.....";
                        statusDiv.className = "malicious";
                        attackOngoing = true;
                        bluePlayed = false;
                        if (soundEnabled) {
                            playAlertSoundLoop();
                        }
                    } else if (status.toLowerCase().includes("danger averted")) {
                        if (attackOngoing) {
                            showAvertedStatus();
                            attackOngoing = false;
                        }
                    } else {
                        statusDiv.textContent = "Benign (Normal Traffic)";
                        statusDiv.className = "benign";
                        stopAlertSoundLoop();
                        attackOngoing = false;
                        bluePlayed = false;
                    }
                    lastStatus = status;
                });

            fetch('/sensor')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('time').textContent = "Time: " + data.time;
                    document.getElementById('hr').textContent = "Heart Rate: " + data.heartRate + " bpm";
                    document.getElementById('spo2').textContent = "SpO₂: " + data.spo2 + " %";
                    document.getElementById('bodytemp').textContent = "Body Temp: " + data.body_temperature + " °C";
                    document.getElementById('ambtemp').textContent = "Ambient Temp: " + data.ambient_temperature + " °C";
                });
        }
        setInterval(updateDashboard, 2000);
        updateDashboard();
    </script>
</body>
</html>
""")

@app.route('/status')
def status():
    try:
        with open('logs/status.txt', 'r') as f:
            return f.read().strip()
    except:
        return "Normal"

@app.route('/sensor')
def sensor():
    try:
        df = pd.read_csv('logs/livedata.csv')
        if df.empty:
            return jsonify({
                "time": "--",
                "heartRate": "--",
                "spo2": "--",
                "body_temperature": "--",
                "ambient_temperature": "--"
            })
        last = df.iloc[-1]
        return jsonify({
            "time": str(last.get('time', '--')),
            "heartRate": str(last.get('heartRate', '--')),
            "spo2": str(last.get('spo2', '--')),
            "body_temperature": str(last.get('body_temperature', '--')),
            "ambient_temperature": str(last.get('ambient_temperature', '--'))
        })
    except:
        return jsonify({
            "time": "--",
            "heartRate": "--",
            "spo2": "--",
            "body_temperature": "--",
            "ambient_temperature": "--"
        })

@app.route('/blocked_ips')
def blocked_ips():
    try:
        with open('logs/blocked_ips.txt', 'r') as f:
            ips = [line.strip() for line in f if line.strip()]
        return jsonify(ips)
    except:
        return jsonify([])

if __name__ == "__main__":
    print('Web dashboard running on http://<pi_ip>:8050')
    app.run(host='0.0.0.0', port=8050, debug=False)
