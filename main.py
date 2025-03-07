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

print('''
    ░█████╗░██╗░░░░░███████╗░█████╗░
    ██╔══██╗██║░░░░░██╔════╝██╔══██╗
    ██║░░╚═╝██║░░░░░█████╗░░██║░░██║
    ██║░░██╗██║░░░░░██╔══╝░░██║░░██║
    ╚█████╔╝███████╗███████╗╚█████╔╝
    ░╚════╝░╚══════╝╚══════╝░╚════╝░
''')

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


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

def extractText(parts, type):
    for part in parts:
        if part.get('mimeType') == 'text/plain':
            data = part[type].get("data")

            if data:
                byte_code = base64.urlsafe_b64decode(data)
                text = byte_code.decode("utf-8")
                return text
            
    for part in parts:
        if part.get('mimeType') == 'text/html':
            data = part['body'].get('data')
            if data:
                byte_code = base64.urlsafe_b64decode(data)
                html = byte_code.decode("utf-8")
                soup = BeautifulSoup(html, 'html.parser')
                return soup.get_text()
            
    return ''

def getMail(creds):

    mails = []

    try:
        service = build("gmail", "v1", credentials=creds)

        # TODO: Decide how many emails to fetch or what conditions they must satisfy
        results = service.users().messages().list(userId = "me", labelIds = ['INBOX'], maxResults = 20).execute()

        messages = results.get('messages', [])

        for message in messages:

            mail = {}

            msg = service.users().messages().get(userId = "me", id = message['id']).execute()
            email_data = msg['payload']['headers']

            for values in email_data:
                name = values['name']
                if name == 'From':
                    mail['from'] = values['value']

                elif name == 'Subject':
                    mail['subject'] = values['value']

            parts = msg['payload']['parts']

            body = extractText(parts, "body")

            mail['body'] = ' '.join(body.split())

            mails.append(mail)


        return mails   

    
    except HttpError as error:
        print(f"An error occurred: {error}")

def extractDates(mails):
        
    regexes = [r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', 
               r'\s\d{1,2}(?:th|st|nd|rd)?(?:[\s,]|(?:\sof\s))?(?:(?:[Jj]an(?:uary)?)|(?:[Ff]eb(?:ruary)?)|(?:[Mm]ar(?:ch)?)|(?:[Aa]pr(?:il)?)|(?:[Mm]ay)|(?:[Jj]un(?:e)?)|(?:[Jj]ul(?:y)?)|(?:[Aa]ug(?:ust)?)|(?:[Ss]ep(?:tember)?)|(?:[Oo]ct(?:ober)?)|(?:[Nn]ov(?:ember)?)|(?:[Dd]ec(?:ember)?)),?\s?(?:\d{4})?', 
               r'(?:(?:[Jj]an(?:uary)?)|(?:[Ff]eb(?:ruary)?)|(?:[Mm]ar(?:ch)?)|(?:[Aa]pr(?:il)?)|(?:[Mm]ay)|(?:[Jj]un(?:e)?)|(?:[Jj]ul(?:y)?)|(?:[Aa]ug(?:ust)?)|(?:[Ss]ep(?:tember)?)|(?:[Oo]ct(?:ober)?)|(?:[Nn]ov(?:ember)?)|(?:[Dd]ec(?:ember)?))\s\d{1,2},?\s?(?:\d{4})?(?:\s|\.)']

    for mail in mails:

        dates = []
            
        for regex in regexes:
            
            for result in re.findall(regex, mail['body']):
                dates.append(result)

        mail['dates'] = dates

# Created a main function for better structure
def main():
    creds = authenticate()

    if creds and creds.valid:

        print("[~] User authenticated!")
        print("[o] Getting mail...")

        mails = getMail(creds)

        if len(mails) > 0:
            print("[~] Pulled mail from Gmail API!")

        extractDates(mails)

        for mail in mails:
            print(mail['from'])
            print(mail['subject'])
            print(mail['body'])
            print(mail['dates'])
            print()
            print()
        
        

if __name__ == '__main__':
    main()