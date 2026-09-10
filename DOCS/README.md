
# The Crawl
## Core Crawl

The crawl works via Breadth-First Search.

Initially, all seed channels are added to the _queue_. In the queue, the channel id (CID) and _hop number_ of the channel is stored. The hop number starts at 0 (for seed nodes) and is incremented based on the channel that added a certain channel to the queue. For example, if a channel $C_0$ at hop 0 references a new channel $C_1$, that new channel is now hop 1. If $C_1$ references a new channel, that channel is at hop 2, and so on.

Each iteration, a channel is popped off of the queue to be processed.

The video data for the past 100 videos, as well as the channel metadata, is scraped using the YouTube Data API. The video title and description data is then sent to an LLM to extract mentions of other creators.

Then, each mentioned creator is sent through the name resolution function to fetch the channel ID associated with the name (e.g., Tubbo -> UCAz5JW1_oryewk0eR-eP7Bw). This is necessary to get the channel metadata and video list later.

Each mentioned creator has a node created for them if they don't have one already.

Then, the edges are formed. If the mentioning channel already has an edge to the mentioned channel, the edge data is appended with the new video(s) that the mentioned channel was mentioned in. Otherwise, a new edge is formed with just the video data from this iteration.

Then, the mentioned channels are added to the queue IF the queue is not already at max capacity AND the mentioning channel's hop number is less than the hop limit.

Then a checkpoint is taken, and the crawl continues.

## Functions

### Name Resolution (`name_to_cid`)

The name resolution function takes in a name that has been detected from a title or description (returned by an LLM), and tries to find the correct YouTube channel ID for the name. It goes through 4 stages:

1. Check the lookup table for the name
2. If the name is not in the lookup table, check if the name is the same as the channel handle using the Youtube API (e.g., Tubbo's channel handle is @Tubbo)
3. If (2) fails (e.g, Purpled's channel handle is @PurpledMC), it will try and find it in the existing lookup table by fuzzy matching
4. If all fails, log it to be manually resolved later

This "manually resolve" step is one reason that the crawl has to be periodically stopped and restarted.

### Mention Resolution (`extract_mentions`)

Using the video data extracted from the main crawl loop, the mention resolution function makes concurrent calls to an LLM to detect and return any names that are identified in video titles and/or descriptions, as well as data for which video each name was mentioned it.

_Notes:_

- Video data is batched into sets of 25 to avoid input/output token limits with the LLM.

## Important Files

### Lookup Table - `lookup.json`

A simple JSON dictionary of the form:

```
{
    "name": "channel_id"
}
```

When a name is identified to be associated with a specific channel ID, it is stored in the lookup table to avoid unnecessary calls to the YouTube Data API. Also used for fuzzy matching if exact lookup fails.

### State File - `state.json`

This file stores the visited and queue sets for the crawl's BFS.

The crawl ran over multiple sessions over multiple days, so a persistent state file was required.

### Log File - `tokens.json`

Initially created to just gauge how many input/output tokens are being used in LLM API calls, but grew to include a log of total time spent waiting for LLM response and an index of which YouTube API key is in rotation.

It also features a "killswitch" parameter that is toggled when an unhandled error occurs. This prevents the program from running endlessly and potentially going awry when unmonitored.

### The Graph - `graph.graphml`

_Initialization_
The nodes in the graph itself were initialized with attributes taken from the channel's YouTube data, and their IDs were set to the channel ID:

- Channel name
- Channel description
- Total video count
- Total view count
- Channel country
- Channel creation date
- Profile picture (URL)
- Subscriber count

Edges only have one attribute: **videos**; a list of every video that the source node mentioned the target node in. The data for a video is stored as `{"id": "", "title": "", "description": "", "url": "", "timestamp": ""}`

This allows for shortest path implementations to show the actual videos involved in the shortest path.

_Later Additions_
After the crawl was completed, some attributes were added to the nodes from post-crawl analysis:
- Betweenness centrality
- Hidden influence score
- Community ID and Community Name (two different attributes)

_Note:_

- I initially used NetworkX to create the graph, which is why there's a bunch of translations between node IDs and node indexes (which iGraph uses). NetworkX is great because it's so simple, but when I started the analysis, the pure Pythonic nature of it made it too slow to actually process the data in any feasible amount of time. So, I switched to iGraph and had to rewrite all the scripts and analysis functions with it.

# The Web App

## Features

### Graph Explorer

Using Dash Cytoscape, the website features a "graph explorer". Searching for a node will reveal it and 50 of its most important (determined by edge weight) neighbors (also known as an "ego network"). Searching for a shortest path will reveal all nodes on the shortest path between two creators.

Selecting a node will also reveal its ego network.

I initially wanted to display the entire graph, but doing so would be infeasible with a graph of this size in a browser.


### Shortest Path

By using iGraph's shortest path functionality along with the edge data stored in the graph, a trace of "creator x mentioned creator y in video a -> creator y mentioned creator z in video b -> creator z ..." can be derived. I took a lot of inspiration from the famous [Oracle of Bacon](https://oracleofbacon.org/) website.

### Global Analytics

A general overview of data for the entire graph is available in the global analytics. This includes:
- A pie chart of community sizes
- A bar graph of community insularity
- A reversible top-20 leaderboard for different channel attributes (degree ratio, centrality, etc.)
- Boxplots for subscriber counts in different communities

### Individual Channel Data

Channels can also be individually selected to see their attributes, such as centrality or sub count. Additionally, this page features:
- A list of communities that this channel is directly connected to (their "bridge" channels)
- A list of creators that are most similar to this channel based on cosine similarity

## Technical Details

The web app is a Plotly Dash frontend with a standard Flask backend. The backend is connected to the data directory, which includes the primary `graph.graphml` file, as well as some other files from the crawl and analysis results:
- `community-translation.json` converts Community IDs to Community Names
- `ratios.json` stores the in-degree to out-degree ratio for each channel
- `lookup.json` discussed in more detail in the Crawl section
- `bridges.json` stores each creator name and a list of communities that they are directly connected to

The data and webpage were initially loaded in the same Dash app, but that became extremely slow, so it was split into two different applications. The functionality from the in-built GraphData "API" was put into the backend, and then replaced with API calls to the Flask app.
