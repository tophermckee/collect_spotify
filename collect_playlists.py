from utilities import *

def collect_playlists():
        
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
                        add_song_to_spotify(song["track"]["uri"], credentials['collections'][collection]['destination_id'], song["track"]["name"], song["track"]["artists"][0]["name"])
                        add_song_to_firestore(song["track"]["uri"], song["track"]["name"], song["track"]["artists"][0]["name"], song["track"]["album"]["images"][0]["url"])
                        added_songs += 1
                
                offset += 100

            logging.info(f'added {added_songs} songs from {playlist_name} songs to {destination_playlist_name}\n')


def collect_playlists_v2():
    access_token = refresh_token()[0]

    playlist_info = {
        'current_yearly': {
            'id': credentials['collections']['yearly_playlist_collection']['playlist_ids'][-1],
            'song_ids': [],
            'song_titles': []
        },
        'country_playlist': {
            'id': credentials['country_collection_id'],
            'song_ids': [],
            'song_titles': []
        },
        'collection_playlist': {
            'id': credentials['collections']['yearly_playlist_collection']['destination_id'],
            'song_ids': [],
            'song_titles': []
        }
    }
    
    for playlist in playlist_info:
        
        offset = 0
        
        while offset < return_playlist_length(playlist_info[playlist]['id']):
            
            params = {'offset': offset}
            request =  requests.get(f"https://api.spotify.com/v1/playlists/{playlist_info[playlist]['id']}/tracks", headers={'Authorization': f'Bearer {access_token}'}, params=params)
            this_playlist_response = request.json()
            
            with open(f"logs/json/{datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}_{playlist}offset{offset}playlistresponse.json", "w") as file:
                json.dump(this_playlist_response, file, indent=4)
            
            for song in this_playlist_response['items']:
                playlist_info[playlist]['song_ids'].append(song["track"]["id"])
                playlist_info[playlist]['song_titles'].append(song["track"]["name"])
            
            offset += 100
        
        logging.info(f"{len(playlist_info[playlist]['song_ids'])} songs in playlist -- {return_playlist_name(playlist_info[playlist]['id'])}")
    
    liked_tracks = get_liked_tracks()['items']

    for track in liked_tracks:
        primary_artist = track['track']['artists'][0]['id']
        artist_info = get_artist(primary_artist)
        country = False
        for genre in artist_info['genres']:                
            if 'country' in genre.lower():
                country = True
                break
        print(f"{artist_info['name']}, {country=}", artist_info['genres'])
        if country:
            
            if track["track"]["id"] not in playlist_info['country_playlist']['song_ids']:
                add_song_to_spotify(track["track"]["uri"], credentials['country_collection_id'], track["track"]["name"], track["track"]["artists"][0]["name"])
            else:
                logging.info(f"not adding {track['track']['name']} by {track['track']['artists'][0]['name']} because already included in playlist")
        
        else:
            
            if track["track"]["id"] not in playlist_info['current_yearly']['song_ids']:
                add_song_to_spotify(track["track"]["uri"], playlist_info['current_yearly']['id'], track["track"]["name"], track["track"]["artists"][0]["name"])
            else:
                logging.info(f"not adding {track['track']['name']} by {track['track']['artists'][0]['name']} because already included in playlist")

            if track["track"]["id"] not in playlist_info['collection_playlist']['song_ids']:
                add_song_to_spotify(track["track"]["uri"], playlist_info['collection_playlist']['id'], track["track"]["name"], track["track"]["artists"][0]["name"])
            else:
                logging.info(f"not adding {track['track']['name']} by {track['track']['artists'][0]['name']} because already included in playlist")

        delete_song_from_likes(track["track"]["id"])
        add_song_to_firestore(track["track"]["uri"], track["track"]["name"], track["track"]["artists"][0]["name"], track["track"]["album"]["images"][0]["url"])

def log_cleaner():
    directory = "logs/json"
    for file in os.listdir(directory):
        file_size = os.stat(f'{directory}/{file}')
        if file_size.st_size >= 5_000:
            logging.info(f"removing {directory}/{file} because it is over 500 KB at {file_size.st_size} bytes")
            os.remove(f'{directory}/{file}')

if __name__ == "__main__":
    refresh_token()
    try:
        collect_playlists_v2()
    except Exception as err:
        logging.error(f"error collecting playlists: {err}", exc_info=True)
    log_cleaner()