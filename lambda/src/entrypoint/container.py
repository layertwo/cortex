"""Container entrypoint for Cortex API. Runs FastAPI with uvicorn."""

import uvicorn

from src.environment.service_provider import ServiceProvider


def main():
    provider = ServiceProvider()
    uvicorn.run(provider.app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
