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


def daily_summary():
    table_data = ''
    songs_added = list(songs_collection.find({'logged': False}))
    song_count = 0

    for song in songs_added:
        song_count += 1
        table_data += f'<tr><td><img src="{song.get("image_url", "")}" width="128px"></td><td><p>Title: "{song.get("title", "")}"</p><p>Artist: {song.get("artist", "")}</p></td></tr>'
        songs_collection.update_one({'_id': song['_id']}, {'$set': {'logged': True}})

    if song_count > 0:
        with open('email.html', 'r') as html_file:
            html_email = html_file.read().replace('###table_data###', table_data)

        # Send email with custom From name
        from email.message import EmailMessage
        import smtplib
        msg = EmailMessage()
        msg['Subject'] = f"Spotify Collection Summary - {datetime.datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = f"Spotify Collection <{credentials['email']}>"
        msg['To'] = credentials['email']
        msg.set_content(html_email, subtype='html')
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(credentials['email'], credentials['password'])
            smtp.send_message(msg)
        logging.info(f"Sent summary email for {song_count} songs.")
    else:
        logging.info(f"😮‍💨 No songs since last email 😮‍💨")

if __name__ == '__main__':
    daily_summary()
