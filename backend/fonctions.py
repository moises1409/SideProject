import logging
import os
from redis import Redis
import json
import uuid
from celery.utils.log import get_task_logger
from azure.storage.blob import BlobServiceClient
import requests
from moviepy.editor import concatenate_videoclips, AudioFileClip, CompositeAudioClip

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

logger = get_task_logger(__name__)
logger.setLevel(logging.DEBUG) 

redis_host = os.getenv("REDIS_HOST")
redis_port = int(os.getenv("REDIS_PORT"))
redis_password = os.getenv("REDIS_PASSWORD")
#redis_ssl = True

redis_client = Redis(
    host=redis_host,
    port=redis_port,
    password=redis_password,
    #ssl=redis_ssl
)

CHUNK_SIZE = 1024

def set_task_status(task_id, status, video_url=None, error=None):
    status_data = {"status": status}
    if video_url:
        status_data["video_url"] = video_url
    if error:
        status_data["error"] = error
    redis_client.set(f"task_status:{task_id}", json.dumps(status_data))
    logging.debug(f"Set task status in Redis for {task_id}: {status_data}")  # Debug log

def get_task_status(task_id):
    data = redis_client.get(f"task_status:{task_id}")
    logging.debug(f"Retrieved task status from Redis for {task_id}: {data}")  # Debug log
    return json.loads(data) if data else {"status": "Rendering video"}

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
    
def create_video_with_scenes(scenes, output_path, music):
    # Combine all the scenes into one video
    final_video = concatenate_videoclips(scenes)
    background_music_path="audios/music.mp3"

    final_video = final_video.set_fps(14)  # Reduce frame rate to 24fps for optimization

    if music == "true":
        background_music = AudioFileClip(background_music_path)

        # Adjust the duration of the background music to match the video duration
        background_music = background_music.set_duration(final_video.duration)

        background_music = background_music.volumex(0.6)  # Lower volume by 80% (adjust as needed)

        # Combine the background music with the video audio (if any)
        if final_video.audio:
            final_audio = CompositeAudioClip([final_video.audio, background_music])
        else:
            final_audio = background_music

        # Set the combined audio as the final video's audio
        final_video = final_video.set_audio(final_audio)
    
    # Export the video to MP4
    final_video.write_videofile(output_path, codec='libx264', fps=14, preset='ultrafast', threads=4, audio_codec='aac', audio_bitrate='128k')


def search_for_stock_videos(query: str, limit: int, min_dur: int):
    logger.debug("search for stock videos...")
    headers = {
        "Authorization": os.getenv("PEXELS_API_KEY"),
    }

    qurl = f"https://api.pexels.com/videos/search?query={query}&per_page={limit}"

    r = requests.get(qurl, headers=headers)
    response = r.json()

    
    logger.debug(f"response from Pexel API: {response}")

    raw_urls = []
    target_width = 640
    target_height = 360
    video_res = target_width * target_height
    target_quality = "sd"
    video_url = ""
    try:
        for i in range(limit):
            if response["videos"][i]["duration"] >= min_dur:
                raw_urls = response["videos"][i]["video_files"]
                logger.debug(f"video founded from Pexel: {raw_urls}")
                for video in raw_urls:
                    if ".com/video-files" in video["link"]:
                        if video["width"] == target_width and video["height"] == target_height and video["quality"] == target_quality:
                            video_url = video["link"]
                            logger.debug(f"video from Pexel: {video_url}")
                            return  video_url
        if video_url == "":
                logger.debug("no ha encontrado el video con los criterios y saca el primero de la busqueda")
                video_url = response["videos"][0]["video_files"][0]["link"]
                return video_url

    except Exception as e:
        logger.error(f"Error Searching for video: {e}")


def download_video(url, local_filename):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise error for bad status codes
        with open(local_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return local_filename
    except requests.RequestException as e:
        logger.error(f"Failed to download video: {e}")
        return None