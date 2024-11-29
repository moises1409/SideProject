from flask import Blueprint, request, jsonify
from prompts.commercial import *
from openai import OpenAI
from pydantic import BaseModel
import os
import requests
from typing import List
from celery_app import celery
import requests
import logging
import traceback
from fonctions import set_task_status, upload_to_blob_storage, create_video_with_scenes, search_for_stock_videos, download_video, logger
from moviepy.editor import *
import uuid

video_commercial = Blueprint('video_commercial', __name__)

api_key = os.getenv('OPENAI_API_KEY')
eleven_labs_api_key = os.getenv("ELEVENLABS_API_KEY")
replicate_api_token = os.getenv("REPLICATE_API_TOKEN")

client = OpenAI(api_key=api_key)

class Webinfo(BaseModel):
   webinfo: str
   logo:str

class Scene(BaseModel):
   sentences: str
   video_prompt: str

class Story(BaseModel):
    scenes: List[Scene]
    complete_story: str
    webinfo: str


@video_commercial.route('/get_commercial', methods=['GET'])
def generate_story():
    #topic = request.args.get('topic')
    url = request.args.get('url')
    language = request.args.get('language')
    
    if url and language:
        try:
            completion = client.beta.chat.completions.parse(
            #model="gpt-4o-2024-08-06",
            model = "gpt-4o-mini",
            
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM_WEBINFO},
                {"role": "user", "content": PROMPT_URL + url},
                {"role": "system", "content": PROMPT_SYSTEM_COMMERCIAL},
                #{"role": "user", "content": PROMPT_USER1 + topic},
                {"role": "user", "content": PROMPT_USER2 +language}
            ],
            response_format=Story,
            )
            response = completion.choices[0].message.parsed
            response_dict = response.model_dump()
            return jsonify(response_dict)
        except Exception as e:
            print(f"Failed to generate commercial script: {e}")
            return None
    else:
        return jsonify({'error': 'No topic provided'}), 400


@video_commercial.route('/commercial_video_editor', methods=['POST'])
def motivation_video_editor():
    scene_data = request.json.get('scene_data')
    logging.debug("commercial_video_editor...")
    if not scene_data:
        return jsonify({"error": "No scene data provided"}), 400
    
    task_id = str(uuid.uuid4())

    # Start the video generation process as a Celery task
    generate_commercial_video_in_background_celery.apply_async(args=[task_id, scene_data])

    return jsonify({"task_id": task_id}), 202

@celery.task(name="commercial_video_task")
def generate_commercial_video_in_background_celery(task_id, scenes_data):
    try:
        output_path = f"final_video_{uuid.uuid4()}.mp4"
        scenes = []
        logger.debug("Generate_commercial_video_in_background....")

        for scene_data in scenes_data:
            prompt_video = scene_data[0]
            text = scene_data[1]
            scenes.append(create_commercial_scene(prompt_video, "Spanish", text))

        music = "true"
        create_video_with_scenes(scenes, output_path, music)
        video_url = upload_to_blob_storage(output_path, "video")

        # Update task status to completed
        set_task_status(task_id, "completed", video_url=video_url)
        logger.debug(f"Task {task_id} marked as completed in Redis.")
    except Exception as e:
        # If an error occurs, update the status to failed
        logger.error(f"Error in generate_video_in_background: {traceback.format_exc()}")
        set_task_status(task_id, "failed", error=str(e))

def create_commercial_scene(prompt_video, language, text, duration=None):
    logger.debug("create commercial scene...")
    size = (1080, 720)

    file_name = generate_audio_scene(text, language)

    # Load the audio file
    audio_clip = AudioFileClip(file_name)
   
    # Set the duration of the scene based on the audio length or provided duration
    if duration is None:
        duration = audio_clip.duration
    logger.debug(f"XXXXX audio duration {duration}")

    url_video = search_for_stock_videos (prompt_video, 10, duration)
    logger.debug(f"YYYYY url video Pexel {url_video}")

    # Download video locally if needed
    local_video_path = download_video(url_video, 'local_video.mp4')
    if not local_video_path:
        logger.error("Failed to download video.")
        return None

    video_clip = VideoFileClip(local_video_path)
    # Resize video clip to a consistent size (e.g., 1280x720)
    video_clip = video_clip.resize(size)

    
    # Set the duration of the image clip
    video_clip = video_clip.set_duration(duration)

    # Set the audio for the image clip
    video_clip = video_clip.set_audio(audio_clip)

    # Clean up local file after upload
    os.remove(file_name)
    os.remove(local_video_path)
    
    return video_clip
    



def generate_audio_scene(text, language):
    logger.debug("generate_audio_scene...")
    if language == "Spanish":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{MOTIVATION_VOICE_ID_ES}"
    if language == "French":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{MOTIVATION_VOICE_ID_FR}"
    if language == "English":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{MOTIVATION_VOICE_ID_EN}"
    else:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{MOTIVATION_VOICE_ID_EN}"  
    
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

@video_commercial.route('/get_webinfo', methods=['GET'])
def get_webinfo():
    url = request.args.get('url')
    
    if url:
        try:
            completion = client.beta.chat.completions.parse(
            #model="gpt-4o-2024-08-06",
            model = "gpt-4o-mini",
            
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM_WEBINFO},
                {"role": "user", "content": PROMPT_URL + url}
            ],
            response_format=Webinfo,
            )
            response = completion.choices[0].message.parsed
            response_dict = response.model_dump()
            return jsonify(response_dict)
        except Exception as e:
            print(f"Failed to extract info: {e}")
            return None
    else:
        return jsonify({'error': 'No url provided'}), 400
    
