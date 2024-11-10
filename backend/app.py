import ssl
from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
import uuid
from dotenv import load_dotenv
import os
from openai import OpenAI
from pydantic import BaseModel
from typing import List
import replicate
import requests
from azure.storage.blob import BlobServiceClient
from urllib.parse import urlparse
from moviepy.editor import *
import json
import traceback
from celery import Celery
from redis import Redis
from celery.utils.log import get_task_logger
from threading import Thread
from moviepy.video.fx.all import resize


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

logger = get_task_logger(__name__)
logger.setLevel(logging.DEBUG)  # Set to DEBUG to see all logs

redis_host = os.getenv("REDIS_HOST", "video-ai.redis.cache.windows.net")
redis_port = int(os.getenv("REDIS_PORT", 6380))
redis_password = os.getenv("REDIS_PASSWORD")
redis_ssl = True

redis_client = Redis(
    host=redis_host,
    port=redis_port,
    password=redis_password,
    ssl=redis_ssl
)

def set_task_status(task_id, status, video_url=None, error=None):
    status_data = {"status": status}
    if video_url:
        status_data["video_url"] = video_url
    if error:
        status_data["error"] = error
    redis_client.set(f"task_status:{task_id}", json.dumps(status_data))
    logger.debug(f"Set task status in Redis for {task_id}: {status_data}")  # Debug log

def get_task_status(task_id):
    data = redis_client.get(f"task_status:{task_id}")
    logger.debug(f"Retrieved task status from Redis for {task_id}: {data}")  # Debug log
    return json.loads(data) if data else {"status": "Rendering video"}

# Initialize Celery
def make_celery(app):
    celery = Celery(
        app.import_name,
        broker=app.config["broker_url"],
        backend=app.config["result_backend"],
    )
    # Ensure SSL parameters if required by Redis
    celery.conf.broker_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    celery.conf.result_backend_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    celery.conf.update(app.config)
    return celery

app = Flask(__name__)
CORS(app)

app.config["broker_url"] = os.getenv("CELERY_BROKER_URL")  # Replaces CELERY_BROKER_URL
app.config["result_backend"] = os.getenv("CELERY_RESULT_BACKEND")  # Replaces CELERY_RESULT_BACKEND

celery = make_celery(app)

api_key = os.getenv('OPENAI_API_KEY')
eleven_labs_api_key = os.getenv("ELEVENLABS_API_KEY")
replicate_api_token = os.getenv("REPLICATE_API_TOKEN")

client = OpenAI(api_key=api_key)

# Keep track of task statuses
task_status = {}

class Scene(BaseModel):
   sentences: str
   image_prompt: str

class Story(BaseModel):
    scenes: List[Scene]
    complete_story: str

# Constants
NUMBER_SCENES = "2"
PROMPT_SYSTEM = """Write an engaging, great 5 scenes children's animated history. Each scene should have 1-2 sentences.  
Generate appropriate prompt to generate a coherent image for each scene. 
The styles of all the images in the story are: Cartoon, vibrant, Pixar style. 
Characters description should be detailed, like hair and color eyes and face. Main character in the story should be the same for all scenes. 
Characters description must be consistent in all the scenes.
Please add the styles in each prompt for images. Be sure that all the prompts are consistent in all the story. For example characters descriptions.
Please respect the styles in all the scenes.
Limit of 5 scenes, do not exceed 5 sentences per scene. Do not exceed 5 scenes."""
PROMPT_USER1 = "Story is about"
PROMPT_USER2 = "Create the story in the following language:"
CHUNK_SIZE = 1024
VOICE_ID_ES = "Ir1QNHvhaJXbAGhT50w3"
VOICE_ID_DEFAULT = "pNInz6obpgDQGcFmaJgB"
VOICE_ID_FR = "hFgOzpmS0CMtL2to8sAl"
VOICE_ID_EN = "jsCqWAovK2LkecY7zXl4"


@app.route("/", methods=['GET'])
def get_test():
    return "holas4s mundos2322aaaa"


@app.route("/get_story", methods=['GET'])
def generate_story():
    topic = request.args.get('topic')
    language = request.args.get('language')
    if topic and language:
        try:
            completion = client.beta.chat.completions.parse(
            #model="gpt-4o-2024-08-06",
            model = "gpt-4o-mini",
            
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": PROMPT_USER1 + topic},
                {"role": "user", "content": PROMPT_USER2 +language}
            ],
            response_format=Story,
            )
            response = completion.choices[0].message.parsed
            response_dict = response.model_dump()
            return jsonify(response_dict)
        except Exception as e:
            print(f"Failed to generate story: {e}")
            return None
    else:
        return jsonify({'error': 'No topic provided'}), 400
    

@app.route("/get_image", methods=['GET'])
def generate_image():
    prompt = request.args.get('prompt')
    # API endpoint for Replicate
    url = "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"

    # Headers for the request
    headers = {
        "Authorization": f"Bearer {replicate_api_token}",
        "Content-Type": "application/json",
        "Prefer": "wait"
    }

    # Payload for the request (JSON data)
    data = {
        "input": {
            "prompt": prompt,
            "output_format": "jpg"
        }
    }

    # Make the POST request
    response = requests.post(url, headers=headers, json=data)
    initial_data = response.json()
    image_id = initial_data["id"]
    prediction = replicate.predictions.get(image_id)
    response = prediction.json()
    response2 = json.loads(response)
    return response2["output"][0]



@app.route("/get_audio", methods=['GET'])
def generate_audio():
    text = request.args.get('text')
    language = request.args.get('language')

    if language == "Spanish":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID_ES}"
    if language == "French":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID_ES}"
    if language == "English":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID_ES}"
    else:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID_ES}"  
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": eleven_labs_api_key
    }
    data = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.5
        }
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        temp_file_name = "audios/audio.mp3"
        with open(temp_file_name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
    
        blob_name = upload_to_blob_storage(temp_file_name, "audio")

        # Clean up local file after upload
        #os.remove(temp_file_name)

        return blob_name
        
    except Exception as e:
        print(f"Error generating audio: {e}")
        return None

@app.route('/delete_audio_files', methods=['POST'])
def delete_audio_files():
    data = request.json
    audio_urls = data.get('audio_urls', [])
    
    if not audio_urls:
        return jsonify({"error": "No audio URLs provided"}), 400

    results = []
    for url in audio_urls:
        result = delete_from_blob_storage(url)
        results.append({"url": url, "deleted": result})
    
    return jsonify({"results": results}), 200

# Function to delete a single file from Azure Blob Storage
def delete_from_blob_storage(blob_name):
    connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    
    container_name = 'audio-files'
    
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    try:
        blob_client.delete_blob()
        print(f"Blob {blob_name} deleted successfully from container {container_name}.")
        return True
    except Exception as e:
        print(f"Failed to delete blob: {blob_name}. Error: {str(e)}")
        return False

def upload_to_blob_storage(local_file_path, type):
    connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    unique_id = uuid.uuid4()  # Generates a unique UUID
    if type == "video":
        container_name = 'video-files'
        blob_name = f"{unique_id}.mp4"  # Create a unique blob name
    if type == "audio":
        container_name = 'audio-files'
        blob_name = f"{unique_id}.mp3"  # Create a unique blob name
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    with open(local_file_path, "rb") as data:
        blob_client.upload_blob(data)
    if type == "video":
        blob_url = blob_client.url
        return blob_url
    if type == "audio": 
        return blob_name

def download_blob(container_name, blob_name, download_file_path):
    # Use the connection string from environment variables
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    
    # Initialize the BlobServiceClient
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    
    # Get a client for the container and blob
    blob_client = blob_service_client.get_blob_client(container_name, blob_name)

    # Download the blob to a local file
    with open(download_file_path, "wb") as download_file:
        download_file.write(blob_client.download_blob().readall())
    
    logger.debug(f"Downloaded blob '{blob_name}' to '{download_file_path}'")


@app.route('/auto_editor', methods=['POST'])
def auto_editor():
    scene_data = request.json.get('scene_data')
    logging.debug("auto_editor...")
    if not scene_data:
        return jsonify({"error": "No scene data provided"}), 400
    
    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    task_status[task_id] = {"status": "processing"}

    # Start the video generation process in a background thread
    #thread = Thread(target=generate_video_in_background_without_celery, args=(task_id, scene_data))
    #thread.start()

    # Start the video generation process as a Celery task
    generate_video_in_background_celery.apply_async(args=[task_id, scene_data])

    # Return the task ID immediately
    return jsonify({"task_id": task_id}), 202

@celery.task(name="generate_video_task")
def generate_video_in_background_celery(task_id, scenes_data):
    try:
        output_path = f"final_video_{uuid.uuid4()}.mp4"
        scenes = []
        logger.debug("Generate_video_in_background....")

        for scene_data in scenes_data:
            image_path = scene_data[0]
            #audio_path = scene_data[1]
            text = scene_data[1]
            scenes.append(create_scene(image_path, "Spanish", text))

        create_video_with_scenes(scenes, output_path)
        video_url = upload_to_blob_storage(output_path, "video")

        # Update task status to completed
        set_task_status(task_id, "completed", video_url=video_url)
        logger.debug(f"Task {task_id} marked as completed in Redis.")
    except Exception as e:
        # If an error occurs, update the status to failed
        logger.error(f"Error in generate_video_in_background: {traceback.format_exc()}")
        set_task_status(task_id, "failed", error=str(e))

def create_scene(image_path, language, text, duration=None):
    logger.debug("create scene...")
    size = (1280, 720)

    file_name = generate_audio_scene(text, language)

    image_clip = ImageClip(image_path).set_fps(10)  # Lower FPS for optimization

    #image_clip = ImageClip(image_path).resize(size).set_fps(10)  # Lower FPS for optimization
    #image_clip = image_clip.resize(lambda t: 1 + 0.02 * t)  # Apply a simple zoom effect

    # Load the audio file
    audio_clip = AudioFileClip(file_name)
   
    # Set the duration of the scene based on the audio length or provided duration
    if duration is None:
        duration = audio_clip.duration
    
    logger.debug(f"XXXXX audio duration {duration}")
    # Set the duration of the image clip
    image_clip = image_clip.set_duration(duration)

    # Create word-by-word TextClips
    words = text.split()
    phrase_length = 1  # Number of words per phrase (adjust as needed)
    phrases = [" ".join(words[i:i + phrase_length]) for i in range(0, len(words), phrase_length)]
    phrase_duration = duration / len(phrases)  # Set duration for each phrase to appear

    #phrase_duration = duration / words  # Set duration for each phrase to appear

    # Create TextClips for each phrase and arrange them in sequence
    phrase_clips = []
    for i, phrase in enumerate(phrases):
        try:
            phrase_clip = TextClip(phrase, fontsize=40, color='white', font='DejaVu-Sans-Bold')
            phrase_clip = phrase_clip.set_position(('center', 'center')).set_duration(phrase_duration)
            phrase_clip = phrase_clip.set_start(i * phrase_duration)  # Set when each phrase appears
            phrase_clips.append(phrase_clip)
        except Exception as e:
            logger.debug(f"Failed to create TextClip for phrase '{phrase}'. Error: {str(e)}")
            raise Exception(f"Failed to create TextClip for phrase '{phrase}'. Error: {str(e)}")
        
    # Overlay the phrases on top of the image using CompositeVideoClip
    video_clip_with_text = CompositeVideoClip([image_clip] + phrase_clips).set_audio(audio_clip)

    # Set the audio for the image clip
    #image_clip = image_clip.set_audio(audio_clip)

    # Clean up local file after upload
    os.remove(file_name)

    # Set the audio for the video clip
    video_clip_with_text = video_clip_with_text.set_audio(audio_clip)
    
    #return image_clip
    return video_clip_with_text


def create_video_with_scenes(scenes, output_path):
    # Combine all the scenes into one video
    final_video = concatenate_videoclips(scenes)

    final_video = final_video.set_fps(14)  # Reduce frame rate to 24fps for optimization
    
    # Export the video to MP4
    final_video.write_videofile(output_path, codec='libx264', fps=14, preset='ultrafast', threads=4, audio_codec='aac', audio_bitrate='128k')


@app.route('/task_status/<task_id>', methods=['GET'])
def task_status_id(task_id):
    # Use the Redis-backed get_task_status function to retrieve status
    status = get_task_status(task_id)
    return jsonify(status)


def generate_audio_scene(text, language):
    logger.debug("generate_audio_scene...")
    if language == "Spanish":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID_ES}"
    if language == "French":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID_ES}"
    if language == "English":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID_ES}"
    else:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID_ES}"  
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": eleven_labs_api_key
    }
    data = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.5
        }
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        temp_file_name = "audios/audio.mp3"
        with open(temp_file_name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)

        return temp_file_name
        
    except Exception as e:
        print(f"Error generating audio: {e}")
        return None
    

@app.route('/auto_video_editor', methods=['POST'])
def auto_video_editor():
    scene_data = request.json.get('scene_data')
    logging.debug("auto_video_editor...")
    if not scene_data:
        return jsonify({"error": "No scene data provided"}), 400
    
    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    task_status[task_id] = {"status": "processing"}

    # Start the video generation process as a Celery task
    generate_video_in_background_celery2.apply_async(args=[task_id, scene_data])

    # Return the task ID immediately
    return jsonify({"task_id": task_id}), 202

@celery.task(name="generate_video_task2")
def generate_video_in_background_celery2(task_id, scenes_data):
    try:
        output_path = f"final_video_{uuid.uuid4()}.mp4"
        scenes = []
        logger.debug("Generate_video_in_background....")

        for scene_data in scenes_data:
            video_path = scene_data[0]
            audio_path = scene_data[1]
            text = scene_data[2]
            scenes.append(create_scene_with_video(video_path, audio_path, "Spanish", text))

        create_video_with_scenes2(scenes, output_path)
        video_url = upload_to_blob_storage(output_path, "video")

        # Update task status to completed
        set_task_status(task_id, "completed", video_url=video_url)
        logger.debug(f"Task {task_id} marked as completed in Redis.")
    except Exception as e:
        # If an error occurs, update the status to failed
        logger.error(f"Error in generate_video_in_background: {traceback.format_exc()}")
        set_task_status(task_id, "failed", error=str(e))

def create_scene_with_video(video_path, audio_path, language, text, duration=None):
    logger.debug("create scene with video...")
    size = (1080, 720)

    #file_name = generate_audio_scene(text, language)

    video_clip = VideoFileClip(video_path)
    # Resize video clip to a consistent size (e.g., 1280x720)
    video_clip = video_clip.resize(size)

    # Load the audio file
    audio_clip = AudioFileClip(audio_path)
   
    # Set the duration of the scene based on the audio length or provided duration
    if duration is None:
        duration = audio_clip.duration
    
    logger.debug(f"XXXXX audio duration {duration}")
    # Set the duration of the image clip
    video_clip = video_clip.set_duration(duration)

    # Set the audio for the image clip
    video_clip = video_clip.set_audio(audio_clip)

    # Create word-by-word TextClips
    words = text.split()
    phrase_length = 4  # Number of words per phrase (adjust as needed)
    phrases = [" ".join(words[i:i + phrase_length]) for i in range(0, len(words), phrase_length)]
    phrase_duration = duration / len(phrases)  # Set duration for each phrase to appear

    # Create TextClips for each phrase and arrange them in sequence
    phrase_clips = []
    for i, phrase in enumerate(phrases):
        try:
            phrase_clip = TextClip(phrase, fontsize=40, color='white', font='DejaVu-Sans-Bold')
            phrase_clip = phrase_clip.set_position(('center', 'center')).set_duration(phrase_duration)
            phrase_clip = phrase_clip.set_start(i * phrase_duration)  # Set when each phrase appears
            phrase_clips.append(phrase_clip)
        except Exception as e:
            logger.debug(f"Failed to create TextClip for phrase '{phrase}'. Error: {str(e)}")
            raise Exception(f"Failed to create TextClip for phrase '{phrase}'. Error: {str(e)}")
        
    # Overlay the phrases on top of the image using CompositeVideoClip
    video_clip_with_text = CompositeVideoClip([video_clip] + phrase_clips).set_audio(audio_clip)

    # Clean up local file after upload
    #os.remove(file_name)

    # Set the audio for the video clip
    video_clip_with_text = video_clip_with_text.set_audio(audio_clip)
    
    #return video_clip
    return video_clip_with_text

def create_video_with_scenes2(scenes, output_path):
    # Combine all the scenes into one video
    final_video = concatenate_videoclips(scenes)

    final_video = final_video.set_fps(14)  # Reduce frame rate to 24fps for optimization

    background_music_path="audios/music.mp3"

    background_music = AudioFileClip(background_music_path)

    # Adjust the duration of the background music to match the video duration
    background_music = background_music.set_duration(final_video.duration)

    background_music = background_music.volumex(0.2)  # Lower volume by 80% (adjust as needed)

    # Combine the background music with the video audio (if any)
    if final_video.audio:
        final_audio = CompositeAudioClip([final_video.audio, background_music])
    else:
        final_audio = background_music
    
    # Set the combined audio as the final video's audio
    final_video = final_video.set_audio(final_audio)
    
    # Export the video to MP4
    final_video.write_videofile(output_path, codec='libx264', fps=14, preset='ultrafast', threads=4, audio_codec='aac', audio_bitrate='128k')
