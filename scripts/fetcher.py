import requests
import json
import os
import sys

# --- Configuration ---
API_BASE = "https://iptv-org.github.io/api"
DB_FOLDER = "database"
COUNTRY_FOLDER = "database_by_countries_list"

def fetch_json(endpoint):
    """Helper to fetch JSON with error handling"""
    url = f"{API_BASE}/{endpoint}"
    print(f"📥 Fetching {endpoint}...")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"❌ Error fetching {endpoint}: {e}")
        sys.exit(1)

def main():
    # 1. Setup Directories
    os.makedirs(DB_FOLDER, exist_ok=True)
    os.makedirs(COUNTRY_FOLDER, exist_ok=True)

    # 2. Fetch All API Data
    print("🚀 Starting Data Sync...")
    channels_data = fetch_json("channels.json")
    streams_data = fetch_json("streams.json")
    countries_data = fetch_json("countries.json")
    logos_data = fetch_json("logos.json")
    guides_data = fetch_json("guides.json")

    # 3. Create Lookup Maps (Optimization)
    print("⚙️ Building Lookup Maps...")
    
    # Map: Country Code -> Country Name (e.g., "IN" -> "India")
    country_map = {c["code"]: c["name"] for c in countries_data}
    
    # Map: Channel ID -> Logo URL
    # Prioritize finding the best logo (ignoring black/white variants if possible, or just taking first)
    logo_map = {}
    for l in logos_data:
        cid = l.get("channel")
        if cid and cid not in logo_map:
            logo_map[cid] = l.get("url")

    # Map: Channel ID -> Guide Info
    guide_map = {}
    for g in guides_data:
        cid = g.get("channel")
        if cid:
            # We store the full guide object to keep all details
            guide_map[cid] = g

    # Map: Channel ID -> Channel Details (The core metadata)
    channel_map = {c["id"]: c for c in channels_data}

    # 4. Merge Data (Streams + Channels + Extras)
    print("🔗 Merging Data...")
    master_database = []
    
    # We iterate over STREAMS because a channel is useless without a link
    for stream in streams_data:
        channel_id = stream.get("channel")
        
        # Skip streams with no valid channel metadata
        if not channel_id or channel_id not in channel_map:
            continue

        channel_info = channel_map[channel_id]
        
        # Combine EVERYTHING into one rich object
        entry = {
            # --- Channel Identity ---
            "id": channel_id,
            "name": channel_info.get("name"),
            "alt_names": channel_info.get("alt_names", []),
            "network": channel_info.get("network"),
            "owners": channel_info.get("owners", []),
            
            # --- Location ---
            "country_code": channel_info.get("country"),
            "country_name": country_map.get(channel_info.get("country"), "Unknown"),
            "subdivision": channel_info.get("subdivision"),
            "city": channel_info.get("city"),
            
            # --- Content Details ---
            "categories": channel_info.get("categories", []),
            "languages": channel_info.get("languages", []),
            "is_nsfw": channel_info.get("is_nsfw", False),
            
            # --- Media Assets ---
            "logo": logo_map.get(channel_id),
            
            # --- Stream Details ---
            "stream_url": stream.get("url"),
            "stream_quality": stream.get("quality"), # e.g. "720p"
            "stream_format": stream.get("format"),   # e.g. "m3u8"
            "user_agent": stream.get("user_agent"),
            "referrer": stream.get("referrer"),
            
            # --- EPG / Guide ---
            "tv_guide": guide_map.get(channel_id),
            
            # --- Extra Metadata ---
            "website": channel_info.get("website"),
            "launched": channel_info.get("launched"),
            "closed": channel_info.get("closed")
        }
        master_database.append(entry)

    # 5. Save Master Database
    print(f"💾 Saving Master DB ({len(master_database)} records)...")
    with open(f"{DB_FOLDER}/database.json", "w", encoding="utf-8") as f:
        json.dump(master_database, f, indent=2, ensure_ascii=False)

    # 6. Split by Country
    print("🌍 Splitting by Country...")
    
    # Group data by country name
    country_groups = {}
    for item in master_database:
        c_name = item.get("country_name", "Unknown")
        # Sanitize filename (remove characters invalid in filenames)
        safe_name = "".join([c for c in c_name if c.isalnum() or c in (' ', '-', '_')]).strip()
        
        if safe_name not in country_groups:
            country_groups[safe_name] = []
        country_groups[safe_name].append(item)

    # Save individual files
    for c_name, items in country_groups.items():
        filename = f"{COUNTRY_FOLDER}/{c_name}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

    print("✅ All Done!")

if __name__ == "__main__":
    main()
