import requests, json, time, datetime, pprint, logging, string
from pprint import pformat
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%B-%d-%Y %H:%M:%S',
    filename=f"./logs/{Path(__file__).stem}.log",
    filemode='a'
)

pp = pprint.PrettyPrinter(indent=2)
# test with comment
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

    logging.info(f'\nClick the link below and authorize the application.\n\n{token_response.url}\n')
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

    logging.info(f'\n{access_response}\n')

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


def add_song(uri, playlist_id, title, artist):
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
    
    logging.info(f'\n{post_attempt}\n')


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


def compare_playlists():
        
    with open('creds.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token'][0]    

    check_token()

    for collection in credentials['collections']:
        
        headers = {'Authorization': f'Bearer {credentials["access_token"][0]}'}
        playlist_ids = credentials['collections'][collection]['playlist_ids']
        destination_song_ids = []
        offset = 0

        destination_playlist_id = credentials['collections'][collection]['destination_id']
        destination_playlist_name = return_playlist_name(destination_playlist_id)

        while offset < return_playlist_length(destination_playlist_id):
            
            params = {'offset': offset}
            this_playlist_response = requests.get(f'https://api.spotify.com/v1/playlists/{destination_playlist_id}/tracks', headers=headers, params=params).json()
            
            for song in this_playlist_response['items']:
                destination_song_ids.append(song["track"]["id"])
            offset += 100
        
        logging.info(f"\n{len(destination_song_ids)} songs in destination playlist -- {return_playlist_name(destination_playlist_id)}\n")
        
        for id in playlist_ids:
            
            playlist_name = return_playlist_name(id)
            logging.info(f'checking playlist {playlist_name}')
            added_songs = 0
            offset = 0
            
            while offset < return_playlist_length(id):
                
                playlist_id = id
                params = {'offset': offset}
                this_playlist_response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=headers, params=params).json()
                
                for song in this_playlist_response['items']:

                    if song["track"]["id"] in destination_song_ids:
                        continue
                    else:
                        add_song(song["track"]["uri"], credentials['collections'][collection]['destination_id'], song["track"]["name"], song["track"]["artists"][0]["name"])
                        added_songs += 1
                
                offset += 100

            logging.info(f'added {added_songs} songs from {playlist_name} songs to {destination_playlist_name}\n')

if __name__ == "__main__":
    refresh_token()
    compare_playlists()