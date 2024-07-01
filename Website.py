from flask import Flask, render_template_string
import plotly.express as px
import pandas as pd
from datetime import datetime
from flask_socketio import SocketIO
import threading
import time
import os
import json
import plotly

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Function to read the log file and return a DataFrame
def read_log_file(file_path):
    data = []
    with open(file_path, 'r') as file:
        for line in file:
            parts = line.split(': Agree Count = ')
            timestamp = datetime.strptime(parts[0], '%Y-%m-%d %H:%M:%S')
            agree_count = int(parts[1].strip())
            data.append({'timestamp': timestamp, 'agree_count': agree_count})
    return pd.DataFrame(data)

# Function to create an interactive graph using Plotly
def create_graph(dataframe):
    fig = px.line(dataframe, x='timestamp', y='agree_count', title='Agree Count Over Time')
    fig.update_layout(
        xaxis_title='Timestamp',
        yaxis_title='Agree Count',
        yaxis_tickformat=',',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color="#333333"),
        title_font=dict(size=24),
    )
    fig.update_traces(line=dict(color="#1E88E5", width=3))
    return fig

# Global variable to control updates
update_active = True

# Function to check for file changes and emit updates
def check_file_changes():
    global update_active
    file_path = 'AgreeCountLog.txt'
    last_modified = os.path.getmtime(file_path)
    
    while True:
        time.sleep(5)
        if update_active:
            current_modified = os.path.getmtime(file_path)
            if current_modified > last_modified:
                df = read_log_file(file_path)
                latest_count = df['agree_count'].iloc[-1] if not df.empty else 'No data available'
                latest_timestamp = df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S') if not df.empty else 'No data available'
                fig = create_graph(df)
                graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
                socketio.emit('update', {'latest_count': str(latest_count), 'latest_timestamp': latest_timestamp, 'graph': graph_json})
                last_modified = current_modified

# Route for the main page
@app.route('/')
def index():
    file_path = 'AgreeCountLog.txt'
    df = read_log_file(file_path)
    latest_count = df['agree_count'].iloc[-1] if not df.empty else 'No data available'
    latest_timestamp = df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S') if not df.empty else 'No data available'
    fig = create_graph(df)
    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    html_template = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Agree Count Graph</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
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
        </style>
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var socket = io();
                var graphData = JSON.parse('{{ graph_json | safe }}');
                Plotly.newPlot('graph-container', graphData.data, graphData.layout);

                var updateActive = true;

                socket.on('connect', function() {
                    console.log('WebSocket connected');
                });
                socket.on('update', function(data) {
                    if (updateActive) {
                        console.log('Received update:', data);
                        document.getElementById('latest-count').textContent = data.latest_count;
                        document.getElementById('latest-timestamp').textContent = data.latest_timestamp;
                        var updatedGraph = JSON.parse(data.graph);
                        Plotly.react('graph-container', updatedGraph.data, updatedGraph.layout);
                    }
                });

                document.getElementById('stopUpdate').addEventListener('click', function() {
                    updateActive = false;
                    this.style.display = 'none';
                    document.getElementById('resumeUpdate').style.display = 'inline-block';
                });

                document.getElementById('resumeUpdate').addEventListener('click', function() {
                    updateActive = true;
                    this.style.display = 'none';
                    document.getElementById('stopUpdate').style.display = 'inline-block';
                });
            });
        </script>
    </head>
    <body>
        <div class="container">
            <h1>윤석열 대통령 탄핵소추안 즉각 발의 요청에 관한 청원</h1>
            <h2><a href="https://petitions-agreecount-01.fediverses.kr/">이미지로 보기</a></h2>
            <div class="current-count">
                Current: <span id="latest-count">{{ latest_count }}</span> 
                <br>
                <small>Last updated: <span id="latest-timestamp">{{ latest_timestamp }}</span></small>
            </div>
            <button id="stopUpdate" class="button">Stop Update</button>
            <button id="resumeUpdate" class="button">Resume Update</button>
            <div id="graph-container"></div>
            <h3><a href="https://namu.wiki/thread/RoughFurtiveAngryFather#19">나O위키에서 이 웹사이트의 "동의하러 가기"라는 문구가 정치적으로 편향된 내용이라고 판단했음을 발견하여, 이 사이트는 정치적으로 편향된 내용을 올릴 의도가 없음을 알리기 위해 바로가기 링크를 삭제하였습니다.</a></h3>
            <div class="footer">
                <p>본 사이트는 국회와 관련이 있지 않으며 국회와 아무 연관이 있지 않습니다. 개인이 사용하기 위하여 만들은 사이트이며, 국회 서버에 심한 부하를 주지 않도록 설계하였습니다.</p>
                <p>본 사이트는 운영이 중단될 수 있으며, 기본 업데이트 빈도는 5초+(국회서버 응답시간) 입니다.</p>
            </div>
        </div>
    </body>
    </html>
    '''

    return render_template_string(html_template, latest_count=latest_count, latest_timestamp=latest_timestamp, graph_json=graph_json)

@socketio.on('connect')
def handle_connect():
    print(f"Client connected at {datetime.now()}")

if __name__ == '__main__':
    thread = threading.Thread(target=check_file_changes)
    thread.daemon = True
    thread.start()
    socketio.run(app, debug=True)
