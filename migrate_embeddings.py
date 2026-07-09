"""
Migration script — downloads images from S3 URLs stored in MongoDB,
generates CLIP embeddings, and stores them in image_embeddings collection.

Run once:
    python migrate_embeddings.py
"""

import io
import requests
import numpy as np
from PIL import Image
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer

MONGO_URI = "mongodb+srv://devmostafiz04_db_user:qq7b36kKKfj3E7KG@cluster0.qii6fpb.mongodb.net/reybarber"
DB_NAME = "reybarber"
EMBED_COL = "image_embeddings"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[EMBED_COL]

print("Loading CLIP model...")
model = SentenceTransformer("clip-ViT-B-32")
print("Model ready.\n")


def get_embedding(image_bytes: bytes) -> list:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    vec = model.encode(img, convert_to_numpy=True)
    vec = vec / np.linalg.norm(vec)
    return vec.astype(np.float32).tolist()


def download_image(url: str) -> bytes:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.content


def index_url(url, shop_id, barber_id, image_name, extra=None):
    """Download URL, embed, store. Skips if already indexed."""
    existing = col.find_one({"image_url": url})
    if existing:
        print(f"  [SKIP] already indexed: {image_name}")
        return

    try:
        image_bytes = download_image(url)
        embedding = get_embedding(image_bytes)
        col.insert_one({
            "embedding":   embedding,
            "shop_id":     str(shop_id),
            "barber_id":   str(barber_id),
            "image_name":  image_name,
            "image_url":   url,
            "extra":       extra or {},
        })
        print(f"  [OK] {image_name}")
    except Exception as e:
        print(f"  [ERR] {image_name} → {e}")

total = 0

# ── 1. saloon_owners → shopImages + shopLogo ──────────────────────────
print("=" * 50)
print("Indexing saloon_owners images...")
for owner in db["saloon_owners"].find():
    shop_id = str(owner["_id"])
    shop_name = owner.get("shopName", "unknown")

    # shopLogo
    logo = owner.get("shopLogo")
    if logo and logo.startswith("http"):
        index_url(logo, shop_id=shop_id, barber_id="",
                  image_name=f"{shop_name}_logo",
                  extra={"type": "shop_logo", "shopName": shop_name})
        total += 1

    # shopImages
    for i, url in enumerate(owner.get("shopImages", [])):
        if url and url.startswith("http"):
            index_url(url, shop_id=shop_id, barber_id="",
                      image_name=f"{shop_name}_shop_{i}",
                      extra={"type": "shop_image", "shopName": shop_name})
            total += 1

# ── 2. barbers → portfolio ────────────────────────────────────────────
print("\n" + "=" * 50)
print("Indexing barbers portfolio images...")
for barber in db["barbers"].find():
    barber_id = str(barber["_id"])
    user_id = str(barber.get("userId", ""))

    # Find linked saloon to get shop_id
    hired = db["hired_barbers"].find_one({"barberId": barber["_id"]})
    shop_id = str(hired["saloonId"]) if hired else ""

    for i, item in enumerate(barber.get("portfolio", [])):
        url = item if isinstance(item, str) else item.get("url") or item.get("image") or item.get("imageUrl")
        if url and url.startswith("http"):
            index_url(url, shop_id=shop_id, barber_id=barber_id,
                      image_name=f"barber_{barber_id}_portfolio_{i}",
                      extra={"type": "barber_portfolio", "userId": user_id})
            total += 1

# ── 3. feeds → images ────────────────────────────────────────────────
print("\n" + "=" * 50)
print("Indexing feeds images...")
for feed in db["feeds"].find():
    feed_id = str(feed["_id"])
    user_id = str(feed.get("userId", ""))

    # Try to find barber/shop from userId
    barber = db["barbers"].find_one({"userId": feed["userId"]})
    barber_id = str(barber["_id"]) if barber else ""
    hired = db["hired_barbers"].find_one({"barberId": barber["_id"]}) if barber else None
    shop_id = str(hired["saloonId"]) if hired else ""

    for i, item in enumerate(feed.get("images", [])):
        url = item if isinstance(item, str) else item.get("url") or item.get("image") or item.get("imageUrl")
        if url and url.startswith("http"):
            index_url(url, shop_id=shop_id, barber_id=barber_id,
                      image_name=f"feed_{feed_id}_image_{i}",
                      extra={"type": "feed", "userId": user_id, "caption": feed.get("caption", "")})
            total += 1

# ── 4. ads → images ──────────────────────────────────────────────────
print("\n" + "=" * 50)
print("Indexing ads images...")
for ad in db["ads"].find():
    ad_id = str(ad["_id"])
    user_id = str(ad.get("userId", ""))

    owner = db["saloon_owners"].find_one({"userId": ad["userId"]})
    shop_id = str(owner["_id"]) if owner else ""

    for i, item in enumerate(ad.get("images", [])):
        url = item if isinstance(item, str) else item.get("url") or item.get("image") or item.get("imageUrl")
        if url and url.startswith("http"):
            index_url(url, shop_id=shop_id, barber_id="",
                      image_name=f"ad_{ad_id}_image_{i}",
                      extra={"type": "ad", "userId": user_id, "description": ad.get("description", "")})
            total += 1

# ── Summary ───────────────────────────────────────────────────────────
final_count = col.count_documents({})
print("\n" + "=" * 50)
print(f"Migration complete.")
print(f"Attempted : {total} images")
print(f"Total in DB now: {final_count} embeddings")
print("Run your search again — it should work now.") 