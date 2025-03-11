# testing manual pdf upload for rag context
# Reminder: export endPint and apiKey env variables before running script
from llmproxy import pdf_upload

if __name__ == "__main__":    
    resp = pdf_upload(
        path = "test_resume.pdf",
        session_id = "5e8882e786",
        strategy = 'smart'
        )
        
    print(resp)