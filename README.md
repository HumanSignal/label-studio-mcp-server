# Label Studio MCP Server

## Overview

This project provides a Model Context Protocol (MCP) server that allows interaction with a Label Studio instance using the `label-studio-sdk`. It enables programmatic management of labeling projects, tasks, and predictions via natural language or structured calls from MCP clients. Using this MCP Server, you can make requests like: 

* "Create a project in label studio with this data ..." 
* "How many tasks are labeled in my RAG review project?" 
* "Add predictions for my tasks." 
* "Update my labeling template to include a comment box." 

<img src="./static/example.png" alt="Example usage of Label Studio MCP Server" width="600">

## Features

*   **Project Management**: Create, update, list, and view details/configurations of Label Studio projects.
*   **Task Management**: Import tasks from files, list tasks within projects, and retrieve task data/annotations.
*   **Prediction Integration**: Add model predictions to specific tasks.
*   **SDK Integration**: Leverages the official `label-studio-sdk` for communication.

## Prerequisites

1.  **Running Label Studio Instance:** You need a running instance of Label Studio accessible from where this MCP server will run.
2.  **API Key:** Obtain an API key from your user account settings in Label Studio.

## Configuration

The MCP server requires the URL and API key for your Label Studio instance. If launching the server via an MCP client configuration file, you can specify the environment variables directly within the server definition. This is often preferred for client-managed servers.

Example `mcp.json` entry:

```json
{
    "mcpServers": {
        "label-studio": {
            "command": "uv",
            "args": [
                "run",
                "--with", 
                "label-studio-mcp", 
                "--python",
                "3.13",
                "label-studio-mcp"
            ],
            "env": {
                "LABEL_STUDIO_API_KEY": "your_actual_api_key_here", // <-- Your API key
                "LABEL_STUDIO_URL": "http://localhost:8080"
            }
        }
    }
}
```
<!-- 
## Installation
Follow these instructions to install the server. 
```bash
git clone https://github.com/HumanSignal/label-studio-mcp-server.git 
cd label-studio-mcp-server

# Install dependencies using uv
uv venv
source .venv/bin/activate 
uv sync
```


    ```json
    {
      "mcpServers": {
        "label-studio": {
            "command": "uv",
            "args": [
                "--directory",
                "/path/to/your/label-studio-mcp-server", // <-- Update this path
                "run",
                "label-studio-mcp.py"
            ],
            "env": {
                "LABEL_STUDIO_API_KEY": "your_actual_api_key_here", // <-- Your API key
                "LABEL_STUDIO_URL": "http://localhost:8080"
            }
        }
      }
    }
    ```
    When configured this way, the `env` block injects the variables into the server process environment, and the script's `os.getenv()` calls will pick them up. -->

## Install for Claude Desktop

To install the MCP server for [Claude Desktop](https://claude.ai/download), you can run the following command from the root of this repository:
```bash
mcp install -e . -v LABEL_STUDIO_API_KEY=<your_api_key> -v LABEL_STUDIO_URL=<your_label_studio_url> label-studio-mcp.py
```

## Tools

The MCP server exposes the following tools:

### Project Management

*   **`get_label_studio_projects_tool()`**: Lists available projects (ID, title, task count).
*   **`get_label_studio_project_details_tool(project_id: int)`**: Retrieves detailed information for a specific project.
*   **`get_label_studio_project_config_tool(project_id: int)`**: Fetches the XML labeling configuration for a project.
*   **`create_label_studio_project_tool(title: str, label_config: str, ...)`**: Creates a new project with a title, XML config, and optional settings. Returns project details including a URL.
*   **`update_label_studio_project_config_tool(project_id: int, new_label_config: str)`**: Updates the XML labeling configuration for an existing project.

### Task Management

*   **`list_label_studio_project_tasks_tool(project_id: int)`**: Lists task IDs within a project (up to 100).
*   **`get_label_studio_task_data_tool(project_id: int, task_id: int)`**: Retrieves the data payload for a specific task.
*   **`get_label_studio_task_annotations_tool(project_id: int, task_id: int)`**: Fetches existing annotations for a specific task.
*   **`import_label_studio_project_tasks_tool(project_id: int, tasks_file_path: str)`**: Imports tasks from a JSON file (containing a list of task objects) into a project. Returns import summary and project URL.

### Predictions

*   **`create_label_studio_prediction_tool(task_id: int, result: List[Dict[str, Any]], ...)`**: Creates a prediction for a specific task. Requires the prediction result as a list of dictionaries matching the Label Studio format. Optional `model_version` and `score`.

## Example Use Case

1.  Create a new project using `create_label_studio_project_tool`.
2.  Prepare a JSON file (`tasks.json`) with task data.
3.  Import tasks using `import_label_studio_project_tasks_tool`, providing the project ID from step 1 and the path to `tasks.json`.
4.  List task IDs using `list_label_studio_project_tasks_tool`.
5.  Get data for a specific task using `get_label_studio_task_data_tool`.
6.  Generate a prediction result structure (list of dicts).
7.  Add the prediction using `create_label_studio_prediction_tool`.



## Contact

For questions or support, reach out via [GitHub Issues](https://github.com/HumanSignal/label-studio-mcp-server/issues).
