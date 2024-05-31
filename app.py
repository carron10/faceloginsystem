from shutil import rmtree
from pathlib import Path
import os
from flask import Flask, render_template, request, send_file, jsonify, session
import re
import uuid
from flask import (Flask, render_template, request)
from flask_security import (Security, SQLAlchemyUserDatastore)
from PIL import Image, ImageDraw
# from flask_session import Session
import numpy as np
from models import Role, User, db, UserTokens
from flask import Flask, request, send_from_directory
import face_recognition
from flask_socketio import SocketIO, emit, disconnect, send
from PIL import Image
import io
import base64
from flask_cors import CORS, cross_origin
import os
from tempfile import mkdtemp
from flask_session import Session


app = Flask(__name__, static_url_path='',
            static_folder='static', template_folder='templates')
app.config.from_pyfile('config.py')
db.init_app(app)

socketio = SocketIO(app, cors_allowed_origins="*", path='/websocket')
# Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)

security = Security(app, user_datastore)

REGISTER_IMAGE_SAMPLE_COUNT = 10
# Allow CORS for SocketIO routes
cors = CORS(app, origins=[r"*"], resources={r"/*": {"origins": r"*"}})


# app.config["SESSION_FILE_DIR"] = mkdtemp()
# app.config["SESSION_PERMANENT"] = False
# app.config["SESSION_TYPE"] = "filesystem"
# Session(app)


def detectFace(img_binary):
    # Convert the base64 image data to a PIL Image object
    image = Image.open(io.BytesIO(img_binary))

    # Convert the PIL Image to an RGB image (required by face_recognition)
    rgb_image = image.convert('RGB')

    # Convert the RGB image to a numpy array
    image_array = np.array(rgb_image)

    # Detect faces in the image
    face_locations = face_recognition.face_locations(image_array)

    return face_locations, image

    # Draw a box around each detected face
    # draw = ImageDraw.Draw(image)
    # for face_location in face_locations:
    #     top, right, bottom, left = face_location
    #     draw.rectangle([left, top, right, bottom],
    #                    outline='red', width=3)
    # Save the modified image to a BytesIO object
    # output_image = io.BytesIO()
    # image.save(output_image, format='JPEG')
    # output_image.seek(0)
    # output_base64 = base64.b64encode(
    #     output_image.getvalue()).decode('utf-8')
    # Return the modified image as a file attachment
    # return jsonify({'processedImage': output_base64})


@app.route('/api/face_login', methods=['POST'])
def image_login():
    # try:
    data = request.get_json()
    user_email = None

    if "email" in data:
        user_email = data['email']

    if not user_email:
        return jsonify({'error': "No email provided"}), 404

    user_folder = f"./user_faces/{user_email}"

    if not os.path.exists(user_folder):
        return jsonify({'error': "User face images folder not found"}), 404

    user = UserTokens.query.filter(UserTokens.email == user_email).first()

    if not user:
        return jsonify({'error': "The user email doesn't exist"}), 404

    if 'pic' in data and data['pic'] is not None:
        image_data = data['pic'].split(',')[1]
        img_binary = base64.b64decode((image_data + "==").encode('utf-8'))

        image = Image.open(io.BytesIO(img_binary))
        rgb_image = image.convert('RGB')
        image_array = np.array(rgb_image)

        
        unkown_face_encoding = face_recognition.face_encodings(image_array)
        if len(unkown_face_encoding) == 0:
            return jsonify({'message': 'No face detected in the provided image'}), 404
        
        known_face_encodings = []
        for filename in os.listdir(user_folder):
            image_path = os.path.join(user_folder, filename)
            known_image = face_recognition.load_image_file(image_path)
            face_encoding = face_recognition.face_encodings(known_image)
            if face_encoding:
                known_face_encodings.append(face_encoding[0])
                results = face_recognition.compare_faces(
                    [face_encoding[0]], unkown_face_encoding[0])
                if results[0] == True:
                    return jsonify({'message': 'Face recognized, login successful'}), 200

        
        return jsonify({'message': 'Face not recognized, login failed'}), 500
    else:
        return jsonify({'error': 'No image data found in the request'}), 500
    # except Exception as e:
    #     return jsonify({'error': str(e)}), 500


@app.route('/api/face_detection/', methods=['POST'])
def process_image():
    data = request.get_json()
    email = None

    if "email" in data:
        email = data['email']
    else:
        return "No email specified", 404
    # Check if the user already registered
    existing_user = UserTokens.query.filter(UserTokens.email == email).first()
    if not existing_user:
        return "User not exist", 500

    # Extract the base64-encoded image data from the form field "pic"
    if 'pic' in data and data['pic'] is not None:
        # Extract the base64 encoded image data from the JSON
        image_data = data['pic'].split(',')[1]
        # Decode the base64 image data
        img_binary = base64.b64decode((image_data + "==").encode('utf-8'))
        # Convert the decoded image data into a PIL Image object

        face_locations, image = detectFace(img_binary)
        # image_name = str(uuid.uuid4()) + ".jpg"
        if face_locations:
            return jsonify({'faceLocation': face_locations})
        else:
            return jsonify({'error': 'No Face Found'}), 404
    else:
        return 'No image data found in the request', 500


@socketio.on('reconnect')
def handle_connect():
    email = request.args.get('email')

    if not email:
        disconnect()
        return

    # Check if the user already registered
    existing_user = UserTokens.query.filter(UserTokens.email == email).first()
    if existing_user:
        print("User reconnected")
        try:
            db.session.delete(existing_user)
            # Check if the directory exists and remove it
            directory_path = Path(f"./user_faces/{email}")
            if directory_path.exists():
                rmtree(directory_path)
        except Exception as e:
            print(f"Error deleting user {email}: {e}")
        return
    emit("register_image_sample", REGISTER_IMAGE_SAMPLE_COUNT)
# Update the session
    session['recognised_image_count'] = 0
    session['email'] = email


@socketio.on('connect')
def handle_connect():
    email = request.args.get('email')

    if not email:
        disconnect()
        return
    re_register = request.args.get('re_register')

    # Check if the user already registered
    existing_user = UserTokens.query.filter(UserTokens.email == email).first()
    if existing_user:
        print("User already exist")
        if re_register:

            try:
                db.session.delete(existing_user)
                # Check if the directory exists and remove it
                directory_path = Path(f"./user_faces/{email}")
                if directory_path.exists():
                    rmtree(directory_path)
            except Exception as e:
                print(f"Error deleting user {email}: {e}")
        else:
            emit("user_exist_error", "Error user already registered")
            db.session.commit()
            return
    emit("register_image_sample", REGISTER_IMAGE_SAMPLE_COUNT)
# Update the session
    session['recognised_image_count'] = 0
    session['email'] = email


@socketio.on('disconnect')
def handle_disconnect():
    session.pop("email", None)
    print('Client disconnected')


token_received = False


def register_token_received():
    token_received = True


@app.route("/remove/<email>")
def remove(email):

    try:
        existing_user = UserTokens.query.filter(
            UserTokens.email == email).first()
        if not existing_user:
            return "User Does not Exist", 404
        db.session.delete(existing_user)
        # Check if the directory exists and remove it
        directory_path = Path(f"./user_faces/{email}")
        if directory_path.exists():
            rmtree(directory_path)
        return "Done", 200
    except Exception as e:
        return f"Error deleting user {email}: {e}", 5000


@socketio.on('image')
def handle_image(image_data):

    # try:
    email = session['email']
    # Decode base64 image data
    image_data = image_data.split(',')[1]
    img_binary = base64.b64decode((image_data + "==").encode('utf-8'))
    face_locations, image = detectFace(img_binary)
    image_name = str(uuid.uuid4()) + ".jpg"

    def get_token():
        if "user_token" in session:
            return session['user_token']
        else:
            existing_user = UserTokens.query.filter(
                UserTokens.email == email).first()
            return existing_user.token
    if face_locations:
        # Save images
        os.makedirs(f"./user_faces/{email}/", exist_ok=True)
        image.save(f"./user_faces/{email}/{image_name}")

        recognised_images = session['recognised_image_count']
        recognised_images += 1
        session['recognised_image_count'] = recognised_images
        # Send face locations to all connected clients

        if recognised_images >= REGISTER_IMAGE_SAMPLE_COUNT:
            if 'alread_registered' in session:
                socketio.emit('faceLocation', {
                              'loc': face_locations, 'register_token': get_token()})
                return

            session['alread_registered'] = True
            token = str(uuid.uuid4())
            user = UserTokens(email=email, token=token)
            db.session.add(user)
            db.session.commit()
            session['user_token'] = token
            socketio.emit('faceLocation', {
                          'loc': face_locations, 'register_token': token})
        else:
            socketio.emit('faceLocation', {'loc': face_locations})
    # except Exception as e:
    #     print("Error", str(e))


@app.route("/")
def home():
    return "This app is running"


with app.app_context():
    db.create_all()
    # build_sample_db(app,user_datastore)
