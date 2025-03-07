# email_service.py
import os
import logging
from postmarker.core import PostmarkClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
POSTMARK_API_KEY = os.getenv("POSTMARK_API_KEY")
if not POSTMARK_API_KEY:
    raise ValueError("POSTMARK_API_KEY not found in environment variables")

# Initialize Postmark client
postmark = PostmarkClient(server_token=POSTMARK_API_KEY)

def send_email(to_email, subject, body):
    try:
        response = postmark.emails.send(
            From="dakshinasree.sreekumar@alpharithm.com",
            To=to_email,
            Subject=subject,
            HtmlBody=body
        )
        logger.info(f"Email sent to {to_email}: {response}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
