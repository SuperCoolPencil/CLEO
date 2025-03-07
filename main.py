import os.path
import base64
from bs4 import BeautifulSoup
import dateparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
from datetime import datetime,timedelta
import sys
from termcolor import colored
from tqdm import tqdm

print('''
    ░█████╗░██╗░░░░░███████╗░█████╗░
    ██╔══██╗██║░░░░░██╔════╝██╔══██╗
    ██║░░╚═╝██║░░░░░█████╗░░██║░░██║
    ██║░░██╗██║░░░░░██╔══╝░░██║░░██║
    ╚█████╔╝███████╗███████╗╚█████╔╝
    ░╚════╝░╚══════╝╚══════╝░╚════╝░
''')

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar"
]


def authenticate():

    creds = None

    # if token.json exists check if creds are still valid
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    # if not valid refresh
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        
        else:

            # TODO: Think of a way to eliminate credentials.json
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )

            creds = flow.run_local_server(port=0)

            with open("token.json", "w") as token:
                token.write(creds.to_json())
        
    return creds

def getPart(parts, type):

    # check for plain text
    for part in parts:
        if part.get('mimeType') == 'text/plain':
            data = part[type].get("data")

            if data:
                byte_code = base64.urlsafe_b64decode(data)
                text = byte_code.decode("utf-8")
                return text
    
    # parse html using beautiful soup 4
    for part in parts:
        if part.get('mimeType') == 'text/html':
            data = part['body'].get('data')
            if data:
                byte_code = base64.urlsafe_b64decode(data)
                html = byte_code.decode("utf-8")
                soup = BeautifulSoup(html, 'html.parser')
                return soup.get_text()
    
    # nothing to do
    return ''

def getMail(creds, maxResults):

    mails = []

    try:
        service = build("gmail", "v1", credentials=creds)

        # TODO: Decide how many emails to fetch or what conditions they must satisfy
        results = service.users().messages().list(userId = "me", labelIds = ['INBOX'], maxResults = maxResults).execute()

        messages = results.get('messages', [])

        for message in messages:

            mail = {}

            msg = service.users().messages().get(userId = "me", id = message['id']).execute()
            email_data = msg['payload']['headers']

            # extract from, subject, datetime from headers
            for values in email_data:
                name = values['name']

                if name == 'From':
                    mail['from'] = values['value']

                elif name == 'Subject':
                    mail['subject'] = values['value']

                elif name == "Date":
                    mail['when'] = values['value']

            parts = msg['payload']['parts']

            body = getPart(parts, "body").lower()

            # Doing it this way so I dont have to deal with escape characters
            mail['body'] = ' '.join(body.split())

            mails.append(mail)


        return mails   

    
    except HttpError as error:
        print(f"An error occurred: {error}")

def extractDate(sentence, contextTime):

    # context time is just time the mail was received. It is needed for relative dates 

    # TODO: implement things like today, tommorow
    # TODO: figure out how this is going to work with multi-day events and stuff
    
    results = []

    relative_date_regex = r'\b(?:(?:today|tomorr?(?:ow|morow)|yesterday)|(?:(?:next|last|this|on)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)))\b'

    results = re.findall(relative_date_regex, sentence)

    if len(results) > 0:
        # if we find relative dates, no need to find hardcoded dates
        
        for i in range(len(results)):
            results[i] = datetime.now() - dateparser.parse(results[i]) + contextTime
        
        return results[0]

    date_regexes = [
        r'\b\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}\b', 
        r'\b\d{1,2}(?:th|st|nd|rd)?(?:[\s,]+|(?:\s+of\s+))?(?:(?:jan(?:uary)?)|(?:feb(?:ruary)?)|(?:mar(?:ch)?)|(?:apr(?:il)?)|may|(?:jun(?:e)?)|(?:jul(?:y)?)|(?:aug(?:ust)?)|(?:sep(?:tember)?)|(?:oct(?:ober)?)|(?:nov(?:ember)?)|(?:dec(?:ember)?))\b,?\s*(?:\d{4})?\b', 
        r'\b(?:(?:jan(?:uary)?)|(?:feb(?:ruary)?)|(?:mar(?:ch)?)|(?:apr(?:il)?)|may|(?:jun(?:e)?)|(?:jul(?:y)?)|(?:aug(?:ust)?)|(?:sep(?:tember)?)|(?:oct(?:ober)?)|(?:nov(?:ember)?)|(?:dec(?:ember)?))\s+\d{1,2},?\s*(?:\d{4})?(?:(?:\s)|\.)\b'
    ]

    for regex in date_regexes:
            
        results = re.findall(regex, sentence)

        if len(results) > 0:

            # we need to remove stuff like 'th' to make it play nice with datetime
            return re.sub(r'(\d+)(st|nd|rd|th)(\s+of)?\s+', r'\1 ', results[0])
        
    return ''

def extractTime(sentence):

    time_regex = r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b'

    results = re.findall(time_regex, sentence)

    if len(results) > 0:

        return results[0]
    
    return ''

def extractDateHelper(sentence, contextTime):

    # We can just work with a single sentence at a time and extract date and time

    date = extractDate(sentence, contextTime)

    if type(date) == type(datetime.now()):
        date = date.strftime("%Y-%m-%d")

    time = extractTime(sentence)

    if date or time:
        return date + ' ' + time
    
    return ''

def normalize_date(date_list):

    date_str = " ".join(date_list) if isinstance(date_list, list) else date_list
    date_obj = dateparser.parse(date_str)
    
    # Convert to desired format (ISO 8601)
    return date_obj if date_obj else None

def extractDateTime(mails):

    # TODO: FIX THIS MESS (it works tho...)

    for mail in tqdm(mails):

        date_format = "%a, %d %b %Y %H:%M:%S %z"

        contextTime = datetime.strptime(mail['when'], date_format)

        dt = []

        for sentence in mail['body'].split('.'):

            data = extractDateHelper(sentence, contextTime)

            if data:

                dt.append(data)
        
        mail['datetime'] = normalize_date(dt)

        if not mail['datetime']:
            # if nothing is found in body we could try looking at the subject
            dt = extractDateHelper(mail['subject'].lower(), contextTime)
            mail['datetime'] = normalize_date(dt)

from datetime import timedelta  # Ensure you import timedelta

def addEvent(creds, mail):
    try:
        service = build("calendar", "v3", credentials=creds)

        event = {
            'summary': mail['title'],
            'description': mail['subject'] + '\n' + mail['body'],
            'start': {
                'dateTime': mail['datetime'].isoformat(),
                'timeZone': 'Asia/Kolkata' 
            },
            'end': {
                'dateTime': (mail['datetime'] + timedelta(hours=int(mail['duration']))).isoformat(),
                'timeZone': 'Asia/Kolkata'
            }
        }

        event = service.events().insert(calendarId='primary', body=event).execute()

        return event.get('htmlLink')

    except HttpError as error:
        print(f"An error occurred: {error}")


# Created a main function for better structure
def main():

    

    maxResults = sys.argv[1] if len(sys.argv) > 1 else 5

    creds = authenticate()

    if creds and creds.valid:

        print("[-] User authenticated!")
        print("[o] Getting mail...")

        mails = getMail(creds, maxResults)

        if len(mails) > 0:
            print("[~] Pulled mail from Gmail API!")

        print("[-] Extracting date and time...")
        extractDateTime(mails)

        # TODO: Extract event names

        for mail in mails:

            if mail['datetime']:
                
                print(colored(mail['subject'], 'yellow'), colored(mail['datetime'], 'cyan'))

                if input("Add event to calendar? [Y/n]: ") == 'n':
                    continue
                
                print()
                print(mail['body'])
                mail['duration'] = input("Enter duration in hours: ")
                mail['title'] = input("Enter event title: ")

                addEvent(creds, mail)


        
        

if __name__ == '__main__':
    main()