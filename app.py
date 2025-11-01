from flask import Flask
import os # Import the os module

app = Flask(__name__)

@app.route('/')
def hello_world():
    return "Hello, World! My website is live!"

# This part is slightly different for a live server
if __name__ == "__main__":
    # Render will set the PORT environment variable for us
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)