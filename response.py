# response.py

from flask import jsonify
from config import get_logger
from utils import scrape, guides, send_files, put_rsme
from chat import welcome, respond as chatRespond

# filespaths, logging, etc.
_LOGGER = get_logger(__name__)

def respond(data: dict, user: str, uid: str, new: bool, sid: str, msg: str, files, rsme: bool):
    # Handle welcome message for new users
    if new:
        _LOGGER.info(f"New user detected: {user}. Processing welcome & file upload.")
        return welcome(uid, user)
    
    # Handle file uploads
    elif "message" in data and "files" in data["message"]:
        _LOGGER.info(f"Detected file upload from {user}. Files: {data['message']['files']}")
        
        file_success = send_files(data, sid)
        _LOGGER.info(f"File upload status: {file_success}")
        
        if file_success:
            return jsonify({"text": "✅ File successfully uploaded! What's next?"})
        else:
            return jsonify({"text": "⚠️ An issue was encountered saving the file. Please try again."})
    
    # Handle resume creation and editing commands
    elif msg == "resume_create":
        rsme = False
        put_rsme(uid, rsme)
        return jsonify({"text": "✍️ We're now creating a new resume. Where should we start?"})
    elif msg == "resume_edit":
        rsme = True
        put_rsme(uid, rsme)
        return jsonify({"text": "📨 Send me your existing resume as a '.pdf' file to get started!"})
    elif rsme == None:
        return jsonify({"text": "‼️Please choose one of the two options above for working on your resume."})

    # Default query handling if none of the above matched
    else:
        _LOGGER.info(f"Processing user query: {msg}")
        # TODO: fix urls
        # If links are in the msg, load their content into the session
        has_urls, url_uploads_failed, urls_failed = scrape(sid, msg)
        _LOGGER.info(f"URL EXTR: has_urls <{has_urls}>, url_uploads_failed <{url_uploads_failed}>, urls_failed <{urls_failed}>")
        
        gbl = guides(msg)  
        _LOGGER.info(f"Guiding info retrieved: {gbl}")      

        return chatRespond(msg=msg, sid=sid, has_urls=has_urls, urls_failed=urls_failed, 
                       gbl_context=gbl, rsme=rsme)
