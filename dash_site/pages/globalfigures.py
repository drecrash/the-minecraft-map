from dash import Dash, html, dcc, callback, Output, Input
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from shared_data import graphData
import dash
import json
import bisect
import pandas as pd

dash.register_page(__name__,name="Global Analytics")

def create_community_count_chart():
    all_communities = graphData.get_all_communities()
    df = pd.DataFrame({
        "Community": [name for name in all_communities],
        "Size": [all_communities[i]["size"] for i in all_communities]
    })

    fig = px.pie(df, values="Size", names="Community", title="Community Sizes")
    fig.update_traces(textinfo='none')

    return fig

def create_community_insularity_chart():
    insularity_data = graphData.get_insularity_data()


    df = pd.DataFrame({

        "Community": [comm for comm in insularity_data],
        "Insularity": [insularity_data[comm]["insularity"] for comm in insularity_data]

    })

    fig = px.bar(df,x="Community",y="Insularity")
    return fig

@callback(
    Output("leaderboard-figure", "figure"),
    Output("leaderboard-reverse-btn", "children"),
    Input("leaderboard-sort", "value"),
    Input("leaderboard-reverse-btn", "n_clicks")
)
def get_leaderboard(sort_by, n_clicks):
    TOP_N = 20
    show_lowest = (n_clicks > 0) and n_clicks % 2 == 1

    data = graphData.get_all_nodes(sort_by=sort_by)
    sortable_attributes = graphData.get_sortable_attributes()

    creator_ids = list(data.keys())
    if show_lowest:
        creator_ids = list(reversed(creator_ids))

    top_creators = creator_ids[:TOP_N]

    df = pd.DataFrame({
        "Creator": [data[id]["name"] for id in top_creators],
        "Score":  [float(data[id][sortable_attributes[sort_by]]) for id in top_creators]
    })

    fig = px.bar(df,y="Creator",x="Score",orientation='h')
    fig.update_yaxes(autorange="reversed")

    button_label = "Show Highest" if show_lowest else "Show Lowest"
    return fig, button_label

def build_community_subcount_boxplots():

    rows = []

    all_communities = graphData.get_all_communities()


    for community_label, community_data in all_communities.items():
        channels = community_data["channels"]

        for channel in channels:
            sub_count = int(channel.get("sub_count"), 0)

            if sub_count > 0:
                rows.append({
                    "community": community_label,
                    "subs": sub_count
                })

    df = pd.DataFrame(rows)

    community_order = df.groupby("community")["subs"].median().sort_values(ascending=False).index.tolist()

    fig = px.box(df,x="community",y="subs",title="Subscriber Distribution by Community",log_y=True,
                 category_orders={"community": community_order})

    return fig


def layout():

    sortable_attributes = graphData.get_sortable_attributes()

    layout = [
        html.Div(className="globalfigures-container", children=[
            html.Div(className="globalfigures-row", children=[
                html.Div(className="chart-card", children=[
                    html.H3("Community Sizes"),
                    dcc.Graph(figure=create_community_count_chart())
                ]),
                html.Div(className="chart-card", children=[
                    html.H3("Community Insularity"),
                    dcc.Graph(figure=create_community_insularity_chart())
                ])
            ]),
            html.Div(className="chart-card", children=[
                html.H3("Leaderboard"),
                html.Div(className="leaderboard-controls", children=[
                    dcc.Dropdown(list(sortable_attributes.keys()), list(sortable_attributes.keys())[0], id="leaderboard-sort"),
                    html.Button("Show Lowest", id="leaderboard-reverse-btn", n_clicks=0)
                ]),
                dcc.Graph(figure=None, id="leaderboard-figure")
            ]),
            html.Div(className="chart-card", children=[
                html.H3("Leaderboard"),
                dcc.Graph(figure=build_community_subcount_boxplots(), id="comm-subcount-figure")
            ])
        ])
    ]

    return layout
