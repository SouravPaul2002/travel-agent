from duckduckgo_search import DDGS

def search_web(query: str) -> str:
    """
    Searches the web for the given query using DuckDuckGo.
    Returns a string summary of the top results.
    """
    try:
        results = DDGS().text(query, max_results=5)
        if not results:
            return "No results found."
        
        formatted_results = []
        for r in results:
            formatted_results.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
            
        return "\n---\n".join(formatted_results)
    except Exception as e:
        return f"Error performing search: {str(e)}"

if __name__ == "__main__":
    # Simple test
    print(search_web("weather in Tokyo"))
