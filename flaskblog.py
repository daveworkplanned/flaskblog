from flask import Flask
app = Flask(__name__)


@app.route("/")
def hello():
    return "What's <u>with</u> all that jibber jabber?"
