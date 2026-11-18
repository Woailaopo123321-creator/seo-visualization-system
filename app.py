from flask import Flask, render_template, jsonify

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/mobile")
def mobile():
    return render_template("mobile_control.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
