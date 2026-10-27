from fastapi import FastAPI

app = FastAPI(title="Football Stats API")


@app.get("/health")
def health_check():
    return {"status": "ok ready for kickoff"}
