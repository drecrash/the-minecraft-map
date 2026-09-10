from dash import Dash, html, dcc, callback, Output, Input
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from shared_data import graphData
import dash
import json
import bisect

dash.register_page(__name__,path_template="/creatordata/<creator_id>",name="Creator Stats")

def get_degree_status(creator_data):
    degrees = sorted(graphData.get_degree_distribution())
    ranks = list(range(1, len(degrees) + 1))

    creator_degree = creator_data["degree"]
    creator_rank = bisect.bisect_left(degrees, creator_degree) + 1

    fig = go.Figure()
    fig.add_scatter(
        x=ranks, y=degrees, mode="markers", name="All Creators",
        marker=dict(size=4, color="lightgray")
    )
    fig.add_scatter(
        x=[creator_rank], y=[creator_degree], mode="markers", name=creator_data["name"],
        marker=dict(size=14, color="crimson")
    )
    fig.update_layout(xaxis_title="Rank", yaxis_title="Degree")

    return fig

def get_similar_channels(creator_data):
    similar_channels = graphData.most_similar_by_mentions(creator_data["name"])
    return html.Div(children=[
            html.Div(children=[
                dcc.Link(f"{c["name"]}: {round(c["similarity"]*100,3)}%\n",href=f"/creatordata/{c["id"]}", target="_blank"),
                html.Br()
            ])
             for c in similar_channels  
            ]
    )

def get_connected_communities(creator_data):
    connected_comms = graphData.get_bridged_communities(creator_data["name"])

    return html.Div([
        html.P(f"Connected to {len(connected_comms)} different communities:"), html.Br(),
        html.Ul([html.Li(name) for name in connected_comms])
    ])

def suggestion_options(query):
    return [html.Option(value=name) for name in graphData.get_name_suggestions(query)]

@callback(
    Output("channel-options", "children"),
    Input("channel-search", "value")
)
def update_name_suggestions(value):
    return suggestion_options(value)

@callback(
    Output("url-redirect", "pathname"),
    Output("channel-button-submit", "n_clicks", allow_duplicate=True),
    Input("channel-search", "value"),
    Input("channel-button-submit", "n_clicks"),
    prevent_initial_call=True
)
def search_for_channel(channel_name, n_clicks):
    if n_clicks > 0:
        cid = graphData.get_channel_id(channel_name)
        return f"/creatordata/{cid}", 0
    return dash.no_update
    


def layout(creator_id):

    if str(creator_id).lower() == "none":
        layout = [
            html.Div([
                dcc.Input(
                    id="channel-search",
                    placeholder="Channel",
                    list='channel-options'
                ),
                html.Datalist(id="channel-options"),
                dcc.Location(id='url-redirect', refresh=True),
                html.Button('Search',id='channel-button-submit',n_clicks=0)
            ])
        ]
    else:
        data = graphData.get_creator_data(id=creator_id)
        layout = [
            html.Div(className="chart-card", children=[
                html.H3("Profile"),
                dcc.Link("Search someone else!",href="/creatordata/none"), html.Br(), html.Br(),
                html.Img(
                    src=data["pfp"]
                ),
                html.P(f"Name: {data["name"]}"),
                html.P(f"Community: {data["community_label"]}"),
                html.A(f"Channel Link", href=f"https://youtube.com/channel/{data["id"]}")
            ]),
            html.Div(className="chart-card", children=[
                html.H3("Stats"),
                html.P(f"Hidden Influence: {round(data["hidden_influence"],3)}"),
                html.P(f"Centrality: {round(data["betweenness"],5)}"),
                html.P(f"Degree: {round(data["degree"],5)}")
            ]),
            html.Div(className="chart-card", children=[
                html.H3("Connections"),
                html.P("Most similar channels based on outgoing edges:"),
                get_similar_channels(data),
                get_connected_communities(data)
            ]),
            html.Div(className="chart-card", children=[
                html.H3("Degree Distribution"),
                dcc.Graph(id="degree-fig",figure=get_degree_status(data))
            ])
        ]

    return layout
