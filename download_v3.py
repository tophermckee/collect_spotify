from utilities_v3 import *
from pymongo import MongoClient
import os

# MongoDB connection - get from credentials (remote-friendly)
with open('creds_v3.json') as file:
    credentials = json.load(file)

mongo_config = credentials.get('mongodb', {})
mongo_host = mongo_config.get('host', 'localhost')
mongo_port = mongo_config.get('port', 27017)
mongo_db_name = mongo_config.get('database', 'spotify_collection')
mongo_username = mongo_config.get('username', None)
mongo_password = mongo_config.get('password', None)

if mongo_username and mongo_password:
    mongo_connection_string = f"mongodb://{mongo_username}:{mongo_password}@{mongo_host}:{mongo_port}/"
else:
    mongo_connection_string = f"mongodb://{mongo_host}:{mongo_port}/"

mongo_client = MongoClient(mongo_connection_string)
db = mongo_client[mongo_db_name]
songs_collection = db['songs']


def daily_download():
    music_dir = "/Volumes/data/media/zotify/Music/"
    if not os.path.isdir(music_dir):
        print(f"ERROR: Music directory '{music_dir}' is not accessible. Please connect to the NAS and try again.")
        return
    not_downloaded_yet = list(songs_collection.find({'downloaded': False}))
    song_count = 0

    def count_mp3_files(root_dir):
        count = 0
        for dirpath, dirnames, filenames in os.walk(root_dir):
            count += len([f for f in filenames if f.lower().endswith('.mp3')])
        return count

    for song in not_downloaded_yet:
        try:
            uri = song.get('uri')
            artist = song.get('artist', 'Unknown Artist')
            album = song.get('album', 'Unknown Album')
            track_number = song.get('track_number', '')
            song_name = song.get('title', 'Unknown Title')
            ext = 'mp3'
            # Build expected file path (adjust if zotify changes structure)
            # Example: /Volumes/data/media/zotify/Music/Artist/Album/01 - Song Name.mp3
            safe_artist = artist.replace('/', '_')
            safe_album = album.replace('/', '_')
            safe_song_name = song_name.replace('/', '_')
            if track_number:
                filename = f"{str(track_number).zfill(2)} - {safe_song_name}.{ext}"
            else:
                filename = f"{safe_song_name}.{ext}"
            before_count = count_mp3_files(music_dir)
            result = os.system(f"/opt/homebrew/bin/zotify '{uri}' --download-real-time --audio-format=mp3 --album-library={music_dir}")
            after_count = count_mp3_files(music_dir)
            if result == 0 and after_count == before_count + 1:
                songs_collection.update_one({'_id': song['_id']}, {'$set': {'downloaded': True}})
            else:
                logging.warning(f"Download for {song.get('_id')} did not increase mp3 count in {music_dir}")
            song_count += 1
        except Exception as err:
            logging.error(f"Error downloading {song.get('_id')}: {err}", exc_info=True)

    if song_count > 0:
        logging.info(f"Successfully processed {song_count} songs.")
    else:
        logging.info(f"😮‍💨 No songs since last email 😮‍💨")

if __name__ == '__main__':
    daily_download()
