from flask import Flask, request, jsonify
from config import get_logger

_LOGGER = get_logger(__name__)
_LOGGER.info("Application started")

app = Flask(__name__)

@app.route('/query', methods=['POST'])
def main():    
    return jsonify({"text":"boilerplate init response"})
    
@app.route('/')
def hello_world():
   return jsonify({"message":'There is nothing on this page. Please return to where you came from!'})

@app.errorhandler(404)
def page_not_found(e):
    return "Error 404: Page Not Found", 404

if __name__ == "__main__":
    app.run(debug=True)
