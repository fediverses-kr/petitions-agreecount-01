import requests
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, send_file, make_response, send_from_directory
from flask_cors import CORS
import threading
import json
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask_socketio import SocketIO, emit

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# File to store wait times
data_file = 'wait_times.json'

# In-memory cache
cache = {
    'wait_times': [],
    'latest_timestamp': None,
    'latest_count': 0
}
cache_time = None  # To track when the cache was last updated
cache_lock = threading.Lock()  # Lock for thread-safe cache updates

# Load existing data if available
if os.path.exists(data_file):
    with open(data_file, 'r') as file:
        cache['wait_times'] = json.load(file)
        if cache['wait_times']:
            cache['latest_timestamp'] = cache['wait_times'][-1][0]
            cache['latest_count'] = cache['wait_times'][-1][1]
            cache_time = datetime.now()

# Track the number of connected users
connected_users = 0

# Function to extract nwait from the response
def extract_nwait(response_text):
    try:
        # Split the response text to find the nwait value
        nwait_part = response_text.split("nwait=")[1]
        nwait_value = nwait_part.split("&")[0]
        return nwait_value
    except IndexError:
        return None

# Function to update wait times if more than 30 seconds have passed
def update_wait_times():
    global cache_time
    while True:
        current_time = datetime.now()
        if cache_time is None or (current_time - cache_time).seconds >= 30:
            with cache_lock:
                timestamp = int(time.time() * 1000)
                base_url = f"https://wpetitions.assembly.go.kr/ts.wseq?opcode=5101&nfid=0&prefix=NetFunnel.gRtype=5101;&sid=service_1&aid=naep_1&js=yes&{timestamp}="
                try:
                    response = requests.get(base_url)
                    response_text = response.text
                    nwait_value = extract_nwait(response_text)

                    if nwait_value:
                        cache['wait_times'].append((current_time.strftime("%Y-%m-%d %H:%M:%S"), int(nwait_value)))
                        # Keep only the latest 800 entries
                        if len(cache['wait_times']) > 800:
                            cache['wait_times'] = cache['wait_times'][-800:]
                        cache['latest_timestamp'] = current_time.strftime("%Y-%m-%d %H:%M:%S")
                        cache['latest_count'] = int(nwait_value)
                        cache_time = current_time
                        print(f"{current_time}: Waiting: {nwait_value}")

                        # Save the updated wait times to file
                        with open(data_file, 'w') as file:
                            json.dump(cache['wait_times'], file)

                        # Emit updated data to all connected clients
                        times = [wt[0] for wt in cache['wait_times']]
                        waits = [wt[1] for wt in cache['wait_times']]
                        socketio.emit('update', {
                            'latest_count': cache['latest_count'],
                            'latest_timestamp': cache['latest_timestamp'],
                            'times': times,
                            'waits': waits
                        })

                except Exception as e:
                    print(f"{current_time}: An error occurred: {e}")

        time.sleep(1)

# Background thread to update wait times
threading.Thread(target=update_wait_times, daemon=True).start()

@app.route('/')
def index():
    return render_template('waiting_count.html')

@app.route('/graph-only')
def graph_only():
    return render_template('waiting-graph-only.html')

@app.route('/initial-data')
def initial_data():
    with cache_lock:
        times = [wt[0] for wt in cache['wait_times']]
        waits = [wt[1] for wt in cache['wait_times']]
        return jsonify({
            'latest_count': cache['latest_count'],
            'latest_timestamp': cache['latest_timestamp'],
            'times': times,
            'waits': waits
        })

@app.route('/raw-data')
def serve_file():
    with cache_lock:
        return jsonify(cache['wait_times'])

@socketio.on('connect')
def handle_connect():
    global connected_users
    connected_users += 1
    emit('user_count', {'count': connected_users}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    global connected_users
    connected_users -= 1
    emit('user_count', {'count': connected_users}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5230)
