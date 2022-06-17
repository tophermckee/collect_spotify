import requests, json, time, datetime, pprint, logging, string, firebase_admin, smtplib
from email.message import EmailMessage
from firebase_admin import credentials
from firebase_admin import firestore
from pprint import pformat
from pathlib import Path

cred = credentials.Certificate('spotify-collection-93bd97a82285.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

with open('creds.json') as file:
    credentials = json.load(file)

pp = pprint.PrettyPrinter(indent=2)

today_with_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')