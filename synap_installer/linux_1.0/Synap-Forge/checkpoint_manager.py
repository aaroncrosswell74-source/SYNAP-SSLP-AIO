# checkpoint_manager.py
"""
RL Model Checkpoint Manager
Handles saving and loading of RL state
"""

import json
import pickle
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class CheckpointManager:
    """Manage RL model checkpoints"""
    
    def __init__(self, checkpoint_dir: Path = Path("state/checkpoints")):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.latest_symlink = self.checkpoint_dir / "latest"
    
    async def save(self, data: Dict[str, Any], name: str = None) -> Path:
        """Save a checkpoint"""
        if name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"checkpoint_{timestamp}"
        
        checkpoint_path = self.checkpoint_dir / f"{name}.json"
        
        # Add metadata
        checkpoint_data = {
            "metadata": {
                "name": name,
                "timestamp": datetime.now().isoformat(),
                "version": "2.0.0"
            },
            "data": data
        }
        
        # Save with atomic write
        temp_path = checkpoint_path.with_suffix(".tmp")
        try:
            with open(temp_path, 'w') as f:
                json.dump(checkpoint_data, f, indent=2, default=str)
            
            # Atomic rename
            temp_path.rename(checkpoint_path)
            
            # Update latest symlink
            if self.latest_symlink.exists() or self.latest_symlink.is_symlink():
                self.latest_symlink.unlink()
            self.latest_symlink.symlink_to(checkpoint_path.name)
            
            logger.info(f"Saved checkpoint: {checkpoint_path}")
            return checkpoint_path
            
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            logger.error(f"Failed to save checkpoint: {e}")
            raise
    
    async def load(self, name: str = None) -> Optional[Dict[str, Any]]:
        """Load a checkpoint"""
        if name is None:
            # Load latest
            if self.latest_symlink.exists() and self.latest_symlink.is_symlink():
                checkpoint_path = self.checkpoint_dir / self.latest_symlink.readlink()
            else:
                # Find latest by timestamp
                checkpoints = sorted(self.checkpoint_dir.glob("checkpoint_*.json"))
                if not checkpoints:
                    return None
                checkpoint_path = checkpoints[-1]
        else:
            checkpoint_path = self.checkpoint_dir / f"{name}.json"
        
        if not checkpoint_path.exists():
            logger.warning(f"Checkpoint not found: {checkpoint_path}")
            return None
        
        try:
            with open(checkpoint_path, 'r') as f:
                checkpoint_data = json.load(f)
            
            logger.info(f"Loaded checkpoint: {checkpoint_path}")
            return checkpoint_data
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all checkpoints with metadata"""
        checkpoints = []
        for path in sorted(self.checkpoint_dir.glob("checkpoint_*.json")):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                checkpoints.append({
                    "name": path.stem,
                    "path": str(path),
                    "timestamp": data.get("metadata", {}).get("timestamp"),
                    "is_latest": path.name == self.latest_symlink.readlink() if self.latest_symlink.exists() else False
                })
            except Exception as e:
                logger.warning(f"Failed to read checkpoint metadata: {e}")
        return checkpoints
    
    async def clean_old(self, keep: int = 5):
        """Keep only the most recent N checkpoints"""
        checkpoints = sorted(self.checkpoint_dir.glob("checkpoint_*.json"))
        if len(checkpoints) <= keep:
            return
        
        for checkpoint in checkpoints[:-keep]:
            checkpoint.unlink()
            logger.info(f"Removed old checkpoint: {checkpoint}")