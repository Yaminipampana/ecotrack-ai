import os
import unittest
from unittest.mock import patch, MagicMock
import requests

from gemini_helper import (
    clean_obfuscated_text,
    get_local_recommendations,
    generate_sustainability_recommendations
)

class GeminiHelperTestCase(unittest.TestCase):
    
    def test_clean_obfuscated_text_no_obfuscation(self):
        """Test clean_obfuscated_text on ordinary text without colon issues."""
        text = "This is a normal sentence. It has: one colon."
        self.assertEqual(clean_obfuscated_text(text), text)
        
        # Test non-string input
        self.assertEqual(clean_obfuscated_text(None), None)
        self.assertEqual(clean_obfuscated_text(123), 123)

    def test_clean_obfuscated_text_with_obfuscation(self):
        """Test clean_obfuscated_text on text that contains high-density colons."""
        # A string with heavy colons (density > 15% and count > 3)
        obfuscated = "T:h:i:s: :i:s: :o:b:f:u:s:c:a:t:e:d:."
        # Expected: Colons preceding characters should be cleaned
        # e.g., re.sub(r':(.)', r'\1', text)
        # "T" -> ":h" -> "h", ":i" -> "i", ":s" -> "s", ": " -> " ", ":i" -> "i", ":s" -> "s", ": " -> " ", ":o" -> "o", ":b" -> "b", ":f" -> "f" ...
        # Result: "This is obfuscated."
        cleaned = clean_obfuscated_text(obfuscated)
        self.assertEqual(cleaned, "This is obfuscated.")

    def test_clean_obfuscated_text_with_day_prefix(self):
        """Test clean_obfuscated_text when a 'Day X:' prefix is present."""
        obfuscated = "Day 1: U:s:e: :p:u:b:l:i:c: :t:r:a:n:s:i:t:."
        cleaned = clean_obfuscated_text(obfuscated)
        self.assertEqual(cleaned, "Day 1: Use public transit.")

    def test_get_local_recommendations_transportation(self):
        """Test get_local_recommendations when Transportation is the highest emissions source."""
        # Total emissions = 5.0 + 1.0 + 1.0 + 1.0 = 8.0 (moderate status)
        recs = get_local_recommendations(
            transport=5.0,
            electricity=1.0,
            food=1.0,
            waste=1.0,
            total=8.0
        )
        
        self.assertIn("summary", recs)
        self.assertIn("tips", recs)
        self.assertIn("weekly_plan", recs)
        self.assertIn("8.00 tCO2e/yr", recs["summary"])
        self.assertIn("Transportation", recs["summary"])
        self.assertIn("moderate", recs["summary"])
        
        # Check that the weekly plan is transportation-focused
        self.assertTrue(recs["weekly_plan"][0].startswith("Day 1: Leave the car at home"))
        
        # Check tips has correct structure
        self.assertEqual(len(recs["tips"]), 3)
        self.assertEqual(recs["tips"][0]["category"], "Transportation")

    def test_get_local_recommendations_home_energy(self):
        """Test get_local_recommendations when Home Energy is the highest emissions source."""
        # Total emissions = 1.0 + 6.0 + 1.0 + 1.0 = 9.0
        recs = get_local_recommendations(
            transport=1.0,
            electricity=6.0,
            food=1.0,
            waste=1.0,
            total=9.0
        )
        
        self.assertIn("Home Energy", recs["summary"])
        self.assertTrue(recs["weekly_plan"][0].startswith("Day 1: Audit your home for drafts"))
        self.assertEqual(recs["tips"][1]["category"], "Energy")

    def test_get_local_recommendations_diet(self):
        """Test get_local_recommendations when Dietary Choices is the highest emissions source."""
        # Total emissions = 1.0 + 1.0 + 5.0 + 0.5 = 7.5
        # food = 5.0 > waste = 0.5
        recs = get_local_recommendations(
            transport=1.0,
            electricity=1.0,
            food=5.0,
            waste=0.5,
            total=7.5
        )
        
        self.assertIn("Dietary Choices", recs["summary"])
        self.assertTrue(recs["weekly_plan"][0].startswith("Day 1: Go 100% plant-based"))
        self.assertEqual(recs["tips"][2]["category"], "Food & Diet")

    def test_get_local_recommendations_waste(self):
        """Test get_local_recommendations when Waste & Recycling is the highest emissions source."""
        # Total emissions = 1.0 + 1.0 + 1.0 + 4.0 = 7.0
        # food = 1.0, waste = 4.0 (waste > food, so waste tip chosen)
        recs = get_local_recommendations(
            transport=1.0,
            electricity=1.0,
            food=1.0,
            waste=4.0,
            total=7.0
        )
        
        self.assertIn("Waste & Recycling", recs["summary"])
        self.assertTrue(recs["weekly_plan"][0].startswith("Day 1: Set up dedicated recycling bins"))
        self.assertEqual(recs["tips"][2]["category"], "Waste & Recycling")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"})
    @patch("requests.post")
    def test_generate_recommendations_api_success(self, mock_post):
        """Test generate_sustainability_recommendations when API succeeds."""
        # Mock successful Gemini API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Gemini API response structure: candidates -> content -> parts -> text
        api_text = """
        {
          "summary": "Your carbon footprint is excellent.",
          "tips": [
            {"category": "Transportation", "tip": "Ride a bike."},
            {"category": "Energy", "tip": "Use LEDs."},
            {"category": "Food/Waste", "tip": "Eat plant-based."}
          ],
          "weekly_plan": [
            "Day 1: Walk to work",
            "Day 2: Turn off lights",
            "Day 3: Compost",
            "Day 4: Buy local",
            "Day 5: Unplug devices",
            "Day 6: Recycle",
            "Day 7: Relax"
          ]
        }
        """
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": api_text}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        recs = generate_sustainability_recommendations(1.0, 1.0, 1.0, 1.0, 4.0)
        
        self.assertEqual(recs["summary"], "Your carbon footprint is excellent.")
        self.assertEqual(len(recs["tips"]), 3)
        self.assertEqual(recs["tips"][0]["tip"], "Ride a bike.")
        self.assertEqual(len(recs["weekly_plan"]), 7)
        mock_post.assert_called_once()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"})
    @patch("requests.post")
    def test_generate_recommendations_api_invalid_json(self, mock_post):
        """Test generate_sustainability_recommendations falls back when API returns invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "invalid json content"}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        # Should fall back to local recommendations instead of raising an error
        recs = generate_sustainability_recommendations(1.0, 1.0, 1.0, 1.0, 4.0)
        self.assertIn("Your annual carbon footprint is", recs["summary"])

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"})
    @patch("requests.post")
    def test_generate_recommendations_api_http_error(self, mock_post):
        """Test generate_sustainability_recommendations falls back on API HTTP error."""
        mock_post.side_effect = requests.RequestException("Network error")

        # Should fall back to local recommendations
        recs = generate_sustainability_recommendations(1.0, 1.0, 1.0, 1.0, 4.0)
        self.assertIn("Your annual carbon footprint is", recs["summary"])

    @patch.dict(os.environ, {}, clear=True)
    def test_generate_recommendations_no_api_key(self):
        """Test generate_sustainability_recommendations falls back when API key is missing."""
        # Should directly fall back to local recommendations
        recs = generate_sustainability_recommendations(1.0, 1.0, 1.0, 1.0, 4.0)
        self.assertIn("Your annual carbon footprint is", recs["summary"])

if __name__ == '__main__':
    unittest.main()
