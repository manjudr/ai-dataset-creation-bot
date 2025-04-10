# AI Chat System

A real-time AI chat system with a modern web interface built using React and Material UI, connected to a Python backend using WebSocket. The system is designed to help users create datasets step by step.

## Features

- Modern, responsive UI built with Material UI
- Real-time chat using WebSocket
- Support for streaming AI responses
- Automatic reconnection on connection loss
- Multi-line message input
- Loading indicators
- Message history with user/AI message distinction
- Error handling with user-friendly notifications
- Dataset creation assistant with step-by-step guidance

## Prerequisites

- Node.js (v14 or higher)
- Python 3.8 or higher
- Ollama running locally with the Mistral model

## Setup and Running

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Start the Python backend server:
```bash
python main.py
# or
uvicorn main:app --reload
```

3. Install frontend dependencies and start the development server:
```bash
cd frontend
npm install
npm start
```

4. Make sure Ollama is running with the Mistral model:
```bash
ollama run mistral
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend WebSocket: ws://localhost:8000/ws
- Backend API: http://localhost:8000

## Color Scheme

The application uses a professional color palette:
- Primary: Blue (#2196f3)
- Secondary: Pink (#f50057)
- Background: Light Gray (#f5f5f5)
- Paper: White (#ffffff)

## Architecture

- Frontend: React with Material UI
- Backend: FastAPI with WebSocket support
- AI Model: Ollama with Mistral
- Real-time Communication: WebSocket

## Backend Features

- WebSocket server for real-time communication
- Streaming AI responses from Ollama
- Conversation history tracking
- Error handling and logging
- CORS support for frontend integration
- Automatic reconnection on disconnection
- Dataset creation assistant with context management
- JSON parsing and validation
- Step-by-step dataset configuration flow

## Frontend Features

- Real-time message streaming
- Typing indicators
- Error notifications
- Responsive design
- Multi-line message input
- Message history with user/AI distinction

## Dataset Creation Flow

The AI assistant guides users through the following steps:

1. **Dataset Purpose**: Define the purpose of the dataset
2. **Data Source**: Specify where the data is located
3. **Storage Recommendation**: Choose between Apache Hudi or Apache Druid
4. **Dataset Name**: Generate and select a name for the dataset
5. **Sample Data**: Provide a sample JSON event or schema
6. **PII Analysis**: Identify and configure PII fields
7. **Deduplication**: Set up deduplication keys
8. **Timestamp Configuration**: Configure timestamp fields
9. **Final Confirmation**: Review and confirm the complete configuration 