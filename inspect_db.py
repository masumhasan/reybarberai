"""
Run this to see EXACTLY what is in your MongoDB.
python inspect_db.py
"""
from pymongo import MongoClient
import gridfs

MONGO_URI = "mongodb+srv://devmostafiz04_db_user:qq7b36kKKfj3E7KG@cluster0.qii6fpb.mongodb.net/reybarber"

client = MongoClient(MONGO_URI)
db = client["reybarber"]

print("=" * 60)
print("ALL COLLECTIONS & DOCUMENT COUNTS")
print("=" * 60)
for name in db.list_collection_names():
    count = db[name].count_documents({})
    print(f"  {name:40s} → {count} docs")

print()
print("=" * 60)
print("SAMPLE DOCUMENT FROM EACH COLLECTION (field names only)")
print("=" * 60)
for name in db.list_collection_names():
    col = db[name]
    doc = col.find_one()
    if doc:
        fields = list(doc.keys())
        print(f"\n  [{name}]")
        for f in fields:
            val = doc[f]
            val_type = type(val).__name__
            val_preview = ""
            if isinstance(val, str):
                val_preview = f'"{val[:60]}"'
            elif isinstance(val, (int, float, bool)):
                val_preview = str(val)
            elif isinstance(val, bytes):
                val_preview = f"<bytes len={len(val)}>"
            elif isinstance(val, list):
                val_preview = f"<list len={len(val)}>"
            elif isinstance(val, dict):
                val_preview = f"<dict keys={list(val.keys())[:5]}>"
            print(f"    {f:30s} {val_type:10s} {val_preview}")

print()
print("=" * 60)
print("GRIDFS FILES")
print("=" * 60)
fs_files = list(db["fs.files"].find())
print(f"  Total GridFS files: {len(fs_files)}")
for f in fs_files[:5]:
    print(f"  filename={f.get('filename')}  length={f.get('length')}  metadata={f.get('metadata')}")  