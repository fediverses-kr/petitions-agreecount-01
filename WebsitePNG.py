from flask import Flask, render_template_string, send_file, make_response
import matplotlib
matplotlib.use('Agg')  # Use Agg backend for rendering plots
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
import io
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)  # Set logging level to INFO

# Function to read the log file and return a DataFrame
def read_log_file(file_path):
    data = []
    try:
        with open(file_path, 'r') as file:
            for line in file:
                parts = line.split(': Agree Count = ')
                timestamp = datetime.strptime(parts[0], '%Y-%m-%d %H:%M:%S')
                agree_count = int(parts[1].strip())
                data.append({'timestamp': timestamp, 'agree_count': agree_count})
        return pd.DataFrame(data)
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

# Route for serving the graph image
@app.route('/graph.png')
def graph_png():
    try:
        app.logger.info("Generating graph.png")

        # Path to your log file
        file_path = 'AgreeCountLog.txt'

        # Read the log file and create the DataFrame
        df = read_log_file(file_path)

        if df.empty:
            raise ValueError("DataFrame is empty")

        # Create the graph
        img_bytes = create_graph(df)
        app.logger.info("Graph generated successfully")

        return send_file(img_bytes, mimetype='image/png')
    except Exception as e:
        app.logger.error(f"Error generating graph: {e}")
        return make_response(f"Error generating graph: {e}", 500)

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
        </head>
        <body>
            <h1>윤석열 대통령 탄핵소추안 즉각 발의 요청에 관한 청원</h1>
            <h2><a href="https://petitions-agreecount-02.fediverses.kr/">그래프로 보기</a><h2>
            <h2>Current: {{ latest_count }} ({{ latest_timestamp }})</h2>
            <img src="{{ url_for('graph_png') }}?t={{ latest_timestamp }}" alt="Agree Count Graph">
            <h2><a href="https://petitions.assembly.go.kr/proceed/afterEstablished/14CBAF8CE5733410E064B49691C1987F">동의하러 가기</a></h2>
            <p>본 사이트는 국회와 관련이 있지 않으며 국회와 아무 연관이 있지 않습니다. 개인이 사용하기 위하여 만들은 사이트이며, 국회 서버에 심한 부하를 주지 않도록 설계하였습니다.</p>
            <p>본 사이트는 운영이 중단될 수 있으며, 기본 업데이트 빈도는 5초+(국회서버 응답시간) 입니다.</p>
        </body>
        </html>
        '''

        app.logger.info("Index page loaded successfully")

        return render_template_string(html_template, latest_count=latest_count, latest_timestamp=latest_timestamp)
    except Exception as e:
        app.logger.error(f"Error loading index: {e}")
        return make_response(f"Error loading page: {e}", 500)

if __name__ == '__main__':
    app.run(debug=True, port=5173)
