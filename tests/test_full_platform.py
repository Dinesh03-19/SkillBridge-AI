import unittest
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

class TestSkillBridgeFullPlatform(unittest.TestCase):

    def test_health(self):
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")

    def test_private_blob_upload_processing(self):
        content = b"Survey sampling methodology and field operations."
        pathname = "training-materials/test-run/sample.txt"
        with patch.dict(os.environ, {"VERCEL": "1"}):
            with patch("vercel.blob.get_blob", new_callable=AsyncMock) as get_blob:
                with patch("backend.api.routes.EmbeddingService.get_instance") as get_embedding_service:
                    get_blob.return_value = SimpleNamespace(body=content)
                    get_embedding_service.return_value.add_chunks.return_value = ["mat_99_chunk_0"]

                    response = client.post("/api/materials/process-blob", json={
                        "pathname": pathname,
                        "skill_id": "sampling_methodology",
                        "title": "Sampling notes",
                        "uploaded_by": "Admin"
                    })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["file_path"], pathname)
        get_blob.assert_awaited_once_with(pathname, access="private")

    def test_coverage_100_percent(self):
        """Verify that PS alignment coverage is 100% across all 8 categories."""
        res = client.get("/api/coverage")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["overall_score"], 100.0)
        self.assertEqual(data["summary"]["implemented_count"], 8)
        self.assertEqual(data["summary"]["partial_count"], 0)
        self.assertEqual(data["summary"]["planned_count"], 0)

    def test_user_profiles_and_rbac(self):
        """Verify user listing and profile retrieval."""
        res = client.get("/api/users")
        self.assertEqual(res.status_code, 200)
        users = res.json()
        self.assertGreaterEqual(len(users), 2)

        # Profile for Rajesh Sharma (SSO)
        p_res = client.get("/api/users/profile?user_id=1")
        self.assertEqual(p_res.status_code, 200)
        prof = p_res.json()
        self.assertIn("Rajesh Sharma", prof["name"])
        self.assertEqual(prof["role"], "learner")
        self.assertEqual(prof["cadre"], "Indian Statistical Service (ISS)")

    def test_competency_framework_and_gaps(self):
        """Verify MoSPI 4-domain competency framework and automated gap calculation."""
        f_res = client.get("/api/competency/framework")
        self.assertEqual(f_res.status_code, 200)
        framework = f_res.json()
        self.assertEqual(len(framework["domains"]), 4)

        g_res = client.get("/api/competency/gaps/1")
        self.assertEqual(g_res.status_code, 200)
        gap_data = g_res.json()
        self.assertIn("domain_scores", gap_data)
        self.assertIn("overall_readiness_pct", gap_data)
        self.assertGreater(gap_data["total_competencies"], 5)

    def test_igot_karmayogi_integration(self):
        """Verify course catalog, recommendations, enrollment, and credit synchronization."""
        # 1. Course catalogue
        c_res = client.get("/api/igot/courses?user_id=1")
        self.assertEqual(c_res.status_code, 200)
        courses = c_res.json()
        self.assertGreaterEqual(len(courses), 5)

        # 2. Personalized recommendations based on skill gaps
        r_res = client.get("/api/igot/recommendations/1")
        self.assertEqual(r_res.status_code, 200)
        rec = r_res.json()
        self.assertIn("recommended_courses", rec)
        self.assertGreaterEqual(len(rec["recommended_courses"]), 1)

        # 3. Enroll user in course 3 (SNA 2008)
        target_course_id = courses[2]["id"]
        enr_res = client.post("/api/igot/enroll", json={"user_id": 1, "course_id": target_course_id})
        self.assertEqual(enr_res.status_code, 200)
        enr_data = enr_res.json()
        self.assertEqual(enr_data["status"], "in_progress")

        # 4. Complete course and verify credit sync
        comp_res = client.post("/api/igot/complete", json={"user_id": 1, "course_id": target_course_id})
        self.assertEqual(comp_res.status_code, 200)
        comp_data = comp_res.json()
        self.assertEqual(comp_data["status"], "completed")
        self.assertIsNotNone(comp_data["new_competency_score"])

    def test_ai_virtual_assistant(self):
        """Verify Karmayogi Saathi AI Assistant responds in English and Hindi."""
        # English query
        en_res = client.post("/api/assistant/chat", json={
            "user_id": 1,
            "message": "Explain the difference between Usual Status and Current Weekly Status in PLFS",
            "language": "en"
        })
        self.assertEqual(en_res.status_code, 200)
        en_data = en_res.json()
        self.assertIn("PLFS", en_data["reply"])
        self.assertEqual(en_data["language"], "en")

        # Hindi query
        hi_res = client.post("/api/assistant/chat", json={
            "user_id": 1,
            "message": "पीएलएफएस में कार्यकलाप स्थिति क्या है?",
            "language": "hi"
        })
        self.assertEqual(hi_res.status_code, 200)
        hi_data = hi_res.json()
        self.assertIn("PLFS", hi_data["reply"])
        self.assertEqual(hi_data["language"], "hi")

    def test_admin_workforce_analytics(self):
        """Verify organization-wide administrative insights and predictive forecasting."""
        res = client.get("/api/analytics/admin-summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total_workforce_enrolled"], 0)
        self.assertGreater(data["avg_competency_readiness"], 50)
        self.assertIn("cadre_distribution", data)
        self.assertGreater(len(data["top_skill_gaps"]), 0)
        self.assertGreater(len(data["predictive_capacity_forecast"]), 0)

if __name__ == "__main__":
    unittest.main()
