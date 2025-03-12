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
    
    # Extract relevant information plus collect & store user data
    user, uid, new, sid, msg, rsme = extract(data)
    _LOGGER.info(f"USER DATA: user <{user}>, new <{new}>, uid <{uid}>, sid <{sid}>, msg <{msg}>, rmse<{rsme}>")

    # Ignore bot messages.
    if bool(data.get("bot")) == True:
        _LOGGER.info("Bot message detected; message ignored.")
        return jsonify({"status": "ignored"})

    # Handle welcome message for new users
    elif new:
        _LOGGER.info(f"New user detected: {user}. Processing welcome & file upload.")
        return welcome(uid, user)
    
    # Handle file uploads
    elif "message" in data and "files" in data["message"]:
        _LOGGER.info(f"Detected file upload from {user}. Files: {data['message']['files']}")
        
        file_success = send_files(data, sid)
        _LOGGER.info(f"File upload status: {file_success}")
        
        if file_success:
            return jsonify({"text": "✅ File successfully uploaded!"})
        else:
            return jsonify({"text": "⚠️ An issue was encountered saving the file. Please try again."})
    
    # Handle resume creation and editing commands
    elif msg == "resume_create":
        rsme = False
        put_resume_editing(uid, rsme)
        return jsonify({"text": "You're now creating a new resume. Where should we start?"})
    elif msg == "resume_edit":
        rsme = True
        put_resume_editing(uid, rsme)
        return jsonify({"text": "Send me your existing resume as a '.pdf' file to get started!"})
    
    # Default query handling if none of the above matched
    else:
        _LOGGER.info(f"Processing user query: {msg}")
        # If links are in the msg, load their content into the session
        has_urls, url_uploads_failed, urls_failed = scrape(sid, msg)
        _LOGGER.info(f"URL EXTR: has_urls <{has_urls}>, url_uploads_failed <{url_uploads_failed}>, urls_failed <{urls_failed}>")
        
        if rsme == None:
            return jsonify({"text": "Please select one of the two options above for working on your resume."})

        gbl = guides(msg)  
        _LOGGER.info(f"Guiding info retrieved: {gbl}")      

        return respond(msg=msg, sid=sid, has_urls=has_urls, urls_failed=urls_failed, 
                       gbl_context=gbl, rsme=rsme)

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
