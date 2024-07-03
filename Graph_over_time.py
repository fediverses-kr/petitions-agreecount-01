from flask import Flask, render_template_string, jsonify
import pandas as pd
import requests
import json
import time
import threading

app = Flask(__name__)

# Initialize cache variables and lock
cache_data = None
cache_timestamp = 0
CACHE_TIMEOUT = 180  # Cache timeout in seconds (3 minutes)
cache_lock = threading.Lock()

# Function to fetch wait times data from JSON file
def fetch_wait_times(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    df = pd.DataFrame(data, columns=["time", "count"])
    df["time"] = pd.to_datetime(df["time"])
    return df

# Function to fetch petition data from API
def fetch_petition_data(url):
    response = requests.get(url)
    data = response.json()
    df = pd.DataFrame(data)
    df["hour"] = pd.to_datetime(df["hour"])
    return df

# Flask route for the main page
@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Interactive Plot</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                background-color: #f4f4f4;
            }
            h1 {
                text-align: center;
                margin: 20px;
            }
            #plot {
                width: 100%;
                max-width: 800px;
                height: auto;
            }
        </style>
    </head>
    <body>
        <h1>청원 페이지 대기자수와 탄핵청원 동의증감수 그래프</h1>
        <h3>드래그와 클릭, 더블클릭 등으로 표를 움직여보세요.</h3>
        <div id="plot"></div>
        <h2><a href="https://petitions-agreecount-01.fediverses.kr/">현재 동의수 이미지로 보기</a> | <a href="https://petitions-agreecount-02.fediverses.kr/">현재 동의수 그래프로 보기</a> | <a href="https://petitions-waitcount-01.fediverses.kr/">현재 웹사이트 대기자 수 보기</a> | <a href="javascript:if(window.confirm('로딩에 시간이 다소 소요될 수 있습니다. 확인을 누르신 후 잠시 기다려주세요.')){window.open('https://petitions.assembly.go.kr/status/onGoing/14CBAF8CE5733410E064B49691C1987F');}">동의하러 가기</a></h2>

        <script>
            fetch('/plot-data')
            .then(response => response.json())
            .then(data => {
                var trace1 = {
                    x: data.time,
                    y: data.count,
                    mode: 'lines',
                    name: '대기자수(실시간)',
                    yaxis: 'y'
                };
                var trace2 = {
                    x: data.hour,
                    y: data.joined,
                    mode: 'lines',
                    name: '추가 동의자수(1시간)',
                    yaxis: 'y'
                };
                var layout = {
                    title: 'Increase in Petitioners and Number of People Waiting Over Time',
                    yaxis: {title: 'Number of Peoples'},
                    xaxis: {title: 'Time'},
                    showlegend: true,
                    legend: { "orientation": "h", x: 0.5, xanchor: 'center', y: -0.2 }
                };
                var data = [trace1, trace2];
                Plotly.newPlot('plot', data, layout, {responsive: true});
            });
        </script>
    </body>
    </html>
    """)

# Flask route to provide data for the plot
@app.route('/plot-data')
def plot_data():
    global cache_data, cache_timestamp
    current_time = time.time()
    
    # Check if cached data is still valid
    if cache_data is not None and (current_time - cache_timestamp) < CACHE_TIMEOUT:
        return jsonify(cache_data)
    
    with cache_lock:
        # Double-check the cache within the lock
        if cache_data is not None and (current_time - cache_timestamp) < CACHE_TIMEOUT:
            return jsonify(cache_data)
        
        # Fetch new data
        wait_times_df = fetch_wait_times('wait_times.json')
        petition_df = fetch_petition_data('https://petitions-agreecount-01.fediverses.kr/api/1_hour_update/json')

        data = {
            'time': wait_times_df['time'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'count': wait_times_df['count'].tolist(),
            'hour': petition_df['hour'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'joined': petition_df['joined'].tolist()
        }

        # Update cache
        cache_data = data
        cache_timestamp = current_time
    
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=3211)
