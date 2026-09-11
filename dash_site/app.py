import dash
from dash import Dash, html, dcc, callback, Output, Input

app = Dash(__name__, use_pages=True,prevent_initial_callbacks="initial_duplicate",suppress_callback_exceptions=True)

@callback(
    Output("_pages_location", "pathname"),
    Input("_pages_location", "pathname")
)
def redirect_root(pathname):
    if pathname == "/":
        return "/home"
    return dash.no_update

app.layout = html.Div([
    html.H1('The Minecraft Map'),
    html.Nav([
        dcc.Link(f"{page['name']}", href=page["relative_path"])
        for page in sorted(dash.page_registry.values(), key=lambda page: page["path"] != "/home")
    ], className="site-nav"),
    dash.page_container
])

if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=True)