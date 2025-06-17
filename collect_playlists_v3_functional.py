from utilities_v3 import *
import pymongo
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
import argparse
import sys

# MongoDB connection - get from credentials
with open('creds_v3.json') as file:
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
        # Test connection first
        mongo_client.admin.command('ping')
        logging.info("MongoDB connection successful")
        
        playlists_collection.create_index("playlist_id", unique=True)
        songs_collection.create_index("song_id", unique=True)
        songs_collection.create_index("date_added")
        songs_collection.create_index("date_cached")
        songs_collection.create_index("logged")
        songs_collection.create_index("playlists")
        add_attempts_collection.create_index([("song_id", 1), ("playlist_id", 1)])
        logging.info("MongoDB indexes created successfully")
        return True
    except pymongo.errors.OperationFailure as e:
        if "authentication" in str(e).lower():
            logging.error("MongoDB authentication required. Please check your credentials in creds_v3.json")
            print("❌ MongoDB requires authentication. Please add credentials to creds_v3.json:")
            print('  "mongodb": {')
            print('    "username": "your_username",')
            print('    "password": "your_password"')
            print('  }')
            return False
        else:
            logging.error(f"MongoDB operation failed: {e}")
            return False
    except Exception as e:
        logging.error(f"Error creating MongoDB indexes: {e}")
        return False

def test_mongodb_connection():
    """Test MongoDB connection and show database info"""
    try:
        # Test connection
        mongo_client.admin.command('ping')
        print(f"✅ MongoDB connection successful")
        print(f"Connected to: {mongo_connection_string}")
        print(f"Database: {mongo_db_name}")
        
        # Show collections
        collections = db.list_collection_names()
        print(f"Collections: {collections}")
        
        # Show collection counts
        for collection_name in ['playlists', 'songs', 'add_attempts']:
            if collection_name in collections:
                count = db[collection_name].count_documents({})
                print(f"  {collection_name}: {count} documents")
            else:
                print(f"  {collection_name}: (collection doesn't exist yet)")
        
        return True
    except pymongo.errors.OperationFailure as e:
        if "authentication" in str(e).lower():
            print(f"❌ MongoDB authentication required")
            print("Please add username/password to creds_v3.json mongodb section")
        else:
            print(f"❌ MongoDB operation failed: {e}")
        return False
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        print(f"Connection string: {mongo_connection_string}")
        return False

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
    """Get playlist songs from cache or Spotify API and cache detailed song information"""
    
    if not force_refresh and not should_refresh_playlist(playlist_id):
        logging.info(f"Using cached data for playlist: {playlist_name}")
        cached_playlist = playlists_collection.find_one({"playlist_id": playlist_id})
        return {
            'song_ids': cached_playlist['song_ids'],
            'song_titles': cached_playlist['song_titles']
        }

    logging.info(f"Refreshing playlist data for: {playlist_name}")

    # Only fetch the latest playlist name from Spotify when refreshing
    playlist_name = get_playlist_name_from_spotify(playlist_id, access_token)

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
                    track = song["track"]
                    song_id = track["id"]
                    song_title = track["name"]
                    artist_name = track["artists"][0]["name"] if track["artists"] else "Unknown Artist"
                    song_uri = track["uri"]
                    image_url = track["album"]["images"][0]["url"] if track["album"]["images"] else ""
                    
                    song_ids.append(song_id)
                    song_titles.append(song_title)
                    
                    # Cache detailed song information
                    song_data = {
                        'song_id': song_id,
                        'uri': song_uri,
                        'title': song_title,
                        'artist': artist_name,
                        'image_url': image_url,
                        'logged': False,  # Mark as not logged yet - another process will email and mark as logged
                        'date_cached': datetime.now(),
                        'playlists': [playlist_id]  # Track which playlists contain this song
                    }
                    
                    # Update or insert song data (add playlist to list if song already exists)
                    existing_song = songs_collection.find_one({"song_id": song_id})
                    if existing_song:
                        # Add this playlist to the list if not already there
                        playlists_list = existing_song.get('playlists', [])
                        if playlist_id not in playlists_list:
                            playlists_list.append(playlist_id)
                        songs_collection.update_one(
                            {"song_id": song_id},
                            {"$set": {"playlists": playlists_list, "date_cached": datetime.now()}}
                        )
                    else:
                        songs_collection.insert_one(song_data)
            
            offset += 50
            
        except Exception as e:
            logging.error(f"Error fetching playlist {playlist_name} at offset {offset}: {e}", exc_info=True)
            break
    
    # Update cache
    playlist_data = {
        'playlist_id': playlist_id,
        'playlist_name': playlist_name,  # Overwrite with latest name from Spotify only on refresh
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
    """Add song to MongoDB with the required fields format"""
    try:
        song_data = {
            'song_id': uri.split(':')[-1],  # Extract ID from URI
            'uri': uri,
            'title': title,
            'artist': artist,
            'image_url': image_url,
            'logged': False,  # Set to False - another process will email and mark as logged
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
    """Get data for all playlists (cached or fresh) - checks ALL playlists from credentials"""
    playlist_info = {}
    
    # Add current yearly playlist
    current_yearly_id = credentials['collections']['yearly_playlist_collection']['playlist_ids'][-1]
    current_yearly_name = get_playlist_name_from_spotify(current_yearly_id, access_token)
    playlist_info['current_yearly'] = {
        'id': current_yearly_id,
        'name': current_yearly_name,
        'song_ids': [],
        'song_titles': []
    }
    
    # Add country playlist
    country_id = credentials['country_collection_id']
    country_name = get_playlist_name_from_spotify(country_id, access_token)
    playlist_info['country_playlist'] = {
        'id': country_id,
        'name': country_name,
        'song_ids': [],
        'song_titles': []
    }
    
    # Add main collection playlist
    collection_id = credentials['collections']['yearly_playlist_collection']['destination_id']
    collection_name = get_playlist_name_from_spotify(collection_id, access_token)
    playlist_info['collection_playlist'] = {
        'id': collection_id,
        'name': collection_name,
        'song_ids': [],
        'song_titles': []
    }
    
    # Add ALL yearly playlists from the credentials file
    yearly_playlist_ids = credentials['collections']['yearly_playlist_collection']['playlist_ids']
    for i, playlist_id in enumerate(yearly_playlist_ids):
        # Use cached playlist name if available, otherwise fetch and cache it
        cached_playlist = playlists_collection.find_one({"playlist_id": playlist_id})
        if cached_playlist and 'playlist_name' in cached_playlist:
            playlist_name = cached_playlist['playlist_name']
        else:
            playlist_name = get_playlist_name_from_spotify(playlist_id, access_token)
            # Cache the playlist name for future use
            playlists_collection.update_one(
            {"playlist_id": playlist_id},
            {"$set": {"playlist_name": playlist_name}},
            upsert=True
            )
        key = f'yearly_playlist_{i}'
        playlist_info[key] = {
            'id': playlist_id,
            'name': playlist_name,
            'song_ids': [],
            'song_titles': []
        }
    logging.info(f"Processing {len(playlist_info)} playlists total")
    
    # Get playlist data (cached or fresh)
    for playlist_key, playlist_data in playlist_info.items():
        # Only limit songs for the current yearly playlist
        limit_songs = NEWEST_PLAYLIST_CHECK_SONGS if playlist_key == 'current_yearly' else None
        
        logging.info(f"Processing playlist: {playlist_data['name']} (ID: {playlist_data['id']})")
        
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
                        playlist_info['country_playlist']['name'],
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
                        playlist_info['current_yearly']['name'],
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
                        playlist_info['collection_playlist']['name'],
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
        'logged_songs': songs_collection.count_documents({"logged": True}),
        'unlogged_songs': songs_collection.count_documents({"logged": False}),
        'recent_add_attempts': add_attempts_collection.count_documents({
            'attempt_time': {'$gt': datetime.now() - timedelta(days=7)}
        }),
        'recently_cached_songs': songs_collection.count_documents({
            'date_cached': {'$gt': datetime.now() - timedelta(days=7)}
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

def get_recently_logged_songs(days=7):
    """Get songs that were logged recently for email updates"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Find songs that are unlogged (ready for email updates)
        recent_songs = songs_collection.find({
            "$or": [
                {"date_added": {"$gt": cutoff_date}},
                {"date_cached": {"$gt": cutoff_date}}
            ],
            "logged": False  # Only get songs that haven't been emailed yet
        }).sort("date_added", -1)
        
        songs_list = []
        for song in recent_songs:
            songs_list.append({
                'artist': song.get('artist', 'Unknown Artist'),
                'title': song.get('title', 'Unknown Title'),
                'uri': song.get('uri', ''),
                'image_url': song.get('image_url', ''),
                'logged': song.get('logged', False),
                'date_added': song.get('date_added'),
                'playlists': song.get('playlists', [])
            })
        
        logging.info(f"Found {len(songs_list)} recently logged songs")
        return songs_list
        
    except Exception as e:
        logging.error(f"Error getting recently logged songs: {e}", exc_info=True)
        return []

def get_playlist_name_from_spotify(playlist_id, access_token):
    """Get the actual playlist name from Spotify API"""
    try:
        request = requests.get(
            f"https://api.spotify.com/v1/playlists/{playlist_id}",
            headers={'Authorization': f'Bearer {access_token}'},
            params={'fields': 'name'}
        )
        response = request.json()
        
        if 'name' in response:
            return response['name']
        else:
            logging.warning(f"Could not get name for playlist {playlist_id}: {response}")
            return f"Playlist {playlist_id}"
            
    except Exception as e:
        logging.error(f"Error getting playlist name for {playlist_id}: {e}")
        return f"Playlist {playlist_id}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Spotify Collector V3 - Function-oriented MongoDB version')
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Main collection command
    collect_parser = subparsers.add_parser('collect', help='Run the main collection process')
    
    # Statistics command
    stats_parser = subparsers.add_parser('stats', help='Show MongoDB statistics')
    
    # Test MongoDB connection
    test_parser = subparsers.add_parser('test-db', help='Test MongoDB connection')
    
    # Setup indexes
    setup_parser = subparsers.add_parser('setup-db', help='Setup MongoDB indexes')
    
    # Clean logs
    clean_parser = subparsers.add_parser('clean-logs', help='Clean up large log files')
    
    # Get recent songs for email updates
    recent_parser = subparsers.add_parser('recent-songs', help='Get recently logged songs for email updates')
    recent_parser.add_argument('--days', type=int, default=7, help='Number of days to look back (default: 7)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command provided, run main collection (backward compatibility)
    if not args.command:
        try:
            collect_playlists_v3()
        except Exception as err:
            logging.error(f"Error in main collection process: {err}", exc_info=True)
            print(f"❌ Error: {err}")
        finally:
            log_cleaner()
        sys.exit(0)
    
    try:
        if args.command == 'collect':
            print("🚀 Starting main collection process...")
            collect_playlists_v3()
            
        elif args.command == 'stats':
            print("📊 MongoDB Statistics:")
            try:
                stats = get_statistics()
                print("\nDetailed breakdown:")
                for key, value in stats.items():
                    print(f"  {key.replace('_', ' ').title()}: {value}")
            except Exception as e:
                print(f"❌ Could not get statistics: {e}")
                
        elif args.command == 'test-db':
            test_mongodb_connection()
            
        elif args.command == 'setup-db':
            print("⚙️  Setting up MongoDB indexes...")
            if setup_mongodb_indexes():
                print("✅ MongoDB indexes created successfully")
            else:
                print("❌ Failed to create MongoDB indexes")
            
        elif args.command == 'clean-logs':
            print("🧹 Cleaning log files...")
            log_cleaner()
            print("✅ Log cleanup complete")
            
        elif args.command == 'recent-songs':
            print(f"📧 Getting recently logged songs (last {args.days} days)...")
            try:
                recent_songs = get_recently_logged_songs(args.days)
                if recent_songs:
                    print(f"\nFound {len(recent_songs)} recently logged songs:")
                    for song in recent_songs:
                        print(f"  • {song['title']} by {song['artist']}")
                        print(f"    URI: {song['uri']}")
                        print(f"    Logged: {song['logged']}")
                        if song.get('playlists'):
                            print(f"    In playlists: {len(song['playlists'])}")
                        print()
                else:
                    print("No recently logged songs found.")
            except Exception as e:
                print(f"❌ Could not get recent songs: {e}")
            
    except Exception as err:
        logging.error(f"Error running command '{args.command}': {err}", exc_info=True)
        print(f"❌ Error: {err}")
        sys.exit(1)
