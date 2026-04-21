import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("FetchNYC")

def fetch_varied_roads():
    # Bounding box: [south, west, north, east]
    # SF + Ocean + Marin Headlands (highly varied density)
    query = """
    [out:json];
    way["highway"](37.70,-122.55,37.90,-122.35);
    out geom;
    """

    log.info("Fetching varied roads from Overpass API (this might take a few seconds)...")
    headers = {"User-Agent": "TileServer/1.0", "Accept": "*/*"}
    resp = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        ways = data.get('elements', [])
        log.info(f"Successfully fetched {len(ways)} road segments.")
        
        with open("varied_roads.json", "w") as f:
            json.dump(data, f)
        log.info("Saved to varied_roads.json")
    else:
        log.error(f"Failed to fetch: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    fetch_varied_roads()
