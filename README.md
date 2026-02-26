# OpenApply Agent

A local-first, AI-powered job search and application automation tool that runs entirely on your machine. All data including your resume and job tracking stays local in an SQLite database.

## Prerequisites

- Python 3.12+
- Gemini API Key (default) or OpenAI API Key

## Setup & Installation

If you are running this in your own VS Code environment (without Antigravity), follow these steps:

1. **Set up Environment Variables**:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and paste your `GEMINI_API_KEY` (or `OPENAI_API_KEY` if you change `LLM_PROVIDER=openai`).

2. **Install Dependencies**:
   Install the application in editable mode. This will install LangChain, Streamlit, SQLAlchemy, and all necessary browser UI frameworks.
   ```bash
   pip install -e "."
   ```

3. **Run the Application**:
   Launch the Streamlit interface. 
   *(Note: Currently, we boot directly into the Setup page because the main dashboard is still under construction).*
   ```bash
   streamlit run ui/pages/1_setup.py
   ```

## Architecture Status
- **Phase 1**: Core State & Schema (Done)
- **Phase 2**: Discovery Nodes fetching from Remotive, RemoteOK, Arbeitnow (Done)
- **Phase 3**: AI Scoring Engine using strict JSON schema (Done)
- **Phase 4**: Resume Ingestion & DB Storage (Done)
- **Phase 5**: Tailoring & PDF Generation (Pending)
