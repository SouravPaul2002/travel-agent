import sys
try:
    import langchain
    print(f"LangChain version: {langchain.__version__}")
    
    import langchain.agents
    print("langchain.agents contents:")
    print(dir(langchain.agents))
    
    from langchain.agents import AgentExecutor
    print("AgentExecutor imported successfully")
except Exception as e:
    print(f"Error: {e}")
