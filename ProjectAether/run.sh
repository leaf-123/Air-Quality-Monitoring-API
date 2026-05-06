#!/usr/bin/env bash

# Start the Aether FastAPI server
uvicorn aether.main:app --reload --app-dir src
