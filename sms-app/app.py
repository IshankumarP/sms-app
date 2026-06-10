from flask import Flask, request, jsonify, render_template
from android_sms_gateway import client, domain
import csv
import io
import time
import threading

app = Flask(__name__)

# Tracks progress per session (keyed by a simple job_id)
jobs = {}

def parse_csv(file_content):
    """Parse CSV content and return list of phone numbers with +91 added if missing."""
    numbers = []
    errors = []
    text = file_content.decode("utf-8-sig").strip()
    reader = csv.DictReader(io.StringIO(text))

    if "phone" not in [h.lower() for h in reader.fieldnames or []]:
        raise ValueError("CSV must have a column named 'phone'")

    for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
        # Find the phone column case-insensitively
        phone = next((v for k, v in row.items() if k.lower() == "phone"), "").strip()
        phone = phone.replace(" ", "").replace("-", "")

        if not phone:
            errors.append(f"Row {i}: empty phone number, skipped")
            continue

        if not phone.startswith("+"):
            phone = "+91" + phone

        if len(phone) < 10:
            errors.append(f"Row {i}: '{phone}' looks invalid, skipped")
            continue

        numbers.append(phone)

    return numbers, errors


def send_bulk(job_id, login, password, numbers, message, daily_limit):
    """Runs in background thread. Updates jobs[job_id] with live progress."""
    jobs[job_id]["status"] = "running"
    sent = 0
    failed = 0
    log = []

    try:
        with client.APIClient(login, password) as c:
            total = min(len(numbers), daily_limit)
            jobs[job_id]["total"] = total

            for i, phone in enumerate(numbers[:daily_limit], 1):
                try:
                    msg = domain.Message(
                        phone_numbers=[phone],
                        text_message=domain.TextMessage(text=message)
                    )
                    c.send(msg)
                    sent += 1
                    entry = {"phone": phone, "status": "sent"}
                    log.append(entry)
                except Exception as e:
                    failed += 1
                    entry = {"phone": phone, "status": "failed", "error": str(e)}
                    log.append(entry)

                jobs[job_id]["sent"] = sent
                jobs[job_id]["failed"] = failed
                jobs[job_id]["log"] = log
                jobs[job_id]["current"] = i

                time.sleep(3)  # Respect carrier rate limits

        skipped = max(0, len(numbers) - daily_limit)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["skipped"] = skipped

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/send", methods=["POST"])
def send():
    login    = request.form.get("login", "").strip()
    password = request.form.get("password", "").strip()
    message  = request.form.get("message", "").strip()
    limit    = int(request.form.get("limit", 100))
    csv_file = request.files.get("csv_file")

    # Validate
    if not login or not password:
        return jsonify({"error": "SMSGate login and password are required."}), 400
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400
    if not csv_file:
        return jsonify({"error": "Please upload a CSV file."}), 400
    if len(message) > 160:
        return jsonify({"error": f"Message is {len(message)} characters. Standard SMS limit is 160. Shorten it or it may be split into multiple messages."}), 400

    try:
        content = csv_file.read()
        numbers, parse_errors = parse_csv(content)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not read CSV: {str(e)}"}), 400

    if not numbers:
        return jsonify({"error": "No valid phone numbers found in the CSV."}), 400

    # Create a job
    import uuid
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "starting",
        "total": min(len(numbers), limit),
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "current": 0,
        "log": [],
        "parse_errors": parse_errors,
        "all_numbers": len(numbers),
    }

    # Run in background so we can stream progress
    thread = threading.Thread(
        target=send_bulk,
        args=(job_id, login, password, numbers, message, limit),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id, "parse_errors": parse_errors, "total": len(numbers)})


@app.route("/progress/<job_id>")
def progress(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
