# app.py
# handles app routing, (TODO) redirecting to utils and chat functionality

# Import statements
import os, logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config import get_logger
from utils import extract
from chat import welcome, query

_LOGGER = get_logger(__name__)
_LOGGER.info("Application starting...")

# Check for dev state.
try:
    _ENV      = os.environ.get("flaskEnv")
    _DEV_HOST = os.environ.get("flaskHost")
    _DEV_PORT = os.environ.get("flaskPort")
    _DEV_PAGE = os.environ.get("flaskPage")
    _DEV_ADDR = "http://" + _DEV_HOST + ":" + _DEV_PORT + "/query"
except:
    _LOGGER.info("flaskEnv not found...setting to production environment.")
    _ENV = ""

app = Flask(__name__)

if _ENV == "dev":
    CORS(app) # Potentially unnecessary but ok to include.

# Main app route; how to query the chatbot and get responses back.
@app.route('/query', methods=['POST'])
def main(): 
    # Enforce only JSON requests
    if not request.is_json:
        _LOGGER.warning("[SECURITY] Non-JSON request blocked.")
        return jsonify({"error": "Invalid content type"}), 400
    
    _LOGGER.info(f"Request type: {type(request)}")
    _LOGGER.info(f"HTTP POST Request: {request}")
    data = request.get_json() 
    _LOGGER.info(f"HTTP POST Data: {data}")
    
    # Extract relevant information
    # (Extract also does some very important cataloguing.)
    user, uid, new, sid, msg = extract(data)

    # Do not respond to bots
    if data.get("bot") or not msg:
        return jsonify({"status": "ignored"})
        
    if new:
        return welcome(uid, user)
    else:
        # TODO: module for parsing message to see if it contains a link
        # it should find every link

        # TODO: module for opening link and returning html/text contents
        # https://www.askpython.com/python/examples/read-html-from-url
        # ideally we could save page contents as a pdf and then upload that pdf
        # to the session for RAG but for now let's just store the contents in a message
        # then query the chatbot telling it to remember the page contents
        
        # TODO: module to handle attached files and upload them to session

        # TODO: actually impl query - see query for another todo
        return query(msg, sid)
    
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
    else:
        app.run(debug=True)
