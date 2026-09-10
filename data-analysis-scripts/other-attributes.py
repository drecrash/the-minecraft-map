from analysistoolkit import G, CID_TO_IDX, highest_degree
import json
import statistics



def hidden_influence(top_print=5):
    nodes = highest_degree(in_deg=True)
    

    degrees = [int(d["degree"]) for d in nodes]
    subs = [int(d["sub_count"]) for d in nodes]

    deg_mean, deg_stdev = statistics.mean(degrees), statistics.stdev(degrees)
    sub_mean, sub_stdev = statistics.mean(subs), statistics.stdev(subs)

    def zscore(val, mean, std):
        return (val - mean) / std if std != 0 else 0.0


    for node in nodes:
        deg_norm = zscore(int(node["degree"]), deg_mean, deg_stdev)
        sub_norm = -1*zscore(int(node["sub_count"]), sub_mean, sub_stdev)
        node["score"] = (deg_norm + sub_norm)/2

    max_score = max(node["score"] for node in nodes)
    min_score = min(node["score"] for node in nodes)

    for node in nodes: #min max
        node["score"] = ((node["score"] - min_score)/(max_score-min_score))*100

    sort_ = sorted(nodes, key=lambda d: d["score"], reverse=True)[:top_print]

    for n in sort_:
        name = n["name"]
        score = n["score"]
        print(f"{name}: {score}")

    outcome = sorted(nodes, key=lambda d: d["score"], reverse=True)


    with open("hidinf.json", "w") as f:
        json.dump(outcome, f, indent=2)

    return outcome


def community_bridges(n=10):
    bridge_data = {}

    for v in G.vs:
        neighbors = G.successors(v.index) + G.predecessors(v.index)

        neighboring_communities = set(G.vs[nb]["community"] for nb in neighbors if
                                      G.vs[nb]["community"] != -1)

        bridge_data[v["id"]] = {
            "name": v["name"],
            "community": v["community_label"],
            "bridge_count": len(neighboring_communities),
            "bridge_list": list(neighboring_communities)
        }

    sorted_bridge_data = sorted(bridge_data.values(), key=lambda x: x["bridge_count"], reverse=True)

    for data in sorted_bridge_data[:n]:
        name = data["name"]
        bridge_count = data["bridge_count"]
        bridge_list = data["bridge_list"]
        print(f"{name} bridges '{bridge_count}' communities: {bridge_list}")


    with open("bridges.json", "w") as f:
        json.dump(sorted_bridge_data, f, indent=2)

    return sorted_bridge_data