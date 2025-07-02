# Needed imports
from fastapi import FastAPI, HTTPException;
from pydantic import BaseModel;
import os;
import re;
import yt_dlp;
import boto3;
from botocore.client import Config;

# initializing the fastAPI
app = FastAPI()

# Cloudflare configs
R2_CONFIGS = {
    'access_key':os.environ['R2_ACCESS_KEY'],
    'secret_key':os.environ['R2_SECREY_KEY'],
    'endpoint': os.environ['R2_ENDPOINT'],
    'bucket': os.environ['R2_BUCKET']
}

# Utility function to sanitize the game name
def sanitize_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)

# Utility function to download the game trailer
def download_game_trailer(game_name: str) -> str:
    # Sanitize the game name
    safe_name = sanitize_name(game_name).replace(" ","_").lower()
    
    # Define the temporary output path on the cloud
    output_path = f'/tmp/{safe_name}.mp4'

    # Define the video download parameters
    ydl_options = {
        'outtmpl': output_path,
        'format': 'best[height<=1080][ext=mp4]/best[ext=mp4]',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch1',
        'merge_output_format': 'mp4'
    }

    # Now start the download and return the path where trailer is stored (temporarily)
    try:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            # print(f"🔍 Downloading trailer: ytsearch1:{game_name} official trailer")
            ydl.download([f"ytsearch1:{game_name} official trailer"])
        
        if os.path.exists(output_path):
            # print(f"✅ Trailer successfully downloaded to {output_path}")
            return output_path
        else:
            # print("❌ Download process ended, but file not found.")
            return None
    except Exception as e:
        # # print(f'Download failed for game {game_name}: {e}')
        # print(f"❌ yt-dlp failed: {e}")
        return None

# Utility function to upload the game trailer
def upload_game_trailer(bucket_name, file_path, object_name, access_key, secret_key, endpoint):
    # Initialize the cloudflare s3 client
    s3 = boto3.client(
        's3',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint,
        region_name='auto',
        config=Config(signature_version='s3v4')
    )

    try:
        with open(file_path, 'rb') as f:
            s3.upload_fileobj(f, bucket_name, object_name)
        return (f"https://thegamerbros.co/{object_name}")
    except Exception as e:
        return None
    

# Request Model
class TrailerRequest(BaseModel):
    game_name: str

# Endpoint
@app.post('/process-trailer')
def process_trailer(req: TrailerRequest):

    game_name = req.game_name
    safe_name = sanitize_name(game_name)

    try:
        trailer_path = download_game_trailer(game_name)
        if not trailer_path or not os.path.exists(trailer_path):
            raise HTTPException(status_code=404, detail="Trailer not found or download failed")
        
        object_name = f'{safe_name}.mp4'.replace(" ","_").lower()
        trailer_url = upload_game_trailer(
            R2_CONFIGS['bucket'], trailer_path, object_name, R2_CONFIGS['access_key'],R2_CONFIGS['secret_key'],R2_CONFIGS['endpoint'])
        
        os.remove(trailer_path)

        return trailer_url
    except Exception as e:
        raise HTTPException(status_code=500,detail=f'Processing Error: {str(e)}')