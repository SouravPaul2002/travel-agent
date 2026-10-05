try:
    from langchain.agents import AgentExecutor
    print("SUCCESS: AgentExecutor imported.")
except ImportError as e:
    print(f"FAILURE: {e}")

try:
    from langchain.agents import create_tool_calling_agent
    print("SUCCESS: create_tool_calling_agent imported.")
except ImportError as e:
    print(f"FAILURE: {e}")
