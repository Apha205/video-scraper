import requests
import time
import random
from yt_dlp import YoutubeDL
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

#session
def create_session():
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# headers
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://watch.entertheden.com/',
        'Origin': 'https://watch.entertheden.com',
        'Connection': 'keep-alive'
    }

# Get specific Brightcove headers from the website
def get_brightcove_headers():
    headers = get_headers()
    headers.update({
        'BCOV-POLICY': 'BCpkADawqM1cdm1RqtIYg6GJ1ZS5-Yj5jSmL5hGwlqkIWpi8IyjlUKq9x-RP6C3hM0GQmh3hfmNRwT-J_Sh4xFznvwxIao0vb2m0257I-q7nPH3Nb0H-wgaEadZGlxw6',  # Example policy key
        'scheme' : 'https',
        'accept' : 'application / json, text / plain, * / *',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language' : 'en',
        'Authorization' : 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYmVhY29uLmJyaWdodGNvdmUuY29tL3R3ZW50eXBvaW50bmluZS9hcGkvYWNjb3VudC9kMzU4NjgxOTI1MDdhNTdiMy9yZWZyZXNoIiwiaWF0IjoxNzQ3MjU5NjYzLCJleHAiOjE3NDc4NjQ0NjMsIm5iZiI6MTc0NzI1OTY2MywianRpIjoiOTVvTkhIa05tRG9wMUE5TSIsInN1YiI6NDQzMzAsInBydiI6IjM1YWY5MzA3OWM1NDU2NmNlM2E2MWIyZThhMDQ2MjUxZTZkMTc3MGMiLCJyZWZyZXNoX3R0bCI6MTc0OTA3NDA2Mywic2Vzc2lvbl9pZCI6NjgyMjEsImR1aWQiOiJhYjVmMzM0OS05NWVkLTRjMWYtYTE2Yy04NjMyYzIzZDUyYzAiLCJhdWQiOiJ0d2VudHlwb2ludG5pbmUifQ.jLBNjKLX17efi6srUQtXb06w8i99Z4jS6FfxAw - se4k',
        'path' : '/twentypointnine/api/account/d35868192507a57b3/bookmarks/28551?device_type=web'
      # Add any other required headers

    })
    return headers

def get_asset_ids(start_playlist_url, session):
    asset_ids = []
    next_url = start_playlist_url

    while next_url:
        print(f'Fetching: {next_url}')
        resp = session.get(next_url, headers=get_headers())
        resp.raise_for_status()  # Raises exception for HTTP errors
        data = resp.json()
        
        try:
            contents = data['data']['blocks'][0]['widgets'][0]['playlist']['contents']
            pagination = data['data']['blocks'][0]['widgets'][0]['playlist'].get('pagination', None)
        except Exception as e:
            print(f"Error finding contents array: {e}")
            print("Response data:", data)
            break

        for item in contents:
            if item.get("type") == "movies" and "id" in item:
                asset_ids.append(item["id"])
                print(f"Found asset ID: {item['id']}, title: {item.get('title', 'Unknown')}")

        # Get next paginated URL if it exists
        if pagination and pagination["url"].get("next"):
            next_url = pagination["url"]["next"]
            # Add a random delay between page requests
            time.sleep(random.uniform(2, 5))
        else:
            next_url = None

    return asset_ids

def asset_id_to_video_id(asset_id, session):
    url = f"https://beacon.playback.api.brightcove.com/twentypointnine/api/account/d35868192507a57b3/bookmarks/{asset_id}?device_type=web"
    try:
        resp = session.get(url, headers=get_headers())
        resp.raise_for_status()
        data = resp.json()
        vpd = data['data'].get('video_playback_details', None)
        if vpd and len(vpd) > 0 and "video_id" in vpd[0]:
            return vpd[0]['video_id']
        else:
            print(f"No video_id found in response for asset {asset_id}. Response data:", data)
            return None
    except Exception as e:
        print(f"Error fetching video_id for asset {asset_id}: {e}")
        return None

def video_id_to_stream_url(video_id, session):
    url = f"https://edge.api.brightcove.com/playback/v1/accounts/6415533679001/videos/{video_id}"
    try:
        resp = session.get(url, headers=get_brightcove_headers())
        resp.raise_for_status()
        data = resp.json()
        sources = data.get('sources', [])
        # Finding first HLS source (application/x-mpegURL)
        for s in sources:
            if s.get('type') == 'application/x-mpegURL' and 'src' in s:
                return s['src']
        
        print(f"No HLS source found for video_id {video_id}. Available sources:", sources)
        return None
    except Exception as e:
        print(f"Error fetching stream URL for video_id {video_id}: {e}")
        return None

def download_with_ytdlp(hls_url, title=None, output_folder='videos'):
    ydl_opts = {
        'outtmpl': f'{output_folder}/{title if title else "%(title)s"}.%(ext)s',
        'format': 'best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        # Add cookies if needed
        # 'cookiefile': 'cookies.txt',
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([hls_url])
        return True
    except Exception as e:
        print(f"Download failed for {hls_url}: {e}")
        return False

if __name__ == "__main__":
    session = create_session()
    start_playlist_url = "https://beacon.playback.api.brightcove.com/twentypointnine/api/playlists/760?cohort=98890104&device_type=web&device_layout=web&playlist_id=760"
    
    # Get list of asset IDs
    asset_ids = get_asset_ids(start_playlist_url, session)
    print(f'Found {len(asset_ids)} asset ids')
    
    # Process each asset
    successful_downloads = 0
    for idx, asset_id in enumerate(asset_ids):
        print(f'[{idx+1}/{len(asset_ids)}] Processing asset {asset_id}')
        
        # Get video ID
        video_id = asset_id_to_video_id(asset_id, session)
        if not video_id:
            print(f'Failed to get video_id for asset {asset_id}')
            continue
        print(f'Video ID: {video_id}')
        
        # Get streaming URL
        hls_url = video_id_to_stream_url(video_id, session)
        if not hls_url:
            print(f'Failed to get stream URL for video_id {video_id}')
            continue
        print(f'HLS URL: {hls_url}')
        
        # Download the video
        print(f'Downloading video for asset {asset_id}...')
        if download_with_ytdlp(hls_url, f"entertheden_{asset_id}"):
            successful_downloads += 1
        
        time.sleep(random.uniform(3, 7))
    
    print(f"Download completed. Successfully downloaded {successful_downloads} out of {len(asset_ids)} videos.")
