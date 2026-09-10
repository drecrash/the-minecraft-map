import requests

class GraphData:

    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url

    def _get(self, path, **params):
        resp = requests.get(f"{self.base_url}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_channel_id(self, name):
        return self._get("/channel_id", name=name)

    def get_all_names(self):
        return self._get("/names")

    def get_name_suggestions(self, query, limit=20):
        return self._get("/name_suggestions", query=query, limit=limit)

    def calculate_shortest_path(self, c1, c2):
        return self._get("/shortest_path", c1=c1, c2=c2)

    def get_creator_data(self, name=None, id=None):
        params = {}
        if name is not None:
            params["name"] = name
        if id is not None:
            params["id"] = id
        return self._get("/creator", **params)

    def get_degree_distribution(self, mode="all"):
        return self._get("/degree_distribution", mode=mode)

    def get_all_communities(self):
        return self._get("/communities")

    def get_sortable_attributes(self):
        return self._get("/sortable_attributes")

    def get_all_nodes(self, sort_by=None, reverse=True):
        params = {"reverse": str(reverse).lower()}
        if sort_by is not None:
            params["sort_by"] = sort_by
        return self._get("/nodes", **params)

    def get_all_attributes(self):
        return self._get("/attributes")

    def get_insularity_data(self):
        return self._get("/insularity")

    def get_ratio_data(self):
        return self._get("/ratios")

    def most_similar_by_mentions(self, name, mode="out", TOP_N=10):
        return self._get("/similar_by_mentions", name=name, mode=mode, top_n=TOP_N)

    def get_bridged_communities(self, name):
        return self._get("/bridged_communities", name=name)

    def get_neighborhood(self, id):
        return self._get("/neighborhood", id=id)

    def get_shortest_path_graph(self, id1, id2):
        return self._get("/shortest_path_graph", id1=id1, id2=id2)
