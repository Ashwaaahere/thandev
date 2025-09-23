from models import Base
from sqlalchemy import create_engine
import os

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    print('Database tables created successfully!')
else:
    print('DATABASE_URL not found!')

