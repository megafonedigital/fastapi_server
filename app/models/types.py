from typing import Dict, Any, Optional, List, Union, Callable, Awaitable
from uuid import UUID, uuid4

# Type aliases
JsonDict = Dict[str, Any]
TaskCallback = Callable[[str, Any], Awaitable[None]]

# Task tracking
class TaskManager:
    """
    Simple in-memory task manager for tracking background tasks
    """
    _tasks: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def create_task(cls, task_type: str) -> str:
        """
        Create a new task and return its ID
        
        Args:
            task_type: Type of task (download, transcription)
            
        Returns:
            str: Task ID
        """
        task_id = str(uuid4())
        cls._tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "status": "pending",
            "progress": 0.0,
            "result": None,
            "error": None
        }
        return task_id
    
    @classmethod
    def update_task(cls, task_id: str, **kwargs) -> None:
        """
        Update task status and details
        
        Args:
            task_id: Task ID
            **kwargs: Task attributes to update
        """
        if task_id in cls._tasks:
            cls._tasks[task_id].update(kwargs)
    
    @classmethod
    def get_task(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task details
        
        Args:
            task_id: Task ID
            
        Returns:
            Optional[Dict[str, Any]]: Task details or None if not found
        """
        return cls._tasks.get(task_id)
    
    @classmethod
    def delete_task(cls, task_id: str) -> None:
        """
        Delete a task
        
        Args:
            task_id: Task ID
        """
        if task_id in cls._tasks:
            del cls._tasks[task_id]