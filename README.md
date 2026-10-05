# Agentic AI-Based Travel Agent

**Project Title**: Agentic AI-Based Travel Agent
**Date**: December 2025
**Tech Stack**: Python, Streamlit, LangChain, Google Gemini

## Overview
This is an advanced AI-powered Travel Agent capable of planning itineraries, checking real-time information, and assisting travelers using Agentic workflows. It leverages **Google's Gemini models** via **LangChain** to reason and use tools (DuckDuckGo Search) to provide accurate, up-to-date responses.

## Features
- **Intelligent Planning**: Generates detailed day-by-day itineraries.
- **Real-time Web Search**: Fetches current weather, events, and prices using DuckDuckGo.
- **Context Aware**: Remembers conversation history for a seamless chat experience.
- **Interactive UI**: Built with Streamlit for a clean, modern interface.

## Setup Instructions

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd travel_agent
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**:
    Create a `.env` file in the root directory and add your Google API Key:
    ```env
    GOOGLE_API_KEY=your_api_key_here
    ```

4.  **Run the Application**:
    ```bash
    streamlit run app.py
    ```

## Usage
Simply type your travel query in the chat box!
*   "Plan a 3-day trip to Kyoto in Spring."
*   "What is the weather in New York right now?"
*   "Find cheap flights from London to Paris."

## License
MIT
