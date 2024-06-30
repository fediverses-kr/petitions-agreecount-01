from flask import Flask, render_template_string
import plotly.express as px
import pandas as pd
from datetime import datetime

app = Flask(__name__)

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
        yaxis_tickformat=',',  # Ensure the y-axis shows integers without scientific notation
    )
    return fig

# Route for the main page
@app.route('/')
def index():
    # Path to your log file
    file_path = 'AgreeCountLog.txt'
    
    # Read the log file and create the DataFrame
    df = read_log_file(file_path)
    
    # Get the latest count
    latest_count = df['agree_count'].iloc[-1] if not df.empty else 'No data available'
    latest_timestamp = df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S') if not df.empty else 'No data available'

    # Create the interactive graph
    fig = create_graph(df)
    
    # Convert the Plotly figure to HTML
    graph_html = fig.to_html(full_html=False)
    
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
        <h2><a href="https://petitions-agreecount-01.fediverses.kr/">이미지로 보기</a><h2>
        <h2>Current: {{ latest_count }} ({{latest_timestamp}})</h2>
        <div>{{ graph|safe }}</div>
        <h2><a href="https://petitions.assembly.go.kr/proceed/afterEstablished/14CBAF8CE5733410E064B49691C1987F">동의하러 가기</a></h2>
        <p>본 사이트는 국회와 관련이 있지 않으며 국회와 아무 연관이 있지 않습니다. 개인이 사용하기 위하여 만들은 사이트이며, 국회 서버에 심한 부하를 주지 않도록 설계하였습니다.</p>
        <p>본 사이트는 운영이 중단될 수 있으며, 기본 업데이트 빈도는 5초+(국회서버 응답시간) 입니다.</p>
    </body>
    </html>
    '''
    
    return render_template_string(html_template, latest_count=latest_count, graph=graph_html, latest_timestamp=latest_timestamp)

if __name__ == '__main__':
    app.run(debug=True)
