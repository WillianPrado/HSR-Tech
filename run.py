#!/usr/bin/env python
"""
Production server entry point for Render.com
Ensures PORT environment variable is properly handled.
"""

import os
import sys
import uvicorn

def main():
    """Start the Uvicorn server with proper PORT handling."""
    # Get PORT from environment, default to 8000 for local development
    port = int(os.getenv("PORT", "8000"))
    host = "0.0.0.0"

    # Log startup information
    print(f"Starting server on {host}:{port}")

    # Run Uvicorn
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()
