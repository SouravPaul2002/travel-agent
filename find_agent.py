import langchain.agents
import pkgutil
import sys

print(f"LangChain Agents Path: {langchain.agents.__path__}")

found_ae = False
found_ctca = False

# Iterate over submodules
def scan_package(package):
    global found_ae, found_ctca
    for importer, modname, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        # Skip weird modules or tests
        if "test" in modname: continue
        
        try:
            module = __import__(modname, fromlist="dummy")
            if hasattr(module, "AgentExecutor"):
                print(f"FOUND AgentExecutor in: {modname}")
                found_ae = True
            if hasattr(module, "create_tool_calling_agent"):
                print(f"FOUND create_tool_calling_agent in: {modname}")
                found_ctca = True
        except ImportError:
            pass
        except Exception as e:
            # print(f"Skipping {modname}: {e}")
            pass

scan_package(langchain.agents)

if not found_ae:
    print("AgentExecutor NOT FOUND in langchain.agents tree.")
if not found_ctca:
    print("create_tool_calling_agent NOT FOUND in langchain.agents tree.")
