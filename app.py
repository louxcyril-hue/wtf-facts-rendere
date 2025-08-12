import os, io, json, uuid, boto3, base64
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from renderer import render_video

load_dotenv()

S3_BUCKET = os.getenv("S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-3")

api = FastAPI(title="WTF Facts Renderer", version="1.1")

class ScriptModel(BaseModel):
    hook: str
    body: list[str] = Field(default_factory=list)
    twist: str
    cta: str

class RenderPayload(BaseModel):
    title: str
    script: ScriptModel
    # Provide either image_urls or image_b64
    image_urls: list[str] | None = None
    image_b64: list[str] | None = None
    # Provide either voice_url or voice_b64
    voice_url: str | None = None
    voice_b64: str | None = None
    music_url: str | None = None
    watermark_text: str | None = None
    brand_color_hex: str | None = "#ffffff"
    upload: bool | None = False  # if S3 configured
    return_b64: bool | None = False  # return base64 mp4 inside JSON

@api.get("/health")
async def health():
    return PlainTextResponse("ok")

@api.post("/render")
async def render_endpoint(payload: RenderPayload):
    try:
        file_id = str(uuid.uuid4())[:8]
        out_path = f"/tmp/{file_id}.mp4"
        dur = render_video(payload.model_dump(), out_path)

        if S3_BUCKET and payload.upload:
            s3 = boto3.client("s3", region_name=AWS_REGION)
            key = f"wtf-facts/{file_id}.mp4"
            s3.upload_file(out_path, S3_BUCKET, key, ExtraArgs={"ContentType": "video/mp4"})
            url = s3.generate_presigned_url("get_object",
                                            Params={"Bucket": S3_BUCKET, "Key": key},
                                            ExpiresIn=60*60*24)
            return JSONResponse({"status": "ok", "duration": dur, "url": url, "s3_key": key})

        if payload.return_b64:
            with open(out_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return JSONResponse({"status": "ok", "duration": dur, "mp4_b64": b64})

        def iterfile():
            with open(out_path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        headers = {
            "X-Video-Duration": str(dur),
            "Content-Disposition": f'attachment; filename="{file_id}.mp4"'
        }
        return StreamingResponse(iterfile(), media_type="video/mp4", headers=headers)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
