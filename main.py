import requests, json, time, datetime, pprint

pp = pprint.PrettyPrinter(indent=2)

def get_auth_token():
    with open('creds.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token']

    token_headers = {
        'client_id': credentials['client_id'],
        'response_type': 'code',
        'redirect_uri': credentials['redirect_uri'],
        'scope': 'playlist-modify-public'
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

    print(f'\n{access_response}\n')

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

    print(f'\n{access_response}\n')
    
    print(f"type of access_token -- {type(access_response['access_token'])}")
    
    credentials['access_token'] = access_response['access_token'],
    credentials['expires_readable'] = datetime.datetime.fromtimestamp(time.time() + int(access_response['expires_in'])).strftime('%Y-%m-%d %H:%M:%S'),
    credentials['expires_integer'] = time.time() + int(access_response['expires_in'])

    pp.pprint(credentials)

    with open('creds.json', 'w', encoding='utf-8') as f:
        json.dump(credentials, f, ensure_ascii=False, indent=4)
        f.close()

def add_song(uri):
    with open('creds.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token'][0]

    print(f'Attempting to add current song with uri {uri}')
    headers = {
        'Authorization': f'Bearer {credentials["access_token"][0]}',
        'Content-Type': 'application/json'
    }

    payload = json.dumps({
        "uris": [uri]
    })

    post_attempt = requests.post(  
        'https://api.spotify.com/v1/playlists/0vgMGc8YNo1mx3FoWWWjzu/tracks',
        headers=headers,
        data=payload
    ).json()
    print(f'\n{post_attempt}\n')

def compare_playlists():
        
    with open('creds.json') as file:
        credentials = json.load(file)

    auth_token = credentials['auth_token']
    access_token = credentials['access_token'][0]

    if credentials['expires_integer'] < time.time():
        print(f"token expired -- {credentials['expires_readable']}")
        refresh_token()
    else:
        print('token still active')

    playlist_ids = credentials['playlist_ids']
    destination_ids = []
    offset = 0
    i = 1
    while offset < 2000:
        playlist_id = credentials['destination_id']
        playlist_headers = {
            'Authorization': f'Bearer {credentials["access_token"][0]}'
        }
        params = {
            'offset': offset
        }
        this_playlist_response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=playlist_headers, params=params).json()
        for song in this_playlist_response['items']:
            destination_ids.append(song["track"]["id"])
            i += 1
        offset += 100
    
    print(f"\n{len(destination_ids)} songs in destination playlist\n")
    
    for id in playlist_ids:
        playlist_name = requests.get(
            f'https://api.spotify.com/v1/playlists/{id}',
            headers={
                'Authorization': f'Bearer {credentials["access_token"][0]}',
                'Content-Type': 'application/json'
            }
        ).json()['name']
        print(f'checking playlist {playlist_name}')
        added_songs = 0
        offset = 0
        i = 1
        while offset < 2000:
            playlist_id = id
            playlist_headers = {
                'Authorization': f'Bearer {credentials["access_token"][0]}',
                'Content-Type': 'application/json'
            }
            params = {
                'offset': offset
            }
            this_playlist_response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=playlist_headers, params=params).json()
            for song in this_playlist_response['items']:
                i += 1

                if song["track"]["id"] in destination_ids:
                    continue
                else:
                    add_song(song["track"]["uri"])
                    added_songs += 1
            offset += 100
        print(f'added {added_songs} songs from {playlist_name} songs to Collected Music\n')

if __name__ == "__main__":
    refresh_token()
    compare_playlists()