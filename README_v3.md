# Spotify Collector V3 - Function-Oriented MongoDB Version

This is an optimized, function-oriented version of the Spotify playlist collector that uses MongoDB exclusively (no Firebase) for caching and implements better tracking of song additions.

## New Features

### 1. Function-Oriented Design
- Simple function-based approach instead of object-oriented
- Easy to understand and modify
- All functions are independent and can be used separately

### 2. MongoDB-Only Storage
- **No Firebase dependencies** - everything stored in MongoDB
- Playlists cached in MongoDB and refreshed only when needed
- Song data stored in MongoDB instead of Firestore
- Addition attempts logged and tracked in MongoDB

### 3. Smart Caching System
- Most playlists refresh only once per month (configurable via `CACHE_REFRESH_DAYS`)
- The newest playlist is always checked, but only the most recent songs (configurable via `NEWEST_PLAYLIST_CHECK_SONGS`)
- Significantly reduces Spotify API calls

### 4. Song Addition Tracking
- All song addition attempts are logged in MongoDB
- Failed additions are automatically retried up to 3 times
- Verification system checks if songs were actually added to playlists
- Provides statistics on success/failure rates

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements_v3.txt
   ```

2. Ensure MongoDB is running on your VPC:
   ```bash
   # Default connection: mongodb://localhost:27017/
   # Modify the connection string in the code if needed
   ```

3. Run the optimized collector:
   ```bash
   python collect_playlists_v3_functional.py
   ```

## Configuration

### Cache Settings
- `CACHE_REFRESH_DAYS = 30`: How often to refresh playlist caches (days)
- `NEWEST_PLAYLIST_CHECK_SONGS = 50`: Only check last N songs of newest playlist

### MongoDB Collections
- `playlists`: Cached playlist data
- `songs`: Song information (replaces Firestore)
- `add_attempts`: Log of song addition attempts for verification

## Key Functions

### Main Functions
- `collect_playlists_v3()`: Main collection function
- `get_playlist_songs()`: Get playlist data from cache or API
- `process_liked_tracks()`: Process and categorize liked tracks
- `verify_song_additions()`: Verify songs were actually added

### Helper Functions
- `should_refresh_playlist()`: Check if playlist needs refreshing
- `log_add_attempt()`: Log song addition attempts
- `add_song_to_mongodb()`: Store songs in MongoDB
- `get_statistics()`: Get system statistics

## Key Differences from V2

1. **Function-Oriented**: Simple functions instead of classes
2. **No Firebase**: Everything stored in MongoDB
3. **Reduced API Calls**: Cached playlists mean fewer Spotify API requests
4. **Smart Refresh**: Only refreshes data when needed
5. **Verification System**: Tracks and verifies song additions
6. **Statistics**: Provides insights into cache usage and success rates
7. **Error Recovery**: Automatically retries failed additions

## Migration Notes

- This version runs alongside your existing systems
- **No Firebase dependencies** - completely self-contained with MongoDB
- Can be tested independently before migration
- All song data will be stored in MongoDB instead of Firestore

## Monitoring

The system provides statistics including:
- Number of cached playlists
- Total cached songs
- Total songs in MongoDB database
- Recent addition attempts
- Unverified attempts
- Failed attempts

These help monitor the system's health and efficiency.
