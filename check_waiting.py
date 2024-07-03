import requests
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template
from flask_cors import CORS
import threading
import json
import os
from flask_socketio import SocketIO, emit
import logging

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

logging.basicConfig(level=logging.WARNING)
app.logger.setLevel(logging.WARNING)

log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

data_file = 'wait_times.json'

cache = {
    'wait_times': [],
    'latest_timestamp': None,
    'latest_count': 0
}
cache_time = None
cache_lock = threading.Lock()

if os.path.exists(data_file):
    with open(data_file, 'r') as file:
        cache['wait_times'] = json.load(file)
        if cache['wait_times']:
            cache['latest_timestamp'] = cache['wait_times'][-1][0]
            cache['latest_count'] = cache['wait_times'][-1][1]
            cache_time = datetime.now()

connected_users = 0

def extract_nwait(response_text):
    try:
        nwait_part = response_text.split("nwait=")[1]
        nwait_value = nwait_part.split("&")[0]
        return int(nwait_value)
    except (IndexError, ValueError):
        return None

def update_wait_times():
    global cache_time
    while True:
        current_time = datetime.now()
        if cache_time is None or (current_time - cache_time).total_seconds() >= 14:
            with cache_lock:
                timestamp = int(time.time() * 1000)
                base_url = f"https://wpetitions.assembly.go.kr/ts.wseq?opcode=5101&nfid=0&prefix=NetFunnel.gRtype=5101;&sid=service_1&aid=naep_1&js=yes&{timestamp}="
                try:
                    response = requests.get(base_url)
                    nwait_value = extract_nwait(response.text)

                    if nwait_value is not None:
                        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
                        cache['wait_times'].append((current_time_str, nwait_value))
                        if len(cache['wait_times']) > 50000:
                            cache['wait_times'] = cache['wait_times'][-50000:]
                        cache['latest_timestamp'] = current_time_str
                        cache['latest_count'] = nwait_value
                        cache_time = current_time
                        print(f"{current_time_str}: Waiting: {nwait_value}")

                        saved = False
                        try:
                            with open(data_file, 'w') as file:
                                json.dump(cache['wait_times'], file)
                            saved = True
                        except Exception as e:
                            print(f"Error saving to file on first attempt: {e}")

                        if not saved:
                            # Retry saving once more
                            try:
                                with open(data_file, 'w') as file:
                                    json.dump(cache['wait_times'], file)
                                print("Successfully saved to file on second attempt")
                            except Exception as e:
                                print(f"Error saving to file on second attempt: {e}")

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

threading.Thread(target=update_wait_times, daemon=True).start()

@app.route('/')
def index():
    return render_template('waiting_count.html')

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
    
@app.route('/latest-data')
def latest_data():
    with cache_lock:
        latest_entry = cache['wait_times'][-1] if cache['wait_times'] else ("", 0)
        latest_data_formatted = [[latest_entry[0], latest_entry[1]]]
        return jsonify(latest_data_formatted)

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
    socketio.run(app, debug=False, port=5230)