# CLEO - Smart Email & Calendar Assistant

CLEO is a command-line tool designed to streamline your inbox by reading your emails, extracting key event details, and automatically updating your Google Calendar. 

## ✅ Project Targets

- [x] **OAuth Authentication:**  
  - Secure, browser-based OAuth login for Gmail & Calendar.
  - Local token storage to avoid repeated logins.

- [x] **Email Fetching:**  
  - Fetching emails from Gmail using the Google API.

- [x] **Date Extraction:**  
  - handling various date formats (e.g., "Friday 7, 2025", "20 May 2024", "7/3/2024", "02/05/2025", and multi-date formats).

- [ ] **Event Title Extraction:**  
  - Capture event titles from email subjects and contextual clues in the body.

- [ ] **Location Extraction:**  
  - Detect internal room codes (e.g., "C7", "LG1") using custom regex or spaCy’s EntityRuler.

- [ ] **Additional NLP Integration:**  
  - Experiment with a small LLM (e.g., DistilBERT) to enhance extraction of nuanced details.

- [ ] **Calendar Syncing:**  
  - Automatically create and update Google Calendar events based on extracted email data.
  - Include a user confirmation step before syncing.

- [ ] **User Interface Enhancements:**  
  - Expand CLI commands for summarizing emails, listing upcoming events, and manual syncing.

- [ ] **Testing & Refinement:**  
  - Continue refining extraction functions using a broader set of test emails, especially focusing on internal college formats.

### Stay Organized, Effortlessly with CLEO! 