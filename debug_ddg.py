try:
    import duckduckgo_search
    print(f"SUCCESS: duckduckgo_search imported. Version: {duckduckgo_search.__version__}")
except ImportError as e:
    print(f"FAILURE: Could not import duckduckgo_search. {e}")

try:
    from langchain_community.tools import DuckDuckGoSearchRun
    print("SUCCESS: DuckDuckGoSearchRun imported.")
    tool = DuckDuckGoSearchRun()
    print("SUCCESS: DuckDuckGoSearchRun instantiated.")
except Exception as e:
    print(f"FAILURE: DuckDuckGoSearchRun error. {e}")
