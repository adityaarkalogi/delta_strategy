from redis import Redis, ConnectionError
from config import Config
import logging
import time
import json
import os

logger = logging.getLogger(__name__)
retry_attempts = 3
sleep_time = 1

def connect_to_redis():
    try:
        return Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)
    except ConnectionError as e:
        logger.error(f"Initial Redis connection failed: {e}")
        raise

user_connection = connect_to_redis()

def get_message():
    global user_connection
    for attempt in range(retry_attempts):
        try:
            return user_connection.lpop("user_input")
        except ConnectionError as e:
            logger.warning(f"Error fetching message from Redis on attempt {attempt + 1}: {e}")
            if attempt < retry_attempts-1:
                time.sleep(sleep_time)
                user_connection = connect_to_redis()
            else:
                raise

def push_message(id , message: str):
    global user_connection
    for attempt in range(retry_attempts):
        try:
            user_connection.publish(f"backend_com_{id}", message)
            return
        except ConnectionError as e:
            logger.warning(f"Error publishing message to Redis on attempt {attempt + 1}: {e}")
            if attempt < retry_attempts-1:
                time.sleep(sleep_time)
                user_connection = connect_to_redis()
            else:
                raise

    
## so called protocol
## input message format
## output message format

## Logs shold be inserted in files in same format
# {
#     "type": "",
#     "data": "",
#     "error_code": 0,
#     "error_message": "",
# }


def get_data():
    current_file_path = os.path.dirname(__file__)
    
    json_path = os.path.join(current_file_path, '..','parameters.json')
    json_path = os.path.abspath(json_path)
  
    with open(json_path, 'r') as f:
        data = json.load(f)

    return data