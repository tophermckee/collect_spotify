import requests, json, time, datetime, pprint, logging, string, firebase_admin, smtplib
from email.message import EmailMessage
from firebase_admin import credentials
from firebase_admin import firestore
from pprint import pformat
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%B-%d-%Y %H:%M:%S',
    filename=f"./logs/{Path(__file__).stem}.log",
    filemode='w'
)

cred = credentials.Certificate('spotify-collection-93bd97a82285.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

with open('creds.json') as file:
    credentials = json.load(file)

pp = pprint.PrettyPrinter(indent=2)

today_with_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def main():
    
    table_data = ''
    songs_added_today = db.collection('songs').where('logged', '==', False).stream()
    song_count = 0
    
    for song in songs_added_today:
        song_count += 1
        table_data += f"<tr><td><img src=\"{song.to_dict()['image_url']}\" width=\"128px\"></td><td><p>Title: \"{song.to_dict()['title']}\"</p><p>Artist: {song.to_dict()['artist']}</p></td></tr>"
        db.collection('songs').document(song.id).update({'logged': True})

    if song_count > 0:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            try:
                smtp.login(credentials['email_address'], credentials['python_gmail_app_password'])
            except Exception as error:
                logging.error(f"Error at SSL login -- {error}", exc_info=True)
                smtp.quit()

            with open('email.html', 'r') as html_file:
                html_email = html_file.read().replace('###table_data###', table_data)
            
            msg = EmailMessage()
            msg['Subject'] = f'Spotify Collection {today_with_time}'
            msg['From'] = credentials['email_address']
            msg['To'] = 'tophermckee@gmail.com'
            msg.set_content('this is the content')
            msg.add_alternative(html_email, subtype='html')

            logging.info(f"🤞 Attempting email for to:tophermckee@gmail.com 🤞")
            try:
                smtp.send_message(msg)
                logging.info(f"🍾 Email sent for to:tophermckee@gmail.com 🍾")
                smtp.quit()
            except Exception as error_inside:
                logging.error(f"Error at send for to:tophermckee@gmail.com -- error: {error_inside}", exc_info=True)
                smtp.quit()
    else:
        logging.info(f"😮‍💨 No songs since last email 😮‍💨")

if __name__ == '__main__':
    main()