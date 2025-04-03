import imaplib
import email
from email.header import decode_header
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import re
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
print("💡 Bot wurde gestartet am", datetime.now())


env_path = Path(__file__).resolve().parent / "safedaten.env"
print("Aktueller Pfad:", Path(__file__).resolve().parent)
print("ENV-Datei vorhanden:", os.path.exists(env_path))


print("📬 Starte get_cyber_emails...")

# **E-Mail- & API-Zugangsdaten laden**

load_dotenv(dotenv_path=env_path)

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# **DEBUGG**
print("EMAIL_ACCOUNT:", EMAIL_ACCOUNT)
print("EMAIL_PASSWORD:", EMAIL_PASSWORD)
print("GEMINI_API_KEY:", GEMINI_API_KEY)

if not EMAIL_ACCOUNT or not EMAIL_PASSWORD or not GEMINI_API_KEY:
    print("❌ Fehler: Zugangsdaten oder API-Key nicht geladen.")
    exit()

# **Google Gemini API konfigurieren**
genai.configure(api_key=GEMINI_API_KEY)

IMAP_SERVER = "imap.ionos.de"
SMTP_SERVER = "smtp.ionos.de"
SMTP_PORT = 587

RECIPIENTS_GERMAN = ["Jonathan.fuerst@regelwerk.ai", "alex.fuerst@regelwerk.ai", "20fuersti03@gmail.com"]
RECIPIENTS_ENGLISH = ["Jonathan.fuerst@regelwerk.ai", "alex.fuerst@regelwerk.ai"]

FILTERED_SENDERS = [
    "info@bleepingcomputer.com", "alerts@cisa.gov", "newsletter@thehackernews.com",
    "updates@darkreading.com", "news@cyberscoop.com", "rss@krebsonsecurity.com", "algorithm@technologyreview.com", 
    "jack@jack-clark.net", "daily@aidaily.us", "newsletter@thegradient.pub", "noreply@deepmind.com", "20fuersti03@gmail.com"
]

def get_cyber_emails():
    print("✅ Login erfolgreich.")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")
    except imaplib.IMAP4.error:
        print("❌ Login fehlgeschlagen!")
        exit()

    _, messages = mail.search(None, "UNSEEN")
    email_texts = []

    for msg_num in messages[0].split():
        _, msg_data = mail.fetch(msg_num, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                raw_sender = msg.get("From", "")
                sender_match = re.search(r"<(.+?)>", raw_sender)
                sender = sender_match.group(1).lower() if sender_match else raw_sender.lower()

                subject, encoding = decode_header(msg.get("Subject", ""))[0]
                subject = subject.decode(encoding) if encoding else subject

                if sender in FILTERED_SENDERS:
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body_bytes = part.get_payload(decode=True)
                                if body_bytes:
                                    body = body_bytes.decode(errors="ignore")
                                    break
                    else:
                        body_bytes = msg.get_payload(decode=True)
                        if body_bytes:
                            body = body_bytes.decode(errors="ignore")

                    email_texts.append(f"📩 **{subject}**\n{body}")

    mail.logout()
    return "\n\n".join(email_texts)

def summarize_content(content, language="de"):
    if not content:
        return "Heute gab es keine relevanten Cybersecurity-Meldungen."
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = (
            f"Fasse die folgenden Nachrichten prägnant und verständlich zusammen, um sie in einem professionellen Newsletter von Regelwerk zu präsentieren. Die Zusammenfassung soll informativ, gut strukturiert und leicht verständlich sein. Achte darauf, dass die wichtigsten Kernpunkte und relevanten Entwicklungen enthalten sind. Halte den Stil seriös, aber ansprechend. Falls notwendig, kannst du Überschriften oder Absätze zur besseren Lesbarkeit nutzen.\n\n{content}"
            if language == "de" else
            f"Summarize the following news concisely and clearly for inclusion in Regelwerk's professional newsletter. The summary should be informative, well-structured, and easy to understand. Ensure that the key points and relevant developments are highlighted. Maintain a serious yet engaging tone. If necessary, use headings or paragraphs to enhance readability in english\n\n{content}"
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"⚠ Gemini Fehler: {e}")
        return "Heute gab es keine relevanten Cybersecurity-Meldungen."

def send_newsletter(summary, recipients, language):
    subject = "📰 Werklich Informiert – Der Regelwerk Report!" if language == "de" else "📰 Rule the Werk – Stay Informed!"
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    html_summary = summary.replace("\n", "<br>")  # FIXED: vorher ausgelagert

    html_content = f"""
    <html>
    <body style='font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;'>
        <div style='max-width: 600px; background: white; padding: 20px; border-radius: 8px;'>
            <h2 style='color: #333; text-align: center;'>🛡️ {subject}</h2>
            <hr style='border: 1px solid #ddd;'>
            <p style='color: #555; line-height: 1.6;'>{html_summary}</p>
            <hr style='border: 1px solid #ddd;'>
            <p style='text-align: center; color: #888;'>© 2024 Regelwerk AI – Alle Rechte vorbehalten.</p>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_content, "html"))

    try:
        print("🔐 Verbinde mit SMTP:", SMTP_SERVER, SMTP_PORT)
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ACCOUNT, recipients, msg.as_string())
        print(f"✅ Mail erfolgreich verschickt an {recipients}")
        server.quit()
        print(f"✅ Cyber-Newsletter ({language}) versendet!")
    except Exception as e:
        print(f"❌ Fehler beim Versand ({language}): {e}")

if __name__ == "__main__":
    print("🚀 Starte tägliche Cybersecurity-Analyse...")

    emails = get_cyber_emails()
    print("📥 Eingegangene Mails:", emails[:500])

    summary_de = summarize_content(emails, "de")
    print("📝 Deutsche Zusammenfassung:\n", summary_de)

    summary_en = summarize_content(emails, "en")
    print("📝 Englische Zusammenfassung:\n", summary_en)

    send_newsletter(summary_de, RECIPIENTS_GERMAN, "de")
    print(f"📤 Bereite Versand vor ")
    send_newsletter(summary_en, RECIPIENTS_ENGLISH, "en")
