 Customer Sentiment Analysis (Call Transcript Analyzer)

A Flask-based web application that analyzes **call transcripts** using the **Groq LLM API**.  
It provides a concise **summary** of the conversation and detects the overall **sentiment** (positive, neutral, or negative).  
The results are stored in a CSV file and can be downloaded for further analysis.

🚀 Features
- Web form to paste call transcripts.
- REST API endpoint (`/api/analyze`) for programmatic access.
- Generates both **summary** and **sentiment** analysis.
- Saves all results into a CSV file (`call_analysis.csv`).
- CSV file can be downloaded via the web interface.
- Supports `.env` for environment configuration.
