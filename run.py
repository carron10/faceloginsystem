from app import app
import logging
if __name__ == "__main__":
    # Start scheduler on new Thread
    app.run(debug=True,host="0.0.0.0",port=5000)
