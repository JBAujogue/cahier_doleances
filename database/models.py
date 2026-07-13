from sqlalchemy import (
    Boolean, Column,
    ForeignKey,
    Integer, String, Text
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Contribution(Base):
    __tablename__ = "contribution"

    id = Column(Integer, primary_key=True)
    city = Column(String) # parsée du nom du fichier ; TODO insee/table city si data INSEE
    pdf_file = Column(String) # nom du fichier du cahier ; TODO ajuster en fonction de l'adaptation S3 de Ronan
    start_page = Column(Integer)
    end_page = Column(Integer) 
    is_handwritten = Column(Boolean)

class Extraction(Base):
    __tablename__ = "extraction"

    id = Column(Integer, primary_key=True)
    contribution_id = Column(Integer, ForeignKey("contribution.id"))
    ocr = Column(String)
    text = Column(Text)
    num_words = Column(Integer)
    num_lines = Column(Integer)

class Topic(Base):
    __tablename__ = "topic"

    id = Column(Integer, primary_key=True)
    contribution_id = Column(Integer, ForeignKey("contribution.id"))
    name = Column(String)

class Feeling(Base):
    __tablename__ = "feeling"

    id = Column(Integer, primary_key=True)
    contribution_id = Column(Integer, ForeignKey("contribution.id"))
    name = Column(String)

class Annotation(Base):
    __tablename__ = "annotation"

    contribution_id = Column(Integer, ForeignKey("contribution.id"), primary_key=True)
    is_anonymized = Column(Boolean)
    is_of_interest = Column(Boolean) 
