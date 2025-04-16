import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# OpenAI API settings
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-3.5-turbo')

# Notion API Configuration
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_PARENT_PAGE_ID = os.getenv('NOTION_PARENT_PAGE_ID')

# Project settings
MAX_TOKENS = 4096
TEMPERATURE = 0.2
