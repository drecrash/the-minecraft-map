from graphdata import GraphData
import os

API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:5000")

graphData = GraphData(API_BASE_URL)
