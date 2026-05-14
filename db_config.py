from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database URL
DATABASE_URL = "postgresql://mlw_attack_user:ShJf3c9NA4Jf1ADITLYh3fIlHc7akHXC@dpg-d8063p9j2pic73f1mm40-a/mlw_attack"

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
