import os.path
import base64
from time import sleep
from bs4 import BeautifulSoup
import dateparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
from datetime import datetime, time
import sys
from termcolor import colored
import os
from google import genai
from google.genai import types
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
    "https://www.googleapis.com/auth/gmail.modify",
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

def getEmailBody(parts, type):

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
            data = part['text'].get('data')
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
        try:
            results = service.users().messages().list(userId = "me", labelIds = ['INBOX'], maxResults = maxResults, q='is:unread newer_than:2d').execute()
        except Exception as e:
            print(f"[!] Error occurred while fetching mail: {e}")
            return []

        messages = results.get('messages', [])

        for message in messages:

            mail = dict()

            msg = service.users().messages().get(userId = "me", id = message['id']).execute()
            headers = msg['payload']['headers']

            # extract from, subject, datetime from headers
            for values in headers:
                name = values['name']

                if name == 'From':
                    mail['from'] = values['value']

                elif name == 'Subject':
                    mail['subject'] = values['value']

                elif name == "Date":
                    date_format = "%a, %d %b %Y %H:%M:%S %z"
                    mail['when'] = datetime.strptime(values['value'], date_format)
                
            if 'parts' in msg['payload']:

                parts = msg['payload']['parts']

                body = getEmailBody(parts, "body").lower()

                # Doing it this way so I dont have to deal with escape characters
                mail['body'] = body

                mails.append(mail)
                
                # Mark email as read by removing the UNREAD label
                service.users().messages().modify(
                    userId="me",
                    id=message['id'],
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()

        return mails   

    
    except HttpError as error:
        print(f"An error occurred: {error}")

def parseDateRange(text: str, context_time):

    # Parses sequential multidates such as 14th - 16th august 2025 and 8th to 30th August

    regexes = [
        # Pattern for 14th - 16th August 2023 or 14-16 August 2023
        r'\b(\d{1,2})(?:th|st|nd|rd)?\s*(?:to|-)\s*(\d{1,2})(?:th|st|nd|rd)?(?:\s+of)?\s+((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)\b',
        
        # Pattern for August 14-16, 2023
        r'\b((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))\s+(\d{1,2})(?:th|st|nd|rd)?\s*(?:to|-)\s*(\d{1,2})(?:th|st|nd|rd)?(?:,?\s+(\d{2,4})?)?\b',
        
        # Pattern for from 14th August to 16th August 2023
        r'\bfrom\s+(\d{1,2})(?:th|st|nd|rd)?\s+((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))\s+to\s+(\d{1,2})(?:th|st|nd|rd)?\s+((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)\b'
    ]   

    for i, regex in enumerate(regexes):

        match = re.search(regex, text)

        if match:
            groups = match.groups()

            if i == 0:
                day1, day2, month_year = groups
                date1_str = f"{day1} {month_year}"
                date2_str = f"{day2} {month_year}"

            elif i == 1:
                month, day1, day2, year = groups
                year = year or ''
                date1_str = f"{day1} {month} {year}"
                date2_str = f"{day2} {month} {year}"
            
            elif i == 2:
                day1, month1, day2, month2_year = groups
                date1_str = f"{day1} {month1}"
                date2_str = f"{day2} {month2_year}"

            date1 = datetime.date(dtparse(date1_str, context_time))
            date2 = datetime.date(dtparse(date2_str, context_time))

            return [date1, date2]
    
    return None

def parseConnectedDates(text: str, context_time):
    """Parse date patterns like "8th & 9th Jan" or "8th and 9th January"."""
    
    # Patterns for dates connected with &, and, or commas
    connected_dates_regex = [
        # Pattern for "8th & 9th Jan" or "8th and 9th January"
        r'\b(\d{1,2})(?:th|st|nd|rd)?\s*(?:&|and)\s*(\d{1,2})(?:th|st|nd|rd)?\s+((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)\b',
        
        # Pattern for "Jan 8th & 9th" or "January 8th and 9th"
        r'\b((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))\s+(\d{1,2})(?:th|st|nd|rd)?\s*(?:&|and)\s*(\d{1,2})(?:th|st|nd|rd)?(?:,?\s+(\d{2,4})?)?\b',
        
        # Pattern for comma-separated dates like "8th, 9th, and 10th Jan"
        r'\b(\d{1,2})(?:th|st|nd|rd)?(?:\s*,\s*(\d{1,2})(?:th|st|nd|rd)?)+(?:\s*(?:&|and)\s*(\d{1,2})(?:th|st|nd|rd)?)?\s+((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)\b'
    ]
    
    results = []
    
    for i, regex in enumerate(connected_dates_regex):
        matches = re.finditer(regex, text, re.IGNORECASE)
        
        for match in matches:
            groups = match.groups()
            
            if i == 0:  # 8th & 9th Jan
                day1, day2, month_year = groups
                date1_str = f"{day1} {month_year}"
                date2_str = f"{day2} {month_year}"
                
                date1 = datetime.date(dtparse(date1_str, context_time))
                date2 = datetime.date(dtparse(date2_str, context_time))
                
                if date1 and date2:
                    results.extend([date1, date2])
                    
            elif i == 1:  # Jan 8th & 9th
                month, day1, day2, year = groups
                year = year or ''
                date1_str = f"{day1} {month} {year}"
                date2_str = f"{day2} {month} {year}"
                
                date1 = datetime.date(dtparse(date1_str, context_time))
                date2 = datetime.date(dtparse(date2_str, context_time))
                
                if date1 and date2:
                    results.extend([date1, date2])
                    
            elif i == 2:  # 8th, 9th, and 10th Jan
                # This is more complex as we have variable number of days
                days = [g for g in groups[:-1] if g is not None]
                month_year = groups[-1]
                
                for day in days:
                    date_str = f"{day} {month_year}"
                    date_obj = datetime.date(dtparse(date_str, context_time))
                    if date_obj:
                        results.append(date_obj)
    
    # Remove duplicates and sort
    if results:
        return sorted(list(set(results)))

def parseExplicitDate(text: str, context_time):
    # Extract and parse explicit date strings from a sentence using regex
    # returns a list of date objects 

    explicit_date_regexes = [
        # ISO format: 2023-08-14, 14/08/2023, 14.08.2023
        r'\b\d{1,4}[-./]\d{1,2}[-./]\d{1,4}\b',
        
        # Format: 14th August 2023, August 14th 2023
        r'\b\d{1,2}(?:th|st|nd|rd)?(?:\s+of)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{2,4}\b',
        r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:th|st|nd|rd)?(?:,?\s+\d{2,4})?\b',
        
        # Month and day without year: 14th August, August 14th
        r'\b\d{1,2}(?:th|st|nd|rd)?(?:\s+of)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b',
        r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:th|st|nd|rd)?\b'
    ]

    results = []

    parsed_results = []

    for regex in explicit_date_regexes:
        results.extend(re.findall(regex, text))

    for result in results:
        # remove any whitespace and surrounding characters
        result = result.strip()
        result = datetime.date(dtparse(result, context_time))
        if result:
            parsed_results.append(result)

    # remove duplicates
    parsed_results = list(set(parsed_results))

    return parsed_results

def parseRelativeDates(text: str, context_time: datetime):
    # Isolate and parse relative date expressions (like “today", “next Monday”) 
    # using regex and a date parsing library with a relative base.
    # returns a list of date objects 

    relative_date_regex = r'\b(?:(?:from|on)\s+)?(today|tomorrow|yesterday|this\s+(?:week|weekend)|(?:(?:coming|next)\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|next\s+(?:week|weekend))\b'
    
    matches = re.finditer(relative_date_regex, text, re.IGNORECASE)
    
    parsed_results = []
    
    for match in matches:
        result = match.group(0)
        
        if not result:
            continue

        parsed_date = dtparse(result, context_time)
        
        if parsed_date:
            date = datetime.date(parsed_date)

            parsed_results.append(date)
    
    return parsed_results

def parseTime(text: str):
    # Extract and parse explicit date strings from a sentence using regex
    # returns a list of time objects 

    time_regexes = [
        # Standard time: 9:00 am, 9.00 am, 9am
        r'\b(\d{1,2})(?::|\.)(\d{2})?\s*(am|pm)\b',
        r'\b(\d{1,2})\s*(am|pm)\b',
        
        # 24-hour time: 14:00, 14.00
        r'\b(\d{1,2})(?::|\.)(\d{2})(?!\s*(?:am|pm))\b',
        
        # Time ranges: 9-11am, 9:00-11:00am, 9am-11am
        r'\b(\d{1,2})(?::(\d{2}))?\s*(?:-|to)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b',
        r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*(?:-|to)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b'
    ]

    results = []

    for i, pattern in enumerate(time_regexes):
        matches = re.finditer(pattern, text)
        for match in matches:

            groups = match.groups()
    
            if i == 0:
                
                hour   = int(groups[0])
                minute = int(groups[1] or 0)
                period = groups[2]
                
                if period == 'pm' and hour < 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                
                results.append(time(hour, minute))

            elif i == 1:
                
                hour = int(groups[0])
                period = groups[1]

                if groups[0] == '00' or hour > 12:
                    continue
                
                if period == 'pm' and hour < 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0

                results.append(time(hour, 0))
                
            elif i == 2:  

                # 24hr time
                hour = int(groups[0])
                minute = int(groups[1] or 0)

                if hour > 24 or minute > 60:
                    continue

                results.append(time(hour, minute))
            
            elif i == 3:  # Time range (same period)
                
                start_hour = int(groups[0])
                start_minute = int(groups[1] or 0)
                end_hour = int(groups[2])
                end_minute = int(groups[3] or 0)
                period = groups[4]
                
                if period == 'pm':
                    if start_hour < 12:
                        start_hour += 12
                    if end_hour < 12:
                        end_hour += 12
                elif period == 'am':
                    if start_hour == 12:
                        start_hour = 0
                    if end_hour == 12:
                        end_hour = 0
                
                return [time(start_hour, start_minute), time(end_hour, end_minute)]
            
            elif i == 4:  # Time range (different periods)
                start_hour   = int(groups[0])
                start_minute = int(groups[1] or 0)
                start_period = groups[2]
                end_hour     = int(groups[3])
                end_minute   = int(groups[4] or 0)
                end_period   = groups[5]
                
                if start_period == 'pm' and start_hour < 12:
                    start_hour += 12
                elif start_period == 'am' and start_hour == 12:
                    start_hour = 0
                    
                if end_period == 'pm' and end_hour < 12:
                    end_hour += 12
                elif end_period == 'am' and end_hour == 12:
                    end_hour = 0
                
                return [time(start_hour, start_minute), time(end_hour, end_minute)]
    
    # remove duplicates
    unique_results = list(set(results))
    return unique_results

def fixDateTime(result, context_time):

    today = context_time.date()

    if result['startdate'] and not result['enddate']:
        result['enddate'] = result['startdate']
    
    # If only enddate use today as startdate
    if not result['startdate'] and result['enddate']:
        result['startdate'] = today
    
    # If dates are in wrong order, swap them
    if result['startdate'] and result['enddate'] and result['startdate'] > result['enddate']:
        result['startdate'], result['enddate'] = result['enddate'], result['startdate']
    
    # Not sure about this
    # If only one time is found early in the day, assume starttime
    # and add a default duration (e.g., 1 hour)
    if result['starttime'] and not result['endtime']:
        hour = result['starttime'].hour
        minute = result['starttime'].minute
        # If time is before 1pm, assume it's a start time and add 1 hour
        if hour < 13:
            result['endtime'] = time((hour + 1) % 24, minute)

    # If times are in wrong order, swap them
    if result['starttime'] and result['endtime']:
        start_minutes = result['starttime'].hour * 60 + result['starttime'].minute
        end_minutes = result['endtime'].hour * 60 + result['endtime'].minute
        
        # Only swap if end is earlier and not likely a next-day event
        if end_minutes < start_minutes and (start_minutes - end_minutes) < 720:
            result['starttime'], result['endtime'] = result['endtime'], result['starttime']
    
    if result['starttime'] and not result['endtime']:
        result['endtime'] = result['starttime']
            
    return None
def extractDateTime(mails):
    for mail in mails:
        body = mail.get('body', '').lower()
        subject = mail.get('subject', '').lower()
        context_time = mail.get('when', datetime.now())

        full_text = f"{subject} {body}".lower()

        datetime_info = {
            'startdate': None,
            'enddate': None,
            'starttime': None,
            'endtime': None,
            'daily': None
        }

        date_range = parseDateRange(full_text, context_time)

        if date_range:
            datetime_info['startdate'] = date_range[0]
            datetime_info['enddate'] = date_range[1]
            datetime_info['daily'] = True
        else:
            # Try to parse connected dates (with &, and, or commas)
            connected_dates = parseConnectedDates(full_text, context_time)
            
            if connected_dates:
                datetime_info['startdate'] = connected_dates[0]
                datetime_info['enddate'] = connected_dates[-1]
                # If we have multiple specific dates, they might not be daily events
                datetime_info['daily'] = False
                # Store all dates for multi-day handling later
                datetime_info['all_dates'] = connected_dates
            else:
                # Try to find individual dates
                dates = parseExplicitDate(full_text, context_time)
                
                if not dates:
                    # Try relative dates
                    dates = parseRelativeDates(full_text, context_time)
                
                if dates:
                    dates.sort()
                    datetime_info['startdate'] = dates[0]
                    datetime_info['enddate'] = dates[-1]
        
        times = parseTime(full_text)
        if times:
            times.sort()
            datetime_info['starttime'] = times[0]
            datetime_info['endtime'] = times[-1] if len(times) > 1 else None

        fixDateTime(datetime_info, context_time)

        for key, value in datetime_info.items():
            mail[key] = value

def extractLocation(text):

    location_regex = r'\b(?:in|venue:?|at|location:?|where:?)(?:\s+the)?\s+([\w\s,()\-]+?)(?=\r|\n|$|-|\.)'

    results = re.findall(location_regex, text)

    if results:
        longest_match = sorted(results, key=len)[-1]
        return longest_match.strip()

    else:
        return ''

def generateTitleLocation(mail):

    if os.path.exists("gemini-api.key"):
        with open("gemini-api.key", 'r') as f:
            api_key = f.read()
    else:
        return None

    client = genai.Client(
        api_key = api_key
    )

    model = "gemini-2.0-flash-lite"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=f"""Extract event details from the following text. Your task is to:
                                                Generate the event title (Be as specific as possible).
                                                Determine the event location.

                                                Respond with only one line in the following format:

                                                [title]|[location]

                                                Where:
                                                    [title]: The event's name from the text.
                                                    [location]: The location where the event takes place.

                                                {mail}
                                            """),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=0.5,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        response_mime_type="text/plain",
    )

    title = ""

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
        ):
        
        title += chunk.text

    return title.strip()

def extractTitleLocation(mails):
    for mail in tqdm(mails):

        if not (mail['startdate'] or mail['starttime']):
            continue

        try:
            mail['title'], mail['location'] = generateTitleLocation(mail['body']).split('|')
        except:
            print(colored(f"[!] Could not generate title and location for {mail['subject']}", 'light_red'))
            mail['title'] = mail['subject']
            mail['location'] = extractLocation(mail['body'])

def insertEvent(service, event, conflict_resolution = 'ask_user', tz = datetime.now().astimezone().tzinfo):

    if event['start'].get('dateTime')   :
        events_result = service.events().list(
                        calendarId='primary',
                        timeMin=event['start']['dateTime'].astimezone(tz).isoformat(),
                        timeMax=event['end']['dateTime'].astimezone(tz).isoformat(),
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
    elif event['start'].get('date'):
        events_result = service.events().list(
                        calendarId='primary',
                        timeMin=datetime.combine(event['start']['date'], time.min).astimezone(tz).isoformat(),
                        timeMax=datetime.combine(event['end']['date'], time.max).astimezone(tz).isoformat(),
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()

    conflicts = events_result.get('items', [])

    if conflicts:
        print(colored("[!] Conflicting events found:", 'light_red'))

        for conflict in conflicts:
            
            summary = conflict.get('summary', 'No Title')
            start = conflict['start']
            end = conflict['end']

            print(f"- {summary}: starts at {start} and ends at {end}")

        while True:

            if conflict_resolution == "1":
                print(colored("[=] Keeping old events. New event will not be added.", 'light_green'))
                return None
            
            elif conflict_resolution == "2":
                # Delete conflicting events.
                for conflict in conflicts:
                    event_id = conflict.get('id')
                    service.events().delete(calendarId='primary', eventId=event_id).execute()
                        
                print(colored("[-] Old conflicting events deleted. Proceeding to add new event.", 'light_green'))
                break
            
            elif conflict_resolution == "3":
                print(colored("[+] Adding new event alongside existing conflicting events.", 'light_green'))
                break
            
            else:
                conflict_resolution = input("1: Keep old\n2: Keep new\n3: Keep both\nOption: ").strip()
    
    if event['start'].get('dateTime'):
        try:
            event['start']['dateTime'] = event['start']['dateTime'].isoformat()
            event['end']['dateTime'] = event['end']['dateTime'].isoformat()
        except:
            event['start']['dateTime'] = event['start']['dateTime']
            event['end']['dateTime'] = event['end']['dateTime']
    else:
        try:
            event['start']['date'] = event['start']['date'].isoformat()
            event['end']['date'] = event['end']['date'].isoformat()
        except:
            # SOMETIMES THESE DECIDE TO IDENTIFY AS A STRING... I DO NOT KNOW WHY!!!!!!!!!!!!
            event['start']['date'] = event['start']['date']
            event['start']['date'] = event['start']['date']

    event = service.events().insert(calendarId='primary', body=event).execute()

    return event.get("htmlLink")

def createEvent(mail, date = None, local_zone = 'Asia/Kolkata'):

    event = {
        'summary': mail['title'],
        'description': mail['subject'],
        'location': mail['location']
    }

    if date is not None:
        event['start'] = {}
        event['end'] = {}

        if mail['starttime'] is None:
            event['start']['date'] = date
            event['start']['timeZone'] = local_zone
            event['end']['date'] = date
            event['end']['timeZone'] = local_zone

        else:
            event['start']['dateTime'] = datetime.combine(date, event['starttime'])
            event['end']['date']       = datetime.combine(date, event['endtime'])
            event['start']['timeZone'] = local_zone
            event['end']['timeZone'] = local_zone

    else:
        if mail['starttime'] is None:
            event['start'] = {
                'date': mail['startdate'],
                'timeZone': local_zone
            }
            event['end'] = {
                'date': mail['enddate'],
                'timeZone': local_zone
            }
        else:
            event['start'] = {
                'dateTime': datetime.combine(mail['startdate'], mail['starttime']),
                'timeZone': local_zone
            }
            event['end'] = {
                'dateTime': datetime.combine(mail['enddate'], mail['endtime']),
                'timeZone': local_zone
            }

    # when creating an event for a date range,
    # we dont want the event to span from say Saturday 8 am to Sunday 10am
    # we want it from Saturday 8am to 10am and then Sunday again from 8am to 10am
    # this is where the recurrence flag comes in

    if mail['daily']:
        if mail['starttime'] is None:
            event['start'] = {
                'date': mail['startdate'],
                'timeZone': local_zone
            }
            event['end'] = event['start']
        else:
            event['end'] = {
                'dateTime': datetime.combine(mail['startdate'], mail['endtime']),
                'timeZone': local_zone
            }

        no_of_days = (mail['enddate'] - mail['startdate']).days
        event['recurrence'] = [
            f'RRULE:FREQ=DAILY;COUNT={no_of_days}'  
        ]
    
    return event

def addEvent(creds, mail, conflict_resolution = 'ask_user'):

    try:
        service = build("calendar", "v3", credentials = creds)
        event_links = []

        if mail.get('all_dates') and len(mail.get('all_dates', [])) > 1:

            for date in mail['all_dates']:

                event = createEvent(mail, date)
                event_links.append(insertEvent(service, event, conflict_resolution))
        else:
            event = createEvent(mail)
            event_links.append(insertEvent(service, event, conflict_resolution))
        
        return event_links
            
    except HttpError as error:
        print(f"An error occurred: {error}")

def wait(seconds):
    print(f'[o] Waiting for {seconds} seconds...')
    sleep(seconds)

def main():
    
    maxResults = sys.argv[1] if len(sys.argv) > 1 else 5
    auto = (sys.argv[2] == '--auto' or sys.argv[2] == '-a') if len(sys.argv) > 2 else False
    sec = sys.argv[3] if len(sys.argv) > 3 else 600 # every 10 minutes

    creds = authenticate()

    if creds and creds.valid:

        print("[~] User authenticated!")
        print("[o] Getting mail...")

        mails = getMail(creds, maxResults)

        if not mails or len(mails) == 0:
            print("[!] No mails fit current criteria")
            if auto:
                wait(sec)
                main()
        
        print("[~] Pulled mail from Gmail API!")

        print("[~] Extracting date and time...")
        extractDateTime(mails)

        print("[~] Generating titles and location...")
        extractTitleLocation(mails)

        addedEvents = []
        for mail in mails:

            if mail['startdate'] or mail['starttime']:

                print("-"*80)

                for key, value in mail.items():
                    print("{}: {}".format(colored(key, 'cyan'), colored(value, 'yellow')))

                if not auto:
                    if input("Add to calendar? [Y/n]: ") == 'n':
                        continue
                if mail["startdate"] is None:
                    if not auto:
                        mail["startdate"] = datetime.date(dtparse(input("Enter start-date: "), mail['when']))
                        mail['enddate']   = datetime.date(dtparse(input("Enter end-date: ")  , mail['when']))
                    else:
                        continue

                    # Check and ask for starttime if None
                if mail["starttime"] is None:
                    if auto:
                        print("Assuming a all day event")
                        starttime = '-1'
                    else:
                        print("Enter -1 for a all day event")
                        starttime = input("Enter starttime: ")

                    if starttime == '-1':
                        pass
                    else:
                        mail["starttime"] = datetime.time(dtparse(starttime                , mail['when']))
                        mail['endtime']   = datetime.time(dtparse(input("Enter end-time: "), mail['when']))

                if auto:
                    # Keep both events
                    conflict_resolution = '3'
                else:
                    conflict_resolution = 'ask_user'

                addedEvent = addEvent(creds, mail, conflict_resolution = conflict_resolution)

                addedEvents.extend(addedEvent)
                
                if addedEvent:
                    print(colored(f"[+] Added \"{mail['title']}\" to your calendar!", 'light_green'))
            else:
                print(colored(f"[=] Skipped \"{mail['subject']}\"", 'light_green'))
    
        if auto:
            wait(sec)
            main()

if __name__ == '__main__':
    main()