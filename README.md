# Rocket.Chat Job Application LLM Assistant Gateway via Koyeb

RocketChat-Application-Assistant hosts a job application AI assistant deployed to Koyeb that connects Rocket.Chat to an early, non-distributed version of LLMProxy used in the paper [LLMProxy: Reducing Cost to Access Large Language Models](https://arxiv.org/pdf/2410.11857). Originally used to test out hosting chatbots on Rocket.Chat and has since been abandoned.

## First-time setup
Clone repository:
```bash
git clone https://github.com/andrewelawrence/RocketChat-Application-Assistant
cd RocketChat-Application-Assistant

pip install -r requirements.txt

sudo apt install koyeb
koyeb login

# redeploy example (replace with your service name)
koyeb service redeploy <your-org>/<your-service-name>
```

## Testing
With environment set (see `config/.env`), you can run:
```bash
chmod +x test.sh
./test.sh
```
This loads env vars and starts the Flask web-app locally. If `flaskEnv=dev` and `flaskPage` are set, a simple dev page is available at `/dev` (default address is [127.0.0.1:5000](127.0.0.1:5000), visit `config\.env` to change this.); otherwise, POST to `/query`.

## Project structure
- `app.py`: Flask app, routes (`/query`, `/dev`, `/`)
- `chat.py`: Welcome text and LLM response assembly
- `response.py`: Dispatcher for uploads, resume mode, and general queries
- `llmproxy.py`: Early LLMProxy client
- `utils.py`: AWS DynamoDB session/persistence, Rocket.Chat file handling, helpers
- `config/load_envs.py`: Loads `config/.env` and runs a target script
- `upload.py`: CLI to upload PDFs to the shared RAG session
- `requirements.txt`, `Procfile`, `test.sh`

## Acknowledgements
- Early LLMProxy implementation used here is from the paper: [LLMProxy: Reducing Cost to Access Large Language Models](https://arxiv.org/pdf/2410.11857).