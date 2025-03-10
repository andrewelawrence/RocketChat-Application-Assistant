# utils.py
# TODO: see upload() & extract()

import os, re, time, hashlib, boto3, requests
from config import get_logger
from llmproxy import upload, pdf_upload, text_upload
from urlextract import URLExtract
from requests_html import HTMLSession
from bs4 import BeautifulSoup

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

def _store_interaction(data: dict, user: str, uid: str, sid: str) -> bool:
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
        }        
        
        # Store interaction in DynamoDB
        _TABLE.put_item(Item=interaction)
        _LOGGER.info(f"Conversation history saved for user <{uid}> at {timestamp}")
        return True
        
    except Exception as e:
        _LOGGER.error(f"Failed to save conversation history to DynamoDB: {e}", exc_info=True)
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
            
            # TODO: delete for prod - too much data logged
            _LOGGER.info(f"Page content: {page}")
            
            if page == None: # ie. web-scraping failed
                failed = True
                failed_urls.append("url")
            else:
                _upload_page(sid, url, page)

        return (has_urls, failed, failed_urls)

    except Exception as e:
        _LOGGER
        return (True, True, "An unknown error occurred when accessing sites; try uploading site content as a PDF.")

def upload(sid : str) -> tuple:
    """
    Upload any file type to chatbot session using llmproxy upload function.
    
    This enables excellent flexability but we must transform the attached file
    to a multi-part form which will require a little research.
    
    Returns true if upload was successful,
    
    # TODO: update params, actually impl. function
    """
    
    failed = False
    failed_uploads = list()
    
    return (failed, failed_uploads) 

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

    # Store conversation in DynamoDB
    _store_interaction(data, user, uid, sid)

    return (user, uid, new, sid, msg)
