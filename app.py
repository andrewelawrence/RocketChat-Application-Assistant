# app.py

import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config import get_logger
from utils import extract, scrape, guides, send_files, send_resume_for_review, put_resume_editing
from chat import welcome, respond

# setup logging
_LOGGER = get_logger(__name__)

# Creates a Flask app instance so Flask can locate resources. 
app = Flask(__name__)

# Check for dev state.
try:
    _ENV      = os.environ.get("flaskEnv")
    _DEV_HOST = os.environ.get("flaskHost")
    _DEV_PORT = os.environ.get("flaskPort")
    _DEV_PAGE = os.environ.get("flaskPage")
    _DEV_ADDR = "http://" + _DEV_HOST + ":" + _DEV_PORT + "/query"
    
    # Only use CORS if in dev state
    if _ENV == "dev":
        CORS(app)
except:
    _ENV = ""

# Main app route; querying the chatbot and sending responses back.
@app.route('/query', methods=['POST'])
def main(): 
    # Delineate logs
    _LOGGER.info(f"========== NEW INTERACTION ==========")
    
    # Enforce only JSON requests
    if not request.is_json:
        _LOGGER.warning("Non-JSON request blocked.")
        return jsonify({"error": "Invalid content type"}), 400
    
    # Get data and log it
    data = request.get_json() 
    _LOGGER.info(f"HTTP POST: {data}")
    
    # Ignore bot messages.
    if bool(data.get("bot")) == True:
        _LOGGER.info("Bot message detected; message ignored.")
        return jsonify({"status": "ignored"})

    # Extract relevant information + collect & store user data
    user, uid, new, sid, msg, resume_editing = extract(data)
    _LOGGER.info(f"EXTR DATA: User: {user}, New User: {new}, User ID: {uid}, Session ID: {sid}, Message: {msg}, Resume Editing: {resume_editing}")
    
    # Handle welcome message for new users
    if new:
        _LOGGER.info(f"New user detected: {user}. Processing welcome & file upload.")
        file_success = send_files(data, sid)
        return welcome(uid, user)
    
    # Handle file uploads
    if "message" in data and "files" in data["message"]:
        _LOGGER.info(f"Detected file upload from {user}. Files: {data['message']['files']}")
        file_success = send_files(data, sid)
        _LOGGER.info(f"File upload status: {file_success}")
        if file_success:
            return jsonify({"text": "✅ File successfully uploaded!"})
        else:
            return jsonify({"text": "⚠️ An issue was encountered saving the file. Please try again."})
    
    # Handle resume creation and editing commands
    if msg == "resume_create":
        resume_editing = False
        put_resume_editing(uid, resume_editing)
        return jsonify({"text": "You're now creating a new resume"})
        # TODO: implement it so that that message appears and then the chatbot provides some question to get things started
    elif msg == "resume_edit":
        resume_editing = True
        put_resume_editing(uid, resume_editing)
        return jsonify({"text": "Send me your existing resume as a '.pdf' or '.txt' file to get started!"})
    
    # Default query handling if none of the above matched
    else:
        _LOGGER.info(f"Processing user query: {msg}")
        # If links are in the msg, load their content into the session
        has_urls, url_uploads_failed, urls_failed = scrape(sid, msg)
        _LOGGER.info(f"URL Extraction info:\n{has_urls}\n{url_uploads_failed}\n{urls_failed}")
        
        if resume_editing == None:
            return jsonify({"text": "Please select one of the two options for working on your resume."})

        gbl_context = guides(msg)        

        return respond(msg=msg, sid=sid, has_urls=has_urls, urls_failed=urls_failed, 
                       gbl_context=gbl_context, resume_editing=resume_editing)

# Dev route; displays a basic prompt/response page that uses /query
@app.route('/dev')
def dev():
    # Restricts access if environment variables improperly setup
    if _ENV != "dev":
        _LOGGER.warning("Attempted access to /dev but not in dev environment.")
        return default()

    _LOGGER.info(f"Serving dev page to {_DEV_ADDR}")
    return render_template(template_name_or_list=_DEV_PAGE, address=_DEV_ADDR)  

# Default page
@app.route('/')
def default():   
   return jsonify({"message":'There is nothing on this page. Please return to where you came from!'})

# Error page
@app.errorhandler(404)
def page_not_found(e):
    return "Error 404: Page Not Found", 404

# App startup
if __name__ == "__main__":
    # If dev state, run verbosely and host locally
    if _ENV == "dev":
        app.run(debug=True, use_reloader=True, host=_DEV_HOST, port=_DEV_PORT)
        
    # Else, run normally
    else:
        app.run(debug=True)
