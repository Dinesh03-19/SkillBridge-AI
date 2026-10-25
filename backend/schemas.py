from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

# --- Gemini Structured Output Schemas ---
class GeneratedQuestion(BaseModel):
    question: str = Field(description="Multiple-choice question text")
    options: List[str] = Field(description="Exactly 4 distinct options")
    correct_index: int = Field(description="Index (0-3) of the single correct option")
    explanation: str = Field(description="Explanation for why the correct answer is right and others are wrong")
    source_excerpt: str = Field(description="Verbatim quote from source material grounding this question")

class QuizGenerationResponse(BaseModel):
    questions: List[GeneratedQuestion] = Field(default_factory=list)
    generation_notes: str = Field(description="Notes regarding generation, e.g. insufficient facts or skipped areas")


# --- API Request & Response Schemas ---
class TrainingMaterialOut(BaseModel):
    id: int
    title: str
    file_path: str
    linked_skill_id: str
    uploaded_by: str
    upload_date: datetime
    processed: bool
    chunk_count: int

    class Config:
        from_attributes = True

class TrainingMaterialBlobUploadRequest(BaseModel):
    pathname: str
    skill_id: str
    title: Optional[str] = None
    uploaded_by: str = "Admin/Trainer"

class QuizGenerateRequest(BaseModel):
    skill_id: str
    material_id: Optional[int] = None
    question_count: int = Field(default=5, ge=1, le=15)
    difficulty: str = Field(default="intermediate")  # beginner, intermediate, advanced

class QuizQuestionOut(BaseModel):
    id: int
    question_text: str
    options: List[str]
    correct_option_index: Optional[int] = None  # Hidden or shown during review
    explanation: Optional[str] = None
    source_chunk_id: Optional[int] = None
    source_excerpt: Optional[str] = None

    class Config:
        from_attributes = True

class QuizOut(BaseModel):
    id: int
    title: str
    source_material_id: Optional[int] = None
    linked_skill_id: str
    difficulty: str
    question_count: int
    generation_model: str
    created_at: datetime
    generation_notes: Optional[str] = None
    questions: List[QuizQuestionOut] = []

    class Config:
        from_attributes = True

class QuizSubmissionItem(BaseModel):
    question_id: int
    selected_option_index: int

class QuizSubmissionRequest(BaseModel):
    answers: List[QuizSubmissionItem]
    user_id: Optional[int] = None  # Optional user ID to record attempt and update competency

class QuestionGradingResult(BaseModel):
    question_id: int
    question_text: str
    selected_option_index: int
    correct_option_index: int
    is_correct: bool
    explanation: str
    source_excerpt: str
    source_document_title: Optional[str] = None

class QuizSubmissionResponse(BaseModel):
    quiz_id: int
    total_questions: int
    score: int
    percentage: float
    passed: bool
    results: List[QuestionGradingResult]
    competency_updated: Optional[bool] = False
    new_competency_score: Optional[float] = None

class QuestionSourceTraceOut(BaseModel):
    question_id: int
    question_text: str
    source_excerpt: str
    source_document_title: str
    material_id: Optional[int] = None
    chunk_index: Optional[int] = None
    similarity_score: float = 1.0

class GenerationLogOut(BaseModel):
    id: int
    quiz_id: Optional[int] = None
    raw_model_response: Optional[str] = None
    parse_success: bool
    retry_count: int
    error_message: Optional[str] = None
    discarded_questions_count: int
    discarded_reasons: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


# =========================================================================
# Schemas: Competency Framework, Learner Profiling & iGOT Karmayogi
# =========================================================================

class CompetencyScoreOut(BaseModel):
    competency_id: int
    code: str
    name: str
    domain: str
    current_score: float
    target_score: float
    gap: float
    status: str  # "proficient", "moderate_gap", "critical_gap"
    last_assessed: datetime

class UserProfileOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    designation: str
    department: str
    cadre: str
    current_assignment: str
    educational_qualifications: str
    experience_years: float
    learning_hours_completed: float
    avatar_url: Optional[str] = None
    competency_summary: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class CompetencyGapAnalysisOut(BaseModel):
    user_id: int
    user_name: str
    designation: str
    overall_readiness_pct: float
    total_competencies: int
    critical_gaps_count: int
    domain_scores: Dict[str, float]
    competency_details: List[CompetencyScoreOut]

class IgotCourseOut(BaseModel):
    id: int
    course_code: str
    title: str
    provider: str
    domain: str
    competency_code: str
    duration_hours: float
    level: str
    tpac_recommended: bool
    description: str
    curriculum_highlights: Optional[List[str]] = None
    external_url: str
    enrolment_count: int
    rating: float
    is_enrolled: Optional[bool] = False
    progress_pct: Optional[float] = 0.0
    status: Optional[str] = "not_enrolled"

    class Config:
        from_attributes = True

class CourseEnrolmentRequest(BaseModel):
    user_id: int
    course_id: int

class CourseCompleteRequest(BaseModel):
    user_id: int
    course_id: int

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    user_id: Optional[int] = 1
    message: str
    language: str = "en"  # "en" or "hi"
    history: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    reply: str
    language: str
    suggested_actions: Optional[List[str]] = []
    grounded_topics: Optional[List[str]] = []

class AdminAnalyticsOut(BaseModel):
    total_workforce_enrolled: int
    avg_competency_readiness: float
    total_learning_hours: float
    quizzes_completed: int
    domain_averages: Dict[str, float]
    cadre_distribution: Dict[str, int]
    top_skill_gaps: List[Dict[str, Any]]
    predictive_capacity_forecast: List[Dict[str, Any]]
    tpac_utilization_rate: float
