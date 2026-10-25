"""
assistant_service.py — AI-Powered Virtual Assistant ("Karmayogi Saathi")

Features:
- Real-time learner support for India's Official Statistical System officials.
- Answers questions on survey design, PLFS, National Accounts, CPI/WPI, data quality, and iGOT courses.
- Multilingual capability (English & Hindi) with contextual quick action prompts.
- Uses Google Gemini API when available, with an intelligent knowledge base fallback.
"""

import logging
from typing import List, Dict, Any, Optional
from backend.config import settings

logger = logging.getLogger(__name__)

KNOWLEDGE_TOPICS_EN = {
    "plfs": (
        "In the Periodic Labour Force Survey (PLFS), activity status is classified into: "
        "1. Usual Principal Activity Status (ps): Determined by the activity on which a person spent relatively long time during the 365 days preceding the date of survey.\n"
        "2. Usual Subsidiary Economic Activity Status (ss): Any economic activity pursued for 30 days or more during the reference year.\n"
        "3. Current Weekly Status (CWS): Activity status during a reference period of 7 days preceding the survey date.\n"
        "In urban areas, PLFS adopts a rotational panel sampling scheme where each selected household is visited 4 times (first visit + 3 quarterly revisits)."
    ),
    "sampling": (
        "MoSPI/NSSO surveys typically utilize a Stratified Multi-Stage Sampling Design:\n"
        "• First Stage Units (FSUs): Census villages in the rural sector and Urban Frame Survey (UFS) blocks in the urban sector.\n"
        "• Second Stage Units (SSUs): Households or enterprises listed within sample FSUs.\n"
        "• Selection Scheme: Probability Proportional to Size with Replacement (PPSWR) or systematic PPS sampling based on population or investigator count."
    ),
    "gdp": (
        "India's National Accounts adhere to the UN System of National Accounts (SNA 2008):\n"
        "• GVA at Basic Prices = Compensation of Employees + Operating Surplus/Mixed Income + Consumption of Fixed Capital (CFC) + Production Taxes less Production Subsidies.\n"
        "• GDP at Market Prices = GVA at Basic Prices + Product Taxes less Product Subsidies.\n"
        "The corporate sector GVA is compiled using automated aggregation of annual audited financial accounts from the Ministry of Corporate Affairs (MCA-21 database)."
    ),
    "cpi": (
        "The Consumer Price Index (CPI) measures changes over time in the general level of prices of goods and services that a reference population acquires for consumption:\n"
        "• Formula: Laspeyres geometric formulation with item weights derived from the Household Consumer Expenditure Survey (HCES).\n"
        "• Periodicity: Released monthly on the 12th of every month.\n"
        "• Categories: Rural, Urban, and Combined (All India)."
    ),
    "igot": (
        "The iGOT Karmayogi ecosystem is the National Programme for Civil Services Capacity Building (NPCSCB). "
        "For MoSPI officials, the National Statistical Systems Training Academy (NSSTA) has approved specific TPAC-recommended "
        "courses covering Survey Design, SNA 2008, Python for Official Statistics, and the DPDP Act 2023. "
        "Completing these courses automatically synchronizes and elevates your competency readiness scores."
    )
}

KNOWLEDGE_TOPICS_HI = {
    "plfs": (
        "आवधिक श्रम बल सर्वेक्षण (PLFS) में कार्यकलाप स्थिति (Activity Status) को दो प्रमुख श्रेणियों में मापा जाता है:\n"
        "1. सामान्य कार्यकलाप स्थिति (Usual Status - ps+ss): सर्वेक्षण की तिथि से पूर्व 365 दिनों की अवधि पर आधारित।\n"
        "2. वर्तमान साप्ताहिक स्थिति (Current Weekly Status - CWS): सर्वेक्षण तिथि से पूर्व के 7 दिनों की संदर्भ अवधि।\n"
        "शहरी क्षेत्रों में आवधिक पैनल (Rotational Panel) का उपयोग किया जाता है जहाँ प्रत्येक चयनित परिवार से 4 बार संपर्क किया जाता है।"
    ),
    "sampling": (
        "एनएसएसओ (NSSO) के बड़े सर्वेक्षणों में सामान्यतः 'स्तरीकृत बहु-चरणीय प्रतिचयन रूपरेखा' (Stratified Multi-Stage Sampling) अपनाई जाती है:\n"
        "• प्रथम चरण इकाइयां (FSUs): ग्रामीण क्षेत्र में जनगणना ग्राम तथा शहरी क्षेत्र में शहरी फ्रेम सर्वेक्षण (UFS) ब्लॉक।\n"
        "• द्वितीय चरण इकाइयां (SSUs): परिवारों या उद्यमों की सूची से चयनित इकाइयां।\n"
        "• चयन विधि: आकार के अनुपात में प्रायिकता (PPS) आधारित प्रणाली।"
    ),
    "gdp": (
        "भारत की राष्ट्रीय लेखा प्रणाली (National Accounts) यूएन एसएनए 2008 (SNA 2008) सिद्धांतों पर आधारित है:\n"
        "• बुनियादी मूल्यों पर जीवीए (GVA at Basic Prices) = कर्मचारियों का पारिश्रमिक + परिचालन अधिशेष + पूंजी का उपभोग + उत्पादन कर - उत्पादन सब्सिडी।\n"
        "• बाजार मूल्य पर जीडीपी = बुनियादी मूल्यों पर जीवीए + उत्पाद कर - उत्पाद सब्सिडी।"
    ),
    "cpi": (
        "उपभोक्ता मूल्य सूचकांक (CPI) खुदरा मूल्य स्तर में समय के साथ होने वाले परिवर्तनों को दर्शाता है। यह प्रतिमाह 12 तारीख को एनएसओ (NSO) द्वारा जारी किया जाता है।"
    ),
    "igot": (
        "आईगॉट कर्मयोगी (iGOT Karmayogi) मिशन कर्मयोगी के अंतर्गत भारत सरकार का क्षमता निर्माण मंच है। "
        "सांख्यिकी अधिकारियों के लिए एनएसएसटीए (NSSTA) की टीपीएसी (TPAC) द्वारा अनुशंसित विशेष पाठ्यक्रम उपलब्ध हैं।"
    )
}


class KarmayogiAssistantService:

    @staticmethod
    def answer_query(
        query: str,
        language: str = "en",
        user_name: Optional[str] = "Officer",
        designation: Optional[str] = "Statistical Official"
    ) -> Dict[str, Any]:
        """
        Generates grounded, helpful answer for learner assistance.
        If Gemini API key is valid, queries Gemini with MoSPI system persona.
        Otherwise, uses authoritative domain knowledge base.
        """
        q_lower = query.lower()
        api_key = settings.GEMINI_API_KEY

        # Check for Gemini API availability
        if api_key and api_key != "your_key_here" and not api_key.startswith("your_"):
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                lang_instruction = "Respond in fluent Hindi (Devanagari script)." if language == "hi" else "Respond in English."
                system_prompt = (
                    f"You are 'Karmayogi Saathi', an expert AI Virtual Assistant for India's Official Statistical System (MoSPI / NSO). "
                    f"You are assisting {user_name}, a {designation}. Provide accurate, authoritative, encouraging answers "
                    f"grounded in Indian official statistical standards (NSSO, PLFS, SNA 2008, CPI, NQAF, iGOT Karmayogi, NSSTA TPAC). "
                    f"{lang_instruction}"
                )

                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=f"{system_prompt}\n\nQuestion: {query}",
                    config=types.GenerateContentConfig(temperature=0.3)
                )

                if response and response.text:
                    return {
                        "reply": response.text,
                        "language": language,
                        "suggested_actions": [
                            "View Recommended iGOT Courses",
                            "Take Competency Assessment Quiz",
                            "Download MoSPI Manuals"
                        ],
                        "grounded_topics": ["Official Statistics", "iGOT Karmayogi", "MoSPI Standards"]
                    }
            except Exception as e:
                logger.warning(f"Gemini API assistant call fallback triggered: {e}")

        # Authoritative Knowledge Base Fallback
        is_hindi = (language == "hi")
        kb = KNOWLEDGE_TOPICS_HI if is_hindi else KNOWLEDGE_TOPICS_EN

        matched_content = []
        topics = []

        if any(w in q_lower for w in ["plfs", "labour", "employment", "cws", "activity status", "श्रम", "रोजगार"]):
            matched_content.append(kb["plfs"])
            topics.append("Periodic Labour Force Survey")
        if any(w in q_lower for w in ["sample", "sampling", "fsu", "ssu", "stratified", "प्रतिचयन", "नमूना"]):
            matched_content.append(kb["sampling"])
            topics.append("Sampling Methodology")
        if any(w in q_lower for w in ["gdp", "gva", "national accounts", "sna", "mca-21", "सकल घरेलू उत्पाद"]):
            matched_content.append(kb["gdp"])
            topics.append("National Accounts (SNA 2008)")
        if any(w in q_lower for w in ["cpi", "wpi", "price", "index", "laspeyres", "महंगाई", "मूल्य सूचकांक"]):
            matched_content.append(kb["cpi"])
            topics.append("Price Statistics (CPI)")
        if any(w in q_lower for w in ["igot", "karmayogi", "course", "nssta", "tpac", "training", "प्रशिक्षण", "कर्मयोगी"]):
            matched_content.append(kb["igot"])
            topics.append("iGOT Karmayogi & NSSTA")

        if not matched_content:
            if is_hindi:
                greeting = f"नमस्ते {user_name}! मैं कर्मयोगी साथी (Karmayogi Saathi) हूँ — भारत की आधिकारिक सांख्यिकी प्रणाली (MoSPI) का AI सहायक। "
                matched_content.append(
                    f"{greeting}आप मुझसे सर्वेक्षण रूपरेखा (Survey Design), पीएलएफएस (PLFS), राष्ट्रीय लेखा (SNA 2008), मूल्य सूचकांक (CPI) या iGOT कर्मयोगी पाठ्यक्रमों के संबंध में प्रश्न पूछ सकते हैं।"
                )
            else:
                greeting = f"Hello {user_name}! I am Karmayogi Saathi — your dedicated AI Virtual Assistant for India's Official Statistical System (MoSPI). "
                matched_content.append(
                    f"{greeting}You can ask me about NSSO Survey Design, PLFS definitions, National Accounts compilation, CPI index theory, or recommended iGOT Karmayogi & NSSTA TPAC courses."
                )
            topics.append("General Support")

        return {
            "reply": "\n\n".join(matched_content),
            "language": language,
            "suggested_actions": [
                "Recommend iGOT courses for my skill gaps",
                "Take a quiz on Sampling Methodology",
                "Explain SNA 2008 GVA calculation"
            ],
            "grounded_topics": topics
        }
