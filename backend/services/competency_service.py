"""
competency_service.py — MoSPI Official Statistics Competency Framework & Gap Engine

Defines competency standards across:
- Statistical Competencies
- Technical Competencies
- Digital Governance
- Behavioural and Managerial Competencies

Computes quantitative skill gaps, readiness indices, and automatically updates
scores upon quiz completion and iGOT course milestones.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models import User, Competency, UserCompetencyScore, LearnerQuizAttempt, Quiz

# Predefined MoSPI Competencies mapped to Problem Statement domains
MOSPI_COMPETENCY_FRAMEWORK = [
    # 1. Statistical Competencies
    {
        "code": "STAT_SURVEY_DESIGN",
        "name": "Survey Design & Sampling Methodology",
        "domain": "Statistical",
        "description": "Probability sampling, multi-stage stratified sampling, sample size estimation, NSSO frame design.",
        "benchmark_jso": 65.0,
        "benchmark_sso": 80.0,
        "benchmark_director": 90.0,
    },
    {
        "code": "STAT_LABOUR_STATISTICS",
        "name": "Periodic Labour Force Statistics (PLFS)",
        "domain": "Statistical",
        "description": "Usual Principal Activity status (ps+ss), Current Weekly Status (CWS), labour force participation rates, worker population ratios.",
        "benchmark_jso": 60.0,
        "benchmark_sso": 75.0,
        "benchmark_director": 85.0,
    },
    {
        "code": "STAT_NATIONAL_ACCOUNTS",
        "name": "National Accounts & GDP Compilation",
        "domain": "Statistical",
        "description": "SNA 2008 frameworks, Gross Value Added (GVA), input-output tables, base year revision methodology.",
        "benchmark_jso": 55.0,
        "benchmark_sso": 70.0,
        "benchmark_director": 85.0,
    },
    {
        "code": "STAT_PRICE_INDICES",
        "name": "Price Statistics & Index Numbers (CPI/WPI)",
        "domain": "Statistical",
        "description": "Laspeyres, Paasche, Fisher indices, item basket selection, price relatives, rural/urban CPI compilation.",
        "benchmark_jso": 60.0,
        "benchmark_sso": 75.0,
        "benchmark_director": 85.0,
    },
    {
        "code": "STAT_DATA_QUALITY",
        "name": "Data Quality Frameworks & SDG Indicators",
        "domain": "Statistical",
        "description": "MoSPI National Quality Assurance Framework (NQAF), SDG baseline mapping, validation rules.",
        "benchmark_jso": 65.0,
        "benchmark_sso": 80.0,
        "benchmark_director": 90.0,
    },

    # 2. Technical Competencies
    {
        "code": "TECH_PYTHON_R",
        "name": "Statistical Programming (Python, R & SQL)",
        "domain": "Technical",
        "description": "Data wrangling, automated tabular processing, reproducible statistical workflows using Pandas, R-Tidyverse, PostgreSQL.",
        "benchmark_jso": 50.0,
        "benchmark_sso": 70.0,
        "benchmark_director": 75.0,
    },
    {
        "code": "TECH_AI_ML_BIGDATA",
        "name": "AI/ML, Big Data & Modern Methodologies",
        "domain": "Technical",
        "description": "High-frequency indicator forecasting, imputation algorithms, large-scale survey data mining.",
        "benchmark_jso": 45.0,
        "benchmark_sso": 65.0,
        "benchmark_director": 75.0,
    },
    {
        "code": "TECH_GIS_SPATIAL",
        "name": "GIS & Spatial Statistical Analytics",
        "domain": "Technical",
        "description": "QGIS, geo-tagging survey enumeration blocks, spatial autocorrelation, remote sensing data integration.",
        "benchmark_jso": 50.0,
        "benchmark_sso": 70.0,
        "benchmark_director": 80.0,
    },

    # 3. Digital Governance
    {
        "code": "GOV_CYBER_PRIVACY",
        "name": "Cybersecurity & Microdata Privacy Standards",
        "domain": "Digital Governance",
        "description": "DPDP Act 2023 compliance, statistical disclosure control (SDC), anonymization, secure government cloud.",
        "benchmark_jso": 65.0,
        "benchmark_sso": 75.0,
        "benchmark_director": 85.0,
    },
    {
        "code": "GOV_OPEN_DATA_API",
        "name": "Open Data, APIs & Metadata Standards",
        "domain": "Digital Governance",
        "description": "National Data Sharing & Accessibility Policy (NDSAP), SDMX exchange, CKAN microdata portals.",
        "benchmark_jso": 55.0,
        "benchmark_sso": 70.0,
        "benchmark_director": 80.0,
    },

    # 4. Behavioural & Managerial
    {
        "code": "MGT_LEADERSHIP_PROJECT",
        "name": "Statistical Project Management & Field Leadership",
        "domain": "Behavioural/Managerial",
        "description": "Large-scale field operation planning, survey budget management, investigator supervision, stakeholder communication.",
        "benchmark_jso": 60.0,
        "benchmark_sso": 75.0,
        "benchmark_director": 90.0,
    },
    {
        "code": "MGT_ETHICS_DECISION",
        "name": "Official Statistical Ethics & Public Decision Making",
        "domain": "Behavioural/Managerial",
        "description": "UN Fundamental Principles of Official Statistics, impartiality, professional independence, transparent revisions.",
        "benchmark_jso": 70.0,
        "benchmark_sso": 85.0,
        "benchmark_director": 95.0,
    }
]


def get_target_benchmark_for_user(designation: str, comp: Competency) -> float:
    """Returns benchmark target score based on official's designation."""
    d_lower = designation.lower()
    if "director" in d_lower or "joint director" in d_lower:
        return comp.benchmark_level_director
    elif "senior statistical officer" in d_lower or "sso" in d_lower or "analyst" in d_lower:
        return comp.benchmark_level_sso
    else:
        return comp.benchmark_level_jso


def calculate_user_skill_gaps(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Computes comprehensive skill-gap analysis for an official.
    Calculates gaps (Target Benchmark - Current Score), classifies severity,
    and breaks down performance across all 4 MoSPI domains.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User with ID {user_id} not found")

    scores = db.query(UserCompetencyScore).filter(UserCompetencyScore.user_id == user_id).all()

    competency_details = []
    domain_totals: Dict[str, List[float]] = {
        "Statistical": [],
        "Technical": [],
        "Digital Governance": [],
        "Behavioural/Managerial": []
    }

    critical_gaps = 0
    total_gap_sum = 0.0

    for s in scores:
        comp = s.competency
        target = get_target_benchmark_for_user(user.designation, comp)
        s.target_score = target
        gap = max(0.0, round(target - s.current_score, 1))

        if gap >= 20.0:
            status = "critical_gap"
            critical_gaps += 1
        elif gap > 5.0:
            status = "moderate_gap"
        else:
            status = "proficient"

        competency_details.append({
            "competency_id": comp.id,
            "code": comp.code,
            "name": comp.name,
            "domain": comp.domain,
            "current_score": round(s.current_score, 1),
            "target_score": round(target, 1),
            "gap": gap,
            "status": status,
            "last_assessed": s.last_assessed
        })

        if comp.domain in domain_totals:
            domain_totals[comp.domain].append(s.current_score)
        total_gap_sum += gap

    db.commit()

    # Calculate domain average scores
    domain_scores = {}
    for dom, vals in domain_totals.items():
        domain_scores[dom] = round(sum(vals) / len(vals), 1) if vals else 0.0

    all_current = [s.current_score for s in scores]
    all_target = [s.target_score for s in scores]
    overall_readiness = (sum(all_current) / sum(all_target) * 100.0) if all_target and sum(all_target) > 0 else 0.0

    return {
        "user_id": user.id,
        "user_name": user.name,
        "designation": user.designation,
        "overall_readiness_pct": round(min(100.0, overall_readiness), 1),
        "total_competencies": len(scores),
        "critical_gaps_count": critical_gaps,
        "domain_scores": domain_scores,
        "competency_details": competency_details
    }


def update_competency_from_quiz(db: Session, user_id: int, quiz: Quiz, percentage: float) -> Optional[float]:
    """
    Updates the official's competency score dynamically when a quiz is submitted.
    Maps linked_skill_id to corresponding competency code.
    """
    skill_map = {
        "sampling_methodology": "STAT_SURVEY_DESIGN",
        "labour_force_survey": "STAT_LABOUR_STATISTICS",
        "data_quality": "STAT_DATA_QUALITY",
        "national_accounts": "STAT_NATIONAL_ACCOUNTS",
        "price_indices": "STAT_PRICE_INDICES",
        "python_statistics": "TECH_PYTHON_R",
        "ai_ml_statistics": "TECH_AI_ML_BIGDATA",
        "sdg_indicators": "STAT_DATA_QUALITY",
        "cybersecurity_governance": "GOV_CYBER_PRIVACY"
    }

    target_code = skill_map.get(quiz.linked_skill_id, "STAT_SURVEY_DESIGN")
    comp = db.query(Competency).filter(Competency.code == target_code).first()
    if not comp:
        return None

    score_rec = db.query(UserCompetencyScore).filter(
        UserCompetencyScore.user_id == user_id,
        UserCompetencyScore.competency_id == comp.id
    ).first()

    if score_rec:
        # Weighted exponential moving average update: 70% previous, 30% new assessment performance
        new_val = (score_rec.current_score * 0.70) + (percentage * 0.30)
        score_rec.current_score = round(min(100.0, new_val), 1)
        score_rec.last_assessed = datetime.utcnow()
        score_rec.assessment_source = f"Assessment Quiz #{quiz.id} ({percentage}%)"
        db.commit()
        return score_rec.current_score

    return None
