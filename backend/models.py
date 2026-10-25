from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import json
from backend.database import Base

class TrainingMaterial(Base):
    __tablename__ = "training_materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    linked_skill_id = Column(String(100), nullable=False, index=True)
    uploaded_by = Column(String(100), default="Admin/Trainer")
    upload_date = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    chunk_count = Column(Integer, default=0)

    chunks = relationship("DocumentChunk", back_populates="material", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="source_material")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("training_materials.id", ondelete="CASCADE"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    token_count = Column(Integer, default=0)
    embedding_id = Column(String(100), nullable=False, index=True)  # maps to ChromaDB ID

    material = relationship("TrainingMaterial", back_populates="chunks")
    questions = relationship("QuizQuestion", back_populates="source_chunk")


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    source_material_id = Column(Integer, ForeignKey("training_materials.id", ondelete="SET NULL"), nullable=True)
    linked_skill_id = Column(String(100), nullable=False, index=True)
    difficulty = Column(String(50), default="intermediate")  # beginner, intermediate, advanced
    question_count = Column(Integer, default=5)
    generation_model = Column(String(100), default="gemini-2.0-flash")
    created_at = Column(DateTime, default=datetime.utcnow)
    generation_notes = Column(Text, nullable=True)

    source_material = relationship("TrainingMaterial", back_populates="quizzes")
    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan")
    logs = relationship("GenerationLog", back_populates="quiz", cascade="all, delete-orphan")
    attempts = relationship("LearnerQuizAttempt", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # JSON array of exactly 4 strings
    correct_option_index = Column(Integer, nullable=False)  # 0 to 3
    explanation = Column(Text, nullable=False)
    source_chunk_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    source_excerpt = Column(Text, nullable=False)  # verbatim text grounded in the source

    quiz = relationship("Quiz", back_populates="questions")
    source_chunk = relationship("DocumentChunk", back_populates="questions")


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=True)
    raw_model_response = Column(Text, nullable=True)
    parse_success = Column(Boolean, default=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    discarded_questions_count = Column(Integer, default=0)
    discarded_reasons = Column(JSON, nullable=True)  # List of reasons/excerpts discarded
    created_at = Column(DateTime, default=datetime.utcnow)

    quiz = relationship("Quiz", back_populates="logs")


# =========================================================================
# MoSPI Official Statistical System: Users, Competencies & iGOT Karmayogi
# =========================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    role = Column(String(50), default="learner")  # learner, trainer, administrator
    designation = Column(String(150), nullable=False)  # e.g. Senior Statistical Officer (SSO), Junior Statistical Officer (JSO), Director
    department = Column(String(150), default="National Statistical Office (NSO)")
    cadre = Column(String(100), default="Indian Statistical Service (ISS)")
    current_assignment = Column(String(255), default="Periodic Labour Force Survey (PLFS) Wing")
    educational_qualifications = Column(String(255), default="M.Sc. Statistics / Mathematical Statistics")
    experience_years = Column(Float, default=4.5)
    learning_hours_completed = Column(Float, default=28.5)
    avatar_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    competency_scores = relationship("UserCompetencyScore", back_populates="user", cascade="all, delete-orphan")
    enrolments = relationship("CourseEnrolment", back_populates="user", cascade="all, delete-orphan")
    quiz_attempts = relationship("LearnerQuizAttempt", back_populates="user", cascade="all, delete-orphan")


class Competency(Base):
    __tablename__ = "competencies"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)  # e.g. STAT_SURVEY_DESIGN, TECH_PYTHON
    name = Column(String(150), nullable=False)
    domain = Column(String(100), nullable=False)  # Statistical, Technical, Digital Governance, Behavioural/Managerial
    description = Column(Text, nullable=True)
    benchmark_level_jso = Column(Float, default=60.0)  # Required % for JSO
    benchmark_level_sso = Column(Float, default=75.0)  # Required % for SSO
    benchmark_level_director = Column(Float, default=85.0)  # Required % for Director

    user_scores = relationship("UserCompetencyScore", back_populates="competency", cascade="all, delete-orphan")


class UserCompetencyScore(Base):
    __tablename__ = "user_competency_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    competency_id = Column(Integer, ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False)
    current_score = Column(Float, default=50.0)  # 0 to 100
    target_score = Column(Float, default=75.0)   # dynamically derived or set by role
    last_assessed = Column(DateTime, default=datetime.utcnow)
    assessment_source = Column(String(100), default="Initial Baseline")  # Baseline, Quiz, iGOT Course

    user = relationship("User", back_populates="competency_scores")
    competency = relationship("Competency", back_populates="user_scores")


class IgotCourse(Base):
    __tablename__ = "igot_courses"

    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    provider = Column(String(150), default="iGOT Karmayogi / MoSPI / NSSTA")
    domain = Column(String(100), nullable=False)
    competency_code = Column(String(50), nullable=False, index=True)
    duration_hours = Column(Float, default=6.0)
    level = Column(String(50), default="Intermediate")
    tpac_recommended = Column(Boolean, default=False)  # NSSTA TPAC recommendation flag
    description = Column(Text, nullable=False)
    curriculum_highlights = Column(JSON, nullable=True)
    external_url = Column(String(500), default="https://igotkarmayogi.gov.in")
    enrolment_count = Column(Integer, default=1420)
    rating = Column(Float, default=4.8)

    enrolments = relationship("CourseEnrolment", back_populates="course", cascade="all, delete-orphan")


class CourseEnrolment(Base):
    __tablename__ = "course_enrolments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("igot_courses.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="in_progress")  # enrolled, in_progress, completed
    progress_pct = Column(Float, default=0.0)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="enrolments")
    course = relationship("IgotCourse", back_populates="enrolments")


class LearnerQuizAttempt(Base):
    __tablename__ = "learner_quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)
    passed = Column(Boolean, default=False)
    completed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="quiz_attempts")
    quiz = relationship("Quiz", back_populates="attempts")
