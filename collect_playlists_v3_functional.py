from utilities_v3 import *
import pymongo
from pymongo import MongoClient
from datetime import datetime, timedelta
import os

# MongoDB connection - get from credentials
with open('creds.json') as file:
    credentials = json.load(file)

# MongoDB connection details from credentials
mongo_config = credentials.get('mongodb', {})
mongo_host = mongo_config.get('host', 'localhost')
mongo_port = mongo_config.get('port', 27017)
mongo_db_name = mongo_config.get('database', 'spotify_collector')
mongo_username = mongo_config.get('username', None)
mongo_password = mongo_config.get('password', None)

# Build connection string
if mongo_username and mongo_password:
    mongo_connection_string = f"mongodb://{mongo_username}:{mongo_password}@{mongo_host}:{mongo_port}/"
else:
    mongo_connection_string = f"mongodb://{mongo_host}:{mongo_port}/"

mongo_client = MongoClient(mongo_connection_string)
db = mongo_client[mongo_db_name]
playlists_collection = db['playlists']
songs_collection = db['songs']
add_attempts_collection = db['add_attempts']

# Configuration
CACHE_REFRESH_DAYS = 30
NEWEST_PLAYLIST_CHECK_SONGS = 50

def setup_mongodb_indexes():
    """Create MongoDB indexes for better performance"""
    try:
        playlists_collection.create_index("playlist_id", unique=True)
        songs_collection.create_index("song_id", unique=True)
        add_attempts_collection.create_index([("song_id", 1), ("playlist_id", 1)])
        logging.info("MongoDB indexes created successfully")
    except Exception as e:
        logging.error(f"Error creating MongoDB indexes: {e}")

def should_refresh_playlist(playlist_id):
    """Check if playlist cache should be refreshed"""
    cached_playlist = playlists_collection.find_one({"playlist_id": playlist_id})
    
    if not cached_playlist:
        return True
        
    last_updated = cached_playlist.get('last_updated')
    if not last_updated:
        return True
        
    # Always refresh the newest playlist
    if playlist_id == credentials['collections']['yearly_playlist_collection']['playlist_ids'][-1]:
        return True
        
    # Check if it's been more than CACHE_REFRESH_DAYS since last update
    cutoff_date = datetime.now() - timedelta(days=CACHE_REFRESH_DAYS)
    return last_updated < cutoff_date

def get_playlist_songs(playlist_id, playlist_name, access_token, force_refresh=False, limit_songs=None):
    """Get playlist songs from cache or Spotify API"""
    
    if not force_refresh and not should_refresh_playlist(playlist_id):
        logging.info(f"Using cached data for playlist: {playlist_name}")
        cached_playlist = playlists_collection.find_one({"playlist_id": playlist_id})
        return {
            'song_ids': cached_playlist['song_ids'],
            'song_titles': cached_playlist['song_titles']
        }
    
    logging.info(f"Refreshing playlist data for: {playlist_name}")
    
    song_ids = []
    song_titles = []
    offset = 0
    total_songs = return_playlist_length(playlist_id)
    
    # If it's the newest playlist, only get the most recent songs
    if playlist_id == credentials['collections']['yearly_playlist_collection']['playlist_ids'][-1] and limit_songs:
        total_songs = min(total_songs, limit_songs)
    
    while offset < total_songs:
        params = {'offset': offset, 'limit': 50}
        
        try:
            request = requests.get(
                f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", 
                headers={'Authorization': f'Bearer {access_token}'}, 
                params=params
            )
            response = request.json()
            
            # Log API response for debugging
            if not os.path.exists("logs/json"):
                os.makedirs("logs/json")
            log_filename = f"logs/json/{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}_{playlist_name}_offset{offset}.json"
            with open(log_filename, "w") as file:
                json.dump(response, file, indent=4)
            
            if 'items' not in response:
                logging.error(f"Unexpected response format for playlist {playlist_name}: {response}")
                break
            
            for song in response['items']:
                if song and song.get("track") and song["track"].get("id"):
                    song_ids.append(song["track"]["id"])
                    song_titles.append(song["track"]["name"])
            
            offset += 50
            
        except Exception as e:
            logging.error(f"Error fetching playlist {playlist_name} at offset {offset}: {e}", exc_info=True)
            break
    
    # Update cache
    playlist_data = {
        'playlist_id': playlist_id,
        'playlist_name': playlist_name,
        'song_ids': song_ids,
        'song_titles': song_titles,
        'last_updated': datetime.now(),
        'total_songs': len(song_ids)
    }
    
    playlists_collection.replace_one(
        {"playlist_id": playlist_id},
        playlist_data,
        upsert=True
    )
    
    logging.info(f"Cached {len(song_ids)} songs for playlist: {playlist_name}")
    
    return {
        'song_ids': song_ids,
        'song_titles': song_titles
    }

def log_add_attempt(song_id, song_name, artist_name, playlist_id, playlist_name, uri):
    """Log an attempt to add a song to a playlist"""
    attempt_data = {
        'song_id': song_id,
        'song_name': song_name,
        'artist_name': artist_name,
        'playlist_id': playlist_id,
        'playlist_name': playlist_name,
        'uri': uri,
        'attempt_time': datetime.now(),
        'verified': False,
        'verification_attempts': 0
    }
    
    add_attempts_collection.insert_one(attempt_data)
    logging.info(f"Logged add attempt for '{song_name}' by {artist_name} to {playlist_name}")

def add_song_to_mongodb(uri, title, artist, image_url):
    """Add song to MongoDB instead of Firestore"""
    try:
        song_data = {
            'song_id': uri.split(':')[-1],  # Extract ID from URI
            'uri': uri,
            'title': title,
            'artist': artist,
            'image_url': image_url,
            'logged': False,
            'downloaded': False,
            'date_added': datetime.now()
        }
        
        songs_collection.replace_one(
            {"song_id": song_data['song_id']},
            song_data,
            upsert=True
        )
        
        logging.info(f"Added song '{title}' by {artist} to MongoDB")
        
    except Exception as e:
        logging.error(f"Error adding song to MongoDB: {e}", exc_info=True)

def verify_song_additions(access_token):
    """Verify that songs were actually added to playlists"""
    unverified_attempts = add_attempts_collection.find({
        "verified": False,
        "verification_attempts": {"$lt": 3},
        "attempt_time": {"$gt": datetime.now() - timedelta(hours=24)}
    })
    
    for attempt in unverified_attempts:
        try:
            # Check if song is now in the playlist
            playlist_data = get_playlist_songs(
                attempt['playlist_id'], 
                attempt['playlist_name'], 
                access_token,
                force_refresh=True
            )
            
            if attempt['song_id'] in playlist_data['song_ids']:
                # Song was successfully added
                add_attempts_collection.update_one(
                    {"_id": attempt["_id"]},
                    {
                        "$set": {
                            "verified": True,
                            "verified_time": datetime.now()
                        }
                    }
                )
                logging.info(f"Verified: '{attempt['song_name']}' was successfully added to {attempt['playlist_name']}")
            else:
                # Song wasn't found, increment verification attempts
                add_attempts_collection.update_one(
                    {"_id": attempt["_id"]},
                    {
                        "$inc": {"verification_attempts": 1}
                    }
                )
                logging.warning(f"Song '{attempt['song_name']}' not found in {attempt['playlist_name']} - attempt {attempt['verification_attempts'] + 1}")
                
                # Try to re-add the song if it's still missing
                if attempt['verification_attempts'] < 2:
                    logging.info(f"Re-attempting to add '{attempt['song_name']}' to {attempt['playlist_name']}")
                    add_song_to_spotify(
                        attempt['uri'], 
                        attempt['playlist_id'], 
                        attempt['song_name'], 
                        attempt['artist_name']
                    )
                    
        except Exception as e:
            logging.error(f"Error verifying song addition: {e}", exc_info=True)

def get_all_playlist_data(access_token):
    """Get data for all playlists (cached or fresh)"""
    playlist_info = {
        'current_yearly': {
            'id': credentials['collections']['yearly_playlist_collection']['playlist_ids'][-1],
            'name': 'Current Yearly',
            'song_ids': [],
            'song_titles': []
        },
        'country_playlist': {
            'id': credentials['country_collection_id'],
            'name': 'Country Collection',
            'song_ids': [],
            'song_titles': []
        },
        'collection_playlist': {
            'id': credentials['collections']['yearly_playlist_collection']['destination_id'],
            'name': 'Main Collection',
            'song_ids': [],
            'song_titles': []
        }
    }
    
    # Get playlist data (cached or fresh)
    for playlist_key, playlist_data in playlist_info.items():
        limit_songs = NEWEST_PLAYLIST_CHECK_SONGS if playlist_key == 'current_yearly' else None
        
        songs_data = get_playlist_songs(
            playlist_data['id'],
            playlist_data['name'],
            access_token,
            limit_songs=limit_songs
        )
        
        playlist_info[playlist_key]['song_ids'] = songs_data['song_ids']
        playlist_info[playlist_key]['song_titles'] = songs_data['song_titles']
    
    return playlist_info

def process_liked_tracks(playlist_info, access_token):
    """Process all liked tracks and add them to appropriate playlists"""
    liked_tracks = get_liked_tracks()['items']
    
    for track in liked_tracks:
        try:
            primary_artist = track['track']['artists'][0]['id']
            artist_info = get_artist(primary_artist)
            
            # Check if country music
            country = any('country' in genre.lower() for genre in artist_info['genres'])
            
            logging.info(f"{artist_info['name']}, country={country}, genres={artist_info['genres']}")
            
            song_id = track["track"]["id"]
            song_name = track["track"]["name"]
            artist_name = track["track"]["artists"][0]["name"]
            song_uri = track["track"]["uri"]
            image_url = track["track"]["album"]["images"][0]["url"] if track["track"]["album"]["images"] else ""
            
            if country:
                # Add to country playlist if not already there
                if song_id not in playlist_info['country_playlist']['song_ids']:
                    add_song_to_spotify(
                        song_uri, 
                        credentials['country_collection_id'], 
                        song_name, 
                        artist_name
                    )
                    
                    # Log the attempt
                    log_add_attempt(
                        song_id, song_name, artist_name,
                        credentials['country_collection_id'],
                        'Country Collection',
                        song_uri
                    )
                else:
                    logging.info(f"Not adding '{song_name}' by {artist_name} - already in country playlist")
            
            else:
                # Add to current yearly playlist if not already there
                if song_id not in playlist_info['current_yearly']['song_ids']:
                    add_song_to_spotify(
                        song_uri,
                        playlist_info['current_yearly']['id'],
                        song_name,
                        artist_name
                    )
                    
                    # Log the attempt
                    log_add_attempt(
                        song_id, song_name, artist_name,
                        playlist_info['current_yearly']['id'],
                        'Current Yearly',
                        song_uri
                    )
                else:
                    logging.info(f"Not adding '{song_name}' by {artist_name} - already in current yearly playlist")
                
                # Add to main collection if not already there
                if song_id not in playlist_info['collection_playlist']['song_ids']:
                    add_song_to_spotify(
                        song_uri,
                        playlist_info['collection_playlist']['id'],
                        song_name,
                        artist_name
                    )
                    
                    # Log the attempt
                    log_add_attempt(
                        song_id, song_name, artist_name,
                        playlist_info['collection_playlist']['id'],
                        'Main Collection',
                        song_uri
                    )
                else:
                    logging.info(f"Not adding '{song_name}' by {artist_name} - already in main collection")
            
            # Remove from likes and add to MongoDB instead of Firestore
            delete_song_from_likes(song_id)
            add_song_to_mongodb(song_uri, song_name, artist_name, image_url)
            
        except Exception as e:
            logging.error(f"Error processing track {track.get('track', {}).get('name', 'Unknown')}: {e}", exc_info=True)

def get_statistics():
    """Get statistics about cached data and recent activity"""
    stats = {
        'cached_playlists': playlists_collection.count_documents({}),
        'total_cached_songs': sum([p.get('total_songs', 0) for p in playlists_collection.find({})]),
        'total_songs_in_db': songs_collection.count_documents({}),
        'recent_add_attempts': add_attempts_collection.count_documents({
            'attempt_time': {'$gt': datetime.now() - timedelta(days=7)}
        }),
        'unverified_attempts': add_attempts_collection.count_documents({
            'verified': False,
            'verification_attempts': {'$lt': 3}
        }),
        'failed_attempts': add_attempts_collection.count_documents({
            'verified': False,
            'verification_attempts': {'$gte': 3}
        })
    }
    
    logging.info(f"MongoDB Statistics: {stats}")
    return stats

def collect_playlists_v3():
    """Main collection function with MongoDB caching and verification"""
    
    # Setup MongoDB
    setup_mongodb_indexes()
    
    # Get access token
    access_token = refresh_token()
    
    # Show current statistics
    get_statistics()
    
    # Get all playlist data
    playlist_info = get_all_playlist_data(access_token)
    
    # Process liked tracks
    process_liked_tracks(playlist_info, access_token)
    
    # Verify recent song additions
    verify_song_additions(access_token)
    
    # Show final statistics
    get_statistics()

def log_cleaner():
    """Clean up large log files"""
    directory = "logs/json"
    if os.path.exists(directory):
        for file in os.listdir(directory):
            file_path = f'{directory}/{file}'
            try:
                file_size = os.stat(file_path)
                if file_size.st_size >= 5_000:
                    logging.info(f"Removing {file_path} because it is over 5KB at {file_size.st_size} bytes")
                    os.remove(file_path)
            except Exception as e:
                logging.error(f"Error cleaning up {file_path}: {e}")

if __name__ == "__main__":
    try:
        collect_playlists_v3()
        
    except Exception as err:
        logging.error(f"Error in main collection process: {err}", exc_info=True)
    
    finally:
        log_cleaner()
