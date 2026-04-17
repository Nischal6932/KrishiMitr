import os
import requests
import json
import logging

logger = logging.getLogger(__name__)

def ask_llm(prompt, model="phi3", timeout=30):
    """
    Safe LLM call with error handling for production deployment
    Returns fallback response if Ollama is not available
    """
    # Check if we're in production (Render) and skip Ollama calls
    if os.environ.get('ENVIRONMENT') == 'production' or os.environ.get('RENDER'):
        # Return a fallback response for production
        return "AI advice service is not available in this deployment. Please consult with a local agricultural expert for detailed advice."
    
    # Try different Ollama URLs for local development
    OLLAMA_URLS = [
        "http://localhost:11434/api/generate",
        "http://127.0.0.1:11434/api/generate",
        "http://0.0.0.0:11434/api/generate"
    ]
    
    for ollama_url in OLLAMA_URLS:
        try:
            response = requests.post(
                ollama_url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 120,
                        "temperature": 0.7
                    }
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if "response" in result:
                    return result["response"]
                else:
                    logger.warning(f"Unexpected response format: {result}")
                    continue
            else:
                logger.warning(f"HTTP {response.status_code} from {ollama_url}")
                continue
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout from {ollama_url}")
            continue
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection failed to {ollama_url}")
            continue
        except Exception as e:
            logger.error(f"Error calling {ollama_url}: {e}")
            continue
    
    # Fallback response if all URLs fail
    return "AI advice service temporarily unavailable. Please try again later or consult with a local agricultural expert."