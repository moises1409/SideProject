from flask import Blueprint, request, jsonify
import uuid
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from celery_app import celery
from fonctions import *
import traceback
from fonctions import set_task_status, upload_to_blob_storage, create_video_with_scenes, search_for_stock_videos, download_video, logger
from moviepy.editor import *
from prompts.motivation import PROMPT_SYSTEM_MOTIVATION, PROMPT_USER1, PROMPT_USER2, MOTIVATION_VOICE_ID_ES, MOTIVATION_VOICE_ID_EN, CHUNK_SIZE

video_motivation = Blueprint('video_motivation', __name__)

api_key = os.getenv('OPENAI_API_KEY')
eleven_labs_api_key = os.getenv("ELEVENLABS_API_KEY")
pexels_api_key=os.getenv("PEXELS_API_KEY")

client = OpenAI(api_key=api_key)

class Scene(BaseModel):
   sentences: str
   video_prompt: str

class Story(BaseModel):
    scenes: List[Scene]
    complete_story: str


@video_motivation.route('/get_motivational', methods=['GET'])
def generate_story():
    topic = request.args.get('topic')
    language = request.args.get('language')
    
    if topic and language:
        try:
            completion = client.beta.chat.completions.parse(
            #model="gpt-4o-2024-08-06",
            model = "gpt-4o-mini",
            
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM_MOTIVATION},
                {"role": "user", "content": PROMPT_USER1 + topic},
                {"role": "user", "content": PROMPT_USER2 +language}
            ],
            response_format=Story,
            )
            response = completion.choices[0].message.parsed
            response_dict = response.model_dump()
            return jsonify(response_dict)
        except Exception as e:
            print(f"Failed to generate motivational script: {e}")
            return None
    else:
        return jsonify({'error': 'No topic provided'}), 400

@video_motivation.route('/motivation_video_editor', methods=['POST'])
def motivation_video_editor():
    scene_data = request.json.get('scene_data')
    logging.debug("motivation_video_editor...")
    if not scene_data:
        return jsonify({"error": "No scene data provided"}), 400
    
    task_id = str(uuid.uuid4())

    # Start the video generation process as a Celery task
    generate_motivation_video_in_background_celery.apply_async(args=[task_id, scene_data])

    return jsonify({"task_id": task_id}), 202

@celery.task(name="motivation_video_task")
def generate_motivation_video_in_background_celery(task_id, scenes_data):
    try:
        output_path = f"final_video_{uuid.uuid4()}.mp4"
        scenes = []
        logger.debug("Generate_motivation_video_in_background....")

        for scene_data in scenes_data:
            prompt_video = scene_data[0]
            text = scene_data[1]
            scenes.append(create_motivation_scene(prompt_video, "Spanish", text))

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

def create_motivation_scene(prompt_video, language, text, duration=None):
    logger.debug("create motivation scene...")
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

    # Set the audio for the video clip
    video_clip_with_text = video_clip_with_text.set_audio(audio_clip)

    # Clean up local file after upload
    os.remove(file_name)
    os.remove(local_video_path)
    
    #return video_clip
    return video_clip_with_text



def generate_audio_scene(text, language):
    logger.debug("generate_audio_scene...")
    if language == "Spanish":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{MOTIVATION_VOICE_ID_ES}"
    if language == "French":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{MOTIVATION_VOICE_ID_ES}"
    if language == "English":
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{MOTIVATION_VOICE_ID_EN}"
    else:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{MOTIVATION_VOICE_ID_ES}"  
    
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




