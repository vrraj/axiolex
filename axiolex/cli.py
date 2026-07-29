"""
Command-line interface for BM25S retriever service.
"""

import argparse
import logging
from pathlib import Path
import uvicorn
from dotenv import load_dotenv
from .api.routes import create_app
from .core.config import load_config, Config
from .retrieval.model_integrity import ensure_default_colbert_model

# Load environment variables from .env file
load_dotenv()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="BM25S Retriever Service")
    parser.add_argument("--config", "-c", type=str, help="Configuration file path")
    parser.add_argument("--host", type=str, help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], 
                       help="Log level")
    subcommands = parser.add_subparsers(dest="command")
    model_ensure = subcommands.add_parser("model-ensure", help="Download and verify the pinned default ColBERT model.")
    model_ensure.add_argument("--cache-dir", type=Path, help="Hugging Face cache directory for the model snapshot.")
    
    args = parser.parse_args()

    if args.command == "model-ensure":
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
        logging.getLogger("axiolex.retrieval.model_integrity").setLevel(logging.INFO)
        path = ensure_default_colbert_model(args.cache_dir)
        print(f"Pinned ColBERT model ready: {path}")
        return
    
    # Load configuration
    config = load_config(args.config)
    
    # Override with CLI arguments
    if args.host:
        config.server.host = args.host
    if args.port:
        config.server.port = args.port
    if args.reload:
        config.server.reload = args.reload
    if args.log_level:
        config.server.log_level = args.log_level
    
    # Create app
    app = create_app(config)
    
    # Run server
    if config.server.reload:
        # Use import string for reload mode
        uvicorn.run(
            "axiolex.api.routes:create_app",
            host=config.server.host,
            port=config.server.port,
            reload=True,
            log_level=config.server.log_level,
            factory=True
        )
    else:
        uvicorn.run(
            app,
            host=config.server.host,
            port=config.server.port,
            reload=False,
            log_level=config.server.log_level
        )


if __name__ == "__main__":
    main()
