from flask import Blueprint, request, jsonify
from celery_app import celery
from fonctions import delete_from_blob_storage, get_task_status, upload_to_blob_storage, search_for_stock_videos
import requests
import replicate
import os
import json
from prompts.animation import ANIMATION_VOICE_ID_FR, ANIMATION_VOICE_ID_DEFAULT, ANIMATION_VOICE_ID_EN, ANIMATION_VOICE_ID_ES, CHUNK_SIZE

generic_apis = Blueprint('generic_apis', __name__)

eleven_labs_api_key = os.getenv("ELEVENLABS_API_KEY")
replicate_api_token = os.getenv("REPLICATE_API_TOKEN")
pexel_api_key = os.getenv("PEXELS_API_KEY")


@generic_apis.route('/', methods=['GET'])
def get_test():
    return "holas4s mundos23221409aaaa"

@generic_apis.route('/task_status/<task_id>', methods=['GET'])
def task_status_id(task_id):
    # Use the Redis-backed get_task_status function to retrieve status
    status = get_task_status(task_id)
    return jsonify(status)
    

@generic_apis.route("/get_image", methods=['GET'])
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

    
@generic_apis.route("/get_video_pexel", methods=['GET'])
def get_pexel_video():
    prompt = request.args.get('prompt')
    limit = 10
    min_dur = 10
    url_video = search_for_stock_videos (prompt, limit, min_dur)
    return url_video


@generic_apis.route("/get_audio", methods=['GET'])
def generate_audio():
    text = request.args.get('text')
    language = request.args.get('language')

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
    
        blob_name = upload_to_blob_storage(temp_file_name, "audio")

        # Clean up local file after upload
        #os.remove(temp_file_name)

        return blob_name
        
    except Exception as e:
        print(f"Error generating audio: {e}")
        return None

@generic_apis.route('/delete_audio_files', methods=['POST'])
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