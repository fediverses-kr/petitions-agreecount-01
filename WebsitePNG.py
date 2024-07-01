from flask import Flask, render_template_string, send_file, send_from_directory, make_response
import matplotlib
matplotlib.use('Agg')  # Use Agg backend for rendering plots
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from flask_socketio import SocketIO, emit
import threading
import time
import os
import io
import logging

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
logging.basicConfig(level=logging.DEBUG)  # Set logging level to DEBUG for troubleshooting

update_active = True  # Global variable to control updates
graph_cache = None  # Cache for the graph image
last_modified = 0  # Timestamp of the last modification to the log file

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

# Function to update the graph cache
def update_graph_cache():
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
            socketio.emit('update', {'latest_count': str(latest_count), 'latest_timestamp': latest_timestamp, 'graph': '/graph.png'})

# Background thread to periodically update the graph cache
def background_update():
    while True:
        if update_active:
            update_graph_cache()
        time.sleep(5)

# Route to serve the image only with direct access
@app.route('/private/<path:filename>')
def serve_image(filename):
    return send_from_directory('private', filename)

# Route for serving the graph image
@app.route('/graph.png')
def graph_png():
    global graph_cache
    if graph_cache is None:
        update_graph_cache()
    return send_file(io.BytesIO(graph_cache.getvalue()), mimetype='image/png')

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

        # HTML template to display the graph and the latest count
        html_template = '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Agree Count Graph</title>
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
                    margin-bottom: 20px;
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
                            document.getElementById('graph-image').src = data.graph + '?t=' + new Date().getTime();
                        }
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
                <h2><a href="https://petitions-agreecount-02.fediverses.kr/">그래프로 보기</a> | <a href="https://petitions.assembly.go.kr/status/onGoing/14CBAF8CE5733410E064B49691C1987F">동의하러 가기</a></h2>
                <div class="current-count">
                    Current: <span id="latest-count" class="rolling-number">{{ latest_count }}</span>
                    <br>
                    <small>Last updated: <span id="latest-timestamp">{{ latest_timestamp }}</span></small>
                </div>
                <button id="stopUpdate" class="button">Stop Update</button>
                <button id="resumeUpdate" class="button">Resume Update</button>
                <img id="graph-image" src="{{ url_for('graph_png') }}?t={{ latest_timestamp }}" alt="Agree Count Graph">
                <div class="footer">
                    <p>본 사이트는 국회와 관련이 있지 않으며 국회와 아무 연관이 있지 않습니다. 개인이 사용하기 위하여 만들은 사이트이며, 국회 서버에 심한 부하를 주지 않도록 설계하였습니다.</p>
                    <p>본 사이트는 운영이 중단될 수 있으며, 기본 업데이트 빈도는 5초+(국회서버 응답시간) 입니다.</p>
                </div>
            </div>
        </body>
        </html>
        '''

        app.logger.info("Index page loaded successfully")

        return render_template_string(html_template, latest_count=latest_count, latest_timestamp=latest_timestamp)
    except Exception as e:
        app.logger.error(f"Error loading index: {e}")
        return make_response(f"Error loading page: {e}", 500)

@socketio.on('connect')
def handle_connect():
    app.logger.info(f"Client connected at {datetime.now()}")

@socketio.on('update_status')
def handle_update_status(data):
    global update_active
    update_active = data['active']
    status = "resumed" if update_active else "stopped"
    app.logger.info(f"Updates have been {status}.")

if __name__ == '__main__':
    thread = threading.Thread(target=background_update)
    thread.daemon = True
    thread.start()
    socketio.run(app, debug=True, port=5173)
