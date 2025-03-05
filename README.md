# Koyeb-mini-1
[![Rocket.Chat](https://img.shields.io/badge/Rocket.Chat-rocketdotchat?logo=rocketdotchat&logoSize=auto&labelColor=white&color=white)](https://docs.rocket.chat/docs/rocketchat)
[![Koyeb](https://img.shields.io/badge/Koyeb-Koyeb?logo=Koyeb&logoColor=white&logoSize=auto&labelColor=black&color=black
)](https://www.koyeb.com/docs/build-and-deploy/cli/reference)
[![Flask](https://img.shields.io/badge/Flask-flask?logo=flask&logoColor=black&logoSize=auto&labelColor=white&color=blue)](https://flask.palletsprojects.com/en/stable/)
[![LLMProxy](https://img.shields.io/badge/LLMProxy-LLMProxy?logo=github&logoColor=white&labelColor=black&color=lightgray)](https://github.com/Tufts-University/LLMProxy)
[![Python](https://img.shields.io/badge/python-3.12.8-blue.svg)](https://www.python.org/downloads/)

Koyeb-mini-1 hosts a job application AI assistant via the Tufts University LLMProxy module. The chatbot is hosted on [Koyeb](https://www.koyeb.com/) and served to the CS 0150 [Rocket.chat](https://chat.genaiconnect.net/group/CS150) platform.

## First-time setup
Clone repository:
```bash
git clone https://github.com/andrewelawrence/Koyeb-mini-1
cd Koyeb-mini-1
```
Install packages (consider using a python venv):
```bash
pip install -r requirements.txt
```
Install Koyeb CLI (optional):
```bash
sudo apt install koyeb
koyeb login
```
Prep test script:
```bash
chmod +x test.sh
```

## Contribute
See the [Features](#features) section for areas of development.

## Test
In order to avoid tedious redeployment on Koyeb, execute the following to test the service:
```bash
./test.sh
```
This will create a locally hosted flask web-app that runs the chatbot without Koyeb and automatically reloads content on refresh. (Default address is [127.0.0.1:5000](127.0.0.1:5000), visit `config\.env` to change this.)

## Deploy
This repository is currently deployed as `BOT-Andrew` on [Rocket.chat](https://chat.genaiconnect.net/group/CS150). If you'd like to deploy it on your own Koyeb instance:
```bash
koyeb deploy -h
```
Or if it's already deployed:
```bash
koyeb service redeploy <service-name>
```
Make sure you have updated your Koyeb Secrets!

## Architecture
- **Front-end:** Rocket.Chat
- **Hosting:** Koyeb  
- **Database:** AWS DynamoDB & S3  
- **Core Packages:**  
  - **LLMProxy:** AI Chatbot  
  - **boto3:** AWS integration
  - **Flask:** Web-app structure & testing  

## Features
### Current Capabilities
- **Koyeb Deploy & Rocket.Chat Integration**  
- **Test/Dev Environment**

### Roadmap
- **User Interaction Logging:**  
  Interfaces with AWS S3 and DynamoDB to store user data and log interactions.
- **AI Chatbot Integration:**  
  Uses LLMProxy to handle AI responses. Chatbots are programmed with agency — if they detect a need, they can suggest human intervention via the Tufts Career Center.   
- **Contextual Conversations:**  
   Enable users to add context to their conversations by uploading resumes, entering job application details, or linking to external applications.
- **Proactive Human Assistance:**  
   Equip the chatbot to autonomously suggest and redirect users to the Tufts Career Center for further help if needed.
- **Multiple Repositories per User:**  
   Allow users to manage distinct, self-contained job application "repositories". Users can select an application to continue or create a new one.
