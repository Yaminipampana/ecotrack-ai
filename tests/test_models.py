import os
import unittest
from datetime import date, datetime, timedelta

# Set testing environment variables before importing app
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test_secret_key_1234567890'

from app import app, db
from models import User, CarbonCalculation, CompletedChallenge, AiRecommendation

class ModelTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_user_password_hashing(self):
        """Test User password hashing and verification."""
        user = User(username='testuser', email='test@example.com')
        user.set_password('securepassword')
        
        self.assertTrue(user.check_password('securepassword'))
        self.assertFalse(user.check_password('wrongpassword'))
        self.assertNotEqual(user.password_hash, 'securepassword')

    def test_user_add_points_and_leveling(self):
        """Test user points addition and automatic level calculation."""
        user = User(username='pointsuser', email='points@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # Check default level and points
        self.assertEqual(user.green_points, 0)
        self.assertEqual(user.current_level, 1)

        # Add points (less than 500)
        user.add_points(300)
        self.assertEqual(user.green_points, 300)
        self.assertEqual(user.current_level, 1)

        # Add points to cross 500 threshold
        user.add_points(200)
        self.assertEqual(user.green_points, 500)
        self.assertEqual(user.current_level, 2)

        # Add points to cross 1000 threshold (level 3)
        user.add_points(550)
        self.assertEqual(user.green_points, 1050)
        self.assertEqual(user.current_level, 3)

    def test_user_get_badges(self):
        """Test user badge awards logic."""
        user = User(username='badgeuser', email='badge@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # 1. Check badges on initialization (no calculations, no challenges, not admin, level 1)
        self.assertEqual(len(user.get_badges()), 0)

        # 2. Add admin badge
        user.is_admin = True
        badges = user.get_badges()
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0]['id'], 'green_admin')

        # Reset admin
        user.is_admin = False

        # 3. Add first calculation -> Eco Novice badge
        calc1 = CarbonCalculation(
            user_id=user.id,
            transport_emissions=1.5,
            electricity_emissions=1.2,
            food_emissions=2.0,
            waste_emissions=0.3,
            total_emissions=5.0,
            calculated_at=datetime.utcnow() - timedelta(days=2)
        )
        db.session.add(calc1)
        db.session.commit()

        badges = user.get_badges()
        badge_ids = [b['id'] for b in badges]
        self.assertIn('eco_novice', badge_ids)
        self.assertEqual(len(badges), 1)

        # 4. Add second calculation with REDUCED emissions -> Carbon Reducer badge
        calc2 = CarbonCalculation(
            user_id=user.id,
            transport_emissions=1.0,
            electricity_emissions=1.0,
            food_emissions=1.5,
            waste_emissions=0.2,
            total_emissions=3.7,
            calculated_at=datetime.utcnow() - timedelta(days=1)
        )
        db.session.add(calc2)
        db.session.commit()

        badges = user.get_badges()
        badge_ids = [b['id'] for b in badges]
        self.assertIn('eco_novice', badge_ids)
        self.assertIn('carbon_reducer', badge_ids)
        self.assertEqual(len(badges), 2)

        # 5. Add completed challenges -> Challenge Champion badge (requires >= 5 challenges)
        for i in range(5):
            challenge = CompletedChallenge(
                user_id=user.id,
                challenge_id=f"challenge_{i}",
                completed_at=date.today() - timedelta(days=i)
            )
            db.session.add(challenge)
        db.session.commit()

        badges = user.get_badges()
        badge_ids = [b['id'] for b in badges]
        self.assertIn('challenge_champion', badge_ids)
        self.assertEqual(len(badges), 3)

        # 6. Raise points to level 3 -> Green Guardian badge
        user.add_points(1000)
        db.session.commit()
        self.assertEqual(user.current_level, 3)

        badges = user.get_badges()
        badge_ids = [b['id'] for b in badges]
        self.assertIn('green_guardian', badge_ids)
        self.assertEqual(len(badges), 4)

    def test_get_carbon_reduction_percentage(self):
        """Test carbon footprint reduction percentage calculations."""
        user = User(username='reductionuser', email='reduction@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # No calculations
        self.assertEqual(user.get_carbon_reduction_percentage(), 0.0)

        # One calculation
        calc1 = CarbonCalculation(
            user_id=user.id,
            transport_emissions=2.0,
            electricity_emissions=2.0,
            food_emissions=2.0,
            waste_emissions=2.0,
            total_emissions=8.0,
            calculated_at=datetime.utcnow() - timedelta(days=5)
        )
        db.session.add(calc1)
        db.session.commit()
        self.assertEqual(user.get_carbon_reduction_percentage(), 0.0)

        # Second calculation with reduction: 8.0 -> 6.0 (25% reduction)
        calc2 = CarbonCalculation(
            user_id=user.id,
            transport_emissions=1.5,
            electricity_emissions=1.5,
            food_emissions=1.5,
            waste_emissions=1.5,
            total_emissions=6.0,
            calculated_at=datetime.utcnow() - timedelta(days=2)
        )
        db.session.add(calc2)
        db.session.commit()
        self.assertEqual(user.get_carbon_reduction_percentage(), 25.0)

        # Third calculation with increase: 8.0 -> 9.0 (negative reduction compared to first, i.e., -12.5% reduction)
        # Note: the code says:
        # calcs = sorted(self.calculations, key=lambda c: c.calculated_at)
        # first_val = calcs[0].total_emissions
        # latest_val = calcs[-1].total_emissions
        # reduction = ((first_val - latest_val) / first_val) * 100
        # Let's verify this logic.
        calc3 = CarbonCalculation(
            user_id=user.id,
            transport_emissions=2.5,
            electricity_emissions=2.5,
            food_emissions=2.5,
            waste_emissions=1.5,
            total_emissions=9.0,
            calculated_at=datetime.utcnow() - timedelta(days=1)
        )
        db.session.add(calc3)
        db.session.commit()
        # first=8.0, latest=9.0. reduction = ((8.0 - 9.0) / 8.0) * 100 = -12.5%
        self.assertEqual(user.get_carbon_reduction_percentage(), -12.5)

    def test_database_cascades(self):
        """Test database cascade deletions when a user is deleted."""
        user = User(username='cascadeuser', email='cascade@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        calc = CarbonCalculation(
            user_id=user.id,
            transport_emissions=1.0,
            electricity_emissions=1.0,
            food_emissions=1.0,
            waste_emissions=1.0,
            total_emissions=4.0
        )
        db.session.add(calc)
        db.session.commit()

        challenge = CompletedChallenge(user_id=user.id, challenge_id='no_meat_day')
        db.session.add(challenge)

        rec = AiRecommendation(
            user_id=user.id,
            calculation_id=calc.id,
            summary="Good job",
            tips_json='["Tip 1"]',
            weekly_plan_json='["Day 1: Do nothing"]'
        )
        db.session.add(rec)
        db.session.commit()

        # Verify items exist
        self.assertEqual(CarbonCalculation.query.filter_by(user_id=user.id).count(), 1)
        self.assertEqual(CompletedChallenge.query.filter_by(user_id=user.id).count(), 1)
        self.assertEqual(AiRecommendation.query.filter_by(user_id=user.id).count(), 1)

        # Delete user
        db.session.delete(user)
        db.session.commit()

        # Verify cascade delete
        self.assertEqual(CarbonCalculation.query.filter_by(user_id=user.id).count(), 0)
        self.assertEqual(CompletedChallenge.query.filter_by(user_id=user.id).count(), 0)
        self.assertEqual(AiRecommendation.query.filter_by(user_id=user.id).count(), 0)

if __name__ == '__main__':
    unittest.main()
