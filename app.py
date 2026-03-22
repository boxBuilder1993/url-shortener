import json
import os
import random
import string
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, request

app = Flask(__name__)

URLS_FILE = os.path.join(os.path.dirname(__file__), "urls.json")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")


def load_urls():
    if not os.path.exists(URLS_FILE):
        return {}
    with open(URLS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_urls(urls):
    with open(URLS_FILE, "w") as f:
        json.dump(urls, f, indent=2)


def generate_code(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True)

    if data is None or "url" not in data:
        return jsonify({"error": "Missing 'url' field in request body"}), 400

    original_url = data["url"]

    if not isinstance(original_url, str) or not original_url.strip():
        return jsonify({"error": "Invalid URL: must be a non-empty string"}), 400

    if not is_valid_url(original_url):
        return jsonify({"error": "Invalid URL: must start with http:// or https:// and have a valid domain"}), 400

    urls = load_urls()

    # Generate a unique code
    code = generate_code()
    while code in urls:
        code = generate_code()

    urls[code] = original_url
    save_urls(urls)

    return jsonify({
        "short_code": code,
        "short_url": f"{BASE_URL}/{code}",
    }), 201


@app.route("/<code>", methods=["GET"])
def redirect_to_url(code):
    urls = load_urls()

    if code not in urls:
        return jsonify({"error": f"Short code '{code}' not found"}), 404

    return redirect(urls[code], code=302)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
