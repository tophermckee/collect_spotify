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
    not_downloaded_yet = list(songs_collection.find({'downloaded': False}))
    song_count = 0

    for song in not_downloaded_yet:
        try:
            # You may want to adjust the format_string logic for your needs
            uri = song.get('uri')
            artist = song.get('artist', 'Unknown Artist')
            album = song.get('album', 'Unknown Album')
            track_number = song.get('track_number', '')
            song_name = song.get('title', 'Unknown Title')
            ext = 'mp3'
            # Download using zotify (adjust path as needed)
            result = os.system(f"/opt/homebrew/bin/zotify '{uri}' --download-real-time --audio-format=mp3 --album-library=/Volumes/data/media/zotify/Music/")
            if result == 0:
                songs_collection.update_one({'_id': song['_id']}, {'$set': {'downloaded': True}})
            song_count += 1
        except Exception as err:
            logging.error(f"Error downloading {song.get('_id')}: {err}", exc_info=True)

    if song_count > 0:
        logging.info(f"Successfully downloaded {song_count} songs.")
    else:
        logging.info(f"😮‍💨 No songs since last email 😮‍💨")

if __name__ == '__main__':
    daily_download()
