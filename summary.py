from utilities import *

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%B-%d-%Y %H:%M:%S',
    filename=f"./logs/{Path(__file__).stem}.log",
    filemode='a'
)

def daily_summary():
    
    table_data = ''
    songs_added_today = db.collection('songs').where('logged', '==', False).stream()
    song_count = 0

    for song in songs_added_today:
        song_count += 1
        table_data += f"<tr><td><img src=\"{song.to_dict()['image_url']}\" width=\"128px\"></td><td><p>Title: \"{song.to_dict()['title']}\"</p><p>Artist: {song.to_dict()['artist']}</p></td></tr>"
        db.collection('songs').document(song.id).update({'logged': True})

    if song_count > 0:

        with open('email.html', 'r') as html_file:
            html_email = html_file.read().replace('###table_data###', table_data)

        send_summary_email(html_email, 'tophermckee@gmail.com')

    else:
        logging.info(f"😮‍💨 No songs since last email 😮‍💨")

if __name__ == '__main__':
    daily_summary()