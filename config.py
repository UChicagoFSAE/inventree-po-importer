import os
from dotenv import load_dotenv
from inventree.api import InvenTreeAPI

def get_api():
    load_dotenv()
    
    url = os.getenv("INVENTREE_URL")
    token = os.getenv("INVENTREE_API_TOKEN")
    
    if not url or not token:
        raise ValueError("INVENTREE_URL and INVENTREE_API_TOKEN must be set in .env")
        
    api = InvenTreeAPI(url, token=token)
    return api

if __name__ == "__main__":
    # Quick connection test
    try:
        api = get_api()
        print(f"Connected to InvenTree: {api.base_url}")
    except Exception as e:
        print(f"Connection failed: {e}")
