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
    _LOGGER.info(f"Processing query for session {sid} - Message: {msg}")

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

    # Extract sources and determine if expert review is needed
    sources = response.get("sources", [])
    major_edit_required = "significant rewording" in response["response"].lower() or response.get("low_confidence", False)

    # Add expert review button if necessary
    buttons = []
    if major_edit_required:
        _LOGGER.info(f"Suggesting expert review for session {sid}.")
        buttons.append({
            "type": "button",
            "text": "📨 Consult a Resume Expert",
            "msg": "send_to_specialist",
            "msg_in_chat_window": True,
            "msg_processing_type": "sendMessage"
        })

    # Format response with RAG context if available
    context_summary = f"🔎 **Relevant Context Used:**\n{'\n'.join([f'- {s}' for s in sources])}" if sources else ""
    final_response = f"{response['response']}\n\n{context_summary}" if context_summary else response['response']

    _LOGGER.info(f"Final response for session {sid}: {final_response}")

    return jsonify({
        "text": final_response,
        "attachments": [{"title": "Next Steps", "actions": buttons}] if buttons else []
    })


def respond(msg: str, sid: str, has_urls: bool, urls_failed: list):

    # Handling resume section updates
    if msg.lower().startswith("create_") or msg.lower().startswith("edit_"):
        section = msg.split("_")[1]  
        user_input = msg[len(f"{section}_"):]  

        if not user_input.strip():
            return jsonify({"text": "❌ Please provide details for your resume section."})

        # Update resume summary
        formatted_summary = update_resume_summary(sid, section, user_input)

        return jsonify({
            "text": "Got it! Your resume has been updated.\n\nWould you like to send this for expert review?",
            "attachments": [
                {
                    "title": "Review Options",
                    "actions": [
                        {
                            "type": "button",
                            "text": "📨 Consult a Resume Expert",
                            "msg": "send_to_specialist",
                            "msg_in_chat_window": True,
                            "msg_processing_type": "sendMessage"
                        }
                    ]
                }
            ]
        })

    # **User Requests Expert Review**
    elif msg == "send_to_specialist":
        send_resume_for_review(sid)
        return jsonify({
            "text": "📨 Your resume has been sent to a career specialist for review!"
        })
    
    # **Expert Approves Resume**
    elif msg.startswith("approve_"):
        return jsonify({
        "text": "🎉 Your resume has been approved by the career specialist! You’re all set! ✅"
        })
    
    # **Expert Denies Resume**
    elif msg.startswith("deny_"):
        return jsonify({
            "text": "🔄 The career specialist has requested some changes. Let's go back and refine your resume together!"
        })
    
    else:
        return query(msg, sid, has_urls, urls_failed)

