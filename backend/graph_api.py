from flask import Flask, jsonify, request
import igraph
import ast
import bisect
import json
import warnings
from pathlib import Path
from scipy import sparse
import numpy as np

class GraphData:

    def __init__(self, graph_path,lookup_path):
        self.G = igraph.Graph.Read_GraphML(graph_path)
        self.id_to_index = {v["id"]: v.index for v in self.G.vs}

        self.sorted_names = sorted( [v["name"].lower() for v in self.G.vs] )
        self.better_lookup = {v["name"].lower(): v["id"] for v in self.G.vs}

        self.analysis_file_directory = Path("data/analysis").resolve()
        self.bridge_data = self.load_json(self.analysis_file_directory / "bridges.json")
        self.mention_matrix = self.cos_sim_mention_matrix()
        pass#

    def load_json(self, path):
        with open(path, "r") as f:
            return json.load(f)

    def get_channel_id(self, name):
        print(name.lower())
        return self.better_lookup.get(name.lower())

    def get_all_names(self):
        return list(self.better_lookup.keys())

    def get_name_suggestions(self, query, limit=20):
        if not query:
            return []

        query = query.lower()
        matches = []
        i = bisect.bisect_left(self.sorted_names, query)
        while i < len(self.sorted_names) and len(matches) < limit:
            name = self.sorted_names[i]
            if not name.startswith(query):
                break
            matches.append(name)
            i += 1

        return matches

    def calculate_shortest_path(self, c1, c2):
        if (self.get_channel_id(c1) is None) or (self.get_channel_id(c2) is None):
            return {"ERROR": "NoChannel"}

        source_idx = self.id_to_index[self.get_channel_id(c1)]
        target_idx = self.id_to_index[self.get_channel_id(c2)]

        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            try:
                paths = self.G.get_shortest_paths(source_idx, to=target_idx, output="vpath")
            except RuntimeWarning:
                return {"ERROR": "NoPath"}

        path = paths[0] if paths else []

        if not path:
            return {"ERROR": "NoPath"}

        name_list = []
        edge_list = []
        results = {}

        for i, idx in enumerate(path):
            name_list.append(self.G.vs[idx]["name"])

            if i !=0:
                edge_id = self.G.get_eid(path[i-1], path[i])
                edge_data = ast.literal_eval(self.G.es[edge_id]["videos"])

                if edge_data == []:
                    new_addition = {"title": "!NOT FOUND SORRY!", "url": "https://youtu.be/dQw4w9WgXcQ"}
                else:
                    edge_data = edge_data[0]

                    new_addition = {"title": edge_data["title"], "url": edge_data["url"]}
                edge_list.append(new_addition)

        for i, name in enumerate(name_list):
            if i < len(name_list)-1:
                results[name] = {
                    "mentioned": name_list[i+1],
                    "video": edge_list[i]
                }

        return results


    def get_creator_data(self, name=None,id=None):

        if id == None:
            id = self.get_channel_id(name)

        node = self.G.vs[self.id_to_index[id]]

        return {**node.attributes(), **{"degree": node.degree()}}

    def get_degree_distribution(self, mode="all"):
        return self.G.degree(mode=mode)


    def get_all_communities(self):
        community_path = self.analysis_file_directory / "communities.json"

        with open(community_path, "r") as f:
            return json.load(f)

    def get_sortable_attributes(self):
        attr_ = {
            "Hidden Influence": "hidden_influence",
            "Betweenness Centrality": "betweenness",
            "Video Count": "video_count",
            "Total Views": "view_count",
            "Subscriber Count": "sub_count",
            "Ratio": "degree_ratio",
            "Bridge Count": "bridge_count"
        }
        return attr_

    def get_all_nodes(self, sort_by=None, reverse=True):
        if sort_by is not None:
            if sort_by not in self.get_sortable_attributes():
                return {}

            if sort_by == "Ratio":
                ratio_data = self.get_ratio_data()

                return {i["id"]: {
                    "name": i["name"],
                    "degree_ratio": float(i["ratio"])
                        }
                    for i in ratio_data
                    }

            elif sort_by == "Bridge Count":
                bridge_nodes = {
                    v["id"]: {
                        "name": v["name"],
                        "bridge_count": len(self.bridge_data.get(v["name"], []))
                    }
                    for v in self.G.vs
                }

                return dict(sorted(bridge_nodes.items(), key=lambda item: item[1]["bridge_count"], reverse=reverse))

        nodes = {
            v["id"]: {**v.attributes(), "degree": v.degree()}
            for v in self.G.vs
        }

        if sort_by is not None:
            sort_by_id = self.get_sortable_attributes()[sort_by]
            for node in nodes:
                try:
                    x = float(nodes[node][sort_by_id])
                except:
                    nodes[node][sort_by_id] = 0

            nodes = dict(sorted(nodes.items(), key=lambda item: float(item[1][sort_by_id]), reverse=reverse))

        return nodes

    def get_all_attributes(self):
        attr_ = self.G.vertex_attributes()
        return attr_


    def get_insularity_data(self):
        insularity_path = self.analysis_file_directory / "insularity.json"


        with open(insularity_path, "r") as f:
            insularity_data = json.load(f)

        insularity_data = dict(sorted(insularity_data.items(), key=lambda c: c[1]["insularity"], reverse=True))

        return insularity_data



    def get_ratio_data(self):
        ratio_path = self.analysis_file_directory / "ratios.json"


        with open(ratio_path, "r") as f:
            ratio_data = json.load(f)

        ratio_data = sorted(ratio_data, key=lambda d: d["ratio"],reverse=True)


        return ratio_data

    """
    The Cosine Similarity code is explained in a supplementary document
    """
    def cos_sim_mention_matrix(self):
        n = self.G.vcount()
        rows, cols, data = [],[],[]

        for e in self.G.es:
            u, v = e.tuple

            weight = len(ast.literal_eval(e["videos"]))

            rows.append(u)
            cols.append(v)
            data.append(weight)

        return sparse.csr_matrix((data, (rows, cols)), shape = (n,n))


    def cos_sim_l2_normalize_rows(self, m):
        norms = np.sqrt(m.multiply(m).sum(axis=1)).A1
        norms[norms==0] = 1

        return sparse.diags(1/norms) @ m

    def most_similar_by_mentions(self, name, mode="out", TOP_N=10):
        cid = self.get_channel_id(name)

        if cid is None:
            return []
        idx = self.id_to_index[cid]

        matrix = self.mention_matrix

        if mode == "in":
            matrix = matrix.T.tocsr()

        normalized = self.cos_sim_l2_normalize_rows(matrix)
        target = normalized[idx]

        similars = np.asarray((normalized @ target.T).todense()).flatten()

        similars[idx] = -1

        top = np.argsort(similars)[::-1][:TOP_N]

        return [
            {
            "name": self.G.vs[i]["name"],
             "id": self.G.vs[i]["id"],
             "similarity": round(float(similars[i]), 4)
            }
            for i in top if similars[i] > 0]

    def get_bridged_communities(self, name):
        return self.bridge_data.get(name, [])

    def get_neighborhood(self, id, limit=50):
        if id not in self.id_to_index:
            return {"ERROR": "NoChannel"}

        source_idx = self.id_to_index[id]
        neighbor_idxs = self.G.neighborhood(source_idx, order=1)

        # if the number of neighbors exceeds the limit, prioritize nodes that the source more often links to (greater edge weight)
        if len(neighbor_idxs) > limit:
            weight_to_source = {}
            for edge_id in self.G.incident(source_idx, mode="all"):
                edge = self.G.es[edge_id]
                neighbor = edge.target if edge.source == source_idx else edge.source
                weight = len(ast.literal_eval(edge["videos"]))
                weight_to_source[neighbor] = weight_to_source.get(neighbor, 0) + weight

            ranked = sorted(neighbor_idxs, key=lambda idx: weight_to_source.get(idx, 0), reverse=True)
            neighbor_idxs = ranked[:limit]
            if source_idx not in neighbor_idxs:
                neighbor_idxs.append(source_idx)

        ego_network = self.G.induced_subgraph(neighbor_idxs)

        nodes = [{"id": v["id"], "name": v["name"], "pfp": v["pfp"]} for v in ego_network.vs]
        edges = [{"source": ego_network.vs[e.source]["id"], "target": ego_network.vs[e.target]["id"]} for e in ego_network.es]

        return {"nodes": nodes, "edges": edges}

    """
    This is specifically for the webpage graph explorer.
    It returns the shortest path in a way that CytoScape can render
    
    """
    def get_shortest_path_graph(self, id1, id2):
        if id1 not in self.id_to_index or id2 not in self.id_to_index:
            return {"ERROR": "NoChannel"}

        source_idx = self.id_to_index[id1]
        target_idx = self.id_to_index[id2]

        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            try:
                paths = self.G.get_shortest_paths(source_idx, to=target_idx, output="vpath")
            except RuntimeWarning:
                return {"ERROR": "NoPath"}

        path = paths[0] if paths else []
        if not path:
            return {"ERROR": "NoPath"}

        nodes = [{"id": self.G.vs[idx]["id"], "name": self.G.vs[idx]["name"], "pfp": self.G.vs[idx]["pfp"]} for idx in path]
        edges = [
            {"source": self.G.vs[path[i]]["id"], "target": self.G.vs[path[i + 1]]["id"]}
            for i in range(len(path) - 1)
        ]

        return {"nodes": nodes, "edges": edges}


app = Flask(__name__)
app.json.sort_keys = False

print("Loading graph")#


GRAPH_PATH = "data/fin_data/graph.graphml"
LOOKUP_PATH = "data/analysis/lookup.json"
graphData = GraphData(GRAPH_PATH, LOOKUP_PATH)

print("Graph loaded")


@app.route("/channel_id")
def channel_id():
    name = request.args.get("name")
    if name is None:
        return jsonify({"error": "missing 'name'"}), 400
    return jsonify(graphData.get_channel_id(name))


@app.route("/names")
def all_names():
    return jsonify(graphData.get_all_names())


@app.route("/name_suggestions")
def name_suggestions():
    query = request.args.get("query", "")
    limit = request.args.get("limit", 20, type=int)
    return jsonify(graphData.get_name_suggestions(query, limit=limit))


@app.route("/shortest_path")
def shortest_path():
    c1 = request.args.get("c1")
    c2 = request.args.get("c2")
    if c1 is None or c2 is None:
        return jsonify({"error": "missing 'c1' or 'c2'"}), 400
    return jsonify(graphData.calculate_shortest_path(c1, c2))


@app.route("/creator")
def creator_data():
    name = request.args.get("name")
    id = request.args.get("id")
    if name is None and id is None:
        return jsonify({"error": "missing 'name' or 'id'"}), 400
    return jsonify(graphData.get_creator_data(name=name, id=id))


@app.route("/degree_distribution")
def degree_distribution():
    mode = request.args.get("mode", "all")
    return jsonify(graphData.get_degree_distribution(mode=mode))


@app.route("/communities")
def all_communities():
    return jsonify(graphData.get_all_communities())


@app.route("/sortable_attributes")
def sortable_attributes():
    return jsonify(graphData.get_sortable_attributes())


@app.route("/nodes")
def all_nodes():
    sort_by = request.args.get("sort_by")
    reverse = request.args.get("reverse", "true").lower() != "false"
    return jsonify(graphData.get_all_nodes(sort_by=sort_by, reverse=reverse))


@app.route("/attributes")
def all_attributes():
    return jsonify(graphData.get_all_attributes())


@app.route("/insularity")
def insularity_data():
    return jsonify(graphData.get_insularity_data())


@app.route("/ratios")
def ratio_data():
    return jsonify(graphData.get_ratio_data())


@app.route("/similar_by_mentions")
def similar_by_mentions():
    name = request.args.get("name")
    mode = request.args.get("mode", "out")
    top_n = request.args.get("top_n", 10, type=int)
    if name is None:
        return jsonify({"error": "missing 'name'"}), 400
    return jsonify(graphData.most_similar_by_mentions(name, mode=mode, TOP_N=top_n))


@app.route("/bridged_communities")
def bridged_communities():
    name = request.args.get("name")
    if name is None:
        return jsonify({"error": "missing 'name'"}), 400
    return jsonify(graphData.get_bridged_communities(name))


@app.route("/neighborhood")
def neighborhood():
    id = request.args.get("id")
    if id is None:
        return jsonify({"error": "missing 'id'"}), 400
    return jsonify(graphData.get_neighborhood(id))


@app.route("/shortest_path_graph")
def shortest_path_graph():
    id1 = request.args.get("id1")
    id2 = request.args.get("id2")
    if id1 is None or id2 is None:
        return jsonify({"error": "missing 'id1' or 'id2'"}), 400
    return jsonify(graphData.get_shortest_path_graph(id1, id2))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
