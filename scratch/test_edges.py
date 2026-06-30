from google.adk.workflow import Workflow, START, Edge, FunctionNode
from google.adk.agents import LlmAgent
from google.adk.models import Gemini

def security_checkpoint(node_input):
    return node_input

def alert(x):
    return "alert"

orchestrator = LlmAgent(
    name="orchestrator",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="Hello",
)

try:
    print("Testing tuple-based edges...")
    edges_tuple = [
        (START, security_checkpoint),
        (security_checkpoint, {
            "SECURITY_EVENT": alert,
            "CLEAN": orchestrator
        })
    ]
    wf = Workflow(name="wf1", edges=edges_tuple)
    print("wf1 created successfully with tuples!")
except Exception as e:
    print("wf1 failed with tuples:", e)

try:
    print("Testing Edge-based edges with wrapped nodes...")
    edges_obj = [
        Edge(from_node=START, to_node=FunctionNode(func=security_checkpoint)),
        Edge(from_node=FunctionNode(func=security_checkpoint), to_node=orchestrator, route="CLEAN")
    ]
    wf = Workflow(name="wf2", edges=edges_obj)
    print("wf2 created successfully with Edge objects!")
except Exception as e:
    print("wf2 failed with Edge objects:", e)
