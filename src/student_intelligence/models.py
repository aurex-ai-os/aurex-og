import logging
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship, declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()

class StudentProfile(Base):
    __tablename__ = 'student_profiles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    preferred_explanation_style = Column(String)
    
    terms = relationship("AcademicTerm", back_populates="student")

class AcademicTerm(Base):
    __tablename__ = 'academic_terms'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('student_profiles.id'))
    name = Column(String) # e.g. Fall 2024
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    student = relationship("StudentProfile", back_populates="terms")
    courses = relationship("Course", back_populates="term")

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    term_id = Column(Integer, ForeignKey('academic_terms.id'))
    name = Column(String)
    code = Column(String)
    
    term = relationship("AcademicTerm", back_populates="courses")
    syllabi = relationship("Syllabus", back_populates="course")

class Syllabus(Base):
    __tablename__ = 'syllabi'
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'))
    raw_text = Column(Text)
    
    course = relationship("Course", back_populates="syllabi")
    units = relationship("CourseUnit", back_populates="syllabus")

class CourseUnit(Base):
    __tablename__ = 'course_units'
    id = Column(Integer, primary_key=True)
    syllabus_id = Column(Integer, ForeignKey('syllabi.id'))
    title = Column(String)
    order = Column(Integer)
    
    syllabus = relationship("Syllabus", back_populates="units")
    topics = relationship("Topic", back_populates="unit")

class Topic(Base):
    __tablename__ = 'topics'
    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey('course_units.id'))
    title = Column(String)
    weight = Column(Float)
    estimated_learning_hours = Column(Float)
    
    unit = relationship("CourseUnit", back_populates="topics")
    concepts = relationship("Concept", back_populates="topic")

class Concept(Base):
    __tablename__ = 'concepts'
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey('topics.id'))
    name = Column(String)
    description = Column(Text)
    self_reported_confidence = Column(Float, default=0.0)
    demonstrated_mastery = Column(Float, default=0.0)
    source_file = Column(String)
    page_num = Column(Integer)
    prerequisite_id = Column(Integer, ForeignKey('concepts.id'), nullable=True)
    
    topic = relationship("Topic", back_populates="concepts")
    prerequisite = relationship("Concept", remote_side=[id])
