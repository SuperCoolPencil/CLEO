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
from datetime import datetime, timedelta
import sys
from termcolor import colored
from tqdm import tqdm
import tzlocal

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

def dtparse(str: str, context_time = None):

    settings = {
        'DATE_ORDER': 'DMY'
    }

    if context_time:
        settings['RELATIVE_BASE'] = context_time

    return dateparser.parse(str, settings = settings)

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
                    date_format = "%a, %d %b %Y %H:%M:%S %z"
                    mail['when'] = datetime.strptime(values['value'], date_format)

            parts = msg['payload']['parts']

            body = getPart(parts, "body").lower()

            # Doing it this way so I dont have to deal with escape characters
            mail['body'] = body

            mails.append(mail)


        return mails   

    
    except HttpError as error:
        print(f"An error occurred: {error}")

def parseExplicitDate(body: str):
    # Extract and parse explicit date strings from a sentence using regex
    # returns a list of date objects 

    explicit_date_regexes = [
        r'\b\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}\b', 
        r'\b\d{1,2}(?:th|st|nd|rd)?(?:[\s,]+|(?:\s+of\s+))?(?:(?:jan(?:uary)?)|(?:feb(?:ruary)?)|(?:mar(?:ch)?)|(?:apr(?:il)?)|may|(?:jun(?:e)?)|(?:jul(?:y)?)|(?:aug(?:ust)?)|(?:sep(?:tember)?)|(?:oct(?:ober)?)|(?:nov(?:ember)?)|(?:dec(?:ember)?))\b,?\s*(?:\d{4})?\b', 
        r'\b(?:(?:jan(?:uary)?)|(?:feb(?:ruary)?)|(?:mar(?:ch)?)|(?:apr(?:il)?)|may|(?:jun(?:e)?)|(?:jul(?:y)?)|(?:aug(?:ust)?)|(?:sep(?:tember)?)|(?:oct(?:ober)?)|(?:nov(?:ember)?)|(?:dec(?:ember)?))\s+\d{1,2},?\s*(?:\d{4})?(?:(?:\s)|\.)\b'
    ]

    results = []

    parsed_results = []

    for regex in explicit_date_regexes:
        results.extend(re.findall(regex, body))

    for result in results:
        # remove any whitespace and surrounding characters
        result = result.strip()
        result = datetime.date(dtparse(result))
        if result:
            parsed_results.append(result)

    return parsed_results

def parseRelativeDates(body: str, context_time: datetime):
    # Isolate and parse relative date expressions (like “today", “next Monday”) 
    # using regex and a date parsing library with a relative base.
    # returns a list of date objects 

    relative_date_regex = r'\b(?:(?:today|tomorr?(?:ow|morow)|yesterday)|(?:(?:next|last|this|on)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)))\b'
    results = re.findall(relative_date_regex, body)

    parsed_results = []

    for result in results:
        # remove any whitespace and surrounding characters
        result = result.strip()
        if result:
            continue
        result = datetime.date(dtparse(result, context_time))
        if result:
            parsed_results.append(result)
    
    return parsed_results

def parseTime(body: str):
    # Extract and parse explicit date strings from a sentence using regex
    # returns a list of time objects 

    time_regex = r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b'

    results = re.findall(time_regex, body)

    parsed_results = []

    for i, result in enumerate(results):
        # remove any whitespace and surrounding characters
        result = result.strip()

        try:
            result = dateparser.parse(result)
            result = datetime.time(result)

            parsed_results.append(result)
        except:
            pass

    return parsed_results

def extractDateTime(mails):

    for mail in mails:

        context_time = mail['when']
        body = mail['body']
        subject = mail['subject']

        dates = parseExplicitDate(body + " " + subject.lower()) + parseRelativeDates(body + " " + subject.lower(), context_time)
        times = parseTime(body)

        # Remove any duplicate entries
        dates = list(set(dates))
        times = list(set(times))

        dates.sort()
        times.sort()

        if dates:
            mail['startdate'] = dates[0]
            mail['enddate'] = dates[-1]
        else:
            mail['startdate'] = None
            mail['enddate'] = None

        if times:
            mail['starttime'] = times[0]
            mail['endtime'] = times[-1]
        else:
            mail['starttime'] = None
            mail['endtime'] = None

def extractLocation(mails):

    location_regex = r'\b(?:in|venue:?|at|location:?|where:?)(?:\s+the)?\s+([\w\s,()\-]+?)(?=\r|\n|$|-|\.)'
    
    for mail in mails:

        results = re.findall(location_regex, mail['body'])

        if results:
            longest_match = sorted(results, key=len)[-1]
            mail['location'] = longest_match.strip()

        else:
            mail['location'] = None

def addEvent(creds, mail, conflict_resolution = "default"):
    try:
        tz = datetime.now().astimezone().tzinfo

        service = build("calendar", "v3", credentials=creds)
        
        # Determine event start and end as datetime objects for conflict checking.
        if mail['starttime'] is None:
            # For all-day events, use the full day.
            event_start = datetime.combine(mail['startdate'], datetime.min.time()).astimezone(tz)
            event_end   = datetime.combine(mail['enddate'], datetime.max.time()).astimezone(tz)
        else:
            event_start = datetime.combine(mail['startdate'], mail['starttime']).astimezone(tz)
            event_end   = datetime.combine(mail['enddate'], mail['endtime']).astimezone(tz)
        
        # Check for conflicting events in the given time range.
        events_result = service.events().list(
            calendarId = 'primary',
            timeMin = event_start.isoformat(),
            timeMax = event_end.isoformat(),
            singleEvents = True,
            orderBy = 'startTime'
        ).execute()

        conflicts = events_result.get('items', [])      
        
        if conflicts:
            print(colored("[!] Conflicting events found:", 'light_red'))

            for conflict in conflicts:

                summary = conflict.get('summary', 'No Title')
                start = conflict['start']
                end = conflict['end']

                print(f"- {summary}: starts at {start} and ends at {end}")
            
            if conflict_resolution == "default":
                return 'conflict_action_needed'
            
            elif conflict_resolution == "keep_old":
                print("Keeping old events. New event will not be added.")
                return None
            
            elif conflict_resolution == "keep_new":
                # Delete conflicting events.
                for conflict in conflicts:
                    event_id = conflict.get('id')
                    service.events().delete(calendarId='primary', eventId=event_id).execute()
            
                print("Old conflicting events deleted. Proceeding to add new event.")

            elif conflict_resolution == "both":
                print("Adding new event alongside existing conflicting events.")

            else:
                print(f"Invalid conflict resolution option: {conflict_resolution}. Aborting.")
                return None
        
        local_zone = 'Asia/Kolkata'

        # Build event body based on whether it's an all-day or timed event.
        if mail['starttime'] is None:
            event_body = {
                'summary': mail['title'],
                'description': mail['subject'],
                'start': {
                    'date': mail['startdate'].isoformat(),
                    'timeZone': local_zone
                },
                'end': {
                    'date': mail['enddate'].isoformat(),
                    'timeZone': local_zone
                },
                'location': mail['location']
            }
        else:
            event_body = {
                'summary': mail['title'],
                'description': mail['subject'],
                'start': {
                    'dateTime': event_start.isoformat(),
                    'timeZone': local_zone
                },
                'end': {
                    'dateTime': event_end.isoformat(),
                    'timeZone': local_zone
                },
                'location': mail['location']
            }
        
        # Insert the new event.
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        return event.get('htmlLink')
    
    except HttpError as error:
        print(f"An error occurred: {error}")

def main():
    
    maxResults = sys.argv[1] if len(sys.argv) > 1 else 5

    creds = authenticate()

    if creds and creds.valid:

        print("[-] User authenticated!")
        print("[o] Getting mail...")

        mails = getMail(creds, maxResults)

        if len(mails) == 0:
            print("[!] No mails fit current criteria")
            return
        
        print("[~] Pulled mail from Gmail API!")

        print("[-] Extracting date and time...")
        extractDateTime(mails)

        print("[~] Extracting location...")
        extractLocation(mails)

        addedEvents = []
        for mail in mails:

            if mail['startdate'] or mail['starttime']:

                print("-"*80)

                for key, value in mail.items():
                    if value:
                        print("{}: {}".format(colored(key, 'cyan'), colored(value, 'yellow')))

                if input("Add to calendar? [Y/n]: ") == 'n':
                    continue

                # TODO: Extract event names
                mail['title'] =    input("Enter Event Name: ")

                if mail['location'] is None: 
                    mail['location'] = input("Enter Event Location: ")

                # Check and ask for startdate if None
                if mail["startdate"] is None:
                    mail["startdate"] = datetime.date(dtparse(input("Enter start-date: "), mail['when']))
                    mail['enddate']   = datetime.date(dtparse(input("Enter end-date: ")  , mail['when']))

                # Check and ask for starttime if None
                if mail["starttime"] is None:
                    print("-1 for a all day event")
                    starttime = input("Enter start-time: ").strip()
                    if starttime == '-1':
                        pass
                    else:
                        mail["starttime"] = datetime.time(dtparse(starttime, mail['when']))
                        mail['endtime']   = datetime.time(dtparse(input("Enter end-time: "), mail['when']))

                addedEvent = addEvent(creds, mail)

                while addedEvent == 'conflict_action_needed':
                    match input("1: Keep old\n2: Keep new\n3: Keep both\nOption: ").strip():
                        case '1':
                            addedEvent = addEvent(creds, mail, 'keep_old')
                        case '2':
                            addedEvent = addEvent(creds, mail, 'keep_new')
                        case '3':
                            addedEvent = addEvent(creds, mail, 'keep_both')

                addedEvents.append(addedEvent)

        print("Added the following events: ")
        for event in addedEvents:
            print(event)

if __name__ == '__main__':
    main()