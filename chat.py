# chat.py
# TODO: see query(). 

import os
from flask import jsonify
from config import get_logger
from llmproxy import generate
from utils import safe_load_text, update_resume_summary, send_resume_for_review 

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

    response = {
        "text": welcome,
        "attachments": [
            {
                "title": "Start building your resume",
                "actions": [
                    {
                        "type": "button",
                        "text": "📑 Existing resume",
                        "msg": "resume_edit",
                        "msg_in_chat_window": True,
                        "msg_processing_type": "sendMessage"
                    },
                    {
                        "type": "button",
                        "text": "🆕 New resume",
                        "msg": "resume_create",
                        "msg_in_chat_window": True,
                        "msg_processing_type": "sendMessage"
                    }
                ]
            }
        ]
    }
    return jsonify(response)



# main query function
def query(msg: str, sid: str, 
          has_urls: bool, urls_failed: list):
    """
    TODO: flesh out what we want for capabilities
    file uploading handled, providing sources, linking to career center, etc.
    
    system file def needs to be fleshed out more to be more rigorous and so the
    AI knows what capabilities it has
    """
    
    # load in system from system.txt file
    system = safe_load_text(_SYSTEM)
        
    # TODO Add context to the system for this specific message:
    # (ie. did the url uploads work)

    if has_urls:
        if bool(urls_failed):
            system += (
                """
                \n\n\n
                The user message includes urls whose site content has been uploaded to the session and can be used for RAG context. 
                Use specific information from these documents when questions are about their contents.
                The following sites the user sent failed to upload their page content to the session: 
                """
                + 
                ", ".join([f"[{url}]({url})" for url in urls_failed])
                + 
                "\nMention the specific urls failed to the user and tell them to consider uploading the pages as PDFs._"
            )  
        else:
            system += (
                """
                \n\n\n
                The user message includes urls whose site content has been uploaded to the session and can be used for RAG context. 
                Use specific information from these documents when questions are about their contents.
                """
            )

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

    resp_text = response['response'] + "\n\n[DEV] Rag Context:\n" + response['rag_context']

    response = {
        "text": resp_text,
        "attachments": [
            {
                "title": "Start building your resume",
                "actions": [
                    {
                        "type": "button",
                        "text": "📑 Existing resume",
                        "msg": "resume_edit",
                        "msg_in_chat_window": True,
                        "msg_processing_type": "sendMessage"
                    },
                    {
                        "type": "button",
                        "text": "🆕 New resume",
                        "msg": "resume_create",
                        "msg_in_chat_window": True,
                        "msg_processing_type": "sendMessage"
                    }
                ]
            }
        ]
    }


    return jsonify(response)


def respond(msg: str, sid: str, has_urls: bool, urls_failed: list):

    # Check if the user is working on a resume section
    if msg.lower().startswith("create_") or msg.lower().startswith("edit_"):
        section = msg.split("_")[1]  # Extracts "experience", "education", etc.
    
        # Get the actual user message from Rocket.Chat
        user_input = msg[len(f"{section}_"):]  # Remove "create_" or "edit_" prefix

        if not user_input.strip():
            return jsonify({"text": "❌ Please provide details for your resume section."})

        # Update the resume summary
        formatted_summary = update_resume_summary(sid, section, user_input)

        return jsonify({
            "text": "Got it! Your resume has been updated.\n\nWould you like to send this for review?",
            "attachments": [
                {
                    "title": "Review Options",
                    "actions": [
                        {
                            "type": "button",
                            "text": "✅ Yes, send to career specialist",
                            "msg": "send_to_specialist",
                            "msg_in_chat_window": True,
                            "msg_processing_type": "sendMessage"
                        },
                        {
                            "type": "button",
                            "text": "❌ No, continue editing",
                            "msg": "continue_editing",
                            "msg_in_chat_window": True,
                            "msg_processing_type": "sendMessage"
                        }
                    ]
                }
            ]
        })

    # If the user wants to send to a career specialist
    elif msg == "send_to_specialist":
        send_resume_for_review(sid)  # ✅ Call the function here
        return jsonify({
            "text": "📨 Your resume has been sent to the career specialist for review!"
        })
    
    else:
        return query(msg, sid, has_urls, urls_failed)
