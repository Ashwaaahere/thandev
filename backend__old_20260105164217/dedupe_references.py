# backend/dedupe_references.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from models import Exploit
from collections import OrderedDict

engine = create_engine(os.environ['DATABASE_URL'])
Session = sessionmaker(bind=engine)

def dedupe_refs():
    s = Session()
    try:
        rows = s.query(Exploit).all()
        for r in rows:
            refs = r.references or []
            seen = OrderedDict()
            for item in refs:
                url = (item.get("url") if isinstance(item, dict) else item) or ""
                url = url.strip()
                if url and url not in seen:
                    seen[url] = item
            new_refs = list(seen.values())
            if len(new_refs) != len(refs):
                r.references = new_refs
                s.add(r)
        s.commit()
    finally:
        s.close()

if __name__ == "__main__":
    dedupe_refs()
    print("done")

