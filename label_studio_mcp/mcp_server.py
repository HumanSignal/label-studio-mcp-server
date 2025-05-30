from typing import Any, List, Dict, Optional
import httpx
from mcp.server.fastmcp import FastMCP
import os
import json
from label_studio_sdk.client import LabelStudio
import argparse
import functools
from label_studio_sdk.label_interface import LabelInterface
from pydantic import BaseModel
import datetime

from .mcp_env import LABEL_STUDIO_URL, LABEL_STUDIO_API_KEY, ls

# Initialize FastMCP server
mcp = FastMCP("label-studio-mcp")

# Helper to handle potential lack of LS connection
def require_ls_connection(func):
    # Preserve original signature using functools.wraps
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if ls is None:
            # Make the error message more informative
            return ("Error: Label Studio client not available. "
                    "Please check server logs for initialization errors "
                    "(e.g., missing 'LABEL_STUDIO_API_KEY', invalid key, or connection issue with 'LABEL_STUDIO_URL').")
        try:
            # Execute the wrapped function (tool or resource handler)
            return func(*args, **kwargs)
        except Exception as e:
            # Return a more informative error message for debugging
            import traceback
            error_type = type(e).__name__
            error_details = str(e)
            # traceback_str = traceback.format_exc() # Optional: include full traceback
            return f"Error in function '{func.__name__}': [{error_type}] {error_details}"
    return wrapper

# --- JSON Serializer for Datetime Objects ---
def json_datetime_serializer(obj):
    """JSON serializer for datetime objects.
    Converts datetime objects to ISO 8601 string format.
    """
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

# ============================================
# == Label Studio Tool Definitions          ==
# ============================================

@mcp.tool()
@require_ls_connection
def get_label_studio_projects_tool() -> str:
    """Lists available Label Studio projects (Tool version)."""
    # Use ls.projects.list() - returns a pager
    projects_pager = ls.projects.list()
    projects_summary = []
    projects_processed = 0
    # Iterate over the pager
    for project in projects_pager:  # <-- Iteration, no subscripting
        if projects_processed >= 100: # Limit for safety/brevity
            break
        project_data = {
            "id": project.id,
            "title": getattr(project, 'title', 'N/A'),
            "task_count": getattr(project, 'task_number', 0) # Use task_number attribute
        }
        projects_summary.append(project_data)
        projects_processed += 1

    return json.dumps(projects_summary)

@mcp.tool()
@require_ls_connection
def get_label_studio_project_details_tool(project_id: int) -> str:
    """Provides details for a specific Label Studio project (Tool version)."""
    project = ls.projects.get(id=project_id) 
    # Assuming the project object has model_dump or dict method
    if hasattr(project, 'model_dump'):
        project_data = project.model_dump(exclude={'created_at', 'updated_at'})
        project_data['created_at'] = project.created_at.isoformat() if project.created_at else None
        return json.dumps(project_data)
    elif hasattr(project, 'dict'):
         project_dict = project.dict()
         project_dict['created_at'] = project.created_at.isoformat() if project.created_at else None # Handle datetime if it exists
         project_dict.pop('updated_at', None)
         return json.dumps(project_dict)
    else:
        # Fallback if direct serialization is not available
        return json.dumps({"id": project.id, "title": getattr(project, 'title', 'N/A')})

@mcp.tool()
@require_ls_connection
def get_label_studio_project_config_tool(project_id: int) -> str:
    """Provides the XML labeling configuration for a Label Studio project (Tool version)."""
    project = ls.projects.get(id=project_id)
    return project.label_config

@mcp.tool()
@require_ls_connection
def list_label_studio_project_tasks_tool(project_id: int) -> str:
    """Lists tasks within a specific Label Studio project (Tool version). Fetches up to 50 tasks.
    Note: This retrieves basic task info (ID and data keys) for brevity.
    """
    # Corrected: Use ls.tasks.list - this returns a pager
    tasks_pager = ls.tasks.list(project=project_id) 
    
    task_list_summary = []
    tasks_processed = 0
    # Iterate directly over the pager object and manually limit
    for task in tasks_pager:
        if tasks_processed >= 50:
            break # Stop after processing 50 tasks
            
        task_summary = {"id": task.id}
        if hasattr(task, 'data') and isinstance(task.data, dict):
            task_summary["data_keys"] = list(task.data.keys())
        else:
            task_summary["data_keys"] = []
        task_list_summary.append(task_summary)
        tasks_processed += 1
        
    return json.dumps(task_list_summary)

@mcp.tool()
@require_ls_connection
def get_label_studio_task_data_tool(project_id: int, task_id: int) -> str:
    """Provides the data payload for a specific Label Studio task (Tool version)."""
    task = ls.tasks.get(id=task_id)
    # Assuming task object has a data attribute which is a dictionary
    if hasattr(task, 'data'):
        return json.dumps(task.data)
    else:
        return json.dumps({}) # Return empty dict if data attribute missing

@mcp.tool()
@require_ls_connection
def get_label_studio_task_annotations_tool(project_id: int, task_id: int) -> str:
    """Provides annotations for a specific Label Studio task (Tool version)."""
    task = ls.tasks.get(id=task_id)
    
    if not hasattr(task, 'get_annotations'):
        raise AttributeError(f"Task object (id: {task_id}) does not have get_annotations method.")
        
    annotations = task.get_annotations()
    # Assuming get_annotations returns a list of objects with model_dump or dict
    serialized_annotations = []
    for anno in annotations:
        if hasattr(anno, 'model_dump'):
            serialized_annotations.append(anno.model_dump())
        elif hasattr(anno, 'dict'):
            serialized_annotations.append(anno.dict())
        elif isinstance(anno, dict):
            serialized_annotations.append(anno) # If already a dict
        else:
            # Fallback for unknown annotation format
            serialized_annotations.append({"details": str(anno)})

    return json.dumps(serialized_annotations)

@mcp.tool()
@require_ls_connection
def create_label_studio_project_tool(
    title: str, 
    label_config: str, # Expecting XML string from the caller
    description: str | None = None,
    expert_instruction: str | None = None,
    show_instruction: bool | None = False,
    show_skip_button: bool | None = True,
    enable_empty_annotation: bool | None = True,
    show_annotation_history: bool | None = False,
    color: str | None = None,
    # Add other relevant parameters from API/SDK as needed
) -> str:
    """Creates a new Label Studio project using the SDK (Tool version).
    Returns JSON including the project details and a direct link to the project's data manager view.
    
    Args:
        title (str): The title for the new project. REQUIRED.
        label_config (str): The XML string defining the labeling interface. REQUIRED.
        description (str | None): Optional description for the project.
        expert_instruction (str | None): Optional instructions for labelers.
        # ... add descriptions for other parameters ...
        
    IMPORTANT Call Guidance:
    - For optional string parameters (like 'description', 'expert_instruction', 'color'): 
      If you do not want to provide a value, **omit the parameter entirely** from your call.
      Do not pass `null` or an empty string `""` unless you specifically intend for that value.

    Reference: https://github.com/HumanSignal/label-studio-sdk?tab=readme-ov-file#create-a-new-project
               https://api.labelstud.io/api-reference/api-reference/projects/create
    """
    kwargs = {
        "title": title, 
        "label_config": label_config, 
        "description": description,
        "expert_instruction": expert_instruction,
        "show_instruction": show_instruction,
        "show_skip_button": show_skip_button,
        "enable_empty_annotation": enable_empty_annotation,
        "show_annotation_history": show_annotation_history,
        "color": color,
    }
    # Filter out None values to avoid sending them in the request
    # This internal filtering handles cases where the parameter *was* omitted in the call
    filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

    # Pass the filtered keyword arguments directly to ls.projects.create
    project = ls.projects.create(**filtered_kwargs)
    
    # Construct the project URL
    project_url = f"{LABEL_STUDIO_URL}/projects/{project.id}/data"
    
    # Manually construct the response dictionary with reliable attributes
    response_data = {
        "id": project.id,
        "title": project.title,
        "project_url": project_url, # Add the URL to the response
    }
    # Attempt to add other fields common in the full API response if they exist
    for attr in ['description', 'color', 'expert_instruction', 'created_at', 'label_config']:
        if hasattr(project, attr):
            value = getattr(project, attr)
            # Handle datetime serialization
            if hasattr(value, 'isoformat'):
                response_data[attr] = value.isoformat()
            else:
                response_data[attr] = value
                
    return json.dumps(response_data)

@mcp.tool()
@require_ls_connection
def update_label_studio_project_config_tool(
    project_id: int,
    new_label_config: str, # The complete, updated XML config string
) -> str:
    """Updates the labeling configuration for a specific Label Studio project.
    
    Args:
        project_id (int): The ID of the project to update.
        new_label_config (str): The **complete** new XML labeling configuration string.
            This will replace the existing configuration.

    Returns:
        JSON string containing the details of the updated project, including the new 
        label config and a link to the project URL.
        
    Reference: Uses ls.projects.update from the SDK v1.0+ (assumed based on PATCH API endpoint).
    """
    try:
        # Call the update method directly on the client's projects manager
        updated_project = ls.projects.update(id=project_id, label_config=new_label_config)
        
        # Construct the project URL
        project_url = f"{LABEL_STUDIO_URL}/projects/{updated_project.id}/data"
        
        # Manually construct the response dictionary 
        # (assuming updated_project might not have reliable serialization)
        response_data = {
            "id": updated_project.id,
            "title": getattr(updated_project, 'title', 'N/A'), # Safely get attributes
            "label_config": getattr(updated_project, 'label_config', new_label_config),
            "project_url": project_url, 
            "message": "Project configuration updated successfully."
        }
        # Attempt to add other common fields if they exist
        for attr in ['description', 'color', 'expert_instruction', 'created_at']:
            if hasattr(updated_project, attr):
                value = getattr(updated_project, attr)
                if hasattr(value, 'isoformat'):
                    response_data[attr] = value.isoformat()
                else:
                    response_data[attr] = value
                    
        return json.dumps(response_data)

    except Exception as e:
        # Catch errors specifically during the update API call
        import traceback
        return f"Error during Label Studio project config update API call: {type(e).__name__} - {e}\n{traceback.format_exc()}"

@mcp.tool()
@require_ls_connection
def import_label_studio_project_tasks_tool(
    project_id: int,
    # Change parameter to accept a file path
    tasks_file_path: str, 
) -> str:
    """Imports tasks into a specific Label Studio project from a JSON file.
    Returns JSON including the import summary and a direct link to the project's data manager view.
    
    Args:
        project_id (int): The ID of the target Label Studio project.
        tasks_file_path (str): The path (relative to workspace or absolute) 
                             to a JSON file containing the tasks to import. 
                             The file MUST contain a valid JSON array (list) 
                             of task data dictionaries.
    
    Example file content (e.g., tasks.json):
    [
        {"data": {"text": "Sentence 1"}},
        {"data": {"text": "Sentence 2"}}
    ]

    Reference: Uses ls.projects.import_tasks from the SDK v1.0+.
               https://api.labelstud.io/api-reference/introduction/getting-started
    """
    tasks_list = None
    try:
        # Read and parse the JSON file
        with open(tasks_file_path, 'r') as f:
            tasks_list = json.load(f) # Use json.load for file handle
            
        if not isinstance(tasks_list, list):
            raise ValueError(f"JSON file '{tasks_file_path}' must contain a valid JSON array (list).")
        
        # Optional: Add validation for task format within the list if needed
        
    except FileNotFoundError:
        return f"Error: Tasks file not found at path: {tasks_file_path}"
    except PermissionError:
        return f"Error: Permission denied when trying to read file: {tasks_file_path}"
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON format in file '{tasks_file_path}' - {e}"
    except ValueError as e:
        return f"Error processing tasks file: {e}"
    except Exception as e:
        import traceback
        return f"Unexpected error reading/processing tasks file '{tasks_file_path}': {type(e).__name__} - {e}\n{traceback.format_exc()}"

    # We don't need to get the project object first for bulk import using ls.projects.import_tasks
    # project = ls.projects.get(id=project_id) # Removed

    # Construct the project URL
    project_url = f"{LABEL_STUDIO_URL}/projects/{project_id}/data"

    # Call the import method directly on the client's projects manager
    # Use 'request' parameter based on SDK v1.0+ documentation
    try:
        import_result = ls.projects.import_tasks(id=project_id, request=tasks_list)
    except Exception as e:
        # Catch errors specifically during the import API call
        import traceback
        return f"Error during Label Studio task import API call: {type(e).__name__} - {e}\n{traceback.format_exc()}"

    # Prepare the final response dictionary
    final_response = {}
    if isinstance(import_result, dict):
        final_response = import_result.copy() # Start with the SDK result
    elif hasattr(import_result, 'model_dump'):
        final_response = import_result.model_dump()
    elif hasattr(import_result, 'dict'):
        final_response = import_result.dict()
    else:
        # Basic fallback
        final_response = {"message": "Import initiated", "details": str(import_result)}
        
    # Add the project URL to the response
    final_response["project_url"] = project_url

    return json.dumps(final_response)

@mcp.tool()
@require_ls_connection
def create_label_studio_prediction_tool(
    task_id: int,
    result: List[Dict[str, Any]],  # Expect result as a list directly
    model_version: str = None,
    score: float = None
) -> str:
    """Creates a prediction for a specific Label Studio task.

    Args:
        task_id (int): The ID of the task to add the prediction to.
        result (List[Dict[str, Any]]): The prediction result list, containing dictionaries 
                                    matching the Label Studio prediction format.
                                    Example: [{"from_name": "label", "to_name": "text", 
                                             "type": "choices", "value": {"choices": ["Positive"]}}]
        model_version (str, optional): String identifying the model version.
        score (float, optional): Confidence score for the prediction (0.0 to 1.0).

    Returns:
        JSON string containing the details of the created prediction.
        
    Reference: Uses ls.predictions.create based on API endpoint /api/predictions/
               https://api.labelstud.io/api-reference/api-reference/predictions/create
    """
    # Prepare arguments for the SDK call, filtering out None values
    sdk_kwargs = {
        "task": task_id,  # Use 'task' instead of 'task_id' for the SDK
        "result": result,  # Already a list, no need to parse JSON
        "model_version": model_version,
        "score": score,
    }
    filtered_sdk_kwargs = {k: v for k, v in sdk_kwargs.items() if v is not None}

    try:
        # Call the create prediction method
        created_prediction = ls.predictions.create(**filtered_sdk_kwargs)
        
        # Manually construct the response dictionary with safe serialization
        response_data = {
             "message": "Prediction created successfully."
        }
        
        # Safely extract common fields and handle datetime
        for attr_name in ['id', 'task', 'model_version', 'score', 'result', 'created_at', 'updated_at']:
            if hasattr(created_prediction, attr_name):
                value = getattr(created_prediction, attr_name)
                if isinstance(value, datetime.datetime):
                    response_data[attr_name] = value.isoformat()
                elif isinstance(value, (str, int, float, list, dict, bool)) or value is None:
                    # Only include basic JSON-serializable types
                    response_data[attr_name] = value
                # else: skip other complex types
        
        # Use the basic json.dumps on the manually constructed dict
        return json.dumps(response_data)

    except Exception as e:
        # Catch errors specifically during the prediction creation API call OR manual serialization
        import traceback
        return f"Error during Label Studio prediction create/serialize: {type(e).__name__} - {e}\n{traceback.format_exc()}"