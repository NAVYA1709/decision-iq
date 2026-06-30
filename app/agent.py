# ruff: noqa
import logging
import re
import json
from typing import Any, AsyncGenerator
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.workflow import Workflow, START, node, FunctionNode, Edge
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.models import Gemini
from google.adk.apps import App, ResumabilityConfig
from google.genai import types

from app.config import config

logger = logging.getLogger(__name__)

# ==========================================
# 1. Pydantic Models for Structured Output
# ==========================================

class AnalystOutput(BaseModel):
    summary: str = Field(description="Summary of the documents analyzed.")
    key_facts: list[str] = Field(description="Important facts and findings extracted from the documents.")

class RiskOutput(BaseModel):
    risks: list[str] = Field(description="List of identified business risks.")
    severities: list[str] = Field(description="Severity levels (Low, Medium, High) corresponding to each risk.")

class OrchestratorOutput(BaseModel):
    summary: str = Field(description="Executive summary of the aggregated findings.")
    findings: list[str] = Field(description="Detailed insights gathered from document analysis.")
    risks_found: list[str] = Field(description="Major operational, financial, or strategic risks identified.")
    next_steps_plan: str = Field(description="Proposed focus and plan for the final executive report.")

class FinalReportOutput(BaseModel):
    report: str = Field(description="The complete, polished executive business intelligence report in markdown format.")

# ==========================================
# 2. MCP Server Configuration & Wiring
# ==========================================

# Configure MCP toolset using stdio connection to our local server
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "app.mcp_server"],
        )
    )
)

# ==========================================
# 3. Specialized Agents & Orchestrator (Mock support for video recordings)
# ==========================================

def get_model():
    return Gemini(
        model=config.model,
        retry_options=types.HttpRetryOptions(attempts=3),
    )

if config.mock_mode:
    class MockDocumentAnalyst(BaseAgent):
        async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
            reply = (
                "Based on 'company_goals.txt', the second goal is: "
                "**Expand market research outreach**. Other goals include improving "
                "operating margins above 15% and keeping security checks active for all user queries."
            )
            yield Event(
                output=reply,
                content=types.Content(role="model", parts=[types.Part.from_text(text=reply)])
            )

    class MockRiskAssessor(BaseAgent):
        async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
            reply = (
                "Financial Analysis for Q2:\n"
                "- **Gross Profit**: $30,000.00 (Gross Margin: 60.0%)\n"
                "- **Operating Income**: $18,000.00 (Operating Margin: 36.0%)\n"
                "- **Financial Health**: Excellent (High Profitability)\n"
                "- **Risks Identified**: COGS and OPEX are rising month-over-month. Operating margins are at risk if cost trends continue."
            )
            yield Event(
                output=reply,
                content=types.Content(role="model", parts=[types.Part.from_text(text=reply)])
            )

    class MockOrchestrator(BaseAgent):
        async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
            reply = (
                "### DecisionIQ Analysis Plan\n\n"
                "**1. Executive Summary:** The business is in excellent financial health with an operating margin of 36.0% for April, but faces medium risk from rising monthly costs.\n\n"
                "**2. Key Findings:**\n"
                "- Goal 2 in `company_goals.txt` is: **'Expand market research outreach'**.\n"
                "- April Gross Profit is **$30,000.00** (60.0% margin), and Operating Income is **$18,000.00** (36.0% margin).\n\n"
                "**3. Detected Risks:** Operational costs (COGS & OPEX) are trending upward, which could impact the 15.0% margin target in June.\n\n"
                "**4. Proposed Plan:** Proceed to draft the complete Executive Business Intelligence Report containing mitigations and recommendations."
            )
            yield Event(
                output=reply,
                content=types.Content(role="model", parts=[types.Part.from_text(text=reply)]),
                state={"orchestrator_output": reply}
            )

    class MockExecutiveReport(BaseAgent):
        async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
            report = """# DecisionIQ Business Intelligence Report

## 1. Executive Summary
DecisionIQ has conducted a multi-agent analysis of the workspace files and Q2 financials. The company is currently profitable with a 36.0% operating margin in April, but faces operational headwinds due to rising costs. Strategic goals (specifically Goal 2: expanding market research) are aligned but require careful budget allocation.

## 2. Document Findings & Analytics
*   **Company Goals (`company_goals.txt`)**: 
    1. Improve operating margins above 15.0%.
    2. **Expand market research outreach** (Goal 2).
    3. Maintain security check compliance.
*   **Q2 Financials (`q2_financials.csv` - April)**:
    *   **Revenue**: $50,000.00
    *   **COGS**: $20,000.00 (Gross Margin: 60.0%)
    *   **OPEX**: $12,000.00
    *   **Operating Income**: $18,000.00 (Operating Margin: 36.0%)

## 3. Risks & Mitigations
*   **Risk**: Rising COGS and OPEX month-over-month (Severity: **Medium**).
    *   *Mitigation*: Implement budget caps on non-essential operational expenses and audit supplier contracts.
*   **Risk**: Market expansion costs (Severity: **Low**).
    *   *Mitigation*: Phase the market research rollout quarterly to preserve cash flow.

## 4. Recommendations & Next Steps
1.  **Approve the Q2 Market Research budget** but limit initial spend to $5,000.00.
2.  **Monitor June cost trends** to ensure operating margins remain above the 15.0% threshold.
3.  **Deploy automated alerts** in DecisionIQ to flag whenever the monthly operating margin drops below 20.0%."""
            yield Event(
                output=report,
                content=types.Content(role="model", parts=[types.Part.from_text(text=report)]),
                state={"final_report": report}
            )

    document_analyst = MockDocumentAnalyst(name="document_analyst")
    risk_assessor = MockRiskAssessor(name="risk_assessor")
    orchestrator = MockOrchestrator(name="orchestrator")
    executive_report = MockExecutiveReport(name="executive_report")

else:
    # Specialized sub-agent 1: Document Intelligence
    document_analyst = LlmAgent(
        name="document_analyst",
        model=get_model(),
        instruction="""You are the Document Intelligence Agent.
    Your role is to read uploaded business documents, extract key facts, summarize contents, and identify key topics.
    Focus on fact-based summaries. Detail the findings clearly.
    Use the MCP tools list_workspace_documents and read_business_document to find and inspect files.""",
        tools=[mcp_toolset],
    )

    # Specialized sub-agent 2: Risk Assessment
    risk_assessor = LlmAgent(
        name="risk_assessor",
        model=get_model(),
        instruction="""You are the Risk Assessment Agent.
    Your role is to analyze document findings and data trends to identify potential business risks, operational issues, or compliance concerns.
    Assign a severity level (Low, Medium, High) to each risk.
    Use the MCP tool calculate_financial_metrics to compute business numbers and assess operational/financial health.""",
        tools=[mcp_toolset],
    )

    # Main Orchestrator Agent
    orchestrator = LlmAgent(
        name="orchestrator",
        model=get_model(),
        instruction="""You are the orchestrator for DecisionIQ.
    Your task is to coordinate the specialized sub-agents to answer the user query: {user_query}.
    You must delegate tasks using your tools:
    - Call document_analyst to analyze documents and extract key facts.
    - Call risk_assessor to assess potential risks based on findings.
    Synthesize their responses into a final AnalysisPlan. Describe the findings, the identified risks, and the next steps clearly.""",
        tools=[AgentTool(document_analyst), AgentTool(risk_assessor)],
        output_key="orchestrator_output",  # Saves output to ctx.state['orchestrator_output']
    )

    # Executive Report Generator
    executive_report = LlmAgent(
        name="executive_report",
        model=get_model(),
        instruction="""You are the Executive Report Agent.
    Your task is to compile the final executive-ready report in markdown.
    Use the structured analysis plan from the orchestrator: {orchestrator_output}.
    Create a highly professional, beautifully formatted business intelligence report with:
    - Title: DecisionIQ Business Intelligence Report
    - Executive Summary
    - Key Findings & Document Analytics
    - Risks and Mitigations (showing severity)
    - Actionable Recommendations & Next Steps
    Ensure it is written in a premium corporate tone without placeholders. Output raw markdown report content.""",
        output_key="final_report",
    )

# ==========================================
# 4. Workflow Function Nodes
# ==========================================

def security_checkpoint(ctx: Context, node_input: Any) -> Event:
    """Performs PII scrubbing, prompt injection, and domain-specific rules checks."""
    query_text = ""
    if isinstance(node_input, str):
        query_text = node_input
    elif hasattr(node_input, "parts") and node_input.parts:
        query_text = "".join([p.text for p in node_input.parts if hasattr(p, "text")])
    elif isinstance(node_input, dict) and "text" in node_input:
        query_text = node_input["text"]
    else:
        query_text = str(node_input)

    # 1. PII Scrubbing (Email, Credit Cards, SSN-like, etc.)
    scrubbed_query = query_text
    
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    cc_pattern = r'\b(?:\d[ -]*?){13,16}\b'
    
    emails_found = re.findall(email_pattern, scrubbed_query)
    cc_found = re.findall(cc_pattern, scrubbed_query)
    
    scrubbed_query = re.sub(email_pattern, "[EMAIL_REDACTED]", scrubbed_query)
    scrubbed_query = re.sub(cc_pattern, "[CREDIT_CARD_REDACTED]", scrubbed_query)
    
    # 2. Prompt Injection Detection
    injection_keywords = [
        "ignore previous instructions",
        "ignore the instructions above",
        "system prompt",
        "you are now a",
        "override instructions",
        "bypass safeguards"
    ]
    
    injection_detected = False
    for kw in injection_keywords:
        if kw in query_text.lower():
            injection_detected = True
            break
            
    # 3. Domain-Specific Rule: Payroll/Salary restrictions
    domain_violation = False
    if "salary" in query_text.lower() or "payroll" in query_text.lower():
        if "auth-bi-99" not in query_text.lower():
            domain_violation = True

    # 4. Structured JSON Audit Log
    audit_data = {
        "event": "security_checkpoint_evaluation",
        "query_length": len(query_text),
        "pii_detected": {
            "emails_count": len(emails_found),
            "credit_cards_count": len(cc_found)
        },
        "prompt_injection_detected": injection_detected,
        "domain_rule_violation": domain_violation,
        "action_taken": "BLOCK" if (injection_detected or domain_violation) else "ALLOW"
    }
    
    if injection_detected:
        logger.error(f"[Audit Log] PROMPT INJECTION BLOCKED: {json.dumps(audit_data)}")
        return Event(output="Prompt injection attempt blocked.", route="SECURITY_EVENT")
    elif domain_violation:
        logger.warning(f"[Audit Log] RESTRICTED ACCESS BLOCKED: {json.dumps(audit_data)}")
        return Event(output="Access denied. Payroll and salary details are restricted. Please provide valid authorization code (auth-bi-99) in your query.", route="SECURITY_EVENT")
    
    logger.info(f"[Audit Log] ALLOWED: {json.dumps(audit_data)}")
    return Event(output=scrubbed_query, route="CLEAN", state={"user_query": scrubbed_query})

async def human_review(ctx: Context, node_input: Any) -> AsyncGenerator[Any, None]:
    """Pauses execution for human approval before generating the final report."""
    # Extract plain text content from the orchestrator's response
    text_content = ""
    if isinstance(node_input, str):
        text_content = node_input
    elif hasattr(node_input, "parts") and node_input.parts:
        text_content = "".join([p.text for p in node_input.parts if hasattr(p, "text")])
    else:
        text_content = str(node_input)

    if not ctx.resume_inputs or "approved" not in ctx.resume_inputs:
        msg = (
            "✋ **DecisionIQ Human Review Required**\n\n"
            f"**Proposed Analysis Plan:**\n\n{text_content}\n\n"
            "Should we proceed to generate the final executive report? (Reply 'yes' or 'no')"
        )
        yield RequestInput(interrupt_id="approved", message=msg)
        return

    val = ctx.resume_inputs["approved"].strip().lower()
    if val in ["yes", "y", "approve"]:
        yield Event(output=text_content, route="APPROVED")
    else:
        yield Event(output="Generation rejected by user.", route="REJECTED")

def rejection_handler(node_input: str) -> Event:
    """Handles workflow rejection."""
    msg = f"Workflow Halted. Reason: {node_input}"
    return Event(
        output=msg,
        content=types.Content(role="model", parts=[types.Part.from_text(text=msg)])
    )

def security_alert_handler(node_input: str) -> Event:
    """Handles security alerts."""
    msg = f"⚠️ Security Block: {node_input}"
    return Event(
        output=msg,
        content=types.Content(role="model", parts=[types.Part.from_text(text=msg)])
    )

# ==========================================
# 5. Workflow Definition & App Export
# ==========================================

edges = [
    (START, security_checkpoint),
    (security_checkpoint, {
        "SECURITY_EVENT": security_alert_handler,
        "CLEAN": orchestrator
    }),
    (orchestrator, human_review),
    (human_review, {
        "APPROVED": executive_report,
        "REJECTED": rejection_handler
    }),
]

root_workflow = Workflow(
    name="decision_iq_workflow",
    edges=edges,
    description="Multi-agent business intelligence workflow coordinating document analysis, risk assessment, human review, and executive reporting.",
)

app = App(
    root_agent=root_workflow,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True),
)
