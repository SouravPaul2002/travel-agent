import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import Tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

class TravelAgent:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env file")
        
        # Initialize Google Gemini
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-flash-latest",
            google_api_key=self.api_key,
            temperature=0.7
        )
        
        # Initialize Tools
        # Using a custom tool wrapper to avoid dependency issues with langchain-community
        from duckduckgo_search import DDGS
        
        def custom_search_func(query: str):
            try:
                # DDGS().text() returns a list of dictionaries
                results = DDGS().text(query, max_results=5)
                if not results:
                    return "No results found."
                # Format results
                return "\n\n".join([f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}" for r in results])
            except Exception as e:
                 return f"Search error: {e}"

        self.tools = [
            Tool(
                name="search_web",
                func=custom_search_func,
                description="Useful for when you need to answer questions about current events, travel information, weather, or prices."
            )
        ]
        
        # Create the LangGraph Agent (ReAct)
        # This replaces AgentExecutor and create_tool_calling_agent
        self.agent_executor = create_react_agent(self.llm, self.tools)

    def run(self, message, history=[]):
        """
        Runs the agent loop using LangGraph.
        """
        # LangGraph inputs: {"messages": [list of messages]}
        # We construct the messages list from history + new message
        
        messages = list(history)
        messages.append(HumanMessage(content=message))
        
        # Invoke via .invoke
        response = self.agent_executor.invoke({"messages": messages})
        
        # Output is the last message content
        return response["messages"][-1].content
