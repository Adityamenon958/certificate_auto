import base64
import os
import json
import re
import smtplib
from datetime import datetime
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from flask import Flask, render_template
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pdfkit
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)

# Read Google Service Account credentials from environment variables
CREDS_FILE = {
    "type": os.getenv("GOOGLE_TYPE"),
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID_UNI"),
    "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
    "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_CERT_URL"),
    "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN"),
}

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

# Sheet and template configuration
SHEET_NAME = os.getenv("SHEET_NAME", "Jolly Phonics Users")
TEMPLATE_NAME = os.getenv("TEMPLATE_NAME", "certificate_template.html")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "certificates")

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

def normalize_time_string(time_str):
    """Convert various time formats or Google Sheets float to HH:MM (24-hour) string."""
    if isinstance(time_str, float) or isinstance(time_str, int):
        # Google Sheets stores times as fraction of a day
        seconds = int(round(float(time_str) * 24 * 60 * 60))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    if not isinstance(time_str, str):
        time_str = str(time_str)
    time_str = time_str.strip()
    # Try parsing as 24-hour or 12-hour with AM/PM
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(time_str, fmt).strftime("%H:%M")
        except ValueError:
            continue
    # Try extracting just HH:MM from a longer string
    match = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    return time_str  # fallback

def send_email(receiver_email, certificate_path, name, course, month):
    try:
        # Compose the email body
        unsubscribe_link = os.getenv("UNSUBSCRIBE_LINK", "https://leveluponline.shop/")
        message_with_unsubscribe = f"""
        <html>
        <body>
            <p>Dear {name},</p>
            <p>Congratulations! You have successfully completed the {course} course on {month}.</p>
            <p>Please find your certificate attached.</p>
            <br><br>
            <p style="font-size:12px;color:gray;">
                If you no longer wish to receive emails, you can <a href="{unsubscribe_link}">unsubscribe here</a>.
            </p>
        </body>
        </html>
        """
        # Set up the MIME structure for the email
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = f"Certificate of Achievement: {course}"
        # Attach the HTML message
        msg.attach(MIMEText(message_with_unsubscribe, "html"))
        # Attach the certificate PDF
        with open(certificate_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename={os.path.basename(certificate_path)}")
            msg.attach(part)
        # Initialize SMTP server and send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
            print(f"[SUCCESS] Certificate sent to {name} at {receiver_email}")
    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP error while sending to {name}: {str(e)}")
        raise
    except Exception as e:
        print(f"[ERROR] Failed to send email to {name}: {str(e)}")
        raise

def generate_all_certificates():
    print(f"[SCHEDULER] Running certificate generation at {datetime.now(ZoneInfo('Asia/Kolkata'))}")

    # Configure wkhtmltopdf path (Linux path for Docker container)
    config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(CREDS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    records = sheet.get_all_records()

    if not records:
        print("[INFO] No user data found in the sheet.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    current_date = now.date()
    current_time = now.strftime("%H:%M")

    # Find the column index for "Certificate Sent"
    cert_sent_col = None
    headers = sheet.row_values(1)
    for idx, header in enumerate(headers, start=1):
        if header.strip().lower() == "certificate sent":
            cert_sent_col = idx
            break

    for row_idx, data in enumerate(records, start=2):  # start=2 because row 1 is header
        print("DEBUG ROW:", data)
        name = data["Name"]
        course = data["Course"]
        month = data["Month"]
        date_of_completion = data.get("Date of Completion", "").strip()
        time_of_completion = str(data.get("Scheduled Time", "")).strip()
        time_of_completion = normalize_time_string(time_of_completion)
        email = data["Email"]
        cert_sent = (data.get("Certificate Sent") or "No").strip().lower()

        # Skip if already sent
        if cert_sent == "yes":
            print(f"[INFO] Certificate already sent for {name}, skipping.")
            continue

        # Skip empty rows or rows with missing critical data
        if not name.strip() or not email.strip() or not date_of_completion.strip() or not time_of_completion.strip() or not course.strip() or not month.strip():
            print(f"[ERROR] Skipping incomplete record for {name}. Data: {data}")
            # Mark as not sent in the sheet if possible
            if cert_sent_col:
                sheet.update_cell(row_idx, cert_sent_col, "No")
            continue

        print(f"Processing {name}: Date = '{date_of_completion}', Time = '{time_of_completion}'")

        # Parse the date and time
        try:
            completion_date = datetime.strptime(date_of_completion, "%m/%d/%Y").date()
        except ValueError:
            print(f"[ERROR] Invalid date format for {name}: {date_of_completion}")
            continue

        # Only send the email if today's date and time matches the scheduled time
        if completion_date == current_date and current_time == time_of_completion:
            # Encode logo image as base64
            with open("static/images/logo.png", "rb") as image_file:
                logo_data_url = f"data:image/png;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"

            # Encode certify.png
            with open("static/images/certify.png", "rb") as image_file:
                certify_data_url = f"data:image/png;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"
                
            with open("static/images/sign.png", "rb") as image_file:
                signature_data_url = f"data:image/png;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"

            # Render the HTML certificate
            rendered = render_template(TEMPLATE_NAME, name=name, course=course, month=month, logo_url=logo_data_url, certify_url=certify_data_url, signature_url=signature_data_url)

            # Create output path and generate PDF
            safe_name = name.replace(" ", "_")
            output_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{course}_{month}.pdf")
            options = {
                'enable-local-file-access': None,
                'no-stop-slow-scripts': '',
                'quiet': '',
                'margin-top': '0mm',
                'margin-bottom': '0mm',
                'margin-left': '0mm',
                'margin-right': '0mm',
                'page-width': '215mm',
                'page-height': '158mm',
                'dpi': '300',
            }

            pdfkit.from_string(rendered, output_path, configuration=config, options=options)
            email_sent = False
            try:
                send_email(email, output_path, name, course, month)
                print(f"[SUCCESS] Certificate saved and sent for {name}: {output_path}")
                email_sent = True
            except Exception as e:
                print(f"[ERROR] Failed to send email to {name}: {str(e)}")
                email_sent = False  # Explicitly set to False on error

            # Mark as sent in the sheet only if email was sent
            if cert_sent_col:
                sheet.update_cell(row_idx, cert_sent_col, "Yes" if email_sent else "No")

# === Scheduler ===
def start_scheduler(app):
    timezone = ZoneInfo("Asia/Kolkata")
    scheduler = BackgroundScheduler(timezone=timezone)

    def scheduled_task():
        with app.app_context():
            print(f"[SCHEDULER] Running certificate generation at {datetime.now(timezone)} (Asia/Kolkata)")
            generate_all_certificates()

    trigger = CronTrigger(minute="*", timezone=timezone)  # Run every minute
    scheduler.add_job(scheduled_task, trigger, misfire_grace_time=60)
    scheduler.start()
    print(f"[INFO] Scheduler started at {datetime.now(timezone)} (Asia/Kolkata)")

# Start scheduler immediately after creating app
start_scheduler(app)

# Simple health check route
@app.route("/")
def health():
    return {"status": "Certificate generation service is running", "time": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()}

if __name__ == "__main__":
    print("[INFO] Starting Certificate Generation Service...")
    print(f"[INFO] Sheet Name: {SHEET_NAME}")
    print(f"[INFO] Output Directory: {OUTPUT_DIR}")
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)), debug=False)