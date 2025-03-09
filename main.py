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
from datetime import datetime, timedelta, time
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
        'DATE_ORDER': 'DMY',
        'PREFER_DATES_FROM': 'future'
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

        # TODO: Decide how many emails to fetch or what conditions they must satisfy
        results = service.users().messages().list(userId = "me", labelIds = ['INBOX'], maxResults = maxResults).execute()

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

            parts = msg['payload']['parts']

            body = getEmailBody(parts, "body").lower()

            # Doing it this way so I dont have to deal with escape characters
            mail['body'] = body

            mails.append(mail)


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

    relative_date_regex = r'\b(?:today|tomorr?ow|yesterday|this (?:coming )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|next (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|(?:this|coming|next) week(?:end)?)\b'
    results = re.findall(relative_date_regex, text)

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
    
    # TODO
    # Not sure about this
    # If only one time is found early in the day, assume starttime
    # and add a default duration (e.g., 1 hour)
    # if result['starttime'] and not result['endtime']:
    #    hour = result['starttime'].hour
    #    minute = result['starttime'].minute
    #    # If time is before 1pm, assume it's a start time and add 1 hour
    #    if hour < 13:
    #        result['endtime'] = time((hour + 1) % 24, minute)

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
                # Store all dates for potential multi-day handling later
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
        
        # Check if we have multiple specific dates (from connected dates)
        if mail.get('all_dates') and len(mail.get('all_dates', [])) > 1:
            # For multiple non-consecutive dates, create separate events
            events_links = []
            
            for date in mail['all_dates']:
                event_copy = mail.copy()
                event_copy['startdate'] = date
                event_copy['enddate'] = date
                event_copy['daily'] = False
                
                # Create individual event
                if mail['starttime'] is None:
                    # For all-day events
                    event_start = datetime.combine(date, datetime.min.time()).astimezone(tz)
                    event_end = datetime.combine(date, datetime.max.time()).astimezone(tz)
                else:
                    event_start = datetime.combine(date, mail['starttime']).astimezone(tz)
                    event_end = datetime.combine(date, mail['endtime']).astimezone(tz)
                
                # Check conflicts for this specific date
                events_result = service.events().list(
                    calendarId='primary',
                    timeMin=event_start.isoformat(),
                    timeMax=event_end.isoformat(),
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                conflicts = events_result.get('items', [])
                
                # Handle conflicts for this specific date
                if conflicts:
                    # Handle conflicts as before...
                    # (conflict resolution code)
                    pass
                
                # Create the event for this date
                local_zone = 'Asia/Kolkata'
                
                event_body = {
                    'summary': mail['title'],
                    'description': mail['subject'],
                    'location': mail['location']
                }
                
                if mail['starttime'] is None:
                    event_body['start'] = {
                        'date': date.isoformat(),
                        'timeZone': local_zone
                    }
                    event_body['end'] = {
                        'date': date.isoformat(),
                        'timeZone': local_zone
                    }
                else:
                    event_body['start'] = {
                        'dateTime': event_start.isoformat(),
                        'timeZone': local_zone
                    }
                    event_body['end'] = {
                        'dateTime': event_end.isoformat(),
                        'timeZone': local_zone
                    }
                
                # Insert the event
                event = service.events().insert(calendarId='primary', body=event_body).execute()
                events_links.append(event.get('htmlLink'))
            
            return events_links
        
    except HttpError as error:
        print(f"An error occurred: {error}")

def main():
    
    maxResults = sys.argv[1] if len(sys.argv) > 1 else 5

    creds = authenticate()

    if creds and creds.valid:

        print("[~] User authenticated!")
        print("[o] Getting mail...")

        mails = getMail(creds, maxResults)

        if len(mails) == 0:
            print("[!] No mails fit current criteria")
            return
        
        print("[~] Pulled mail from Gmail API!")

        print("[~] Extracting date and time...")
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
                        mail["starttime"] = datetime.time(dtparse(starttime                , mail['when']))
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

                if addedEvent:
                    print(colored(f"[+] Added \"{mail['title']}\" to your calendar!", 'green'))
            else:
                print(colored(f"[=] Skipped \"{mail['subject']}\"", 'green'))

if __name__ == '__main__':
    main()