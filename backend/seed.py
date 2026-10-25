import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal, init_db
from backend.models import (
    TrainingMaterial, DocumentChunk, Quiz, QuizQuestion, GenerationLog,
    User, Competency, UserCompetencyScore, IgotCourse, CourseEnrolment, LearnerQuizAttempt
)
from backend.services.parser import chunk_text
from backend.services.embeddings import EmbeddingService
from backend.services.competency_service import MOSPI_COMPETENCY_FRAMEWORK
from backend.services.igot_service import SEED_IGOT_COURSES
from backend.config import settings

SAMPLE_DOCS = [
    {
        "title": "NSSO 78th Round: Survey Protocols and Sampling Methodology Manual",
        "skill_id": "sampling_methodology",
        "content": """The National Sample Survey Office (NSSO) under the Ministry of Statistics and Programme Implementation (MoSPI) employs a stratified multi-stage design for nationwide socio-economic surveys. In the rural sector, the First Stage Units (FSUs) are census villages as per the latest Population Census, whereas in the urban sector, the FSUs are Urban Frame Survey (UFS) blocks. The Ultimate Stage Units (USUs) are households in both rural and urban sectors.

Stratification within each district involves forming two basic strata: rural stratum comprising all rural areas of the district and urban stratum comprising all urban areas of the district. Within each stratum, sample FSUs are selected following Circular Systematic Sampling with Probability Proportional to Size (PPSWR) in rural areas where size is village population, and Simple Random Sampling Without Replacement (SRSWOR) in urban areas.

Listing and Sub-Stratification Protocol: Before listing households, an FSU with population greater than 1200 or having more than 300 households is divided into two or more hamlet-groups (in rural areas) or sub-blocks (in urban areas) of approximately equal population. Two hamlet-groups or sub-blocks are selected for the survey: one with the highest population (selected with certainty) and one randomly from the remaining ones.

Household Selection in Sample FSUs: All households in the selected hamlet-groups or sub-blocks are listed. Households are categorized into second-stage strata based on land possessed or monthly per capita consumer expenditure (MPCE). A fixed number of 8 to 12 sample households are selected systematically from each second-stage stratum for detailed schedule canvassing. Multipliers and design weights are calculated as the inverse of inclusion probabilities."""
    },
    {
        "title": "Periodic Labour Force Survey (PLFS) Activity Status & Classification Guidelines",
        "skill_id": "labour_force_survey",
        "content": """The Periodic Labour Force Survey (PLFS) uses three distinct activity status concepts to measure employment and unemployment characteristics across India: Usual Principal Status (UPS), Usual Principal and Subsidiary Status (UPSS), and Current Weekly Status (CWS).

Usual Principal Status (UPS): The activity status on which a person spent relatively long time (major time criterion) during the 365 days preceding the date of survey is termed as the Usual Principal Activity Status. A person is categorized as 'Employed' (in labour force), 'Unemployed' (seeking or available for work in labour force), or 'Out of Labour Force' (students, domestic duties, retired persons, rentiers, and others not available for work).

Subsidiary Economic Activity Status (SS): A person who was not categorized as employed under the principal status is considered as employed under the subsidiary status if the person engaged in any economic activity for at least 30 days during the reference period of 365 days. The combined UPSS gives the comprehensive measure of chronic or long-term employment.

Current Weekly Status (CWS): Under the Current Weekly Status framework, the reference period is the 7 days preceding the date of interview. A person is considered employed if they worked for at least 1 hour on any day during the 7-day reference week. A person is classified as unemployed under CWS if they did not work even for 1 hour on any day but were actively seeking or available for work. In urban areas, a rotational panel sampling design with four visits is implemented where 25% of FSUs are replaced each quarter."""
    },
    {
        "title": "National Statistical Office (NSO) Data Verification & Imputation Protocol",
        "skill_id": "data_quality",
        "content": """Data quality assurance at the National Statistical Office (NSO) is governed by the Generic Statistical Business Process Model (GSBPM) standards. The verification framework encompasses range validation checks, consistency checks, and statistical outlier identification routines executed at both field scrutiny and centralized data processing stages.

Range Checks and Logical Consistency: Range checks ensure that numerical data values fall strictly between predefined biological or administrative boundaries (for example, age between 0 and 115, hours worked per week between 0 and 112). Logical consistency checks ensure inter-field compatibility; for instance, marital status cannot be 'married' if recorded age is below legal threshold, and highest educational level must align with technical training qualifications.

Imputation Rules for Missing Values: When item non-response occurs, imputation must preserve multivariate relationships. The preferred methodology for continuous variables (such as household consumer expenditure) is Hot-Deck Imputation within homogeneous imputation classes defined by district, occupation, and household size. Mean or median imputation is strictly prohibited for socio-economic indicators as it artificially reduces population variance.

Cold-Deck Imputation and Historical Donor Matching: Cold-deck imputation using historical data from previous rounds is permitted exclusively when fewer than 5 valid donor records are available within the same regional stratum. Every imputed record must be permanently flagged with an imputation code specifying the imputation algorithm employed, preserving complete traceability for analytical audits."""
    }
]

def seed_database():
    print("Initializing Database tables...")
    init_db()
    db = SessionLocal()

    # 1. Seed Competencies
    print("Seeding MoSPI Competencies...")
    comp_map = {}
    for c in MOSPI_COMPETENCY_FRAMEWORK:
        existing = db.query(Competency).filter(Competency.code == c["code"]).first()
        if not existing:
            existing = Competency(
                code=c["code"],
                name=c["name"],
                domain=c["domain"],
                description=c["description"],
                benchmark_level_jso=c["benchmark_jso"],
                benchmark_level_sso=c["benchmark_sso"],
                benchmark_level_director=c["benchmark_director"]
            )
            db.add(existing)
            db.flush()
        comp_map[c["code"]] = existing
    db.commit()

    # 2. Seed MoSPI Officials (Users)
    print("Seeding Official Profiles (Users)...")
    users_data = [
        {
            "id": 1,
            "name": "Rajesh Sharma, ISS",
            "email": "rajesh.sharma@mospi.gov.in",
            "role": "learner",
            "designation": "Senior Statistical Officer (SSO)",
            "department": "National Statistical Office (NSO), MoSPI",
            "cadre": "Indian Statistical Service (ISS)",
            "current_assignment": "Periodic Labour Force Survey (PLFS) Central Scrutiny Wing",
            "educational_qualifications": "M.Sc. Statistics (Delhi School of Economics)",
            "experience_years": 5.5,
            "learning_hours_completed": 34.0,
            "avatar_url": "https://api.dicebear.com/7.x/bottts/svg?seed=Rajesh"
        },
        {
            "id": 2,
            "name": "Dr. Priya Nair, ISS",
            "email": "priya.nair@mospi.gov.in",
            "role": "administrator",
            "designation": "Joint Director & Divisional Head",
            "department": "Survey Design & Research Division (SDRD), Kolkata",
            "cadre": "Indian Statistical Service (ISS)",
            "current_assignment": "National Quality Assurance Framework (NQAF) Implementation",
            "educational_qualifications": "Ph.D. in Mathematical Statistics (ISI Kolkata)",
            "experience_years": 14.0,
            "learning_hours_completed": 92.5,
            "avatar_url": "https://api.dicebear.com/7.x/bottts/svg?seed=Priya"
        },
        {
            "id": 3,
            "name": "Amit Kumar Verma",
            "email": "amit.verma@mospi.gov.in",
            "role": "trainer",
            "designation": "Senior Faculty & Training In-Charge",
            "department": "National Statistical Systems Training Academy (NSSTA), Greater Noida",
            "cadre": "Subordinate Statistical Service (SSS)",
            "current_assignment": "CAPI and Data Processing Training Division",
            "educational_qualifications": "M.Sc. Applied Statistics (BHU)",
            "experience_years": 9.0,
            "learning_hours_completed": 64.0,
            "avatar_url": "https://api.dicebear.com/7.x/bottts/svg?seed=Amit"
        }
    ]

    for ud in users_data:
        u = db.query(User).filter(User.id == ud["id"]).first()
        if not u:
            u = User(**ud)
            db.add(u)
            db.flush()

            # Seed competency baseline scores for this user
            baseline_scores = {
                "STAT_SURVEY_DESIGN": 78.0 if u.id == 2 else 68.0,
                "STAT_LABOUR_STATISTICS": 82.0 if u.id == 1 else 74.0,
                "STAT_NATIONAL_ACCOUNTS": 65.0 if u.id == 2 else 52.0,
                "STAT_PRICE_INDICES": 70.0,
                "STAT_DATA_QUALITY": 75.0,
                "TECH_PYTHON_R": 55.0,  # Critical skill gap!
                "TECH_AI_ML_BIGDATA": 48.0,  # Critical skill gap!
                "TECH_GIS_SPATIAL": 58.0,
                "GOV_CYBER_PRIVACY": 64.0,
                "GOV_OPEN_DATA_API": 62.0,
                "MGT_LEADERSHIP_PROJECT": 82.0 if u.id == 2 else 70.0,
                "MGT_ETHICS_DECISION": 88.0
            }

            for code, score_val in baseline_scores.items():
                if code in comp_map:
                    ucs = UserCompetencyScore(
                        user_id=u.id,
                        competency_id=comp_map[code].id,
                        current_score=score_val,
                        target_score=comp_map[code].benchmark_level_sso if u.id == 1 else comp_map[code].benchmark_level_director,
                        assessment_source="Initial MoSPI Competency Evaluation"
                    )
                    db.add(ucs)
    db.commit()

    # 3. Seed iGOT Courses
    print("Seeding iGOT Karmayogi & NSSTA TPAC Courses...")
    for c_data in SEED_IGOT_COURSES:
        existing = db.query(IgotCourse).filter(IgotCourse.course_code == c_data["course_code"]).first()
        if not existing:
            course = IgotCourse(**c_data)
            db.add(course)
    db.commit()

    # Seed sample enrolment for Rajesh Sharma
    u1 = db.query(User).filter(User.id == 1).first()
    c1 = db.query(IgotCourse).filter(IgotCourse.course_code == "IGOT_STAT_002").first()
    if u1 and c1:
        enr = db.query(CourseEnrolment).filter(CourseEnrolment.user_id == u1.id, CourseEnrolment.course_id == c1.id).first()
        if not enr:
            enr = CourseEnrolment(
                user_id=u1.id,
                course_id=c1.id,
                status="in_progress",
                progress_pct=60.0
            )
            db.add(enr)
            db.commit()

    # 4. Seed Training Materials & Vectors
    print("Seeding Official Training Documents and vector embeddings...")
    embedding_service = EmbeddingService.get_instance()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    materials_created = []

    for doc in SAMPLE_DOCS:
        existing = db.query(TrainingMaterial).filter(TrainingMaterial.title == doc["title"]).first()
        if existing:
            materials_created.append(existing)
            continue

        file_path = os.path.join(settings.UPLOAD_DIR, f"{doc['skill_id']}_sample.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(doc["content"])

        chunks_data = chunk_text(doc["content"], target_chunk_size=450, overlap_size=50)

        material = TrainingMaterial(
            title=doc["title"],
            file_path=file_path,
            linked_skill_id=doc["skill_id"],
            uploaded_by="MoSPI / NSO System Administrator",
            processed=True,
            chunk_count=len(chunks_data)
        )
        db.add(material)
        db.flush()

        embedding_ids = embedding_service.add_chunks(
            chunks=chunks_data,
            material_id=material.id,
            skill_id=doc["skill_id"],
            doc_title=doc["title"]
        )

        for i, c in enumerate(chunks_data):
            doc_chunk = DocumentChunk(
                material_id=material.id,
                chunk_text=c["chunk_text"],
                chunk_index=c["chunk_index"],
                token_count=c["token_count"],
                embedding_id=embedding_ids[i]
            )
            db.add(doc_chunk)

        db.commit()
        db.refresh(material)
        materials_created.append(material)
        print(f"[OK] Seeded document: {doc['title']} ({len(chunks_data)} chunks indexed)", flush=True)

    # 5. Pre-generate starter quiz if none exists
    existing_quiz = db.query(Quiz).first()
    if not existing_quiz and materials_created:
        mat = materials_created[0]
        first_chunk = db.query(DocumentChunk).filter(DocumentChunk.material_id == mat.id).first()
        sample_quiz = Quiz(
            title="NSSO Sampling Design & Survey Protocols Certification Quiz",
            source_material_id=mat.id,
            linked_skill_id="sampling_methodology",
            difficulty="intermediate",
            question_count=3,
            generation_model=settings.GEMINI_MODEL,
            generation_notes="Pre-seeded starter quiz for instant judge evaluation and demonstration."
        )
        db.add(sample_quiz)
        db.flush()

        q1 = QuizQuestion(
            quiz_id=sample_quiz.id,
            question_text="In the rural sector of the NSSO multi-stage stratified survey design, what constitutes the First Stage Units (FSUs)?",
            options=[
                "Census villages as per the latest Population Census",
                "Urban Frame Survey (UFS) blocks",
                "Sub-district administrative tehsils",
                "Gram Panchayats with population exceeding 5,000"
            ],
            correct_option_index=0,
            explanation="As explicitly stated in NSSO protocols, First Stage Units (FSUs) in the rural sector are census villages as per the latest Population Census, while in urban areas they are UFS blocks.",
            source_chunk_id=first_chunk.id if first_chunk else None,
            source_excerpt="In the rural sector, the First Stage Units (FSUs) are census villages as per the latest Population Census, whereas in the urban sector, the FSUs are Urban Frame Survey (UFS) blocks."
        )
        q2 = QuizQuestion(
            quiz_id=sample_quiz.id,
            question_text="Under what specific condition is an NSSO sample FSU divided into two or more hamlet-groups or sub-blocks?",
            options=[
                "When population is greater than 1200 or has more than 300 households",
                "When the geographical area of the village exceeds 50 square kilometers",
                "When literacy rate is recorded below national average in previous census",
                "When the number of second-stage strata exceeds 10 categories"
            ],
            correct_option_index=0,
            explanation="The manual specifies that an FSU with population greater than 1200 or having more than 300 households is divided into two or more hamlet-groups or sub-blocks of approximately equal population.",
            source_chunk_id=first_chunk.id if first_chunk else None,
            source_excerpt="Before listing households, an FSU with population greater than 1200 or having more than 300 households is divided into two or more hamlet-groups (in rural areas) or sub-blocks (in urban areas) of approximately equal population."
        )
        q3 = QuizQuestion(
            quiz_id=sample_quiz.id,
            question_text="What sampling method is applied in rural strata where selection size corresponds to village population?",
            options=[
                "Circular Systematic Sampling with Probability Proportional to Size (PPSWR)",
                "Simple Random Sampling Without Replacement (SRSWOR)",
                "Stratified Multi-Cluster Sampling with Fixed Proportions",
                "Non-probability quota allocation based on district density"
            ],
            correct_option_index=0,
            explanation="In rural areas, sample FSUs are selected following Circular Systematic Sampling with Probability Proportional to Size (PPSWR) where size is village population.",
            source_chunk_id=first_chunk.id if first_chunk else None,
            source_excerpt="Within each stratum, sample FSUs are selected following Circular Systematic Sampling with Probability Proportional to Size (PPSWR) in rural areas where size is village population, and Simple Random Sampling Without Replacement (SRSWOR) in urban areas."
        )
        db.add_all([q1, q2, q3])

        gen_log = GenerationLog(
            quiz_id=sample_quiz.id,
            raw_model_response='{"questions": 3, "status": "pre-seeded-golden-benchmark"}',
            parse_success=True,
            retry_count=0,
            error_message=None,
            discarded_questions_count=0,
            discarded_reasons=[]
        )
        db.add(gen_log)
        db.commit()

        # Add sample attempt for Rajesh
        if u1:
            att = LearnerQuizAttempt(
                user_id=u1.id,
                quiz_id=sample_quiz.id,
                score=3,
                total_questions=3,
                percentage=100.0,
                passed=True
            )
            db.add(att)
            db.commit()

    db.close()
    print("[OK] Complete MoSPI Database successfully seeded (Users, Competencies, iGOT Courses, Materials, Quizzes)!", flush=True)

if __name__ == "__main__":
    seed_database()
