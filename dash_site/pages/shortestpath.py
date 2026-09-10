from dash import Dash, html, dcc, callback, Output, Input
import plotly.express as px
import pandas as pd
from shared_data import graphData
import dash



dash.register_page(__name__,name="Shortest Path Calculator")


def shortest_path_input_element():
    return html.Div(children=[

        dcc.Input(
            id="path-calc-c1",
            placeholder="Source Channel",
            list='channel-options-c1'
        ),

        html.P("to"),

        dcc.Input(
            id="path-calc-c2",
            placeholder="Target Channel",
            list='channel-options-c2'
        ),

        html.Datalist(id="channel-options-c1"),
        html.Datalist(id="channel-options-c2"),

        dcc.Button("Submit", id="path-button-submit", n_clicks=0),
        dcc.Button("Try the Other Way", id="reverse-path-button-submit", n_clicks=0, style={"display": "none"})
    ])


def suggestion_options(query):
    return [html.Option(value=name) for name in graphData.get_name_suggestions(query)]


@callback(
    Output("channel-options-c1", "children"),
    Input("path-calc-c1", "value")
)
def update_c1_suggestions(value):
    return suggestion_options(value)


@callback(
    Output("channel-options-c2", "children"),
    Input("path-calc-c2", "value")
)
def update_c2_suggestions(value):
    return suggestion_options(value)

@callback(
    Output("path-results", "children"),
    Output("path-button-submit", "n_clicks", allow_duplicate=True),
    Output("reverse-path-button-submit", "style"),
    Input("path-calc-c1", "value"),
    Input("path-calc-c2", "value"),
    Input("path-button-submit", "n_clicks"),
    prevent_initial_call=True
)
def display_shortest_path(c1, c2, n_clicks):
    shortest_path = None
    response = []
    hide_reverse_button = {"display": "none"}
    if n_clicks > 0:
        shortest_path = graphData.calculate_shortest_path(c1, c2)

    if shortest_path:
        if "ERROR" in shortest_path:
            if shortest_path["ERROR"] == "NoPath":
                response.append(html.P(f"No path exists from {c1} to {c2}."))
                hide_reverse_button = {"display": "inline-block"}
            return response, 0, hide_reverse_button

        chain = []
        for creator, data in shortest_path.items():
            chain.append({"type": "channel", "data": creator})
            chain.append({"type": "channel", "data": data["mentioned"]})
            chain.append({"type": "video", "data": data["video"]})

        connector_labels = ["mentions", "in", None]

        rows = []

        for i, item in enumerate(chain):
            css = "pathchannel" if item["type"] == "channel" else "pathvideo"
            element = item["data"] if item["type"] == "channel" else html.A(item["data"]["title"], href=item["data"]["url"])
            rows.append(html.Tr(html.Td(element, className=css)))
            if i < len(chain) - 1:
                label = connector_labels[i % 3]
                if label:
                    rows.append(html.Tr(html.Td(label, className="pathconnector")))
        response.append(html.P(f"{c1} is {len(shortest_path)} steps from {c2}"))
        response.append(html.Br())
        
        response.append(
            html.Table(html.Tbody(rows))
        )




    return response, 0, hide_reverse_button

@callback(
    Output("path-calc-c1", "value"),
    Output("path-calc-c2", "value"),
    Output("path-button-submit", "n_clicks", allow_duplicate=True),
    Output("reverse-path-button-submit", "n_clicks"),
    Input("path-calc-c1", "value"),
    Input("path-calc-c2", "value"),
    Input("reverse-path-button-submit", "n_clicks", allow_optional=True),
    prevent_initial_call=True
)
def reverse_shortest_path(c1, c2, n_clicks):
    if n_clicks > 0:
        return c2, c1, 1, 0
    return c1, c2, 0, n_clicks

layout = [
    html.Div(children=[
        html.H1(children='Shortest Path', style={'textAlign':'center'}),
        shortest_path_input_element(),
        html.Div(children=[], id="path-results",style={'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center','justifyContent': 'center'})
    ])
]
