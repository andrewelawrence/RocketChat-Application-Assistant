# chat.py

import os, json
from flask import jsonify
from datetime import datetime, timezone
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
          has_urls: bool, urls_failed: list,
          rsme: bool, gbl_context: str):
    _LOGGER.info(f"Processing query for session {sid} - Message: {msg}")

    """
    file uploading handled, providing sources, linking to career center, etc.
    
    system file def needs to be fleshed out more to be more rigorous and so the
    AI knows what capabilities it has
    """
    
    # load in system from system.txt file
    system = safe_load_text(_SYSTEM)
        
    # TODO: get this working sometime in the future
    # if has_urls:
    #     if bool(urls_failed):
    #         system += (
    #             """
    #             \n\n\n
    #             The user message includes urls whose site content has been uploaded to the session and can be used for RAG context. 
    #             Use specific information from these documents when questions are about their contents.
    #             The following sites the user sent failed to upload their page content to the session: 
    #             """
    #             + 
    #             ", ".join([f"[{url}]({url})" for url in urls_failed])
    #             + 
    #             "\nMention the specific urls failed to the user and tell them to consider uploading the pages as PDFs._"
    #         )  
    #     else:
    #         system += (
    #             """
    #             \n\n\n
    #             The user message includes urls whose site content has been uploaded to the session and can be used for RAG context. 
    #             Use specific information from these documents when questions are about their contents.
    #             """
    #         )

    query = {
        "msg": msg,
        "gbl_context": gbl_context,
        "resume_editing": rsme,
        "date": datetime.now(timezone.utc).isoformat(),
        }
    query = json.dumps(query, indent=4)
    _LOGGER.info(f"User query: {query}")
    
    response = generate(
        model=_MODEL,
        system=system,
        query=query,
        temperature=_TEMP,
        lastk=_LAST_K,
        rag_usage=_RAG,
        rag_k=_RAG_K,
        rag_threshold=_RAG_THR,
        session_id=sid,
    )

    _LOGGER.info(f"RESP: {response}")
    
    resp = json.loads(response)

   # Check if human intervention is needed
    human_in_the_loop = resp.get("human_in_the_loop", False)
    _LOGGER.info(f"Human escalation needed: {human_in_the_loop}")

  # Prepare buttons for user action
    buttons = [{
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
    }]

    if human_in_the_loop:
        _LOGGER.info(f"Suggesting human review for session {sid}.")
        buttons.append({
            "type": "button",
            "text": "📨 Consult a Resume Expert",
            "msg": "send_to_specialist",
            "msg_in_chat_window": True,
            "msg_processing_type": "sendMessage"
        })


    # Format response with RAG context if available
    context_summary = f"🔎 **Relevant Context Used:**\n{'\n'.join([f'- {s}' for s in response.get('sources', [])])}" if response.get("sources") else ""
    final_response = f"{response['response']}\n\n{context_summary}" if context_summary else response['response']

    return jsonify({
        "text": final_response,
        "attachments": [{"title": "Next Steps", "actions": buttons}] if buttons else []
    })


def respond(msg: str, sid: str, has_urls: bool, urls_failed: list,
            rsme: bool, gbl_context: str) -> dict:

    # Handling resume section updates
    if msg.lower().startswith(("create_", "edit_")):
        section = msg.split("_")[1]  
        user_input = msg[len(f"{section}_"):]  

        if not user_input.strip():
            return jsonify({"text": "❌ Please provide details for your resume section."})

        # Update resume summary
        formatted_summary = update_resume_summary(sid, section, user_input)

        return jsonify({
            "text": "✅ Your resume has been updated!",
        })

    # **User Clicks "Consult a Resume Expert" Button (Triggered by human_in_the_loop)**
    elif msg == "send_to_specialist":
        _LOGGER.info(f"User {sid} confirmed sending resume to expert.")
        
        # Actually send the resume for review
        send_resume_for_review(sid)

        return jsonify({
            "text": "📨 Your resume has been sent to a career specialist for review!"
        })

    # **Expert Approves Resume**
    elif msg.startswith("approve_"):
        return jsonify({
            "text": "🎉 Your resume has been approved by the career specialist! You’re all set! ✅"
        })

    # **Expert Requests Changes**
    elif msg.startswith("deny_"):
        return jsonify({
            "text": "🔄 The career specialist has requested some changes. Let's go back and refine your resume together!"
        })

    else:
        return query(msg, sid, has_urls, urls_failed, rsme, gbl_context)
