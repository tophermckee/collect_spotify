# Configuration Guide for Spotify Collector V3

## Credentials Storage

All credentials and configuration are stored in the `creds.json` file. Here's how to set it up:

### 1. Copy the Template
```bash
cp creds_v3.json-TEMPLATE creds.json
```

### 2. Configure Each Section

#### Spotify API Credentials
```json
{
  "client_id": "your_spotify_client_id",
  "client_secret": "your_spotify_client_secret",
  "redirect_uri": "https://github.com/your_username"
}
```

Get these from: https://developer.spotify.com/dashboard

#### Playlist Configuration
```json
{
  "collections": {
    "yearly_playlist_collection": {
      "playlist_ids": [
        "37i9dQZF1DX0XUsuxWHRQd",  // 2023 playlist
        "37i9dQZF1DX4JAvHpjipBk",  // 2024 playlist  
        "37i9dQZF1DX2RxBh64BHjQ"   // 2025 playlist (newest)
      ],
      "destination_id": "37i9dQZF1DX5Ejj0EkURtP"  // Main collection
    }
  },
  "country_collection_id": "37i9dQZF1DX1lVhptIYRda"
}
```

To get playlist IDs:
1. Open Spotify playlist in web browser
2. Copy the ID from the URL: `https://open.spotify.com/playlist/PLAYLIST_ID`

#### Email Configuration (for notifications)
```json
{
  "email": "your_email@gmail.com",
  "password": "your_app_password"
}
```

For Gmail, use an App Password: https://support.google.com/accounts/answer/185833

#### MongoDB Configuration

##### Local MongoDB (default)
```json
{
  "mongodb": {
    "host": "localhost",
    "port": 27017,
    "database": "spotify_collector",
    "username": null,
    "password": null
  }
}
```

##### MongoDB with Authentication
```json
{
  "mongodb": {
    "host": "your-mongo-server.com",
    "port": 27017,
    "database": "spotify_collector",
    "username": "your_mongo_username",
    "password": "your_mongo_password"
  }
}
```

##### MongoDB Atlas (Cloud)
```json
{
  "mongodb": {
    "host": "cluster0.xxxxx.mongodb.net",
    "port": 27017,
    "database": "spotify_collector",
    "username": "your_atlas_username",
    "password": "your_atlas_password"
  }
}
```

## Security Best Practices

### 1. File Permissions
```bash
chmod 600 creds.json
```

### 2. Git Ignore
Make sure `creds.json` is in your `.gitignore`:
```
creds.json
*.log
logs/
```

### 3. Environment Variables (Alternative)
If you prefer environment variables, you can modify the code to read from environment instead:

```python
import os

# Alternative: Use environment variables
mongo_host = os.getenv('MONGO_HOST', 'localhost')
mongo_port = int(os.getenv('MONGO_PORT', 27017))
mongo_db_name = os.getenv('MONGO_DB', 'spotify_collector')
```

## Directory Structure
```
collect_spotify/
├── creds.json                           # Your credentials (not in git)
├── creds_v3.json-TEMPLATE              # Template file
├── collect_playlists_v3_functional.py  # Main script
├── utilities_v3.py                     # Helper functions
├── requirements_v3.txt                 # Dependencies
├── logs/                               # Log files
│   ├── 2025-06-17_collect_playlists_v3_functional.log
│   └── json/                           # API response logs
└── README_v3.md                        # Documentation
```

## First Run Setup

1. Install dependencies:
   ```bash
   pip install -r requirements_v3.txt
   ```

2. Set up credentials:
   ```bash
   cp creds_v3.json-TEMPLATE creds.json
   # Edit creds.json with your actual values
   ```

3. Start MongoDB (if running locally):
   ```bash
   brew services start mongodb/brew/mongodb-community
   # or
   sudo systemctl start mongod
   ```

4. Run the collector:
   ```bash
   python collect_playlists_v3_functional.py
   ```

The first run will create the necessary MongoDB collections and indexes automatically.
