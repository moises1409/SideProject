from flask import Flask
from flask_cors import CORS
import os
from apis.motivational_apis import video_motivation
from apis.animation_apis import animated_story
from apis.generic_apis import generic_apis
from celery_app import celery

app = Flask(__name__)
CORS(app)

app.register_blueprint(generic_apis, url_prefix='/generic_apis')
app.register_blueprint(animated_story, url_prefix='/animated_story')
app.register_blueprint(video_motivation, url_prefix='/video_motivation')

app.config["broker_url"] = os.getenv("CELERY_BROKER_URL")  # Replaces CELERY_BROKER_URL
app.config["result_backend"] = os.getenv("CELERY_RESULT_BACKEND")  # Replaces CELERY_RESULT_BACKEND

# Keep track of task statuses
task_status = {}


