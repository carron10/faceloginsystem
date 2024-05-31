from app import app
import logging
if __name__ == "__main__":
    # Start scheduler on new Thread
    # context = ('/etc/letsencrypt/live/tekon.co.zw/fullchain.pem', '/etc/letsencrypt/live/tekon.co.zw/privkey.pem')#certificate and key files
    # app.run(debug=True, ),
    app.run(debug=True,host="0.0.0.0",port=5000)
