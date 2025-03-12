# app.py

import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config import get_logger
from utils import extract
from response import respond

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
    user, uid, new, sid, msg, files, rsme = extract(data)
    _LOGGER.info(f"USER DATA: user <{user}>, new <{new}>, uid <{uid}>, sid <{sid}>, msg <{msg}>, rmse <{rsme}>, files <{bool(files)}")

    # Ignore bot messages.
    if bool(data.get("bot")) == True:
        _LOGGER.info("Bot message detected; message ignored.")
        return jsonify({"status": "ignored"})
    else:
        return respond(data, user, uid, new, sid, msg, files, rsme)
    
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
