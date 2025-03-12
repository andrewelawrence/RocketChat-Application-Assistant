# upload.py 
# Manually add files to the common app RAG directory
# Note that this can only be used with .pdf files

import os, sys
from config import get_logger
from llmproxy import pdf_upload

_LOGGER = get_logger(__name__)
_SID = os.environ.get("guidesSid")

def _help():
    help_text = """Usage: python upload.py /path/to/file.pdf [path/to/file_2.pdf] ...
    
    This script uploads one or more PDF files to the ResumAI common RAG session.
    
    Arguments:
      -h, --help    Show this help message and exit.
    
    Example:
      python upload.py /path/to/file_1.pdf /path/to/file_2.pdf
    """
    print(help_text)
    sys.exit(0)

if __name__ == "__main__":
    # Check for help argument
    if "-h" in sys.argv or "--help" in sys.argv:
        _help()

    # Ensure at least one file path is provided
    if len(sys.argv) < 2:
        print("Error: Provide at least one filepath. Use -h for help.")
        sys.exit(1)

    fps = sys.argv[1:]

    for fp in fps:
        try:
            # If not absolute, check if it exists relative to cwd
            if not os.path.isabs(fp):
                p_fp = os.path.join(os.getcwd(), fp)
                if os.path.exists(p_fp):
                    _LOGGER.info(f"Resolved relative path: {fp} -> {p_fp}")
                    fp = p_fp
                else:
                    raise FileNotFoundError(f"File not found (absolute or relative): {fp}")

            # Ensure it's a PDF
            if not fp.lower().endswith(".pdf"):
                _LOGGER.error(f"Skipping {fp}: Not a PDF file.")
                continue

            _LOGGER.info(f"Uploading: {fp}")

            resp = pdf_upload(
                path=fp,
                session_id=_SID,
                strategy='smart'
            )
            _LOGGER.info(f"Response for {fp}: {resp}")
            print(f"Upload successful: {fp}")

        except FileNotFoundError as e:
            _LOGGER.error(str(e))
            print(str(e))
        except Exception as e:
            _LOGGER.error(f"Failed to upload {fp}: {str(e)}")
            print(f"Upload failed: {fp}")

    print("Upload process completed.")
    