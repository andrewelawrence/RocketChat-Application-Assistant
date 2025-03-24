# chat.py

import os, json
from flask import jsonify, session
from datetime import datetime, timezone
from config import get_logger
from llmproxy import generate
from utils import safe_load_text, update_resume_summary, send_resume_for_review
 

# Setup logger
_LOGGER = get_logger(__name__)

# Model info
_WELCOME = os.environ.get("welcomePage")
_SYSTEM  = os.environ.get("systemPrompt")
_MODEL   = os.environ.get("model")
_TEMP    = os.environ.get("temp")
_LAST_K  = os.environ.get("lastK")
_RAG     = os.environ.get("rag")
_RAG_K   = os.environ.get("ragK")
_RAG_THR = os.environ.get("ragThr")

def welcome(uid: str, user: str):
    """
    Generate and return a welcome message for a new user.

    The welcome text is read from a file defined by the environment variable.
    The response includes buttons for starting or editing a resume.

    Parameters:
        uid (str): The unique identifier of the user.
        username (str): The user's name.

    Returns:
        A Flask JSON response with the welcome message and action buttons.
    """
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


def query(msg: str, sid: str, has_urls: bool, urls_failed: list, rsme: bool, gbl: str):
    """
    Process a user's query and generate a response using the language model.

    The function loads the system prompt from a file, constructs a query payload that
    includes the user's message, guide context, and resume editing flag, then calls the
    language model to generate a response. It also appends action buttons for further steps.

    Parameters:
        msg (str): The user's input message.
        sid (str): The session identifier.
        has_urls (bool): Flag indicating whether URLs were found in the message.
        urls_failed (list): List of URLs that failed during scraping/upload.
        rsme (bool): Flag indicating if resume editing mode is active.
        gbl (str): Additional context guiding the response.

    Returns:
        A Flask JSON response with the generated text and action buttons.
    """
    _LOGGER.info(f"Processing query for session {sid} - Message: {msg}")
    
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
        "gbl_context": gbl,
        "resume_editing": rsme,
        "date": datetime.now(timezone.utc).isoformat(),
        }
    
    _LOGGER.info(f"User Query: {json.dumps(query, separators=(',', ':'))}")    
    query = json.dumps(query, indent=4)

    _LOGGER.info(f"Query parameters: model {_MODEL}, temp: {_TEMP}, lastK: {_LAST_K}, rag_usage: {_RAG}, rag_k: {_RAG_K}, rag_threshold: {_RAG_THR}, session_id: {sid}")
    resp = generate(
        model=str(_MODEL),
        system=str(system),
        query=str(query),
        temperature=float(_TEMP),
        lastk=int(_LAST_K),
        rag_usage=bool(_RAG),
        rag_k=int(_RAG_K),
        rag_threshold=float(_RAG_THR),
        session_id=str(sid),
    )

    _LOGGER.info(f"Response: {resp}")

    try:
        rag = resp.get('rag_context')
        resp = json.loads(resp.get('response', '')) 
            # now resp is exclusively the inner "response"
        section = resp.get('section', "general")
        sources = resp.get('sources', [])
        incl_human = resp.get('human_in_the_loop', False)
        resp = resp.get('response', "An error occurred; notify the team.") 
            # now response is exclusively the innermost "response" - the real message
        _LOGGER.info(f"Response Parsed: rag: {rag}, resp: {resp}, section: {section}, sources: {sources}, human_in_the_loop: {incl_human}")

        # 🧠 Store chat history in session for AI summary later
        if sid not in session:
            session[sid] = {}

        if "chat_log" not in session[sid]:
            session[sid]["chat_log"] = []

        session[sid]["chat_log"].append({"role": "user", "msg": msg})
        session[sid]["chat_log"].append({"role": "bot", "msg": resp})
     
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

        # If AI thinks a human should be looped in, include that button
        _LOGGER.info(f"Human escalation: {incl_human}")
        if incl_human:
            buttons.append({
                "type": "button",
                "text": "📨 Consult a Resume Expert",
                "msg": "send_to_specialist",
                "msg_in_chat_window": True,
                "msg_processing_type": "sendMessage"
            })

        # Format response with RAG context if available
        context_summary = f"🔎 *Sources:*\n{'\n'.join([f'- {s}' for s in sources])}" if sources else ""
        final_response = f"{resp}\n\n{context_summary}" if context_summary else resp

        return jsonify({
            "text": final_response,
            "attachments": [{"title": "Next Steps", "actions": buttons}] if buttons else []
            })
    
    except Exception as e:
        _LOGGER.error(f"An error occurred in the response: {e}")
        return jsonify({"text": "An error occurred in the response. Please try again. If this continues, please notify the team."})


def respond(msg: str, sid: str, has_urls: bool, urls_failed: list, rsme: bool, gbl: str) -> dict:
    """
    Route the incoming user message to the appropriate handler based on its content.

    The function handles:
      - Resume section updates (commands starting with 'create_' or 'edit_').
      - Requests to consult a resume expert.
      - Expert approval or rejection commands.
      - Otherwise, the message is processed as a general query.

    Parameters:
        user_message (str): The user's input message or command.
        session_id (str): The session identifier.
        has_urls (bool): Flag indicating if URLs are present in the message.
        urls_failed (list): List of URLs that failed to process.
        resume_editing (bool): Flag indicating if resume editing mode is active.
        guide_context (str): Additional context or guiding information.

    Returns:
        A Flask JSON response with the appropriate response text and action buttons.
    """
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

        # Call the test function for now
        # test_send_resume_for_review(sid)
        
        # Uncomment this when you want to use the full resume send function
        send_resume_for_review(sid)

        return jsonify({"text": "📨 Your resume has been sent to a career specialist for review!"})


     # 🚨 Expert Response (Approve/Deny)
    elif msg.startswith("approve_") or msg.startswith("deny_"):
        action = "approved" if msg.startswith("approve_") else "requested changes"
        sid = msg.split("_")[1]

        # Retrieve original user channel
        user_channel = session.get(sid, {}).get("channel_id", None)

        if not user_channel:
            _LOGGER.warning(f"No user channel found for session {sid}")
            return jsonify({"text": f"The resume has been {action} by the expert, but we could not notify the user."})

        # Prepare message for user
        user_message = (
            "🎉 Your resume has been approved by the career specialist! You’re all set! ✅"
            if action == "approved" else
            "🔄 The career specialist has requested some changes. Let's go back and refine your resume together!"
        )

        # Send message to user channel via Rocket.Chat API
        try:
            rocket_url = os.getenv("rocketUrl")
            rocket_user_id = os.getenv("rocketUid")
            rocket_token = os.getenv("rocketToken")

            url = f"{rocket_url}/api/v1/chat.postMessage"
            headers = {
                "Content-Type": "application/json",
                "X-Auth-Token": rocket_token,
                "X-User-Id": rocket_user_id
            }
            payload = {
                "channel": f"@{user_name}",
                "text": user_message
            }
            response = requests.post(url, json=payload, headers=headers)
            _LOGGER.info(f"Sent expert response to user channel {user_channel} with code {response.status_code}")
        except Exception as e:
            _LOGGER.error(f"Failed to send expert response to user: {e}", exc_info=True)

        return jsonify({"text": f"✅ Expert decision ({action}) delivered to user channel @{user_channel}."})


    else:
        return query(msg=msg, sid=sid, has_urls=has_urls, urls_failed=urls_failed, 
                     rsme=rsme, gbl=gbl)
