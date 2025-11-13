# Cooking Assistant

## Overview
An intelligent cooking assistant built with Python and LLM agents. The assistant helps users discover recipes based on available ingredients and guides them step-by-step through the cooking process with timer support.

## Recent Changes
- **November 13, 2025**: Initial project setup
  - Created state machine for managing cooking workflow states
  - Integrated OpenAI LLM for natural language understanding
  - Implemented timer functionality for cooking steps (timestamp-based polling)
  - Built interactive CLI with Rich library
  - Added servings tracking - assistant asks number of people at start and adjusts all quantities

## Features
- **Servings-aware cooking**: Asks for number of people at the start and adjusts all ingredient quantities
- **Ingredient-based recipe suggestions**: Provide your ingredients, get recipe recommendations
- **State-based workflow**: Natural progression through cooking stages
- **Step-by-step guidance**: LLM-powered assistance for each cooking step with specific quantities
- **Timer management**: Track cooking times for various steps with countdown display
- **Interactive CLI**: Clean, colorful terminal interface with retry logic for inputs

## Project Architecture

### States
- `STARTING`: Initial greeting and introduction
- `INGREDIENT_COLLECTION`: Gathering available ingredients from user
- `RECIPE_PROPOSAL`: LLM suggests recipes based on ingredients
- `RECIPE_CONFIRMATION`: User selects preferred recipe
- `COOKING_GUIDANCE`: Main cooking state with step-by-step instructions
- `STEP_EXECUTION`: Execute individual cooking steps with timers
- `COMPLETED`: Recipe finished

### Core Components
- `src/states.py`: State machine implementation
- `src/llm_agent.py`: OpenAI LLM wrapper for intelligent responses
- `src/timer.py`: Cooking timer functionality
- `src/cooking_assistant.py`: Main application orchestrator
- `main.py`: Entry point

### Dependencies
- `openai`: LLM integration for recipe and guidance generation
- `rich`: Terminal formatting and UI
- `python-dotenv`: Environment configuration

## User Preferences
- Focused on simplicity and testing of basic components
- State-based architecture with LLM-driven transitions
- Terminal-based interface for easy testing

## Next Steps
- Add MCP server integration for structured recipe databases
- Implement multimodal capabilities (image recognition for ingredients)
- Add voice interaction support
- Create recipe history and favorites tracking
