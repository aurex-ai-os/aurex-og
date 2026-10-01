import subprocess
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class DockerManager:
    """Manages spawning background Docker containers (e.g. SearXNG)."""
    
    @staticmethod
    def is_docker_installed() -> bool:
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True, check=True)
            return "Docker version" in result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
            
    @staticmethod
    def is_searxng_running() -> bool:
        try:
            result = subprocess.run(["docker", "ps", "--filter", "name=aurex-search", "--format", "{{.Names}}"], capture_output=True, text=True, check=True)
            return "aurex-search" in result.stdout
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def launch_searxng() -> Tuple[bool, str]:
        """Launches the SearXNG Docker container and binds it to 8080."""
        if not DockerManager.is_docker_installed():
            return False, "Docker is not installed or not running."
            
        if DockerManager.is_searxng_running():
            return True, "SearXNG is already running."
            
        try:
            # First try to remove any stopped container with the same name
            subprocess.run(["docker", "rm", "-f", "aurex-search"], capture_output=True)
            
            # Run the container
            cmd = [
                "docker", "run", "-d", 
                "--name", "aurex-search",
                "-p", "8080:8080",
                "-e", "BASE_URL=http://localhost:8080/",
                "-e", "INSTANCE_NAME=aurex-search",
                "-e", "SEARXNG_SETTINGS_FORMAT=json",
                "searxng/searxng"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Successfully launched SearXNG: {result.stdout.strip()}")
            return True, "Successfully launched SearXNG."
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to launch SearXNG: {e.stderr}")
            return False, f"Docker error: {e.stderr}"
