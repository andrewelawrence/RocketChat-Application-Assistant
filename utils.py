# utils.py
# TODO: see upload() & extract()

import os, re, time, hashlib, boto3, requests
from config import get_logger
from llmproxy import retrieve, pdf_upload, text_upload
from flask import jsonify, session
from urlextract import URLExtract
from requests_html import HTMLSession
from bs4 import BeautifulSoup
from time import sleep

# setup logging
_LOGGER = get_logger(__name__)
_HASH = hashlib.sha1()

# auth AWS connection
_BOTO3_SESSION = boto3.Session(
   aws_access_key_id=os.environ.get("awsAccessKey"),
   aws_secret_access_key=os.environ.get("awsSecretKey"),
   region_name=os.environ.get("awsRegion")
)
_S3_BUCKET = _BOTO3_SESSION.client("s3")
_DYNAMO_DB = _BOTO3_SESSION.resource("dynamodb")
_TABLE = _DYNAMO_DB.Table(os.environ.get("dynamoTable"))

# restrict valid uids
_UID_RE = re.compile(r'^[A-Za-z0-9]+$')

def _gen_sid() -> str:
    """Generate a hashed SID from the epoch time (or any other scheme)."""
    _HASH.update(str(time.time()).encode('utf-8'))
    return _HASH.hexdigest()[:10]

def _new_sid() -> bool:
    try:
        sid = _gen_sid()
        _TABLE.put_item(
            Item={
                "uid": str("free"),
                "sid": str(sid),
                "created_at": str(time.time()).encode('utf-8')
            }
        )
        
        _LOGGER.info(f"Reserved new free SID <{sid}> for future assignment.")    
        return True
    except Exception as e:
        _LOGGER.error(f"Error creating overhead SID in DynamoDB: {e}", exc_info=True)
        return False
        
def _get_sid(uid: str, user: str = "UnknownName") -> tuple:
    """Determine if the UID is already tied to a SID. Otherwise, create a new SID."""
    sid = ""
    try:
        # Check if SID already exists in DynamoDB
        resp = _TABLE.get_item(Key={"uid": uid})
        if "Item" in resp:
            sid = resp["Item"]["sid"]
            _LOGGER.info(f"User <{uid}> has existing SID <{sid}>")
            # _new_sid() - generates a new sid even though the free sid should alr exist.s
            return (str(sid), False)

        # If not, the user is new and so we return True for second part of Tuple
        # Check if a "free" SID exists
        resp = _TABLE.get_item(Key={"uid": "free"})
        if "Item" in resp:
            sid = resp["Item"]["sid"]
            _TABLE.delete_item(Key={"uid": "free"})  # Remove old free SID
            _LOGGER.info(f"Assigned existing free SID <{sid}> to user <{uid}>")
        # If not, create a new SID and store it
        else:
            sid = _gen_sid()
            _LOGGER.info(f"No free SID found. Created new SID <{sid}> for user <{uid}>")

        # Store new SID for the user
        _new_sid()
        return (str(sid), True)
    
    except Exception as e:
        _LOGGER.error(f"Error accessing DynamoDB for SID: {e}", exc_info=True)
        return (str(""), False)


def _get_resume_editing(uid: str) -> bool:
    """
    Get the resume_editing variable from the table
    """

    try:
        resp = _TABLE.get_item(Key={"uid": uid})
        if "Item" in resp:
            resume_editing = resp["Item"]["resume_editing"]
            _LOGGER.info(f"User <{uid}> has resume_editing: {resume_editing}")

            return bool(resume_editing)
        else:
            _LOGGER.info(f"User <uid> has no resume_editing item. Set to default (None)")
            return None

    except Exception as e:
        _LOGGER.error(f"Error accessing DynamoDB for SID: {e}", exc_info=True)
        return None


def _validate(vValue, vName : str = "unknown", vType : type = str, 
              vValueDefault = None,
              log_level = _LOGGER.warning):
    """
    Verify that 'vValue' is an instance of 'vType'.
    If not, log a message at 'log_level' and return 'vValueDefault'.
    Otherwise, return 'vValue'.
    """
    if not isinstance(vValue, vType):
        _LOGGER.log(
            log_level,
            f"Received non-{vType.__name__} for {vName}: {vValue}"
        )
        return vValueDefault
    
    return vValue

def _store_interaction(data: dict, user: str, uid: str, sid: str, resume_editing: bool) -> bool:
    """Stores the data payload in DynamoDB instead of local files."""
    
    try:
        timestamp = data.get("timestamp", "UnknownTimestamp")

        # init user data structure
        interaction = {
            "user": user,
            "uid": uid,                                         # user id
            "sid": sid ,                                        # session id
            "mid": data.get("message_id", "UnknownMessageID"),  # message id
            "cid": data.get("channel_id", "UnknownChannelID"),  # channel id
            "timestamp": timestamp,
            "token": data.get("token", ""),
            "bot": data.get("bot", False),
            "url": data.get("siteUrl", ""),
            "resume_editing": resume_editing
        }        
        
        # Store interaction in DynamoDB
        _TABLE.put_item(Item=interaction)
        _LOGGER.info(f"Conversation history saved for user <{uid}> at {timestamp}")
        return True
        
    except Exception as e:
        _LOGGER.error(f"Failed to save conversation history to DynamoDB: {e}", exc_info=True)
        return False   

def put_resume_editing(uid: str, resume_editing: bool) -> None:
    """ 
    Add the satus of the resume_editing choice to the dynamo table
    """
    try:

        # init user data structure
        status = {
            "uid": uid,                                  
            "resume_editing": resume_editing                
        }        
        
        # Store interaction in DynamoDB
        _TABLE.put_item(Item=status)
        _LOGGER.info(f"Resume path choice saved for user <{uid}>.")
        return True
        
    except Exception as e:
        _LOGGER.error(f"Failed to save resume path choice to DynamoDB: {e}", exc_info=True)
        return False   


# Tool to return the webpage based on URL
# def get_page(url):

#     if response.status_code == 200:
#         soup = BeautifulSoup(response.text, "html.parser")
        
#         # Extracting the main content (removing scripts, styles, and ads)
#         for unwanted in soup(["script", "style", "header", "footer", "nav", "aside"]):
#             unwanted.extract()  # Remove these elements

#         text = soup.get_text(separator=" ", strip=True)  # Extract clean text

#         # Limit length to avoid very long output
#         clean_text = " ".join(text.split())  # First 500 words
#         return clean_text
        
#     else:
#         return f"Failed to fetch {url}, status code: {response.status_code}"

def _upload_page(sid: str, url: str, page: str) -> bool:
    """Upload page contents to session RAG as text files"""
    try:
        text_upload(text=page, description=url, session_id=sid)
        _LOGGER.info(f"Page {url} successfully uploaded to session: {sid}")
        return True
    except Exception as e:
        _LOGGER.error(f"Exception raised when uploading page: {url}")  
        return False

def _extract_urls(msg: str) -> list:
    """Extract URLs in many different formats from the message."""
    try:
        extractor = URLExtract()
        urls = extractor.find_urls(msg)
        _LOGGER.info(f"Extracted urls: {urls}")
        return urls
    except Exception as e:
        _LOGGER.warning(f"An error occurred when extracting urls: {e}")
        return []

def _scrape_requests_html(url: str) -> str:
    """
    Scraps web content using requests-html. 
    Raises an HTTPError if the status isn't successful.
    Returns the text as a string.
    
    Note that error is handled in _robust_scrape
    """
    session = HTMLSession()
    response = session.get(url)
    response.raise_for_status()
    _LOGGER.info(f"{url} scraped with requests-html")
    return response.html.text

def _scrape_bs4(url: str) -> str:
    """
    Fetch the text content of a webpage using requests + BeautifulSoup.
    Raises an HTTPError if the status isn't successful.
    Returns the text as a string.
    
    Note that error is handled in _robust_scrape
    """
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}    
    response = requests.get(url, headers=headers)

    response.raise_for_status() # raises of 400 or 500 error in response
    
    soup = BeautifulSoup(response.text, "html.parser")

    # Extracting the main content (removing scripts, styles, and ads)
    for unwanted in soup(["script", "style", "header", "footer", "nav", "aside"]):
        unwanted.extract()  # Remove these elements

    text = soup.get_text(separator=" ", strip=True)  # Extract clean text
    
    # Limit length to avoid very long output
    clean_text = " ".join(text.split())  # First 500 words
    return clean_text

    soup = BeautifulSoup(response.text, "html.parser")
    _LOGGER.info(f"{url} scraped with BeautifulSoup")
    return soup.get_text()

def _robust_scrape(url: str) -> str | None:
    """
    Attempts to scrape using BeautifulSoup first,
    If that fails, uses requests-html.
    If both fail, returns None.
    """
    try:
        return _scrape_bs4(url)
    except Exception as e:
        _LOGGER.error(f"BeautifulSoup failed to scrape {url}: {e}")
        pass

    try:
        return _scrape_requests_html(url)
    except Exception as e:
        _LOGGER.error(f"Requests-html failed to scrape {url}: {e}")
        pass
    
    return None

# used in query to load system prompt
def safe_load_text(filepath : str) -> dict:
    """Safely read in file contents; return empty string if file not found."""
    if not os.path.exists(filepath):
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()    
    except Exception as e:
        _LOGGER.error(f"Could not load text from {filepath}: {e}", exc_info=True)
        return ""
    
def scrape(sid: str, msg: str) -> tuple:
    """
    returns status of if any url scrape failed, and a list of failed urls
    """
    try:
        urls = list(_extract_urls(msg))
        
        has_urls = bool(urls)
        failed = False
        failed_urls = list()
        
        for url in urls:
            page = _robust_scrape(url)
                        
            if page == None: # ie. web-scraping failed
                failed = True
                failed_urls.append("url")
            else:
                _upload_page(sid, url, page)

        return (has_urls, failed, failed_urls)

    except Exception as e:
        _LOGGER
        return (True, True, "An unknown error occurred when accessing sites; try uploading site content as a PDF.")

def extract(data) -> tuple:
    """
    Extract user information and store conversation to DynamoDB.
    
    TODO: extract attached files & other media + upload metadata to the table
    """
    
    if not isinstance(data, dict):
        _LOGGER.warning("extract() called with non-dict data.")
        return ("UnknownUserID", "UnknownUserName", "")
    
    uid  = data.get("user_id", "UnknownUserID")
    user = data.get("user_name", "UnknownUserName")
    msg  = data.get("text", "")
    
    uid  = _validate(uid, "uid", str, "UnknownUserID", _LOGGER.warning)
    user = _validate(user, "user", str, "UnknownUserName", _LOGGER.warning)
    msg  = _validate(msg, "msg", str, "", _LOGGER.warning)
    
    if not _UID_RE.match(uid):
        _LOGGER.warning(f"Potentially invalid characters in user_id: {uid}")
        
    # Fetch/create SID from DynamoDB
    sid, new = _get_sid(uid, user)

    # Fetch the resume status from DynamoDB
    resume_editing = _get_resume_editing(uid)
    _LOGGER.info(f"resume_editing status: {resume_editing}")
    
    # Store conversation in DynamoDB
    _store_interaction(data, user, uid, sid, resume_editing)

    return (user, uid, new, sid, msg, resume_editing)

_GUIDES_SID = os.environ.get("guidesSid")
_RAG_THR = os.environ.get("ragThr")
_RAG_K = os.environ.get("ragK")

def guides(msg: str):
    message = (
        "Please provide any salient information on drafting effective resumes related to the following prompt:\n\n"
        + msg)
    
    resp = retrieve(
        query = message,
        session_id= _GUIDES_SID,
        rag_threshold= _RAG_THR,
        rag_k= _RAG_K
        )
    
    _LOGGER.info(f"Guides supplied info: {resp}")
    return resp


# File Uploading and Accessing through RocketChat
ROCKET_CHAT_URL = os.environ.get("rocketUrl")
ROCKET_USER_ID = os.environ.get("rocketUid")
ROCKET_AUTH_TOKEN = os.environ.get("rocketToken")

# File temporary section
UPLOAD_FOLDER = os.getcwd() + "/tmp"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def download_file(file_id, filename):
    """Download file from Rocket.Chat and save locally."""

    if allowed_file(filename):
        file_url = f"{ROCKET_CHAT_URL}/file-upload/{file_id}/{filename}"
        headers = {
            "X-User-Id": ROCKET_USER_ID,
            "X-Auth-Token": ROCKET_AUTH_TOKEN
        }

        response = requests.get(file_url, headers=headers, stream=True)
        if response.status_code == 200:
            local_path = os.path.join(UPLOAD_FOLDER, filename)
            _LOGGER.info(f"Local filepath: {local_path}")
            with open(local_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            return local_path
    
    print(f"INFO - some issue with {filename} with {response.status_code} code")
    return None

def send_message_with_file(room_id, message, file_path):
    """Send a message with the downloaded file back to the chat."""
    url = f"{ROCKET_CHAT_URL}/api/v1/rooms.upload/{room_id}"
    headers = {
        "X-User-Id": ROCKET_USER_ID,
        "X-Auth-Token": ROCKET_AUTH_TOKEN
    }
    files = {"file": (os.path.basename(file_path), open(file_path, "rb"))}
    data = {"msg": message}

    response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code != 200:
        return {"error": f"Failed to upload file, Status Code: {response.status_code}, Response: {response.text}"}
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError:
        return {"error": "Invalid JSON response from Rocket.Chat API", "raw_response": response.text}
    

def send_files(data, sid):
    user = data.get("user_name", "Unknown")
    room_id = data.get("channel_id", "")
    # A file is sent by the user
    if ("message" in data) and ('file' in data['message']):
        _LOGGER.info(f"INFO - detected file by {user}.")
        saved_files = []

        for file_info in data["message"]["files"]:
            file_id = file_info["_id"]
            filename = file_info["name"]

            # Download file
            _LOGGER.info(f"Downloading file {filename} from Rocket.Chat.")
            file_path = download_file(file_id, filename)

            if file_path:
                saved_files.append(file_path)
                # upload it to RAG so that session has the file
                _LOGGER.info(f"Uploading file {file_path} to RAG...")
                _LOGGER.info(f"pdf_upload path = {file_path}, session_id = {sid}, strategy = {'smart'}")
                response = pdf_upload(
                    path = file_path,
                    session_id = sid,
                    strategy = 'smart')
                _LOGGER.info(f"Resp from RAG upload: {response}\n")
                sleep(10) # so that documents are uploaded to RAG session

            else:
                _LOGGER.info(f"Failed to download file")
                return jsonify({"error": "Failed to download file"}), 500
            
        
        # Send message with the downloaded file
        message_text = f"File(s) uploaded by {user}"
        for saved_file in saved_files:
            send_message_with_file(room_id, message_text, saved_file)
            _LOGGER.info(f"Sending message with {saved_file}\n")

        _LOGGER.info(f"Files processed and re-sent successfully!")
        return jsonify({"text": "Files processed and re-sent successfully!"})


# Rocket Chat Message Sending

def update_resume_summary(sid, section, content):
    """
    Updates the structured resume summary stored in session data.
    Keeps track of completed resume sections and content.
    """
    if sid not in session:
        session[sid] = {"resume_summary": {}}

    # Store the new content for the section
    session[sid]["resume_summary"][section] = content

    # Generate formatted summary to send later
    formatted_summary = "\n".join(
        [f"**{sec.capitalize()}**:\n{data}" for sec, data in session[sid]["resume_summary"].items()]
    )

    return formatted_summary

def send_resume_for_review(sid):
    """
    Sends the formatted resume summary to a career specialist.
    """
    summary = session.get(sid, {}).get("resume_summary", {})

    if not summary:
        _LOGGER.warning(f"No resume summary found for session {sid}.")
        return {"error": "No resume summary found!"}

    formatted_summary = "\n".join(
        [f"**{sec.capitalize()}**:\n{data}" for sec, data in summary.items()]
    )

    message_text = (
        f"🔎 **Resume Review Request** 🔎\n\n"
        f"Here’s the updated section for review:\n\n"
        f"{formatted_summary}"
    )
    
    _LOGGER.info(f"Attempting to send resume review request. Session: {sid}")
    _LOGGER.debug(f"Formatted Message: {message_text}")  # Log the exact message being sent

    # Fetch Rocket.Chat credentials correctly
    rocket_url = os.getenv("rocketUrl")
    rocket_user_id = os.getenv("rocketUid")
    rocket_token = os.getenv("rocketToken")

    if not rocket_url or not rocket_user_id or not rocket_token:
        _LOGGER.error("Rocket.Chat environment variables are missing.")
        return {"error": "Rocket.Chat credentials not found."}

    # Rocket.Chat API setup
    url = f"{rocket_url}/api/v1/chat.postMessage"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": rocket_token,
        "X-User-Id": rocket_user_id
    }
    payload = {
        "channel": "@michael.brady631208",  # Make sure this username is correct
        "text": message_text,
        "attachments": [
            {
                "title": "Approve or request changes:",
                "actions": [
                    {
                        "type": "button",
                        "text": "✅ Approve",
                        "msg": f"approve_{sid}",
                        "msg_in_chat_window": True,
                        "msg_processing_type": "sendMessage"
                    },
                    {
                        "type": "button",
                        "text": "❌ Request Changes",
                        "msg": f"deny_{sid}",
                        "msg_in_chat_window": True,
                        "msg_processing_type": "sendMessage"
                    }
                ]
            }
        ]
    }

    _LOGGER.debug(f"Rocket.Chat API Payload: {payload}")  # Log the full API request

    response = requests.post(url, json=payload, headers=headers)
    
    _LOGGER.info(f"Rocket.Chat API Response Code: {response.status_code}")
    
    try:
        response_data = response.json()
        _LOGGER.debug(f"Rocket.Chat Response: {response_data}")  # Log the full response
    except Exception as e:
        _LOGGER.error(f"Failed to parse response from Rocket.Chat: {e}")
        response_data = {"error": "Invalid response from Rocket.Chat"}

    return response_data
