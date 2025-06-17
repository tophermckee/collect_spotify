import requests, json, time, datetime, pprint, logging, string, smtplib, os
from email.message import EmailMessage
from pprint import pformat
from pathlib import Path
import __main__

logging.basicConfig(
    level=logging.INFO,
    format="\n[%(levelname)s] %(asctime)s -- %(filename)s on line %(lineno)s\n\tFunction name: %(funcName)s\n\tMessage: %(message)s\n",
    datefmt='%B-%d-%Y %H:%M:%S',
    filename=f"./logs/{datetime.datetime.today().strftime('%Y-%m-%d')}_{Path(__main__.__file__).stem}.log",
    filemode='a'
)

with open('creds_v3.json') as file:
    credentials = json.load(file)

pp = pprint.PrettyPrinter(indent=2)

today_with_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get_auth_token():
    with open('creds_v3.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token']

    token_headers = {
        'client_id': credentials['client_id'],
        'response_type': 'code',
        'redirect_uri': credentials['redirect_uri'],
        'scope': 'playlist-modify-public,playlist-modify-private,user-library-modify,user-library-read'
    }
    token_response = requests.get(
        'https://accounts.spotify.com/authorize',
        params=token_headers
    )

    print(f'\nClick the link below and authorize the application.\n\n{token_response.url}\n')
    auth_token = input('Paste your token from the URL.   ').strip()
    
    credentials['auth_token'] = auth_token.replace('https://github.com/tophermckee?code=', '')

    with open('creds_v3.json', 'w', encoding='utf-8') as f:
        json.dump(credentials, f, ensure_ascii=False, indent=4)
        f.close()

    return auth_token


def get_access_token():
    with open('creds_v3.json') as file:
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

    logging.info(f'\n{access_response}\n')

    credentials['access_token'] = access_response['access_token'],
    credentials['refresh_token'] = access_response['refresh_token'],
    credentials['expires_readable'] = datetime.datetime.fromtimestamp(time.time() + int(access_response['expires_in'])).strftime('%Y-%m-%d %H:%M:%S'),
    credentials['expires_integer'] = time.time() + int(access_response['expires_in'])

    with open('creds_v3.json', 'w', encoding='utf-8') as f:
        json.dump(credentials, f, ensure_ascii=False, indent=4)
        f.close()


def refresh_token():
    with open('creds_v3.json') as file:
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

    credentials['access_token'] = access_response['access_token'],
    credentials['expires_readable'] = datetime.datetime.fromtimestamp(time.time() + int(access_response['expires_in'])).strftime('%Y-%m-%d %H:%M:%S'),
    credentials['expires_integer'] = time.time() + int(access_response['expires_in'])

    with open('creds_v3.json', 'w', encoding='utf-8') as f:
        json.dump(credentials, f, ensure_ascii=False, indent=4)

    return access_response['access_token']


def add_song_to_spotify(uri: str, playlist_id: str, title: str, artist: str):
    with open('creds_v3.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token'][0]

    logging.info(f"Attempting to add \'{title.translate(str.maketrans('', '', string.punctuation))}\' by {artist} with uri {uri}")
    
    headers = {'Authorization': f'Bearer {credentials["access_token"][0]}', 'Content-Type': 'application/json'}

    payload = json.dumps({
        "uris": [uri]
    })

    try:
        addition = requests.post(f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", headers=headers, data=payload)
        
        if addition.status_code == 201:
            logging.info(f"Successfully added \'{title}\' by {artist}")
        else:
            logging.error(f"Failed to add song. Status code: {addition.status_code}, Response: {addition.text}")
            
        return addition
        
    except Exception as error:
        logging.error(f"Exception adding song to Spotify: {error}", exc_info=True)


def check_token():
    with open('creds_v3.json') as file:
        credentials = json.load(file)

    if credentials['expires_integer'] < time.time():
        refresh_token()
    else:
        logging.info("Access token is still valid")


def return_playlist_length(playlist_id) -> int:
    with open('creds_v3.json') as file:
        credentials = json.load(file)
    return requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers={'Authorization': f'Bearer {credentials["access_token"][0]}'}).json()['total']


def return_playlist_name(playlist_id) -> str:
    with open('creds_v3.json') as file:
        credentials = json.load(file)
    return requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers={'Authorization': f'Bearer {credentials["access_token"][0]}'}).json()['name']

def send_summary_email(html_email, recipient):
    with open('creds_v3.json') as file:
        credentials = json.load(file)
        
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(credentials['email'], credentials['password'])
        
        msg = EmailMessage()
        msg['Subject'] = f"Spotify Collection Summary - {datetime.datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = credentials['email']
        msg['To'] = recipient
        msg.set_content(html_email, subtype='html')
        
        smtp.send_message(msg)
    
def get_liked_tracks():
    with open('creds_v3.json') as file:
        credentials = json.load(file)
    try:
        liked_tracks = requests.get('https://api.spotify.com/v1/me/tracks?limit=50', headers={'Authorization': f'Bearer {credentials["access_token"][0]}'}).json()
        logging.info(f"Retrieved {len(liked_tracks['items'])} liked tracks")
    except Exception as err:
        logging.error(f"Error getting liked tracks: {err}", exc_info=True)

    return liked_tracks

def get_artist(artist_id):
    with open('creds_v3.json') as file:
        credentials = json.load(file)
    try:
        artist = requests.get(f'https://api.spotify.com/v1/artists/{artist_id}', headers={'Authorization': f'Bearer {credentials["access_token"][0]}'}).json()
    except Exception as err:
        logging.error(f"Error getting artist info for {artist_id}: {err}", exc_info=True)

    return artist

def delete_song_from_likes(uri: str) -> None:
    with open('creds_v3.json') as file:
        credentials = json.load(file)
    json_info = {"ids": [uri]}
    payload = json.dumps(json_info)
    try:
        deletion = requests.delete('https://api.spotify.com/v1/me/tracks', headers={'Authorization': f'Bearer {credentials["access_token"][0]}', 'Content-Type': 'application/json'}, data=payload)
        if deletion.status_code == 200:
            logging.info(f"Successfully removed song {uri} from likes")
        else:
            logging.error(f"Failed to remove song from likes. Status: {deletion.status_code}, Response: {deletion.text}")
    except Exception as err:
        logging.error(f"Exception removing song from likes: {err}", exc_info=True)

    return deletion
