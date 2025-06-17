from utilities import *

def collect_playlists_v2():
    access_token = refresh_token()

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
        logging.info(f"{artist_info['name']}, {country=}", artist_info['genres'])
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
