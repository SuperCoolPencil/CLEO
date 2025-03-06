import os.path
import base64
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
    
def getMail(creds):

    mails = []

    try:
        service = build("gmail", "v1", credentials=creds)

        # TODO: Decide how many emails to fetch or what conditions they must satisfy
        results = service.users().messages().list(userId = "me", labelIds = ['INBOX'], q = "newer_than:2d").execute()

        messages = results.get('messages', [])

        for message in messages:

            mail = {}

            msg = service.users().messages().get(userId = "me", id = message['id']).execute()
            email_data = msg['payload']['headers']

            for values in email_data:
                name = values['name']
                if name == 'From':
                    mail['from'] = values['value']

            parts = msg['payload']['parts']

            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    data = part['body'].get("data")

                    if data:
                        byte_code = base64.urlsafe_b64decode(data)
                        text = byte_code.decode("utf-8")
                        mail['body'] = text
                        text_found = True
            
            if not text_found:
                for part in parts:
                    if part.get('mimeType') == 'text/html':
                        data = part['body'].get('data')
                        if data:
                            byte_code = base64.urlsafe_b64decode(data)
                            html = byte_code.decode("utf-8")
                            soup = BeautifulSoup(html, 'html.parser')
                            mail['body'] = soup.get_text()
                            break
            
            mails.append(mail)


        return mails   

    
    except HttpError as error:
        print(f"An error occurred: {error}")

creds = authenticate()

if creds and creds.valid:
   mails = getMail(creds)

   for mail in mails:
       print(mail['from'])
       print(mail['body'])