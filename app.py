# app.py
# TODO: see main()

import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config import get_logger
from utils import extract, scrape
from chat import welcome, query

# setup logging
_LOGGER = get_logger(__name__)
_LOGGER.info("Application starting...")

# Creates a Flask app instance so Flask can locate resources. 
app = Flask(__name__)

# Check for dev state.
try:
    _ENV      = os.environ.get("flaskEnv")
    _DEV_HOST = os.environ.get("flaskHost")
    _DEV_PORT = os.environ.get("flaskPort")
    _DEV_PAGE = os.environ.get("flaskPage")
    _DEV_ADDR = "http://" + _DEV_HOST + ":" + _DEV_PORT + "/query"
except:
    _LOGGER.info("DEV environment not found...setting to PROD environment.")
    _ENV = ""

# Only use CORS if in dev state
if _ENV == "dev":
    CORS(app)

# Main app route; querying the chatbot and sending responses back.
@app.route('/query', methods=['POST'])
def main(): 
    # Enforce only JSON requests
    if not request.is_json:
        _LOGGER.warning("[SECURITY] Non-JSON request blocked.")
        return jsonify({"error": "Invalid content type"}), 400
    
    # Get data and log it
    data = request.get_json() 
    _LOGGER.info(f"HTTP POST Data: {data}")
    
    # Extract relevant information + collect & store user data
    # TODO: extract any files
    user, uid, new, sid, msg = extract(data)

    # Do not respond to bots
    # Done after data collection so bot interactions are stored
    if data.get("bot") or not msg:
        return jsonify({"status": "ignored"})
        
    # Handle message
    if new:
        return welcome(uid, user)
    elif msg == "resume_create":
        return jsonify({"text": "You're now creating a new resume"})
    elif msg == "resume_edit":
        return jsonify({"text": "You're now editing an existing resume"})
    else:
        # If links are in the msg, load their content into the session
        has_urls, url_uploads_failed, urls_failed = scrape(sid, msg)
        _LOGGER.info(f"URL Extraction infO:\n{has_urls}\n{url_uploads_failed}\n{urls_failed}")
        
        # TODO: If files were attached, load them into the session

        # TODO: see chat.py query function
        return query(msg, sid, 
                     has_urls, urls_failed)

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
