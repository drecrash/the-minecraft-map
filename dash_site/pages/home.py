from dash import Dash, html, dcc, callback, Output, Input
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from shared_data import graphData
import dash
import json
import bisect

dash.register_page(__name__)


def get_path_path(target):
    page_path = next(
        (page["relative_path"] for page in dash.page_registry.values() if page["name"] == target),
        "/"
    )
    return page_path

def layout():

    intro_text = [
        html.P([
        "Welcome to the Minecraft Map project!\nThis project is an attempt to graph the Minecraft community on YouTube.\nMore details can be found "
        ,
        html.A("here,", href="https://github.com/drecrash/the-minecraft-map"),
        " but essentially: if one creator mentioned another: they're linked!\n"]),
        html.Br(),
        "If you want to see the graph itself, head "
        ,
        dcc.Link("here", href=get_path_path("Graph Explorer")),
        "\nIf you're curious about the overall graph statistics, head "
        ,
        dcc.Link("here", href=get_path_path("Global Analytics")),
        "\nTo see the stats of your favorite creator, head ",
        dcc.Link("here", href=get_path_path("Creator Stats")),
        "\nTo find the shortest path of connections from one creator to another, head ",
        dcc.Link("here", href=get_path_path("Shortest Path Calculator"))
        ]

    layout = [
        html.Div(children=[

            html.P(intro_text, style={'whiteSpace': 'pre-wrap'})

        ])
    ]

    return layout
