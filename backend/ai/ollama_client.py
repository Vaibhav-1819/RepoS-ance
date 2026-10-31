"""
Local Ollama runtime client for RepoSéance.
Connects to localhost:11434, queries installed models, and performs bounded inference.
"""

import json
from typing import Dict, Any, List, Optional
import httpx

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"
FALLBACK_MODELS = ["qwen2.5-coder:7b", "qwen2.5:3b", "qwen2.5:1.5b", "gemma2:2b", "llama3.2:1b"]


class OllamaClient:
    """Manages local communication with the Ollama inference engine."""

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL, model_name: str = DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    async def check_status(self) -> Dict[str, Any]:
        """Checks if Ollama is reachable and returns available installed models."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    is_model_present = any(self.model_name in m for m in models)
                    return {
                        "is_available": True,
                        "base_url": self.base_url,
                        "configured_model": self.model_name,
                        "is_model_installed": is_model_present,
                        "installed_models": models,
                        "message": "Local inference engine online." if is_model_present else f"Model '{self.model_name}' not installed. Run 'ollama pull {self.model_name}' or select an installed model."
                    }
        except Exception as e:
            pass

        return {
            "is_available": False,
            "base_url": self.base_url,
            "configured_model": self.model_name,
            "is_model_installed": False,
            "installed_models": [],
            "message": "Local Ollama service not reachable on localhost:11434. Operating in offline deterministic heuristic mode."
        }

    async def generate_response(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> Optional[str]:
        """Sends a request to local Ollama and returns the completion."""
        try:
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 4096
                }
            }
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(f"{self.base_url}/api/chat", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("message", {}).get("content", "").strip()
        except Exception:
            return None
        return None
