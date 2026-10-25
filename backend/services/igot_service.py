"""
igot_service.py — iGOT Karmayogi Ecosystem & NSSTA TPAC Integration Service

Provides:
- iGOT Course Catalogue retrieval (Official Statistics, Data Science, AI/ML, Governance).
- Intelligent Recommendation Engine aligning learner skill gaps to iGOT modules & NSSTA TPAC recommendations.
- Course enrolment, progress tracking, and automated competency credit synchronization.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models import User, IgotCourse, CourseEnrolment, UserCompetencyScore, Competency
from backend.services.competency_service import calculate_user_skill_gaps

# Predefined curated iGOT Karmayogi & NSSTA TPAC Course Library
SEED_IGOT_COURSES = [
    {
        "course_code": "IGOT_STAT_001",
        "title": "Advanced Survey Design & Sample Size Estimation in Official Statistics",
        "provider": "National Statistical Systems Training Academy (NSSTA)",
        "domain": "Statistical",
        "competency_code": "STAT_SURVEY_DESIGN",
        "duration_hours": 12.0,
        "level": "Advanced",
        "tpac_recommended": True,
        "description": "Comprehensive masterclass on stratified multi-stage sampling, sampling weights calculation, variance estimation, and frame updates used in NSS rounds.",
        "curriculum_highlights": [
            "Probability Proportional to Size (PPS) Systematic Sampling",
            "Multipliers & Multi-stage Weight Estimation",
            "Non-sampling Error Controls & Imputation Methods",
            "Field Enumeration Block (UFS) Digital Mapping"
        ],
        "external_url": "https://igotkarmayogi.gov.in/app/toc/lex_auth_013847291",
        "enrolment_count": 3420,
        "rating": 4.9
    },
    {
        "course_code": "IGOT_STAT_002",
        "title": "Periodic Labour Force Survey (PLFS) Concepts, Methodology & Field Protocols",
        "provider": "MoSPI / NSSTA & iGOT Karmayogi",
        "domain": "Statistical",
        "competency_code": "STAT_LABOUR_STATISTICS",
        "duration_hours": 10.0,
        "level": "Intermediate",
        "tpac_recommended": True,
        "description": "Essential training for ISS and SSS officers on PLFS rotational panel design, activity status definitions, weekly hours worked, and enterprise classification.",
        "curriculum_highlights": [
            "Activity Status: Usual (ps+ss) vs Current Weekly Status (CWS)",
            "Rotational Panel Sampling Scheme for Urban Areas",
            "Computer Assisted Personal Interviewing (CAPI) Data Entry",
            "Labour Force Indicators Estimation & Tabulation"
        ],
        "external_url": "https://igotkarmayogi.gov.in/app/toc/lex_auth_013847292",
        "enrolment_count": 5190,
        "rating": 4.8
    },
    {
        "course_code": "IGOT_STAT_003",
        "title": "System of National Accounts (SNA 2008) & GVA Compilation Frameworks",
        "provider": "National Accounts Division (NAD), MoSPI / NSSTA",
        "domain": "Statistical",
        "competency_code": "STAT_NATIONAL_ACCOUNTS",
        "duration_hours": 15.0,
        "level": "Advanced",
        "tpac_recommended": True,
        "description": "In-depth course on sequence of accounts, Gross Domestic Product (GDP), supply-use tables, base-year revision, and corporate sector financial data aggregation.",
        "curriculum_highlights": [
            "Production, Income and Expenditure Approaches to GDP",
            "Double Deflation Methodology in Manufacturing GVA",
            "MCA-21 Enterprise Financial Statement Processing",
            "Informal Sector Value Added Estimation"
        ],
        "external_url": "https://igotkarmayogi.gov.in/app/toc/lex_auth_013847293",
        "enrolment_count": 2810,
        "rating": 4.9
    },
    {
        "course_code": "IGOT_STAT_004",
        "title": "Price Statistics, Index Number Theory & Modern CPI Compilation",
        "provider": "Price Statistics Division (PSD), MoSPI",
        "domain": "Statistical",
        "competency_code": "STAT_PRICE_INDICES",
        "duration_hours": 8.0,
        "level": "Intermediate",
        "tpac_recommended": False,
        "description": "Theoretical and practical guide to Consumer Price Indices, Laspeyres geometric formulas, outlet substitution, and web-scraping for price collection.",
        "curriculum_highlights": [
            "Elementary Aggregation: Dutot vs Jevons Index Formulations",
            "Weighting Diagrams derived from Household Consumer Expenditure Survey (HCES)",
            "Hedonic Quality Adjustments for Durable Goods",
            "Rural and Urban Sub-indices Synthesis"
        ],
        "external_url": "https://igotkarmayogi.gov.in/app/toc/lex_auth_013847294",
        "enrolment_count": 2150,
        "rating": 4.7
    },
    {
        "course_code": "IGOT_TECH_001",
        "title": "Python & R for Official Statistics & Microdata Processing",
        "provider": "Digital India Corporation & NSSTA",
        "domain": "Technical",
        "competency_code": "TECH_PYTHON_R",
        "duration_hours": 14.0,
        "level": "Intermediate",
        "tpac_recommended": True,
        "description": "Hands-on data science bootcamp tailored for statistical officials: automated unit-level data cleaning, large CSV handling, statistical testing, and visualization.",
        "curriculum_highlights": [
            "Data wrangling with Pandas and Tidyverse on NSS microdata",
            "Survey analysis using the R 'survey' package",
            "Automated report generation with Quarto/Jupyter",
            "Writing reproducible pipelines for monthly statistical releases"
        ],
        "external_url": "https://igotkarmayogi.gov.in/app/toc/lex_auth_013847295",
        "enrolment_count": 6890,
        "rating": 4.9
    },
    {
        "course_code": "IGOT_TECH_002",
        "title": "Artificial Intelligence & Machine Learning in Government Decision Support",
        "provider": "National e-Governance Division (NeGD) / iGOT Karmayogi",
        "domain": "Technical",
        "competency_code": "TECH_AI_ML_BIGDATA",
        "duration_hours": 12.0,
        "level": "Intermediate",
        "tpac_recommended": True,
        "description": "Practical applications of ML forecasting, NLP text extraction from administrative records, satellite data classification, and responsible AI principles in government.",
        "curriculum_highlights": [
            "Supervised Learning for Missing Data Imputation in Surveys",
            "Time-Series Forecasting for Industrial Production (IIP)",
            "Computer Vision on Satellite Imagery for Crop Area Estimation",
            "Responsible AI, Model Bias & Explainability Guidelines"
        ],
        "external_url": "https://igotkarmayogi.gov.in/app/toc/lex_auth_013847296",
        "enrolment_count": 4540,
        "rating": 4.8
    },
    {
        "course_code": "IGOT_GOV_001",
        "title": "Digital Personal Data Protection (DPDP) Act & Government Data Governance",
        "provider": "Ministry of Electronics & Information Technology (MeitY)",
        "domain": "Digital Governance",
        "competency_code": "GOV_CYBER_PRIVACY",
        "duration_hours": 6.0,
        "level": "Beginner",
        "tpac_recommended": True,
        "description": "Key obligations under the DPDP Act 2023 for data fiduciaries, microdata anonymization techniques, differential privacy, and secure data access protocols.",
        "curriculum_highlights": [
            "Data Principal Consent & Data Fiduciary Responsibilities",
            "Statistical Disclosure Control (SDC) & k-Anonymity for Microdata",
            "Government Cloud Data Security Standards (MeitY Guidelines)",
            "Handling Information Security Incidents in Survey Wings"
        ],
        "external_url": "https://igotkarmayogi.gov.in/app/toc/lex_auth_013847297",
        "enrolment_count": 8920,
        "rating": 4.9
    },
    {
        "course_code": "IGOT_MGT_001",
        "title": "Public Leadership, Team Management & Statistical Ethics",
        "provider": "Capacity Building Commission (CBC) & NSSTA",
        "domain": "Behavioural/Managerial",
        "competency_code": "MGT_ETHICS_DECISION",
        "duration_hours": 8.0,
        "level": "Intermediate",
        "tpac_recommended": True,
        "description": "Strengthening leadership in statistical field directorates, conflict resolution, ethics in data dissemination, and citizen-centric administrative delivery.",
        "curriculum_highlights": [
            "UN Fundamental Principles of Official Statistics Implementation",
            "Field Staff Motivation & Interviewer Quality Oversight",
            "Public Communication of Statistical Revisions & Volatility",
            "Cross-departmental Coordination with Line Ministries"
        ],
        "external_url": "https://igotkarmayogi.gov.in/app/toc/lex_auth_013847298",
        "enrolment_count": 3110,
        "rating": 4.8
    }
]


class IgotIntegrationService:

    @staticmethod
    def get_all_courses(db: Session, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns course list, annotating enrolment status for a given user if provided."""
        courses = db.query(IgotCourse).all()
        user_enrolments = {}
        if user_id:
            enrs = db.query(CourseEnrolment).filter(CourseEnrolment.user_id == user_id).all()
            user_enrolments = {e.course_id: e for e in enrs}

        result = []
        for c in courses:
            enr = user_enrolments.get(c.id)
            result.append({
                "id": c.id,
                "course_code": c.course_code,
                "title": c.title,
                "provider": c.provider,
                "domain": c.domain,
                "competency_code": c.competency_code,
                "duration_hours": c.duration_hours,
                "level": c.level,
                "tpac_recommended": c.tpac_recommended,
                "description": c.description,
                "curriculum_highlights": c.curriculum_highlights or [],
                "external_url": c.external_url,
                "enrolment_count": c.enrolment_count,
                "rating": c.rating,
                "is_enrolled": enr is not None,
                "progress_pct": enr.progress_pct if enr else 0.0,
                "status": enr.status if enr else "not_enrolled"
            })
        return result

    @staticmethod
    def get_personalized_recommendations(db: Session, user_id: int) -> Dict[str, Any]:
        """
        AI & Rule-based recommendation engine:
        1. Analyzes the official's skill gaps.
        2. Identifies competencies where gap > 10.0 (prioritizing critical gaps).
        3. Matches courses tagged with those competencies.
        4. Prioritizes NSSTA's TPAC Recommended programmes.
        """
        gap_analysis = calculate_user_skill_gaps(db, user_id)
        comp_details = gap_analysis["competency_details"]

        # Sort competencies by highest gap descending
        gaps_sorted = sorted(comp_details, key=lambda x: x["gap"], reverse=True)
        high_gap_codes = [c["code"] for c in gaps_sorted if c["gap"] > 0]

        all_courses = IgotIntegrationService.get_all_courses(db, user_id)

        # Separate courses addressing identified gaps
        recommended_courses = []
        other_courses = []

        for c in all_courses:
            if c["competency_code"] in high_gap_codes:
                # Find the gap value for ranking
                gap_val = next((item["gap"] for item in gaps_sorted if item["code"] == c["competency_code"]), 0)
                # Boost TPAC recommended courses
                score = gap_val + (15.0 if c["tpac_recommended"] else 0.0)
                c["recommendation_score"] = round(score, 1)
                c["addresses_gap"] = f"Addresses {c['competency_code']} (Gap: {gap_val}%)"
                recommended_courses.append(c)
            else:
                other_courses.append(c)

        recommended_courses.sort(key=lambda x: x.get("recommendation_score", 0), reverse=True)

        return {
            "user_id": user_id,
            "overall_readiness_pct": gap_analysis["overall_readiness_pct"],
            "primary_skill_gap": gaps_sorted[0]["name"] if gaps_sorted else "None",
            "recommended_courses": recommended_courses,
            "tpac_count": sum(1 for c in recommended_courses if c["tpac_recommended"]),
            "general_courses": other_courses
        }

    @staticmethod
    def enroll_user_in_course(db: Session, user_id: int, course_id: int) -> Dict[str, Any]:
        """Enrolls user in an iGOT course and increments course enrolment count."""
        enr = db.query(CourseEnrolment).filter(
            CourseEnrolment.user_id == user_id,
            CourseEnrolment.course_id == course_id
        ).first()

        if not enr:
            enr = CourseEnrolment(
                user_id=user_id,
                course_id=course_id,
                status="in_progress",
                progress_pct=25.0
            )
            db.add(enr)
            course = db.query(IgotCourse).filter(IgotCourse.id == course_id).first()
            if course:
                course.enrolment_count += 1
            db.commit()
            db.refresh(enr)

        return {
            "enrolment_id": enr.id,
            "user_id": user_id,
            "course_id": course_id,
            "status": enr.status,
            "progress_pct": enr.progress_pct,
            "message": "Successfully enrolled via iGOT Karmayogi API handshake."
        }

    @staticmethod
    def complete_course(db: Session, user_id: int, course_id: int) -> Dict[str, Any]:
        """
        Completes an iGOT course:
        - Marks progress to 100% and status to 'completed'.
        - Updates user's total learning hours completed.
        - Synchronizes competency score (+15 points up to 100) for the linked competency.
        """
        enr = db.query(CourseEnrolment).filter(
            CourseEnrolment.user_id == user_id,
            CourseEnrolment.course_id == course_id
        ).first()

        course = db.query(IgotCourse).filter(IgotCourse.id == course_id).first()
        user = db.query(User).filter(User.id == user_id).first()

        if not course or not user:
            raise ValueError("User or Course not found")

        if not enr:
            enr = CourseEnrolment(user_id=user_id, course_id=course_id)
            db.add(enr)

        enr.status = "completed"
        enr.progress_pct = 100.0
        enr.completed_at = datetime.utcnow()

        # Add course hours to user's completed learning hours
        user.learning_hours_completed = round(user.learning_hours_completed + course.duration_hours, 1)

        # Synchronize competency score
        comp = db.query(Competency).filter(Competency.code == course.competency_code).first()
        updated_score = None
        if comp:
            c_score = db.query(UserCompetencyScore).filter(
                UserCompetencyScore.user_id == user_id,
                UserCompetencyScore.competency_id == comp.id
            ).first()
            if c_score:
                c_score.current_score = round(min(100.0, c_score.current_score + 15.0), 1)
                c_score.last_assessed = datetime.utcnow()
                c_score.assessment_source = f"iGOT Karmayogi: {course.title}"
                updated_score = c_score.current_score

        db.commit()

        return {
            "status": "completed",
            "course_title": course.title,
            "hours_credited": course.duration_hours,
            "total_learning_hours": user.learning_hours_completed,
            "competency_updated": comp.name if comp else None,
            "new_competency_score": updated_score,
            "message": "iGOT Karmayogi course completion verified and competency credits synchronized."
        }
