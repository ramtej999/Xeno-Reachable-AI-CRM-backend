# Reachable AI: Backend Services

This directory contains the backend infrastructure for the **Reachable AI** CRM. It is built with **FastAPI** and powered by **PostgreSQL** and **Groq (LLaMA-3)**.

## Architecture Overview

The backend is composed of two independent microservices running on different ports:

1. **Main CRM API (`port 8000`)**: Handles user authentication, database operations (customers, segments, campaigns), analytics calculations, and LLM integrations for the AI Copilot.
2. **Channel Simulator Service (`port 8001`)**: A dedicated mock service that simulates sending messages (WhatsApp, SMS, Email) to customers. It handles delayed processing and sends delivery/open/click/purchase webhooks back to the main API.

## Tech Stack

*   **Framework**: FastAPI
*   **Database**: PostgreSQL (Neon Serverless)
*   **ORM**: SQLAlchemy + Pydantic
*   **AI Engine**: Groq (LLaMA-3.3-70b-versatile)
*   **Authentication**: JWT (JSON Web Tokens)
*   **Concurrency**: AsyncIO for webhook handling and parallel API calls

## Environment Variables

Create a `.env` file in the `backend` directory with the following variables:

```env
DATABASE_URL=postgresql://<user>:<password>@<host>/<database>?sslmode=require
GROQ_API_KEY=gsk_********************************
GROQ_MODEL=llama-3.3-70b-versatile
CHANNEL_SERVICE_URL=http://localhost:8001
CRM_WEBHOOK_URL=http://localhost:8000/webhook
```

## Running Locally

1. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Main API**:
   ```bash
   python -m uvicorn app.main:app --port 8000 --reload
   ```

4. **Start the Channel Simulator** (in a new terminal):
   ```bash
   python -m uvicorn channel_service.main:app --port 8001 --reload
   ```

## Key Directories

*   `app/main.py`: Main entrypoint and FastAPI application instance.
*   `app/models/`: SQLAlchemy ORM definitions for database tables.
*   `app/schemas/`: Pydantic models for request/response validation.
*   `app/routes/`: API endpoint definitions (auth, customers, campaigns, copilot, analytics).
*   `app/services/`: Core business logic (Groq API integrations, segment building, negotiation logic).
*   `channel_service/`: The independent messaging webhook simulator.
