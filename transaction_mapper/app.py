from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from config_manager import ConfigManager
from werkzeug.utils import secure_filename
import os
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user
from models import db, User
from forms import RegistrationForm, LoginForm
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
config_manager = ConfigManager('config.json')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = 'your_secret_key'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_first_request
def create_tables():
    db.create_all()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html', config=config_manager.config_data)

@app.route('/update_config', methods=['POST'])
def update_config():
    new_config = request.json
    config_manager.update_config(new_config)
    return jsonify({'status': 'success', 'message': 'Configuration updated successfully'})

@app.route('/upload_transactions', methods=['POST'])
def upload_transactions():
    if 'file' not in request.files:
        return jsonify({'status': 'fail', 'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'fail', 'message': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Process the uploaded file
        transactions_df = pd.read_csv(file_path) if filename.endswith('.csv') else pd.read_excel(file_path)
        # Here you would integrate the transaction processing logic

        return jsonify({'status': 'success', 'message': 'Transactions uploaded successfully'})
    else:
        return jsonify({'status': 'fail', 'message': 'File type not allowed'}), 400

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='sha256')
        new_user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form)

if __name__ == '__main__':
    app.run(debug=True)
