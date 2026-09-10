from analysistoolkit import G, CID_TO_IDX
import json

def betweenness_calculation(deg_req=0, sub_req=0):

    degrees = G.degree()
    core = [v.index for v in G.vs
            if (degrees[v.index] >= deg_req) and
            int(v["sub_count"]) >= sub_req]

    print(f"Calculating betweenness for {len(core)} nodes")

    G_sub = G.subgraph(core)

    n = G_sub.vcount()
    raw_betweenness = G_sub.betweenness(directed=True)
    scale = 1 / ((n-1)*(n-2)) # Raw betweenness is just how many shortest paths the node lies on. Scaling it shows what *fraction* of shortest paths the node lies on
    betweenness = [b*scale for b in raw_betweenness]

    betweenness_list = [{**G_sub.vs[i].attributes(), "id": G_sub.vs[i]["id"], "betweenness": score} for i, score in sorted(enumerate(betweenness), key=lambda x: x[1], reverse=True)]

    with open("betweenness.json", "w") as f:
        json.dump(betweenness_list, f,indent=2)

