from googleapiclient.discovery import build
import os
import shutil
#import networkx as nx # slow as hell man
import igraph as ig
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import time
import random
from openai import OpenAI
import concurrent.futures
import threading
from google.genai import errors, types
from googleapiclient.errors import HttpError
from urllib.parse import unquote, urlparse, parse_qs
from difflib import get_close_matches

load_dotenv()


GRAPH_FILE = "data/graph.graphml"
STATE_FILE="data/state.json"
LOOKUP_FILE = "data/lookup.json"
SEED_FILE = "data/mcyt_seed.json"

TOKEN_USAGE_FILE = "data/tokens.json"
FAILED_LOG_FILE = "data/failed_channels.json"

UNRESOLVED_FILE = "data/unresolved.json"

BACKUP_DIR = "backups"
BACKUP_EVERY_N_CHECKPOINTS = 20
BACKUP_KEEP_LAST = 10
checkpoint_count = 0

YT_KEYS = [
    os.getenv("YT_API_KEY"), 
    os.getenv("YT_API_KEY2"),
    os.getenv("YT_API_KEY3"),
    os.getenv("YT_API_KEY4"),
    os.getenv("YT_API_KEY5"),
    os.getenv("YT_API_KEY6"),
    os.getenv("YT_API_KEY7"),
    os.getenv("YT_API_KEY8"),
    os.getenv("YT_API_KEY9"),
    os.getenv("YT_API_KEY10")
]

yt_key_index = 0

YT_API_KEY = os.getenv("YT_API_KEY")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")

MENTION_EXTRACTION_PROMPT_FILE = "prompt.txt"

DEEPSEEK_AI_MODEL = "deepseek-v4-flash"

HOP_LIMIT = 2
MAX_QUEUE = 50000

LLM = "deepseek" # i experimented with different models, ended up only using Deepseek


MENTION_EXTRACTION_PROMPT = ""

# Because calls that read and write from the lookup/unresolved files are made concurrently, a threading lock is here
lookup_lock = threading.Lock()
unresolved_lock = threading.Lock()

deepseek_client = OpenAI(
    api_key=DEEPSEEK_KEY,
    base_url="https://api.deepseek.com"
)

youtube=build("youtube","v3",developerKey=YT_KEYS[yt_key_index])

_thread_local = threading.local()

yt_cycled = False

# YouTube client is called concurrently
def get_thread_youtube():
    if getattr(_thread_local, "yt_key_index", None) != yt_key_index:
        _thread_local.youtube = build("youtube", "v3", developerKey=YT_KEYS[yt_key_index])
        _thread_local.yt_key_index = yt_key_index
    return _thread_local.youtube

token_usage = {}

"""
YouTube has a token cap of 10,000, so I rotated keys every time I hit a usage limit
"""
def rotate_yt():
    global yt_key_index, youtube, token_usage

    yt_key_index += 1

    if yt_key_index >= len(YT_KEYS):
        yt_key_index = 0
        # I did the math, and with how many tokens I was using per hour, I could rely on the token limit resetting every 24 hours.
        token_usage["yt_cycled"] = True
        log_tokens()


    youtube=build("youtube","v3",developerKey=YT_KEYS[yt_key_index])
    token_usage["yt_key_idx"] = yt_key_index



def load_mention_extraction_prompt():
    global MENTION_EXTRACTION_PROMPT
    with open(MENTION_EXTRACTION_PROMPT_FILE, "r") as f:
        MENTION_EXTRACTION_PROMPT = f.read()


def load_yt():
    global yt_key_index, youtube
    if os.path.exists(TOKEN_USAGE_FILE):
        with open(TOKEN_USAGE_FILE, "r") as f:
            data = json.load(f)
        yt_key_index = data.get("yt_key_idx", yt_key_index)
        youtube = build("youtube", "v3", developerKey=YT_KEYS[yt_key_index])




def load_seed():
    seed_data = {}

    lookup_table = {}
    queue = []

    try:
        with open(SEED_FILE, "r") as f:
            seed_data = json.load(f)

        lookup_table = {username.lower(): cid for username, cid in seed_data.items()}
        queue = [{"cid": cid, "hop": 0} for username, cid in seed_data.items()]
    except:
        print("Error loading initial seed")

    return lookup_table, queue


def log_tokens():
    with open(TOKEN_USAGE_FILE, "w") as f:
        json.dump(token_usage, f, indent=2)

"""
Sometimes the program fails to get data for a channel. (e.g. maybe the LLM returned faulty data).
This function sends all failed channels to a log file to manually review later
"""
def log_failure(cid, hop, error):
    failures = []
    if os.path.exists(FAILED_LOG_FILE):
        with open(FAILED_LOG_FILE, "r") as f:
            failures = json.load(f)

    failures.append({
        "cid": cid,
        "hop": hop,
        "error": str(error),
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    })

    with open(FAILED_LOG_FILE + ".tmp", "w") as f:
        json.dump(failures, f, indent=2)
    os.replace(FAILED_LOG_FILE + ".tmp", FAILED_LOG_FILE)


def load_token_usage():
    global token_usage
    if os.path.exists(TOKEN_USAGE_FILE):
        with open(TOKEN_USAGE_FILE, "r") as f:
            token_usage = json.load(f)
    else:
        token_usage = {
            "input": 0,
            "output": 0,
            "thinking": 0,
            "channels": 0, # yk, I never figured out why this didn't properly update, but it doesn't
            "ttl_time": 0,
            "killswitch": False,
            "yt_key_idx": yt_key_index,
            "yt_cycled": False
        }
        log_tokens()


def load():
    load_mention_extraction_prompt()
    load_token_usage()
    load_yt()

    if os.path.exists(GRAPH_FILE) and os.path.exists(STATE_FILE):
        print("Resuming")
        graph = ig.Graph.Read_GraphML(GRAPH_FILE)
        with open(STATE_FILE, "r") as f:
            state=json.load(f)
        state["visited"] = set(state["visited"])
        with open(LOOKUP_FILE, "r") as f:
            lookup_table=json.load(f)
    else:
        print("Starting up")
        graph = ig.Graph(directed=True)

        visited = set()
        lookup_table, queue = load_seed()

        if os.path.exists(LOOKUP_FILE):
            with open(LOOKUP_FILE, "r") as f:
                lookup_table=json.load(f)

        state = {
            "visited": visited,
            "queue": queue
        }

    cid_to_idx = {v["id"]: v.index for v in graph.vs}

    print("Data Loaded")

    return graph, cid_to_idx, state, lookup_table

# Frequency determined by BACKUP_EVERY_N_CHECKPOINTS
def backup_checkpoint():
    if not (os.path.exists(GRAPH_FILE) and os.path.exists(STATE_FILE) and os.path.exists(LOOKUP_FILE)):
        return

    dest = os.path.join(BACKUP_DIR, time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(dest, exist_ok=True)
    shutil.copy2(GRAPH_FILE, dest)
    shutil.copy2(STATE_FILE, dest)
    shutil.copy2(LOOKUP_FILE, dest)

    backups = sorted(
        d for d in os.listdir(BACKUP_DIR)
        if os.path.isdir(os.path.join(BACKUP_DIR, d))
    )
    for old in backups[:-BACKUP_KEEP_LAST]:
        shutil.rmtree(os.path.join(BACKUP_DIR, old))


def log_unresolved(name, hop=None, mentioned_by=None, videos=None):
    with unresolved_lock:
        unresolved = []
        if os.path.exists(UNRESOLVED_FILE):
            with open(UNRESOLVED_FILE) as f:
                raw = json.load(f)

            for entry in raw:
                if not isinstance(entry, dict):
                    unresolved.append({"name": entry, "hop": 0, "mentioned_by": {}})
                    continue

                mb = entry.get("mentioned_by", {})
                if isinstance(mb, list):
                    mb = {cid: [] for cid in mb}

                unresolved.append({"name": entry["name"], "hop": entry.get("hop"), "mentioned_by": mb})

        entry = next((e for e in unresolved if e["name"] == name), None)
        if entry is None:
            entry = {"name": name, "hop": hop, "mentioned_by": {}}
            unresolved.append(entry)

        if mentioned_by is not None:
            channel_videos = entry["mentioned_by"].setdefault(mentioned_by, [])
            seen_ids = {v["id"] for v in channel_videos}
            for v in (videos or []):
                if v["id"] not in seen_ids:
                    channel_videos.append({"id": v["id"], "title": v.get("title"), "url": v.get("url")})
                    seen_ids.add(v["id"])

        with open(UNRESOLVED_FILE + ".tmp", "w") as f:
            json.dump(unresolved, f, indent=2)
        os.replace(UNRESOLVED_FILE + ".tmp", UNRESOLVED_FILE)

def checkpoint(graph, state, lookup_table):
    global checkpoint_count

    graph.write_graphml(GRAPH_FILE + ".tmp", prefixattr=False)

    # I kept accidentally overwriting the graph file. Eventually realized I should probably create a temporary file when updating.
    with open(STATE_FILE + ".tmp", "w") as f:
        json.dump({**state, "visited": list(state["visited"])}, f, indent=2)

    with open(LOOKUP_FILE + ".tmp", "w") as f:
        json.dump(lookup_table, f, indent=2)

    os.replace(GRAPH_FILE + ".tmp", GRAPH_FILE)
    os.replace(STATE_FILE + ".tmp", STATE_FILE)
    os.replace(LOOKUP_FILE + ".tmp", LOOKUP_FILE)

    checkpoint_count += 1
    if checkpoint_count % BACKUP_EVERY_N_CHECKPOINTS == 0:
        backup_checkpoint()

    log_tokens()

"""
Pretty self explanatory. Returns a list of video ids and the metadata for the channel
""" 
def get_recent_videos(yt, channel, limit):
    global token_usage
    t = time.time()
    PAGE_SIZE = 50

    try:

        channel_data = yt.channels().list(
            part="contentDetails,snippet,statistics",
            id=channel
        ).execute()


        if not channel_data["items"]:
            return [], {}

        
        channel_info = channel_data["items"][0]
        metadata = {
            "name": channel_info["snippet"]["title"],
            "sub_count": channel_info["statistics"].get("subscriberCount", 0),
            "pfp": channel_info["snippet"]["thumbnails"]["default"]["url"],
            "creation_date": channel_info["snippet"]["publishedAt"],
            "country": channel_info["snippet"].get("country", ""),
            "view_count": channel_info["statistics"].get("viewCount", 0),
            "video_count": channel_info["statistics"].get("videoCount", 0),
            "description": channel_info["snippet"]["description"][:500]
        }

        uploads_id = channel_data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        videos = []
        next_page_token = None

        while len(videos) < limit:
            upload_data = yt.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_id,
                maxResults=min(PAGE_SIZE,limit-len(videos)),
                pageToken=next_page_token
            ).execute()

            video_ids = [item["contentDetails"]["videoId"] for item in upload_data["items"]]

            video_data = yt.videos().list(
                part="snippet",
                id=",".join(video_ids)
            ).execute()

            videos = videos + video_data["items"]


            next_page_token = upload_data.get("nextPageToken")

            if next_page_token is None:
                break

        print(f"Getting Recent Videos: {time.time()-t}")
        return videos, metadata

    except HttpError as e:
        if e.resp.status == 403:

            
            if (token_usage["yt_cycled"] and yt_key_index == len(YT_KEYS)-1):
                print(f"Failed to get videos for {channel}\n. No more keys available. Terminating")
                token_usage["killswitch"] = True
                log_tokens()
                print(f"{e}\n")
                raise 
            else:
                rotate_yt()
                print(f"Failed to get videos for {channel}\n. Rotating token and retrying.")
                return get_recent_videos(youtube, channel, limit)

        else:
            print(f"Failed to get videos for {channel}\n.")
            print(f"{e}\n")
        

    except Exception as e:
        print(f"Failed to get videos for {channel}\n.")
        print(f"{e}\n")

    return [], {}

def call_llm(prompt,default_response="{}"):
    response = default_response
    t = time.time()
    RETRIES = 4

    if LLM == "deepseek":
        for attempt in range(RETRIES):
            try:
                ai_response = deepseek_client.chat.completions.create(
                    model = DEEPSEEK_AI_MODEL,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }],
                    max_tokens=8000,
                    extra_body={"thinking": {"type": "disabled"}}
                )
                break
            except Exception as e:
                print("Deepseek Error: ", e)
                if attempt < RETRIES - 1:
                    time.sleep(30)
                else:
                    raise

        try:
            usage = ai_response.usage
            token_usage["input"] += usage.prompt_tokens or 0
            token_usage["output"] += usage.completion_tokens or 0


            if usage.completion_tokens_details:
                token_usage["thinking"] += usage.completion_tokens_details["reasoning_tokens"] or 0
        except Exception as e:
            print(f"Error logging token usage: {e}")

        try:
            response = ai_response.choices[0].message.content
        except:
            print("HELL HAS BROKEN LOOSE OHH LAWDY") # i am a professional poorgrammer

    print("Current usage: ", token_usage)
    print(f"LLM Time: {time.time()-t}")
    token_usage["ttl_time"] += time.time()-t
    return response

def call_llm_w_batch_data(batch):
    prompt = MENTION_EXTRACTION_PROMPT


    video_data = []
    for video in batch:
        snippet = video["snippet"]

        video_data.append({
            "id": video["id"],
            "title": snippet["title"],
            "description": snippet["description"],
            "url": "https://www.youtube.com/watch?v="+str(video["id"]),
            "timestamp": snippet["publishedAt"]
        })

    prompt += "\nVideo Data:\n"
    prompt += str(video_data)
    print(f"Making call to {LLM};")

    try:
        return json.loads(call_llm(prompt))
    except:
        raise

    return {}

    
def find_creator_vids(creator_name, vid_data):
    matches = []
    for video in vid_data:
        text = (video["snippet"]["title"] + " " + video["snippet"]["description"]).lower()

        if creator_name.lower() in text:
            matches.append({
                "id": video["id"],
                "title":video["snippet"]["title"],
                "description": video["snippet"]["description"],
                "url": "https://www.youtube.com/watch?v="+str(video["id"]),
                "timestamp": video["snippet"]["publishedAt"]
            })

    return matches

def extract_mentions(videos):
    VIDEO_BATCH_SIZE = 25
    
    batches = [videos[i:i+VIDEO_BATCH_SIZE] for i in range(0, len(videos), VIDEO_BATCH_SIZE)]

    all_mentions = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(call_llm_w_batch_data, batches))

    all_creators = set()
    for result in results:
        for creator in result:
            all_creators.add(creator)
    for creator in all_creators:
        print("Finding vids for ", creator)
        all_mentions[creator] = find_creator_vids(creator, videos)


    print("ALL MENTIONS: ", list(all_mentions.keys()))



    return all_mentions



# Simple function to help mitigate problems due to spelling errors and such
def fuzzy_lookup(name, lookup_table):
    with lookup_lock:
        keys = list(lookup_table.keys())

    matches = get_close_matches(name.lower(), keys, n=1, cutoff=0.85)
    if matches:
        matched = matches[0]
        print(f"Fuzzy matched {matched} for {name}")
        return lookup_table[matched]
    return None

# This function basically never worked because google has super strict ratelimits
def scrape_for_cid(name):
    print("Using scrape to find channel for ", name)
    query = name.replace(" ", "+") + "+minecraft+youtube+channel"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
    }

    url = f"https://www.google.com/search?q={query}"


    request = requests.get(
        url,
        headers=headers,
        timeout=10
    )


    soup = BeautifulSoup(request.text, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])

        if "youtube.com/@" in href:
            return ("handle", href.split("youtube.com/@")[1].split("&")[0].split("/")[0])
        if "youtube.com/c/" in href:
            return ("custom", href.split("youtube.com/c/")[1].split("&")[0].split("/")[0])
        if "youtube.com/user/" in href:
            return ("user", href.split("youtube.com/user/")[1].split("&")[0].split("/")[0])
        if "youtube.com/channel/" in href:
            return ("id", href.split("youtube.com/channel/")[1].split("&")[0].split("/")[0])
    print(soup.find_all("a", href=True))


    print(f"Scrape found nothing for {name}")
    return None, None


"""
When the program detects a name, it needs to convert it to a channel ID in order to get data on it.
There are three options here:

a) If the name is already in the lookup table: baddabing baddaboom, you have it.
b) If it's *not* already in the lookup table, check if the name is the same as the channel handle using the Youtube API (e.g., Tubbo's channel handle is @Tubbo)
b) If (b) fails (e.g, Purpled's channel handle is @PurpledMC), it will try and find it in the existing lookup table by fuzzy matching
c) If all fails: cry and log it to be manually identified later.
"""
def name_to_cid(yt, name, lookup_table, hop=None, mentioned_by=None, videos=None):
    name = name.lower()

    with lookup_lock:
        if name in lookup_table:
            return lookup_table[name]

 
    try:
        print("Using YT to find channel for ", name)
        channel_options = yt.channels().list(
            part="id",
            forHandle=name
        ).execute()

        if channel_options["items"]:
            cid = channel_options["items"][0]["id"]

            lookup_table[name] = cid

            return cid
    except:
        pass


    cid = None

    if cid is None:
        cid = fuzzy_lookup(name, lookup_table)


    if cid:
        with lookup_lock:
            lookup_table[name] = cid
    else:
        log_unresolved(name, hop, mentioned_by, videos)

    return cid


def get_creator(args):
    try:
        collab, lookup_table, hop, mentioned_by, videos = args
        collab_id = name_to_cid(get_thread_youtube(), collab, lookup_table, hop, mentioned_by, videos)
        return {collab: collab_id}
    except Exception as e:
        print("ERROR GETTING CREATOR: ", e)
        return {collab: None}


# Unlike NetworkX, iGraph doesn't automatically create a node when you create an edge to a node that doesn't exist
def get_or_add_vertex(graph, cid_to_idx, cid):
    idx = cid_to_idx.get(cid)
    if idx is None:
        v = graph.add_vertex(id=cid)
        idx = v.index
        cid_to_idx[cid] = idx
    return idx

def crawl():
    graph, cid_to_idx, state, lookup_table = load()

    while state["queue"]:
        current = state["queue"].pop(0)
        cid = current["cid"]
        hop = current["hop"]

        if cid in state["visited"]:
            continue

        vids, channel_metadata = get_recent_videos(youtube, cid, limit=100)

        if not vids and not channel_metadata:
            state["visited"].add(cid)
            continue


        idx = get_or_add_vertex(graph, cid_to_idx, cid)
        for key, value in channel_metadata.items():
            graph.vs[idx][key] = value

        try:
            mentioned_creators = extract_mentions(vids)
        except Exception as e:
            print(f"ERROR EXTRACTING MENTIONS for {cid}: ", e)
            log_failure(cid, hop, e)
            state["visited"].add(cid)
            checkpoint(graph, state, lookup_table)
            continue

        collab_dict = {}
        results = []

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(get_creator, [(collab, lookup_table, hop, cid, collab_list) for collab, collab_list in mentioned_creators.items()]))
        except Exception as e:
            print("ERROR GETTING CREATOR NAMES: ", e)
            log_failure(cid, hop, e)

        for result in results:
            for collab, collab_id in result.items():
                if collab_id != None:
                    collab_dict[collab_id] = mentioned_creators[collab]


        for collab_id, collab_list in collab_dict.items():
            collab_idx = get_or_add_vertex(graph, cid_to_idx, collab_id)
            eid = graph.get_eid(idx, collab_idx, directed=True, error=False)

            if eid != -1:
                existing_vids = json.loads(graph.es[eid]["videos"])
                existing_vids.extend(collab_list)
                graph.es[eid]["videos"] = json.dumps(existing_vids)
            else:
                graph.add_edge(idx, collab_idx, videos=json.dumps(collab_list))

            if len(state["queue"]) < MAX_QUEUE and hop < HOP_LIMIT and collab_id not in state["visited"]:
                state["queue"].append({"cid": collab_id, "hop": hop + 1})

        state["visited"].add(cid)
        checkpoint(graph, state, lookup_table)


        print(f"Collaborators Found: ",len(mentioned_creators))
        print(f"Current Queue Size: ", len(state["queue"]))
        print(f"So far visited: ",len(state["visited"]))

if __name__ == "__main__":
    load_token_usage()
    if (token_usage["killswitch"]):
        print("Killswitch Activated.")
        time.sleep(4*60*60) # just wait until midnight for the tokens to reset
        token_usage["killswitch"] = False
        log_tokens()
        crawl()
    else:
        crawl()






