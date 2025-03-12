# utils.py

import os, re, time, hashlib, boto3, requests, json
from time import sleep
from flask import jsonify, session
from urlextract import URLExtract
from requests_html import HTMLSession
from bs4 import BeautifulSoup
from config import get_logger
from llmproxy import retrieve, pdf_upload, text_upload

# setup logging
_LOGGER = get_logger(__name__)

# SID Hash
_HASH = hashlib.sha1()

# AWS connection
_BOTO3_SESSION = boto3.Session(
   aws_access_key_id=os.environ.get("awsAccessKey"),
   aws_secret_access_key=os.environ.get("awsSecretKey"),
   region_name=os.environ.get("awsRegion")
)
_S3_BUCKET = _BOTO3_SESSION.client("s3")
_DYNAMO_DB = _BOTO3_SESSION.resource("dynamodb")
_TABLE     = _DYNAMO_DB.Table(os.environ.get("dynamoTable"))

# Global settings for guiding retrieval
_GUIDES_SID = os.environ.get("guidesSid")
_RAG_THR    = os.environ.get("ragThr")
_RAG_K      = os.environ.get("ragK")

# Regular expression to validate UIDs (alphanumeric only)
_UID_RE = re.compile(r'^[A-Za-z0-9]+$')

# Rocket.Chat configuration for file uploads and messaging
_ROCKET_URL   = os.environ.get("rocketUrl")
_ROCKET_UID   = os.environ.get("rocketUid")
_ROCKET_TOKEN = os.environ.get("rocketToken")

# Temporary file upload folder and allowed file extensions
_UPLOADS = os.path.join(os.getcwd(), "tmp")
if not os.path.exists(_UPLOADS):
    os.makedirs(_UPLOADS, exist_ok=True)
_ALLOWED_FILES = {'pdf'}

def extract(data) -> tuple:
    """
    Extract and validate user information from the incoming data.
    Also stores the conversation history in DynamoDB.

    Parameters:
        data (dict): The input data containing user and message details.

    Returns:
        tuple: (username, uid, is_new_user, sid, message_text, file_info, resume_edit_status)
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
    
    try:
        files = data["message"].get("files", False)
    except KeyError:
        files = []

    if not _UID_RE.match(uid):
        _LOGGER.warning(f"Potentially invalid characters in user_id: {uid}")
        
    # Fetch/create SID from DynamoDB
    sid, new = _get_sid(uid, user)

    # Fetch the resume status from DynamoDB
    rsme = _get_rsme(uid)
    
    # Store conversation in DynamoDB
    _store_interaction(data, user, uid, sid, bool(files), rsme)

    return (user, uid, new, sid, msg, files, rsme)


def guides(msg: str) -> str:
    """
    Retrieve guiding context for drafting effective resumes based on the provided prompt.

    This function constructs a query by appending a resume-related request to the given message.
    It then calls the 'retrieve' function (from the llmproxy module) with the configured session
    and RAG parameters to obtain additional context for resume drafting. If no context is retrieved,
    a default message is returned.

    Parameters:
        msg (str): The user prompt related to resume drafting.

    Returns:
        str: A JSON-formatted string containing the retrieved guiding information, or a default message 
             indicating no extra context was retrieved.
    """
    message = (
        "Please provide any salient information on drafting effective resumes related to the following prompt:\n"
        + msg)
    
    resp = retrieve(
        query = message,
        session_id= _GUIDES_SID,
        rag_threshold= _RAG_THR,
        rag_k= _RAG_K
        )
    
    if not resp: # if resp is empty
        _LOGGER.info("No guiding info found.")
        return "No extra context retrieved."
    else:
        _LOGGER.info(f"Guiding info retrieved: {resp}")
        return json.dumps(resp)


def safe_load_text(filepath : str) -> str:
    """
    Safely read in file contents; return empty string if file not found.
    """
    if not os.path.exists(filepath):
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()    
    except Exception as e:
        _LOGGER.error(f"Could not load text from {filepath}: {e}", exc_info=True)
        return ""
    

def put_rsme(uid: str, rsme: bool) -> bool:
    """
    Update the 'rsme' attribute for a given user in the DynamoDB table.
    
    If the item with the specified uid does not exist, it is created with the provided 'rsme' value.
    
    Parameters:
        uid (str): The unique identifier of the user.
        rsme (bool): The resume editing mode status.
        
    Returns:
        bool: True if the update/creation was successful, otherwise False.
    """
    try:
        _TABLE.update_item(
            Key={"uid": uid},
            UpdateExpression="SET rsme = :rsme",
            ExpressionAttributeValues={":rsme": rsme},
            ReturnValues="UPDATED_NEW"
        )
        _LOGGER.info(f"Resume path choice <rsme> = '{rsme}' saved for user <{uid}>.")
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to save resume path choice to DynamoDB: {e}", exc_info=True)
        return False
    

def scrape(sid: str, msg: str) -> tuple:
    """
    returns status of if any url scrape failed, and a list of failed urls
    
    TODO: fix uploading page content to sid
    TODO: see the github for an example of how to do it.
    """
    return (False, False, [])
    # try:
    #     urls = list(_extract_urls(msg))
        
    #     has_urls = bool(urls)
    #     failed = False
    #     failed_urls = list()
        
    #     for url in urls:
    #         page = _robust_scrape(url)
                        
    #         if page == None: # ie. web-scraping failed
    #             failed = True
    #             failed_urls.append("url")
    #         else:
    #             _upload_page(sid, url, page)

    #     return (has_urls, failed, failed_urls)

    # except Exception as e:
    #     _LOGGER
    #     return (True, True, "An unknown error occurred when accessing sites; try uploading site content as a PDF.")
    

def upload(data, sid):
    """
    Process file attachments from the incoming data: download from Rocket.Chat,
    upload to the session's RAG, and optionally notify via chat.

    Parameters:
        data (dict): The input data containing file attachment details.
        session_id (str): The session identifier.

    Returns:
        A Flask JSON response indicating success or error.
    """
    user = data.get("user_name", "Unknown")
    room_id = data.get("channel_id", "")
    
    # A file is sent by the user
    if ("message" in data) and ('file' in data['message']):
        saved_files = []

        for file_info in data["message"]["files"]:
            file_id = file_info["_id"]
            filename = file_info["name"]

            # Download file
            _LOGGER.info(f"Downloading file <{filename}> from Rocket.Chat.")
            file_path = _download_file(file_id, filename)

            if file_path:
                saved_files.append(file_path)
                # upload it to RAG so that session has the file
                _LOGGER.info(f"Uploading file <{file_path}> to RAG.")
                _LOGGER.info(f"pdf_upload path = {file_path}, session_id = {sid}, strategy = {'smart'}")
                response = pdf_upload(
                    path = file_path,
                    session_id = sid,
                    description=filename,
                    strategy = 'smart'
                    )
                _LOGGER.info(f"Response from RAG upload: {response}")
                sleep(10) # so that documents have time to load

            else:
                _LOGGER.info(f"Failed to download file.")
                return jsonify({"error": "Failed to download file"}), 500
            
        # Commented out for now because of double messages sent - which is 
        # unnecessary.
        # Send message with the downloaded file
        # message_text = f"File(s) uploaded by {user}"
        # for saved_file in saved_files:
        #     _send_message_with_file(room_id, message_text, saved_file)
        #     _LOGGER.info(f"Sending message with {saved_file}\n")

        # _LOGGER.info(f"Files processed and re-sent successfully!")
        return jsonify({"text": "Files processed and re-sent successfully!"})


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
    Sends the full formatted resume summary to a career specialist.
    """

    # 🔍 DEBUG: Log session data before sending
    _LOGGER.debug(f"Session data before sending to expert: {session.get(sid, {})}")

    summary = session.get(sid, {}).get("resume_summary", {})

    if not summary:
        _LOGGER.warning(f"No resume summary found for session {sid}.")
        return {"error": "No resume summary found!"}

    # 🔥 New Fix: Format the entire resume properly
    formatted_resume = "\n\n".join(
        [f"**{sec.capitalize()}**:\n{data}" for sec, data in summary.items()]
    )

    message_text = (
        f"🔎 **Resume Review Request** 🔎\n\n"
        f"Here’s the full updated resume for review:\n\n"
        f"{formatted_resume}"
    )
    
    _LOGGER.info(f"Attempting to send full resume review request. Session: {sid}")
    _LOGGER.debug(f"Formatted Message: {message_text}")  # Log the exact message being sent

    # Fetch Rocket.Chat credentials
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


def _gen_sid() -> str:
    """
    Generate a unique session identifier (SID) using the current epoch time.

    Returns:
        str: A 10-character hexadecimal string.
    """
    _HASH.update(str(time.time()).encode('utf-8'))
    return _HASH.hexdigest()[:10]


def _new_sid() -> bool:
    """
    Reserve a new free session ID in the DynamoDB table for future assignment.

    Returns:
        bool: True if the free SID was successfully stored, otherwise False.
    """
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
    """
    Retrieve the session ID (SID) associated with a given user ID (uid).
    If no SID exists, assign a free or new SID to the user.

    Parameters:
        uid (str): The user's unique identifier.
        username (str): The user's name (default is "UnknownName").

    Returns:
        tuple: A tuple (sid, is_new) where 'sid' is the session ID (str)
               and 'is_new' is a boolean indicating if the user is new.
    """
    sid = ""
    
    try:
        # Check if SID already exists in DynamoDB
        resp = _TABLE.get_item(Key={"uid": uid})
        if "Item" in resp:
            sid = resp["Item"]["sid"]
            _LOGGER.info(f"User <{uid}> has existing SID <{sid}>")
            return (str(sid), False)

        # If no SID, try to assign a free SID.
        resp = _TABLE.get_item(Key={"uid": "free"}) # "free" because thats the UID
        if "Item" in resp:
            sid = resp["Item"]["sid"]
            _TABLE.delete_item(Key={"uid": "free"}) # Remove free SID after assignment
            _LOGGER.info(f"Assigned existing free SID <{sid}> to user <{uid}>")
        # If not, create a new SID and store it
        else:
            sid = _gen_sid()
            _LOGGER.info(f"No free SID found. Created new SID <{sid}> for user <{uid}>")

        # Reserve another free SID for future assignments.
        _new_sid()
        return (str(sid), True)
    
    except Exception as e:
        _LOGGER.error(f"Error accessing DynamoDB for SID: {e}", exc_info=True)
        return (str(""), False)


def _get_rsme(uid: str) -> bool | None:
    """
    Retrieve the resume editing (rsme) status for a user from DynamoDB.

    Parameters:
        uid (str): The user's unique identifier.

    Returns:
        bool | None: The resume editing status if found, or None if not set or on error.
    """
    try:
        resp = _TABLE.get_item(Key={"uid": uid})
        if "Item" in resp:
            rsme = resp["Item"]["rsme"]
            if rsme == None:
                _LOGGER.info(f"User <{uid}> has no resume editing status set.")
                return None
            else:
                _LOGGER.info(f"User <{uid}> has resumes editing status: {rsme}")
                return rsme
        else:
            raise LookupError
    except Exception as e:
        _LOGGER.info("Error accessing DynamoDB for resume editing status. Assuming rsme is None.", exc_info=False)
        return None


def _validate(vValue, vName : str = "unknown", vType : type = str, 
              vValueDefault = None,
              log_level = _LOGGER.warning):
    """
    Validate that 'value' is an instance of 'expected_type'.
    Logs a warning and returns 'default_value' if the check fails.

    Parameters:
        value: The value to validate.
        value_name (str): The name of the value (for logging purposes).
        expected_type (type): The expected type of the value.
        default_value: The default value to return if validation fails.
        log_level: The logging level to use if validation fails.

    Returns:
        The original value if valid; otherwise, the default_value.
    """
    if not isinstance(vValue, vType):
        _LOGGER.log(
            log_level,
            f"Received non-{vType.__name__} for {vName}: {vValue}"
        )
        return vValueDefault
    
    return vValue


def _store_interaction(data: dict, user: str, uid: str, sid: str, files: bool,
                       rsme: bool) -> bool:
    """
    Store conversation interaction data in the DynamoDB table.

    Parameters:
        interaction_data (dict): The full payload of interaction data.
        username (str): The user's name.
        uid (str): The user's unique identifier.
        sid (str): The session identifier.
        has_files (bool): Flag indicating whether files were attached.
        rsme_status (bool): The resume editing status.

    Returns:
        bool: True if the interaction was successfully stored, otherwise False.
    """    
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
            "files": files,
            "rsme": rsme
        }        
        
        # Store interaction in DynamoDB
        _TABLE.put_item(Item=interaction)
        _LOGGER.info(f"Conversation history saved for user <{uid}> at {timestamp}")
        return True
        
    except Exception as e:
        _LOGGER.error(f"Failed to save conversation history to DynamoDB: {e}", exc_info=True)
        return False   


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


def _allowed_files(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in _ALLOWED_FILES


def _download_file(file_id, filename):
    """Download file from Rocket.Chat and save locally."""

    if _allowed_files(filename):
        file_url = f"{_ROCKET_URL}/file-upload/{file_id}/{filename}"
        headers = {
            "X-User-Id": _ROCKET_UID,
            "X-Auth-Token": _ROCKET_TOKEN
        }

        response = requests.get(file_url, headers=headers, stream=True)
        if response.status_code == 200:
            local_path = os.path.join(_UPLOADS, filename)
            _LOGGER.info(f"Local filepath: {local_path}")
            with open(local_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            return local_path
    
    print(f"INFO - some issue with {filename} with {response.status_code} code")
    return None


def _send_message_with_file(room_id, message, file_path):
    """Send a message with the downloaded file back to the chat."""
    url = f"{_ROCKET_URL}/api/v1/rooms.upload/{room_id}"
    headers = {
        "X-User-Id": _ROCKET_UID,
        "X-Auth-Token": _ROCKET_TOKEN
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
