import os
import glob
import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("DecisionIQ Server")

@mcp.tool()
def list_workspace_documents() -> list[str]:
    """Lists all business documents (TXT, CSV, PDF, DOCX, XLSX) in the workspace directory.
    
    Returns:
        A list of relative file paths.
    """
    # Look for files in workspace root or subdirectories
    supported_extensions = ["*.txt", "*.csv", "*.pdf", "*.docx", "*.xlsx"]
    found_files = []
    # For safety/simplicity, we search the workspace directory
    workspace_dir = os.getcwd()
    for ext in supported_extensions:
        found_files.extend(glob.glob(os.path.join(workspace_dir, ext)))
        found_files.extend(glob.glob(os.path.join(workspace_dir, "**", ext), recursive=True))
    
    # Return relative paths for easier reading (ignore python environment directories)
    return [
        os.path.relpath(f, workspace_dir)
        for f in found_files
        if ".venv" not in f and ".adk" not in f and "node_modules" not in f
    ]

@mcp.tool()
def read_business_document(file_path: str) -> str:
    """Reads the contents of a business document (supports TXT and CSV formats).
    
    Args:
        file_path: Relative path to the file.
        
    Returns:
        The content of the file or an error message.
    """
    safe_path = os.path.abspath(file_path)
    # Ensure it's inside the current directory
    if not safe_path.startswith(os.path.abspath(os.getcwd())):
        return "Error: Access denied. Cannot read files outside the workspace."
        
    if not os.path.exists(safe_path):
        return f"Error: File '{file_path}' not found."

    ext = os.path.splitext(safe_path)[1].lower()
    if ext not in [".txt", ".csv"]:
        return f"Warning: Reading {ext} file formats directly is not supported via this tool. Please summarize or extract facts using specialist agents."

    try:
        with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(4000)  # limit to 4000 characters
    except Exception as e:
        return f"Error reading file: {str(e)}"

@mcp.tool()
def calculate_financial_metrics(revenue: float, operating_expenses: float, cost_of_goods_sold: float) -> dict:
    """Calculates gross profit, operating income, gross margin, operating margin, and financial health status.
    
    Args:
        revenue: Total revenue.
        operating_expenses: Operating expenses (OPEX).
        cost_of_goods_sold: Cost of goods sold (COGS).
        
    Returns:
        A dictionary with calculated financial metrics.
    """
    gross_profit = revenue - cost_of_goods_sold
    gross_margin = (gross_profit / revenue) * 100 if revenue > 0 else 0
    operating_income = gross_profit - operating_expenses
    operating_margin = (operating_income / revenue) * 100 if revenue > 0 else 0
    
    health = "Stable"
    if operating_income < 0:
        health = "Distressed (Negative Operating Income)"
    elif operating_margin < 10:
        health = "Caution (Low Operating Margin)"
    elif operating_margin > 25:
        health = "Excellent (High Profitability)"
        
    return {
        "gross_profit": round(gross_profit, 2),
        "gross_margin_percentage": round(gross_margin, 2),
        "operating_income": round(operating_income, 2),
        "operating_margin_percentage": round(operating_margin, 2),
        "financial_health": health
    }

if __name__ == "__main__":
    mcp.run()
