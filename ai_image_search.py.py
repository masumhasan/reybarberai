"""
FastAPI — AI Image Search Service (single-file, no external AI module needed)
POST /search       : upload an image → returns similar images with metadata
POST /index        : index a new image with metadata
GET  /images       : list all indexed images
GET  /images/{id}  : get one image's metadata
DELETE /images/{id}: remove an indexed image
"""

import io
import os
import numpy as np
from typing import Optional
from bson import ObjectId

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from pydantic import BaseModel
from PIL import Image
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
import gridfs


# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

MONGO_URI = "mongodb+srv://devmostafiz04_db_user:qq7b36kKKfj3E7KG@cluster0.qii6fpb.mongodb.net/reybarber"
DB_NAME = "reybarber"
COLLECTION_NAME = "image_embeddings"
TOP_K_DEFAULT = 5
THRESHOLD_DEFAULT = 0.75


# ──────────────────────────────────────────────
# Embedding Model (CLIP)
# ──────────────────────────────────────────────

class ImageEmbedder:
    MODEL_NAME = "clip-ViT-B-32"

    def __init__(self):
        print(f"[Embedder] Loading model '{self.MODEL_NAME}' ...")
        self.model = SentenceTransformer(self.MODEL_NAME)
        print("[Embedder] Model ready.")

    def embed(self, image: Image.Image) -> np.ndarray:
        image = image.convert("RGB")
        vector = self.model.encode(image, convert_to_numpy=True)
        vector = vector / np.linalg.norm(vector)
        return vector.astype(np.float32)

    def embed_from_bytes(self, data: bytes) -> np.ndarray:
        return self.embed(Image.open(io.BytesIO(data)))


# ──────────────────────────────────────────────
# MongoDB Layer
# ──────────────────────────────────────────────

class ImageDatabase:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.col = self.db[COLLECTION_NAME]
        self.fs = gridfs.GridFS(self.db)
        self.col.create_index([("shop_id", 1), ("barber_id", 1)])
        print(f"[DB] Connected → '{DB_NAME}'.'{COLLECTION_NAME}'")

    def insert(self, vector, shop_id, barber_id, image_name, extra=None, raw=None):
        doc = {
            "embedding": vector.tolist(),
            "shop_id": shop_id,
            "barber_id": barber_id,
            "image_name": image_name,
            "extra": extra or {},
        }
        if raw:
            doc["gridfs_id"] = self.fs.put(raw, filename=image_name)
        return str(self.col.insert_one(doc).inserted_id)

    def search(self, query_vector, top_k=TOP_K_DEFAULT, threshold=THRESHOLD_DEFAULT):
        query_vector = query_vector / np.linalg.norm(query_vector)
        results = []
        for doc in self.col.find({}, {"shop_id": 1, "barber_id": 1,
                                       "image_name": 1, "extra": 1, "embedding": 1}):
            stored = np.array(doc["embedding"], dtype=np.float32)
            stored = stored / (np.linalg.norm(stored) + 1e-9)
            sim = float(np.dot(query_vector, stored))
            if sim >= threshold:
                results.append({
                    "_id": str(doc["_id"]),
                    "similarity": round(sim, 4),
                    "shop_id": doc.get("shop_id"),
                    "barber_id": doc.get("barber_id"),
                    "image_name": doc.get("image_name"),
                    "extra": doc.get("extra", {}),
                })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]


# ──────────────────────────────────────────────
# Startup — load model & DB once
# ──────────────────────────────────────────────

embedder = ImageEmbedder()
db = ImageDatabase()


# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────

app = FastAPI(
    title="ReyBarber Image Search API",
    description="Visual similarity search for barber shop images",
    version="1.0.0",
)


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class SearchResult(BaseModel):
    id: str
    similarity: float
    shop_id: str
    barber_id: str
    image_name: str
    extra: dict

class SearchResponse(BaseModel):
    query_image: str
    total_results: int
    results: list[SearchResult]

class IndexResponse(BaseModel):
    success: bool
    message: str
    document_id: str

class ImageRecord(BaseModel):
    id: str
    shop_id: str
    barber_id: str
    image_name: str
    extra: dict

class ImageListResponse(BaseModel):
    total: int
    images: list[ImageRecord]

# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "ReyBarber Image Search API"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search_similar_images(
    file: UploadFile = File(..., description="Image file to search"),
    top_k: int = Query(default=5, ge=1, le=20),
    threshold: float = Query(default=0.75, ge=0.0, le=1.0),
):
    """Upload an image → returns visually similar images with Shop ID, Barber ID, and metadata."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        vector = embedder.embed_from_bytes(image_bytes)
        results = db.search(vector, top_k=top_k, threshold=threshold)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    return SearchResponse(
        query_image=file.filename,
        total_results=len(results),
        results=[SearchResult(**{**r, "id": r["_id"]}) for r in results],
    )


@app.post("/index", response_model=IndexResponse, tags=["Indexing"])
async def index_image(
    file: UploadFile = File(..., description="Image to index"),
    shop_id: str = Form(...),
    barber_id: str = Form(...),
    image_name: Optional[str] = Form(default=None),
    style: Optional[str] = Form(default=None),
    store_raw: bool = Form(default=False),
):
    """Add a new image to the search database."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    name = image_name or file.filename
    extra = {"style": style} if style else {}

    try:
        vector = embedder.embed_from_bytes(image_bytes)
        doc_id = db.insert(
            vector, shop_id, barber_id, name, extra,
            raw=image_bytes if store_raw else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")

    return IndexResponse(success=True, message=f"'{name}' indexed.", document_id=doc_id)


@app.get("/images", response_model=ImageListResponse, tags=["Metadata"])
async def list_images(
    shop_id: Optional[str] = Query(default=None),
    barber_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
):
    """List indexed images, optionally filtered by shop_id or barber_id."""
    query_filter = {}
    if shop_id:
        query_filter["shop_id"] = shop_id
    if barber_id:
        query_filter["barber_id"] = barber_id

    try:
        total = db.col.count_documents(query_filter)
        cursor = db.col.find(query_filter, {"embedding": 0}).skip(skip).limit(limit)
        images = [
            ImageRecord(
                id=str(doc["_id"]),
                shop_id=doc.get("shop_id", ""),
                barber_id=doc.get("barber_id", ""),
                image_name=doc.get("image_name", ""),
                extra=doc.get("extra", {}),
            )
            for doc in cursor
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return ImageListResponse(total=total, images=images)


@app.get("/images/{image_id}", response_model=ImageRecord, tags=["Metadata"])
async def get_image(image_id: str):
    """Get metadata for a single image by its MongoDB _id."""
    try:
        oid = ObjectId(image_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image ID.")

    doc = db.col.find_one({"_id": oid}, {"embedding": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Image not found.")

    return ImageRecord(
        id=str(doc["_id"]),
        shop_id=doc.get("shop_id", ""),
        barber_id=doc.get("barber_id", ""),
        image_name=doc.get("image_name", ""),
        extra=doc.get("extra", {}),
    )


@app.delete("/images/{image_id}", tags=["Metadata"])
async def delete_image(image_id: str):
    """Remove an indexed image."""
    try:
        oid = ObjectId(image_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image ID.")

    result = db.col.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Image not found.")

    return {"success": True, "message": f"Image {image_id} deleted."}


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)