from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
import os
from apis.motivational_apis import video_motivation
from apis.animation_apis import animated_story
from apis.commercial_apis import video_commercial
from apis.generic_apis import generic_apis
from apis.db_apis import db_apis
from db_app import db
from celery_app import celery

app = Flask(__name__)
CORS(app)

app.config["broker_url"] = os.getenv("CELERY_BROKER_URL")  # Replaces CELERY_BROKER_URL
app.config["result_backend"] = os.getenv("CELERY_RESULT_BACKEND")  # Replaces CELERY_RESULT_BACKEND
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

app.register_blueprint(generic_apis, url_prefix='/generic_apis')
app.register_blueprint(animated_story, url_prefix='/animated_story')
app.register_blueprint(video_motivation, url_prefix='/video_motivation')
app.register_blueprint(video_commercial, url_prefix='/video_commercial')
app.register_blueprint(db_apis, url_prefix='/db_apis')

migrate = Migrate(app, db)

# Ensure database tables are created
with app.app_context():
    db.create_all()

# Keep track of task statuses
task_status = {}


