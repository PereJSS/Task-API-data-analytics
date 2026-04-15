import uvicorn


if __name__ == "__main__":
    # Keep a tiny local entrypoint so the project can still be run without memorizing uvicorn flags.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)