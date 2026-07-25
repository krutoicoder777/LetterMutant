import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DATABASE_URL = os.environ.get('DATABASE_URL')
    SESSION_TYPE = 'filesystem'

    ENGINEIO_ASYNC_MODE = 'eventlet'

    GAME_DURATION = 60
    BOARD_SIZE = 5
