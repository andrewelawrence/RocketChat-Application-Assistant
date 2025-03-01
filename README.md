# Koyeb-mini-1
[![Python](https://img.shields.io/badge/python-3.12.8-blue.svg)](https://www.python.org/downloads/) ![Status](https://img.shields.io/github/deployments/andrewelawrence/Koyeb-mini-1/deployments?logo=%23121212) [![LLMProxy](https://img.shields.io/badge/GitHub-LLMProxy-lightgrey)](https://github.com/Tufts-University/LLMProxy)

## Overview
This repository hosts Python code running on a Koyeb server. It is designed for a Rocket.Chat Bot that users interact with, querying an AI chatbot.

## Architecture
- **Front-end:** Rocket.Chat  
- **Hosting:** Koyeb  
- **Database:** AWS DynamoDB & S3  
- **Core Packages:**  
  - **LLMProxy:** Access to AI Chatbots with supplemental programmatic info  
  - **boto3:** AWS integration
  - **Flask:** For web-app testing  

## Features
### Current Capabilities
- **Rocket.Chat Integration:**  
  Interacts with Rocket.Chat to trigger bot responses.

### Roadmap
- **User Interaction Logging:**  
  Interfaces with AWS S3 and DynamoDB to store user data and interaction logs.

- **AI Chatbot Integration:**  
  Uses LLMProxy to handle AI responses. Chatbots are programmed with agency — if they detect a need, they can suggest human intervention via the Tufts Career Center.
  
- **Multiple Repositories per User:**  
   Allow users to manage distinct, self-contained job application "repositories". Users can select an application to continue or create a new one.
   
- **Contextual Conversations:**  
   Enable users to add context to their conversations by uploading resumes, entering job application details, or linking to external applications.
      
- **Proactive Human Assistance:**  
   Equip the chatbot to autonomously suggest and redirect users to the Tufts Career Center for further help if needed.

## Notes on envrionment variables
Currently set up so that Andrew hosts the instance and integrates the back-end to the Rocket.Chat bot. You're welcome to also change the evironment variables so that you host it yourself.

_Last edit: Andrew Lawrence 03/01/2025_