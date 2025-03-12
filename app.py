# app.py

import os, json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config import get_logger
from utils import extract
from response import respond

# Setup logging
_LOGGER = get_logger(__name__)

# Creates a Flask app instance so Flask can locate resources. 
app = Flask(__name__)

# Check for dev state. Will raise an error if in Koyeb environment.
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
    
@app.route('/query', methods=['POST'])
def main():
    """
    Handles chatbot query requests via HTTP POST.

    This function:
    - Ensures the request is in JSON format.
    - Extracts relevant user information from the request payload.
    - Logs request details and extracted user data.
    - Ignores bot-generated messages.
    - Passes the extracted data to the chatbot response handler.

    Returns:
        - JSON response from `respond()` if the request is valid.
        - HTTP 400 error if the request is not JSON.
        - JSON response indicating ignored bot messages.   
    """    
    # Delineate logs
    _LOGGER.info("|" * 51)
    _LOGGER.info("|" * 13 + " NEW INTERACTION STARTED " + "|" * 13)
    _LOGGER.info("|" * 51)
    
    # Enforce only JSON requests
    if not request.is_json:
        _LOGGER.warning("Error: Non-JSON request. Request blocked.")
        return jsonify({"error": "Invalid content type"}), 400   
     
    # Get data and log it
    data = request.get_json() 
    _LOGGER.info(f"HTTP POST: {json.dumps(data, separators=(',', ':'))}")
    
    # Extract relevant information plus collect & store user data
    user, uid, new, sid, msg, files, rsme = extract(data)
    _LOGGER.info(f"User <{user}>: uid <{uid}>, sid <{sid}>, new <{new}>, msg <{msg}>, rmse <{rsme}>, files <{bool(files)}>")

    # Ignore bot messages.
    if bool(data.get("bot")) == True:
        _LOGGER.info("Bot message detected; message ignored.")
        return jsonify({"status": "ignored"})
    else:
        return respond(data, user, uid, new, sid, msg, files, rsme)
    
# Dev route; displays a basic prompt/response page that uses /query
@app.route('/dev')
def dev():
    """
    Serves the development interface page.

    This function:
    - Restricts access to only when the app is running in "dev" mode.
    - Logs an access attempt to the dev page.
    - Renders a development page for testing, which interacts with `/query`.

    Returns:
        - Rendered HTML template of the dev page if in dev environment.
        - Default response if not in dev mode.
    """
    if _ENV != "dev":
        _LOGGER.warning("Attempted access to /dev but not in dev environment.")
        return default()

    _LOGGER.info(f"Serving dev page to {_DEV_ADDR}")
    return render_template(template_name_or_list=_DEV_PAGE, address=_DEV_ADDR)  

# Default page
@app.route('/')
def default():   
    """
    Serves the default response for the root URL.

    This function:
    - Returns a simple JSON message informing users that there is nothing on this page.

    Returns:
        - JSON response with a message indicating the page is empty.
    """
    return jsonify({"message":'There is nothing on this page. Please return to where you came from!'})

# Error page
@app.errorhandler(404)
def page_not_found(e):
    """
    Handles 404 errors (Page Not Found).

    This function:
    - Returns a simple text response for any invalid URL.

    Args:
        e (Exception): The error object (not used in the response).

    Returns:
        - String message "Error 404: Page Not Found" with HTTP status 404.
    """
    return "Error 404: Page Not Found", 404

# App startup
if __name__ == "__main__":
    """
    Runs the Flask application.

    This function:
    - Checks if the app is in "dev" mode.
    - If in dev mode, enables debugging and runs locally on the configured host/port.
    - Otherwise, starts the Flask server in production mode with debugging enabled.

    The `use_reloader=True` in dev mode ensures changes are automatically reloaded.
    """
    if _ENV == "dev":
        app.run(debug=True, use_reloader=True, host=_DEV_HOST, port=_DEV_PORT)
        
    # Else, run normally
    else:
        app.run(debug=True)
