from flask import Flask, render_template_string, send_file, send_from_directory, make_response, jsonify
import matplotlib
matplotlib.use('Agg')  # Use Agg backend for rendering plots
import matplotlib.pyplot as plt
import pandas as pd
from flask_cors import CORS
import numpy as np  # Import numpy
from datetime import datetime, timedelta
from flask_socketio import SocketIO, emit
import threading
import time
import os
import io
import logging
from functools import wraps
from cachetools import TTLCache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
logging.basicConfig(level=logging.WARNING)  # Set logging level to DEBUG for troubleshooting
app.logger.setLevel(logging.WARNING)

# Configure logging to suppress INFO messages
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

update_active = True  # Global variable to control updates
graph_cache = None  # Cache for the graph image
last_modified = 0  # Timestamp of the last modification to the log file
user_count = 0  # Global counter for connected users

# Function to read the log file and return a DataFrame
def read_log_file(file_path):
    try:
        data = pd.read_csv(file_path, sep=': Agree Count = ', header=None, names=['timestamp', 'agree_count'], engine='python')
        data['timestamp'] = pd.to_datetime(data['timestamp'], format='%Y-%m-%d %H:%M:%S')
        data['agree_count'] = data['agree_count'].astype(int)
        return data
    except Exception as e:
        app.logger.error(f"Error reading log file: {e}")
        return pd.DataFrame()

# Function to create a graph using Matplotlib
def create_graph(dataframe):
    plt.figure(figsize=(10, 6))
    plt.plot(dataframe['timestamp'], dataframe['agree_count'], marker='o')
    plt.title('Agree Count Over Time')
    plt.xlabel('Timestamp')
    plt.ylabel('Agree Count')
    plt.grid(True)
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

# Function to update the graph cache and prediction
def update_graph_cache_and_prediction():
    global graph_cache, last_modified
    file_path = 'AgreeCountLog.txt'
    
    current_modified = os.path.getmtime(file_path)
    if current_modified > last_modified:
        df = read_log_file(file_path)
        if not df.empty:
            graph_cache = create_graph(df)
            last_modified = current_modified
            latest_count = df['agree_count'].iloc[-1]
            latest_timestamp = df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')
            target_date = None
            if latest_count < 2000000:
                target_date = predict_target_date(df).strftime('%Y-%m-%d %H:%M:%S')
            socketio.emit('update', {
                'latest_count': str(latest_count),
                'latest_timestamp': latest_timestamp,
                'graph': '/graph.png',
                'target_date': target_date
            })

# Background thread to periodically update the graph cache and prediction
def background_update():
    while True:
        if update_active:
            update_graph_cache_and_prediction()
        time.sleep(1)

# Function to predict when the agree count will reach 1,000,000
def predict_target_date(df, target=2000000):
    df['time_diff'] = (df['timestamp'] - df['timestamp'].min()).dt.total_seconds()
    model = np.polyfit(df['time_diff'], df['agree_count'], 1)
    slope = model[0]
    intercept = model[1]
    time_needed = (target - intercept) / slope
    target_date = df['timestamp'].min() + timedelta(seconds=time_needed)
    return target_date

# Route to serve the image only with direct access
@app.route('/private/<path:filename>')
def serve_image(filename):
    return send_from_directory('private', filename)

# Send the original data on request
@app.route('/raw_data')
def serve_file():
    return send_from_directory('.', 'AgreeCountLog.txt')

# Update History
@app.route('/update-history')
def update_history():
    return send_from_directory('.', 'update_history.html')

# Route for serving the graph image
@app.route('/graph.png')
def graph_png():
    global graph_cache
    if graph_cache is None:
        update_graph_cache_and_prediction()
    return send_file(io.BytesIO(graph_cache.getvalue()), mimetype='image/png')

def read_data_from_file(filename):
    with open(filename, 'r') as file:
        return file.readlines()

cache = {
    'data': None,
    'timestamp': 0
}
cache_lock = threading.Lock()
# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["5000 per minute", "200000 per hour"]
)

# Initialize cache
cache = TTLCache(maxsize=1000, ttl=60)

# ... (rest of the original code remains the same)

# Caching decorator
def cached(timeout=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = f.__name__ + str(args) + str(kwargs)
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            result = f(*args, **kwargs)
            cache[cache_key] = result
            return result
        return decorated_function
    return decorator

# Modified route with caching and rate limiting
@app.route('/api/1_hour_update/json')
@app.route('/api/1h-update/json')
@limiter.limit("5000 per minute")
@cached(timeout=60)
def hourly_update():
    current_time = time.time()
    
    data = read_data_from_file('AgreeCountLog.txt')
    hourly_data = {}
    
    for entry in data:
        entry = entry.strip()  # Remove any trailing newline characters
        if not entry:  # Skip empty lines
            continue
        
        try:
            timestamp_str, count_str = entry.split(": Agree Count = ")
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            count = int(count_str)
        except ValueError:
            # Handle the case where the line does not match the expected format
            continue
        
        # Round down to the nearest hour
        hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
        
        # Always update the count, this will keep the latest count for each hour
        hourly_data[hour_key] = count
    
    # Sort the hours
    sorted_hours = sorted(hourly_data.keys())
    
    result = []
    for i in range(len(sorted_hours) - 2):  # Adjust the range to exclude the last hour
        current_hour = sorted_hours[i]
        next_hour = sorted_hours[i + 1]
        
        joined = hourly_data[next_hour] - hourly_data[current_hour]
        
        result.append({
            'hour': (current_hour + timedelta(hours=1)).isoformat(),  # Shift to +1 hour
            'count': hourly_data[current_hour],
            'joined': joined
        })
    
    return jsonify(result)

# Route for the main page
@app.route('/')
def index():
    try:
        app.logger.info("Loading index page")

        # Path to your log file
        file_path = 'AgreeCountLog.txt'

        # Read the log file and create the DataFrame
        df = read_log_file(file_path)

        if df.empty:
            raise ValueError("DataFrame is empty")

        # Get the latest count and timestamp
        latest_count = df['agree_count'].iloc[-1] if not df.empty else 'No data available'
        latest_timestamp = df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S') if not df.empty else 'No data available'

        # Predict the date when the count will reach 1,000,000
        target_date = None
        if latest_count < 2000000:
            target_date = predict_target_date(df).strftime('%Y-%m-%d %H:%M:%S')

        # HTML template to display the graph and the latest count
        html_template = '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Agree Count Graph</title>
            <meta property="og:title" content="Agree Count Graph">
            <meta name="twitter:card" content="Agree Count Graph">
            <meta property="og:url" content="https://petitions-agreecount-01.fediverses.kr/">
            <meta name="twitter:url" content="https://petitions-agreecount-01.fediverses.kr/">
            <meta name="twitter:title" content="청원 동의수 실시간 현황 및 그래프">
            <meta property="og:image" content="https://petitions-agreecount-01.fediverses.kr/graph.png">
            <meta name="twitter:image" content="https://petitions-agreecount-01.fediverses.kr/graph.png">
            <meta property="og:description" content="실시간 청원 동의수 현황 및 그래프를 확인할 수 있습니다.">
            <meta name="twitter:description" content="실시간 청원 동의수 현황 및 그래프를 확인할 수 있습니다.">
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f4f4f4;
                }
                h1, h2, h3 {
                    color: #2c3e50;
                }
                h1 {
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                }
                .container {
                    background-color: #ffffff;
                    border-radius: 8px;
                    padding: 20px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }
                .current-count {
                    font-size: 24px;
                    font-weight: bold;
                    color: #2980b9;
                    margin-bottom: 0px;
                }
                #graph-container {
                    margin-top: 20px;
                }
                a {
                    color: #3498db;
                    text-decoration: none;
                }
                a:hover {
                    text-decoration: underline;
                }
                .footer {
                    margin-top: 20px;
                    font-size: 14px;
                    color: #7f8c8d;
                }
                .button {
                    display: inline-block;
                    padding: 10px 20px;
                    margin: 10px 5px;
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    transition: background-color 0.3s;
                }
                .button:hover {
                    background-color: #2980b9;
                }
                #stopUpdate {
                    background-color: #e74c3c;
                }
                #stopUpdate:hover {
                    background-color: #c0392b;
                }
                #resumeUpdate {
                    display: none;
                    background-color: #2ecc71;
                }
                #resumeUpdate:hover {
                    background-color: #27ae60;
                }
                .rolling-number {
                    font-size: 36px;
                    font-weight: bold;
                    color: #2980b9;
                    transition: all 0.5s ease-out;
                }
                .target-date {
                    display: none;
                    font-size: 17px;
                    font-weight: bold;
                    color: #2980b9;
                }
            </style>
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    var socket = io();
                    var updateActive = true;

                    function animateValue(obj, start, end, duration) {
                        let startTimestamp = null;
                        const step = (timestamp) => {
                            if (!startTimestamp) startTimestamp = timestamp;
                            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                            obj.innerHTML = Math.floor(progress * (end - start) + start).toLocaleString();
                            if (progress < 1) {
                                window.requestAnimationFrame(step);
                            }
                        };
                        window.requestAnimationFrame(step);
                    }

                    socket.on('connect', function() {
                        console.log('WebSocket connected');
                    });

                    socket.on('update', function(data) {
                        if (updateActive) {
                            console.log('Received update:', data);
                            var latestCountElement = document.getElementById('latest-count');
                            var currentCount = parseInt(latestCountElement.textContent.replace(/,/g, ''));
                            var newCount = parseInt(data.latest_count);
                            animateValue(latestCountElement, currentCount, newCount, 1000);
                            document.getElementById('latest-timestamp').textContent = data.latest_timestamp;
                            document.getElementById('graph-image').src = data.graph + '?t=' + data.latest_timestamp;
                            if (data.target_date) {
                                document.getElementById('target-date').style.display = 'block';
                                document.getElementById('target-date').textContent = '200만 예상일시: ' + data.target_date;
                            } else {
                                document.getElementById('target-date').style.display = 'none';
                            }
                        }
                    });

                    socket.on('user_count', function(data) {
                        document.getElementById('user-count').textContent = data.count;
                    });

                    document.getElementById('stopUpdate').addEventListener('click', function() {
                        updateActive = false;
                        socket.emit('update_status', {active: false});
                        this.style.display = 'none';
                        document.getElementById('resumeUpdate').style.display = 'inline-block';
                    });

                    document.getElementById('resumeUpdate').addEventListener('click', function() {
                        updateActive = true;
                        socket.emit('update_status', {active: true});
                        this.style.display = 'none';
                        document.getElementById('stopUpdate').style.display = 'inline-block';
                    });
                });
            </script>
        </head>
        <body>
            <div class="container">
                <h1>윤석열 대통령 탄핵소추안 즉각 발의 요청에 관한 청원</h1>
                <h2><a href="https://petitions-agreecount-02.fediverses.kr/">그래프로 보기</a> | <a href="javascript:if(window.confirm('로딩에 시간이 다소 소요될 수 있습니다. 확인을 누르신 후 잠시 기다려주세요.')){window.open('https://petitions.assembly.go.kr/status/onGoing/14CBAF8CE5733410E064B49691C1987F');}">동의하러 가기</a> (<a href="https://petitions-waitcount-01.fediverses.kr/">대기열</a>) | <a href="https://twitter.com/intent/post?text=%23%ED%83%84%ED%95%B5%EC%B2%AD%EC%9B%90+%EC%8B%A4%EC%8B%9C%EA%B0%84+%EB%8F%99%EC%9D%98%EC%88%98+%EB%B3%B4%EB%9F%AC%EA%B0%80%EA%B8%B0%0A&url=https%3A%2F%2Fpetitions-agreecount-01.fediverses.kr%2F%0A" target="_blank"><img src="https://petitions-agreecount-01.fediverses.kr/private/x-128.png" style="width: 28px;margin: -4px;"></a></h2>
                <div class="current-count">
                    현재 동의수: <span id="latest-count" class="rolling-number">{{ latest_count }}</span> 명
                    <br>
                    <small>기준일시: <span id="latest-timestamp">{{ latest_timestamp }}</span></small>
                </div>
                <div id="target-date" class="target-date"></div>
                <img id="graph-image" src="{{ url_for('graph_png') }}?t={{ latest_timestamp }}" alt="Agree Count Graph">
                <div>
                    <strong>Users Online (Image): <span id="user-count">0</span></strong> | <a href="https://petitions-agreecount-01.fediverses.kr/raw_data">평문데이터 보기</a>
                </div>
                <div class="footer">
                    <p>본 사이트는 국회와 관련이 있지 않으며 국회와 아무 연관이 있지 않습니다. 개인이 사용하기 위하여 만들은 사이트이며, 국회 서버에 심한 부하를 주지 않도록 설계하였습니다.</p>
                    <p>본 사이트는 운영이 중단될 수 있으며, 기본 업데이트 빈도는 5초+(국회서버 응답시간) 입니다.</p>
                    <p><a href="https://petitions-agreecount-01.fediverses.kr/update-history">업데이트 기록</a></p>
                </div>
            </div>
        </body>
        </html>
        '''

        app.logger.info("Index page loaded successfully")

        return render_template_string(html_template, latest_count=latest_count, latest_timestamp=latest_timestamp, target_date=target_date)
    except Exception as e:
        app.logger.error(f"Error loading index: {e}")
        return make_response(f"Error loading page: {e}", 500)

@socketio.on('connect')
def handle_connect():
    global user_count
    user_count += 1
    app.logger.info(f"Client connected at {datetime.now()}. Total users: {user_count}")
    socketio.emit('user_count', {'count': user_count})

@socketio.on('disconnect')
def handle_disconnect():
    global user_count
    user_count -= 1
    app.logger.info(f"Client disconnected at {datetime.now()}. Total users: {user_count}")
    socketio.emit('user_count', {'count': user_count})

if __name__ == '__main__':
    thread = threading.Thread(target=background_update)
    thread.daemon = True
    thread.start()
    socketio.run(app, debug=False, port=5120)
