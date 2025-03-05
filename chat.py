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

# Dictionary to track user interactions
# USER_INTERACTIONS = {}

# welcome page for new users
def welcome(uid: str, user: str):
    with open(_WELCOME, "r", encoding="utf-8") as f:
        welcome = f.read()
    
    _LOGGER.info(f"Welcomed {user} (uid: {uid})")
    return jsonify({"text": welcome})

# main query function
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
    # TODO: query the chatbot to see if we should reach out to Career Center'
    # Initialize user interaction tracking if new session
    # if sid not in USER_INTERACTIONS:
        USER_INTERACTIONS[sid] = {"career_mentions": 0, "total_messages": 0}

    # Update interaction count
    # USER_INTERACTIONS[sid]["total_messages"] += 1

    # STEP 1: Ask AI if the message is career-related
    # career_check_prompt = (
        # "Analyze this message and determine if it is related to career help, job search, resume writing, or interview preparation. "
        # "Respond with 'YES' if it is career-related, otherwise respond with 'NO'. "
        # f"User message: {msg}"
    # )

    # career_check = generate(
        # model=_MODEL,
        # system="You are an assistant identifying if a message is career-related.",
        # query=career_check_prompt,
        # temperature=0,
        # session_id=sid,
    #)

    #is_career_related = career_check['response'].strip().upper()

    # If the AI determines this is a career-related question, update count
    # if is_career_related == "YES":
        # USER_INTERACTIONS[sid]["career_mentions"] += 1

    # _LOGGER.info(f"User {sid} has asked about career topics {USER_INTERACTIONS[sid]['career_mentions']} times.")

    # STEP 2: If the user has repeatedly asked about career help, trigger Career Center referral with a BUTTON
    # if USER_INTERACTIONS[sid]["career_mentions"] >= 3:  # Adjust threshold as needed
        # response = {
            # "text": resp_text + "\n\n💡 It looks like you've asked multiple questions about career help!",
            # "attachments": [
                #{
                    # "title": "Would you like to schedule a meeting with the Tufts Career Center?",
                    # "text": "Click below to book an appointment.",
                    # "actions": [
                        # {
                            # "type": "button",
                            # "text": "📅 Schedule a Meeting",
                            # "msg": "career_support_clicked",
                            # "url": "https://careers.tufts.edu/channels/see-an-advisor/",
                            # "msg_in_chat_window": False
                        # }
                    # ]
                # }
            # ]
        # }
        # return jsonify(response)

    # STEP 3: Always show a "Contact Career Center" button with every response
    # response = {
        # "text": resp_text,
        # "attachments": [
            # {
                # "title": "Need more career support?",
                # "text": "Click below to contact the Career Center.",
                # "actions": [
                    # {
                        # "type": "button",
                        # "text": "📅 Schedule a Meeting",
                        # "msg": "career_support_clicked",
                        # "url": "https://careers.tufts.edu/channels/see-an-advisor/",
                        # "msg_in_chat_window": False
                    # }
                # ]
            # }
        # ]
    # }

    # return jsonify(response)
    


    return jsonify({"text": resp_text})
