from utilities import *

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%B-%d-%Y %H:%M:%S',
    filename=f"./logs/{Path(__file__).stem}.log",
    filemode='a'
)

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

if __name__ == "__main__":
    refresh_token()
    collect_playlists()