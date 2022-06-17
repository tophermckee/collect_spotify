import requests, json, time, datetime, pprint, logging, string, firebase_admin, smtplib
from email.message import EmailMessage
from firebase_admin import credentials
from firebase_admin import firestore
from pprint import pformat
from pathlib import Path

cred = credentials.Certificate('collect-spotify-firebase.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

with open('creds.json') as file:
    credentials = json.load(file)

pp = pprint.PrettyPrinter(indent=2)

today_with_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get_auth_token():
    with open('creds.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token']

    token_headers = {
        'client_id': credentials['client_id'],
        'response_type': 'code',
        'redirect_uri': credentials['redirect_uri'],
        'scope': 'playlist-modify-public,playlist-modify-private'
    }
    token_response = requests.get(
        'https://accounts.spotify.com/authorize',
        params=token_headers
    )

    print(f'\nClick the link below and authorize the application.\n\n{token_response.url}\n')
    auth_token = input('Paste your token from the URL.   ').strip()
    
    credentials['auth_token'] = auth_token.replace('https://github.com/tophermckee?code=', '')

    with open('creds.json', 'w', encoding='utf-8') as f:
        json.dump(credentials, f, ensure_ascii=False, indent=4)
        f.close()

    return auth_token


def get_access_token():
    with open('creds.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token']
    
    access_params = {
        "client_id": credentials['client_id'],
        "client_secret": credentials['client_secret'],
        'grant_type': 'authorization_code',
        'code': credentials['auth_token'],
        'redirect_uri': credentials['redirect_uri']
    }

    access_response = requests.post(
        'https://accounts.spotify.com/api/token',
        data=access_params
    ).json()

    # logging.info(f'\n{access_response}\n')

    credentials['access_token'] = access_response['access_token'],
    credentials['refresh_token'] = access_response['refresh_token'],
    credentials['expires_readable'] = datetime.datetime.fromtimestamp(time.time() + int(access_response['expires_in'])).strftime('%Y-%m-%d %H:%M:%S'),
    credentials['expires_integer'] = time.time() + int(access_response['expires_in'])

    with open('creds.json', 'w', encoding='utf-8') as f:
        json.dump(credentials, f, ensure_ascii=False, indent=4)
        f.close()


def refresh_token():
    with open('creds.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token']

    access_params = {
        "client_id": credentials['client_id'],
        "client_secret": credentials['client_secret'],
        'grant_type': 'refresh_token',
        'refresh_token': credentials['refresh_token'][0],
        'redirect_uri': credentials['redirect_uri']
    }

    access_response = requests.post(
        'https://accounts.spotify.com/api/token',
        data=access_params
    ).json()

    # logging.info(f'\n{access_response}\n')
    
    # logging.info(f"type of access_token -- {type(access_response['access_token'])}")
    
    credentials['access_token'] = access_response['access_token'],
    credentials['expires_readable'] = datetime.datetime.fromtimestamp(time.time() + int(access_response['expires_in'])).strftime('%Y-%m-%d %H:%M:%S'),
    credentials['expires_integer'] = time.time() + int(access_response['expires_in'])

    # logging.info(pformat(credentials))

    with open('creds.json', 'w', encoding='utf-8') as f:
        json.dump(credentials, f, ensure_ascii=False, indent=4)
        f.close()


def add_song_to_spotify(uri, playlist_id, title, artist):
    with open('creds.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token'][0]

    logging.info(f"Attempting to add \'{title.translate(str.maketrans('', '', string.punctuation))}\' by {artist} with uri {uri}")
    
    headers = {'Authorization': f'Bearer {credentials["access_token"][0]}', 'Content-Type': 'application/json'}

    payload = json.dumps({
        "uris": [uri]
    })

    post_attempt = requests.post(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=headers, data=payload).json()
    
    logging.info(f'{post_attempt}')

def add_song_to_firestore(uri, title, artist, image_url):

    doc_ref = db.collection(u'songs').document(uri).set({
        'uri': uri,
        'title': title,
        'artist': artist,
        'image_url': image_url,
        'logged': False
    })

def check_token():
    with open('creds.json') as file:
        credentials = json.load(file)

    if credentials['expires_integer'] < time.time():
        logging.info(f"token expired -- {credentials['expires_readable']}")
        refresh_token()
    else:
        logging.info('token still active')


def return_playlist_length(playlist_id) -> int:
    with open('creds.json') as file:
        credentials = json.load(file)
    return requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers={'Authorization': f'Bearer {credentials["access_token"][0]}'}).json()['total']


def return_playlist_name(playlist_id) -> str:
    with open('creds.json') as file:
        credentials = json.load(file)
    return requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers={'Authorization': f'Bearer {credentials["access_token"][0]}'}).json()['name']

def send_summary_email(html_email, recipient):
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        try:
            smtp.login(credentials['email_address'], credentials['python_gmail_app_password'])
        except Exception as error:
            logging.error(f"Error at SSL login -- {error}", exc_info=True)
            smtp.quit()
        
        msg = EmailMessage()
        msg['Subject'] = f'Spotify Collection {today_with_time}'
        msg['From'] = credentials['email_address']
        msg['To'] = recipient
        msg.add_alternative(html_email, subtype='html')
        logging.info(f"🤞 Attempting email to {recipient} 🤞")
        try:
            smtp.send_message(msg)
            logging.info(f"🍾 Email sent for to:{recipient} 🍾")
            smtp.quit()
        except Exception as error:
            logging.error(f"Error at send for to:{recipient} -- error: {error}", exc_info=True)
            smtp.quit()
    