from flask import Blueprint, request, jsonify
import uuid
from celery_app import celery
from fonctions import set_task_status, upload_to_blob_storage, create_video_with_scenes, logger
import traceback
import requests
import logging
from moviepy.editor import *
from prompts.animation import PROMPT_SYSTEM_ANIMATION, PROMPT_USER1, PROMPT_USER2, ANIMATION_VOICE_ID_DEFAULT,ANIMATION_VOICE_ID_EN, ANIMATION_VOICE_ID_ES, ANIMATION_VOICE_ID_FR, CHUNK_SIZE
from openai import OpenAI
from pydantic import BaseModel
from typing import List
import os


animated_story = Blueprint('animated_story', __name__)

api_key = os.getenv('OPENAI_API_KEY')
eleven_labs_api_key = os.getenv("ELEVENLABS_API_KEY")
replicate_api_token = os.getenv("REPLICATE_API_TOKEN")

client = OpenAI(api_key=api_key)

class Scene(BaseModel):
   sentences: str
   image_prompt: str

class Story(BaseModel):
    scenes: List[Scene]
    complete_story: str

@animated_story.route('/get_story', methods=['GET'])
def generate_story():
    topic = request.args.get('topic')
    language = request.args.get('language')
    if topic and language:
        try:
            completion = client.beta.chat.completions.parse(
            #model="gpt-4o-2024-08-06",
            model = "gpt-4o-mini",
            
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM_ANIMATION},
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

@animated_story.route('/video_animated_editor', methods=['POST'])
def animated_video_editor():
    scene_data = request.json.get('scene_data')
    logging.debug("animated_video_editor...")
    if not scene_data:
        return jsonify({"error": "No scene data provided"}), 400
    
    task_id = str(uuid.uuid4())
    set_task_status(task_id, "processing")

    # Start the video generation process as a Celery task
    generate_animated_video_in_background_celery.apply_async(args=[task_id, scene_data])

    return jsonify({"task_id": task_id}), 202

@celery.task(name="animated_video_task")
def generate_animated_video_in_background_celery(task_id, scenes_data):
    try:
        output_path = f"final_video_{uuid.uuid4()}.mp4"
        scenes = []
        logger.debug("Generate_animated_video_in_background....")

        for scene_data in scenes_data:
            image_path = scene_data[0]
            #audio_path = scene_data[1]
            text = scene_data[1]
            scenes.append(create_animated_scene(image_path, "Spanish", text))
        
        music = "false"
        create_video_with_scenes(scenes, output_path, music)
        video_url = upload_to_blob_storage(output_path, "video")

        # Update task status to completed
        set_task_status(task_id, "completed", video_url=video_url)
        logger.debug(f"Task {task_id} marked as completed in Redis.")
    except Exception as e:
        # If an error occurs, update the status to failed
        logger.error(f"Error in generate_video_in_background: {traceback.format_exc()}")
        set_task_status(task_id, "failed", error=str(e))

def create_animated_scene(image_path, language, text, duration=None):
    logger.debug("create animated scene...")
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


def generate_audio_scene(text, language):
    logger.debug("generate_audio_scene...")
    if language == "Spanish":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ANIMATION_VOICE_ID_ES}"
    if language == "French":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ANIMATION_VOICE_ID_FR}"
    if language == "English":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ANIMATION_VOICE_ID_EN}"
    else:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ANIMATION_VOICE_ID_ES}"  
    
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
    
