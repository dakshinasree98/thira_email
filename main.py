from flask import Flask, request, jsonify
import os
import sqlite3
import imaplib
import email
import smtplib
import logging
from email.mime.text import MIMEText
from dotenv import load_dotenv
from groq import Groq

# Initialize Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")  # Business email
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # App Password
SMTP_SERVER = "smtp.gmail.com"
IMAP_SERVER = "imap.gmail.com"

if not API_KEY:
    raise ValueError("GROQ_API_KEY not found in environment variables")

groq_client = Groq(api_key=API_KEY)

# Connect to SQLite database
def connect_to_db():
    return sqlite3.connect('emails.db')

# Fetch room details from the database
def fetch_room_availability():
    conn = connect_to_db()
    cursor = conn.cursor()
    cursor.execute("SELECT room_name, availability_status, price FROM room_data")
    rooms = cursor.fetchall()
    conn.close()

    if rooms:
        return "\n".join([f"Room: {room[0]}, Available: {room[1]}, Price: {room[2]}" for room in rooms])
    return "No room details available."

# Classify email queries into 3 categories: Booking Inquiry, General Inquiry, or Complaints
def classify_query(email_body):
    prompt = f"""Classify the following email into one of three categories:
    1. Booking Inquiry - If the email asks about room availability or making a reservation.
    2. General Inquiry - If the email is about general hotel information.
    3. Complaint - If the email is about dissatisfaction or an issue with service.

    Email: {email_body}
    Respond with only the category number (1, 2, or 3)."""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10
    )
    return response.choices[0].message.content.strip()

# Generate AI Response
def generate_response(email_body, context):
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are an AI hotel assistant. Provide polite and professional responses."},
            {"role": "user", "content": f"Email: {email_body}\nContext: {context}"}
        ],
        max_tokens=300
    )
    return response.choices[0].message.content

# Fetch unread emails
def fetch_unread_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("inbox")

        result, data = mail.search(None, "UNSEEN")
        email_ids = data[0].split()

        unread_emails = []
        for email_id in email_ids:
            result, msg_data = mail.fetch(email_id, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            email_from = msg["From"]
            email_subject = msg["Subject"]
            email_body = ""

            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        email_body = part.get_payload(decode=True).decode()
            else:
                email_body = msg.get_payload(decode=True).decode()

            unread_emails.append((email_from, email_subject, email_body))

        mail.logout()
        return unread_emails

    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
        return []

# Send email response
def send_email(to_email, subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email

        server = smtplib.SMTP(SMTP_SERVER, 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()
        logging.info(f"Email sent to {to_email}")

    except Exception as e:
        logging.error(f"Error sending email: {e}")

# Process emails and send automated responses
def process_emails():
    unread_emails = fetch_unread_emails()

    for email_from, subject, body in unread_emails:
        logging.info(f"Processing email from {email_from} - Subject: {subject}")

        query_type = classify_query(body)

        if query_type == "1":
            context = fetch_room_availability()
            response = generate_response(body, context)
        elif query_type == "2":
            context = "Thank you for reaching out! Thira Beach Home offers luxurious stays with modern amenities."
            response = generate_response(body, context)
        elif query_type == "3":  # Complaint handling
            response = "We're very sorry to hear about your experience. The property staff will contact you shortly to resolve the issue."
        else:
            response = "Thank you for reaching out. We will get back to you soon."

        send_email(email_from, f"Re: {subject}", response)

@app.route('/process_emails', methods=['GET'])
def process_email_endpoint():
    process_emails()
    return jsonify({"message": "Email processing completed."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
