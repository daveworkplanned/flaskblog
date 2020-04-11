from flask import Flask
app = Flask(__name__)


@app.route("/")
def hello():
    return "What's <u>with</u> all that jibber jabber?"

if __name__ == '__main__':
      app.run(host='http://35.230.92.154/', port=80)