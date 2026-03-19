from pantry_backend.app import create_app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("pantry_backend:app", host="127.0.0.1", port=8000, reload=True)
