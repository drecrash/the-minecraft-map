from analysistoolkit import G, CID_TO_IDX
import json
from collections import Counter, defaultdict

def community_calculation(sub_req= 0, deg_req = 1, res=1.0):

    MIN_COMMUNITY_SIZE = 10

    degrees = G.degree()

    meets_req = [v.index for v in G.vs if (int(v["sub_count"]) >= sub_req and degrees[v.index] >= deg_req)]

    G_sub = G.subgraph(meets_req).as_undirected()

    print(f"Sampling {G_sub.vcount()}/{G.vcount()} nodes")

    clustering = G_sub.community_multilevel(resolution=res)
    community_data = defaultdict(list)
    for i, community_id in enumerate(clustering.membership):
        attrs = G_sub.vs[i].attributes()
        cid = attrs["id"]
        community_data[community_id].append({
            "id": cid,
            "name": attrs.get("name", cid),
            "sub_count": attrs.get("sub_count", 0),
            "degree": degrees[CID_TO_IDX[cid]]
        })
    for community_id in community_data:
        community_data[community_id].sort(key=lambda x: x["degree"], reverse=True)

    output = {
        str(cid): {
            "size": len(channels),
            "channels": channels
        }
        for cid, channels in community_data.items()
    }

    print(f"Found {len(community_data)} initial communities")

    other_id = len(community_data)

    fin_output = {}

    fin_output[other_id] = {
        "size": 0,
        "channels": []
    }

    # move all communities below the minimum community size to an "Other"
    merged_community_count = 0
    for id, data in output.items():
        if len(data["channels"]) < MIN_COMMUNITY_SIZE:
            for channel in data["channels"]:
                fin_output[other_id]["size"] += 1
                fin_output[other_id]["channels"].append(channel)
            merged_community_count+=1
        else:
            fin_output[id] = data

    print(f"Moved {merged_community_count} communities to 'other'")


    with open("communities.json", "w") as f:
        json.dump(fin_output, f, indent=2)

# NOTE TO SELF: UPDATE TO USE ACTUAL TRANSLATION TABLE
"""
If a node wasn't given a community by default (for not meeting subscriber and/or degree requirements), it is 
automatically assigned the community that the majority of its neighbors have
"""
def assign_nodes_community():
    community_table = {
        "-1": "Other",
        "0": "Children/International",
        "1": "Streamers/Twitch",
        "2": "Mature Minecraft/Hermitcraft",
        "3": "Adult Comedy",
        "4": "German",
        "5": "Core MCYT",
        "6": "Pokemon",
        "7": "Music 1",
        "8": "Modern MCYT",
        "9": "Brands",
        "10": "Gaming Music",
        "11": "Roleplay",
        "12": "Guns/Military",
        "13": "Internet Comedy",
        "14": "IRL Comedy Sketches",
        "15": "Horror/Kids",
        "16": "Hypixel",
        "17": "Educational",
        "18": "Vloggers/Traditional Youtube",
        "19": "Animators",
        "20": "Shooter Games",
        "21": "French",
        "22": "Spanish",
        "23": "Indian",
        "24": "Yogscast",
        "25": "Real World Documentary",
        "26": "Hardcore Gaming",
        "27": "Brazilian",
        "28": "The Sims",
        "29": "Geometry Dash",
        "30": "Mixed",
        "31": "Indonesian",
        "32": "Analog Horror/Undertale",
        "33": "SCP/Lore/Anime",
        "34": "Music 2"
    }
    with open("communities.json", "r") as f:
        communities = json.load(f)

    node_to_com = {}

    for community_id, data in communities.items():
        for channel in data["channels"]:
            channel_id = channel["id"]
            node_to_com[channel_id] = community_id

    for v in G.vs:
        node = v["id"]
        if node in node_to_com.keys():
            pass # node in community
        else:
            neighbor_idxs = G.successors(v.index) + G.predecessors(v.index)
            neighbors = [G.vs[i]["id"] for i in neighbor_idxs]
            neighbors_with_community = [nb for nb in neighbors if (nb in node_to_com and node_to_com[nb] != "-1")]

            if neighbors_with_community:
                neighboring_communities = [node_to_com[nb] for nb in neighbors_with_community]
                most_common = max(set(neighboring_communities), key=neighboring_communities.count)
                node_to_com[node] = most_common
                print(f"Added {node} to community {most_common}")
            else:
                node_to_com[node] = "-1"
                print(f"Added {node} to the other community")


    for node, comm_id in node_to_com.items():
        v = G.vs[CID_TO_IDX[node]]
        v["community"] = int(node_to_com[node])
        v["community_label"] = community_table[node_to_com[node]]


    G.write_graphml("UPDATEDGRAPH.graphml", prefixattr=False)