from utilities import *

def daily_download():
    
    table_data = ''

    not_downloaded_yet = list(db.collection('songs').where(filter=FieldFilter('downloaded', '==', False)).stream())
    song_count = 0

    for song in not_downloaded_yet:
        try:
            format_string = r"{artist}/{album}/{track_number} - {song_name}.{ext}"
            result = os.system(f"/opt/homebrew/bin/zotify '{song.to_dict()['uri']}' --download-real-time --audio-format=mp3 --album-library=/Volumes/data/media/zotify/Music/")
            if result == 0:
                db.collection('songs').document(song.id).update({'downloaded': True})
            song_count += 1
        except Exception as err:
            logging.error(f"Error downloading {song.id}: {err}", exc_info=True)
        

    if song_count > 0:

        logging.info(f"Successfully downloaded {song_count} songs.")

    else:
        logging.info(f"😮‍💨 No songs since last email 😮‍💨")

if __name__ == '__main__':
    daily_download()