# chat.py

# TODO: implement the real query architecture in this module. 
# (resume uploading, etc.)

import os
from flask import jsonify
from config import get_logger
from llmproxy import generate
from utils import safe_load_text

# filespaths, logging, etc.
_LOGGER = get_logger(__name__)
_WELCOME = os.environ.get("welcomePage")
_SYSTEM = os.environ.get("systemPrompt")
_MODEL = os.environ.get("model")
_TEMP = os.environ.get("temp")
_LAST_K = os.environ.get("lastK")
_RAG = os.environ.get("rag")
_RAG_K = os.environ.get("ragK")
_RAG_THR = os.environ.get("ragThr")

# welcome page for new users
def welcome(uid: str, user: str):
    with open(_WELCOME, "r", encoding="utf-8") as f:
        welcome = f.read()
    
    _LOGGER.info(f"Welcomed {user} (uid: {uid})")
    return jsonify({"text": welcome})

# main query function
# TODO: a lot of stuff lol
def query(msg: str, sid: str):
    # load in system from system.txt file
    system = safe_load_text(_SYSTEM)
    
    _LOGGER.info(f"SID: {sid}")
    _LOGGER.info(f"MSG: {msg}")
    
    response = generate(
        model=_MODEL,
        system=system,
        query=msg,
        temperature=_TEMP,
        lastk=_LAST_K,
        rag_usage=_RAG,
        rag_k=_RAG_K,
        rag_threshold=_RAG_THR,
        session_id=sid,
    )

    _LOGGER.info(f"RESP: {response}")
    _LOGGER.info(f"RESP[RESP]: {response['response']}")

    resp_text = response['response']
    # resp_context = response['rag???']
    
    # Send response back
    # rc_resp = {
    #     "text": resp_text
    # }

    return jsonify({"text": resp_text})
