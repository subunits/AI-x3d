## Installation & Initialization

Follow these steps to set up and run the environment locally or inside a GitHub Codespace.

### 1. Prerequisites
Ensure you have Python 3.8+ installed along with `pip`.

### 2. Install Dependencies
Run the following command to install the required web framework packages:
```bash
pip install fastapi uvicorn pydantic

```

# Semantic Kernel X3D Agent

A lightweight bridge between natural language instructions and X3D 3D scenes. This project allows you to modify 3D environments dynamically using conversational prompts, running directly in GitHub Codespaces.

## Architecture

The system uses a FastAPI backend to process natural language, parse intent, and mutate an underlying `.x3d` file. The X3D scene is rendered in the browser using the X_ite viewer.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser as X_ite Viewer
    participant API as FastAPI Server
    participant File as scene.x3d File

    User->>Browser: Types prompt & clicks Run
    Browser->>API: POST /api/agent { prompt }
    Note over API: Parses shape, color, coords
    API->>File: Modifies XML & saves file
    API-->>Browser: Returns status response
    Browser->>File: Reloads <inline url="scene.x3d">
    File-->>Browser: Serves updated XML graph
    Browser->>User: Re-renders 3D viewport
