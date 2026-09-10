from dash import Dash, html, dcc, callback, Output, Input, State
import dash_cytoscape as cyto
from shared_data import graphData
import dash
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
import bisect

dash.register_page(__name__, name="Graph Explorer")


def suggestion_options(query):
    return [html.Option(value=name) for name in graphData.get_name_suggestions(query)]


# instead of rerendering a new neighborhood, merge the old graph with the new neighborhood
def merge_neighborhood(elements, neighborhood):
    existing_node_ids = [elem["data"]["id"] for elem in elements if "source" not in elem["data"]]
    existing_edges = [(elem["data"]["source"], elem["data"]["target"]) for elem in elements if "source" in elem["data"]]

    for n in neighborhood.get("nodes", []):
        if n["id"] not in existing_node_ids:
            elements.append({"data": {"id": n["id"], "label": n["name"], "img": n["pfp"]}})

    for e in neighborhood.get("edges", []):
        if (e["source"], e["target"]) not in existing_edges:
            elements.append({"data": {"source": e["source"], "target": e["target"]}})

    return elements

def set_highlight(elements, highlight_id):
    for elem in elements:
        if "source" not in elem["data"]: # don't check edges
            elem["classes"] = "highlighted" if elem["data"]["id"] == highlight_id else ""
    return elements


def mark_path_nodes(elements, node_ids):
    for elem in elements:
        if "source" not in elem["data"]:
            if elem["data"]["id"] in node_ids:
                elem["classes"] = "path-highlighted"
            elif elem.get("classes") == "path-highlighted":
                elem["classes"] = ""
    return elements


@callback(
    Output("graph-search-options", "children"),
    Input("graph-search", "value")
)
def update_search_suggestions(value):
    return suggestion_options(value)


@callback(
    Output("graph-path-source-options", "children"),
    Input("graph-path-source", "value")
)
def update_path_source_suggestions(value):
    return suggestion_options(value)


@callback(
    Output("graph-path-target-options", "children"),
    Input("graph-path-target", "value")
)
def update_path_target_suggestions(value):
    return suggestion_options(value)


@callback(
    Output("graph-cyto", "elements"),
    Output("graph-loaded-ids", "data"),
    Input("graph-search-submit", "n_clicks"),
    State("graph-search", "value"),
    State("graph-cyto", "elements"),
    State("graph-loaded-ids", "data"),
    prevent_initial_call=True
)
def search_graph(n_clicks, name, elements, expanded_ids):
    channel_id = graphData.get_channel_id(name)
    if channel_id is None:
        return dash.no_update, dash.no_update

    if channel_id not in expanded_ids:

        neighborhood = graphData.get_neighborhood(channel_id)

        if not neighborhood.get("nodes"):
            return dash.no_update, dash.no_update

        elements = merge_neighborhood(elements, neighborhood)
        expanded_ids = expanded_ids + [channel_id]

    elements = set_highlight(elements, channel_id)
    return elements, expanded_ids


@callback(
    Output("graph-cyto", "elements", allow_duplicate=True),
    Output("graph-loaded-ids", "data", allow_duplicate=True),
    Output("graph-path-status", "children"),
    Output("graph-path-reverse", "style"),
    Output("graph-path-submit", "n_clicks", allow_duplicate=True),
    Input("graph-path-submit", "n_clicks"),
    State("graph-path-source", "value"),
    State("graph-path-target", "value"),
    State("graph-cyto", "elements"),
    prevent_initial_call=True
)
def show_shortest_path(n_clicks, source_name, target_name, elements):
    hide_reverse_button = {"display": "none"}

    source_id = graphData.get_channel_id(source_name)
    target_id = graphData.get_channel_id(target_name)

    if source_id is None or target_id is None:
        return dash.no_update, dash.no_update, "", hide_reverse_button, 0

    path_graph = graphData.get_shortest_path_graph(source_id, target_id)

    if "ERROR" in path_graph:
        if path_graph["ERROR"] == "NoPath":
            message = f"No path exists from {source_name} to {target_name}."
            
            return dash.no_update, dash.no_update, message, {"display": "inline-block"}, 0
        return dash.no_update, dash.no_update, "", hide_reverse_button, 0

    elements = merge_neighborhood(elements, path_graph)
    path_ids = {n["id"] for n in path_graph["nodes"]}
    elements = mark_path_nodes(elements, path_ids)
    return elements, [], "", hide_reverse_button, 0


@callback(
    Output("graph-path-source", "value"),
    Output("graph-path-target", "value"),
    Output("graph-path-submit", "n_clicks", allow_duplicate=True),
    Output("graph-path-reverse", "n_clicks"),
    Input("graph-path-reverse", "n_clicks"),
    State("graph-path-source", "value"),
    State("graph-path-target", "value"),
    prevent_initial_call=True
)
def reverse_shortest_path(n_clicks, source_name, target_name):
    if n_clicks > 0:
        return target_name, source_name, 1, 0
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update


@callback(
    Output("graph-cyto", "elements", allow_duplicate=True),
    Output("graph-loaded-ids", "data", allow_duplicate=True),
    Input("graph-cyto", "tapNodeData"),
    State("graph-cyto", "elements"),
    State("graph-loaded-ids", "data"),
    prevent_initial_call=True
)
def expand_highlight(node_data, elements, expanded_ids):
    node_id = node_data["id"]

    if node_id not in expanded_ids:
        neighborhood = graphData.get_neighborhood(node_id)
        elements = merge_neighborhood(elements, neighborhood)
        expanded_ids = expanded_ids + [node_id]

    elements = set_highlight(elements, node_id)
    return elements, expanded_ids


CYTO_STYLESHEET = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "background-image": "data(img)",
            "background-fit": "cover",
            "width": 40,
            "height": 40,
            "border-width": 1,
            "border-color": "#111111",
        }
    },
    {
        "selector": "edge",
        "style": {
            "line-color": "#111111",
            "width": 1,
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#111111",
            "curve-style": "bezier",
        }
    },
    {
        "selector": ".highlighted",
        "style": {
            "border-color": "#3f7d20",
            "border-width": 6,
            "line-color": "#3f7d20",
            "target-arrow-color": "#3f7d20",
        }
    },
    {
        "selector": ".path-highlighted",
        "style": {
            "border-color": "#cc0000",
            "border-width": 6,
        }
    }
]

layout = [
    html.Div(children=[
        dcc.Input(
            id="graph-search",
            placeholder="Channel",
            list="graph-search-options"
        ),
        html.Datalist(id="graph-search-options"),
        html.Button("Search", id="graph-search-submit", n_clicks=0)
    ]),
    html.Div(children=[
        dcc.Input(
            id="graph-path-source",
            placeholder="Source Channel",
            list="graph-path-source-options"
        ),
        html.Datalist(id="graph-path-source-options"),
        dcc.Input(
            id="graph-path-target",
            placeholder="Target Channel",
            list="graph-path-target-options"
        ),
        html.Datalist(id="graph-path-target-options"),
        html.Button("Show Shortest Path", id="graph-path-submit", n_clicks=0),
        html.Button("Try the Other Way", id="graph-path-reverse", n_clicks=0, style={"display": "none"}),
        html.Div(id="graph-path-status")
    ]),
    cyto.Cytoscape(
        id="graph-cyto",
        elements=[],
        layout={
            "name": "cose",
            "nodeDimensionsIncludeLabels": True,
            "idealEdgeLength": 250,
            "nodeRepulsion": 60000,
            "componentSpacing": 300,
            "padding": 50
        },
        style={"width": "100%", "height": "600px"},
        stylesheet=CYTO_STYLESHEET
    ),
    dcc.Store(id="graph-loaded-ids", data=[])
]
