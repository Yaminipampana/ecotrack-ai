import os
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

# Set testing environment variables before importing app
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test_secret_key_1234567890'

from app import app, db, CHALLENGES
from models import User, CarbonCalculation, CompletedChallenge, AiRecommendation

class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        # Disable CSRF protection during tests if any is added, and enable session modifications
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed default admin user (matching app.py's seeded admin, but in our in-memory DB)
        self.admin_username = 'admin'
        self.admin_email = 'admin@ecotrack.ai'
        self.admin_password = 'admin123'
        
        # Verify if admin already exists due to app.py initialization code
        admin = User.query.filter_by(username=self.admin_username).first()
        if not admin:
            admin = User(username=self.admin_username, email=self.admin_email, is_admin=True)
            admin.set_password(self.admin_password)
            db.session.add(admin)
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def register_user(self, username, email, password, confirm_password):
        return self.client.post('/signup', data={
            'username': username,
            'email': email,
            'password': password,
            'confirm_password': confirm_password
        }, follow_redirects=True)

    def login_user(self, username_or_email, password):
        return self.client.post('/login', data={
            'username_or_email': username_or_email,
            'password': password
        }, follow_redirects=True)

    def logout_user(self):
        return self.client.get('/logout', follow_redirects=True)

    # 1. Authentication Tests
    def test_signup_success(self):
        """Test successful signup flow."""
        response = self.register_user('newuser', 'new@example.com', 'mypassword', 'mypassword')
        self.assertIn(b'Account created successfully', response.data)
        
        # Should redirect to calculator page
        self.assertIn(b'Carbon Calculator', response.data)
        
        # Check user database insertion
        user = User.query.filter_by(username='newuser').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'new@example.com')

    def test_signup_validation_failures(self):
        """Test signup validations."""
        # Password mismatch
        response = self.register_user('user1', 'u1@example.com', 'pass1', 'pass2')
        self.assertIn(b'Passwords do not match', response.data)
        
        # Missing fields
        response = self.register_user('', 'u2@example.com', 'pass1', 'pass1')
        self.assertIn(b'All fields are required', response.data)

        # Duplicate username
        self.register_user('user2', 'u2@example.com', 'pass1', 'pass1')
        self.logout_user()
        response = self.register_user('user2', 'u3@example.com', 'pass1', 'pass1')
        self.assertIn(b'Username is already taken', response.data)

        # Duplicate email
        response = self.register_user('user3', 'u2@example.com', 'pass1', 'pass1')
        self.assertIn(b'Email is already registered', response.data)

    def test_signup_admin_privileges(self):
        """Test that registering with username 'admin' or admin email grants admin status."""
        response = self.register_user('admin2', 'admin@another.com', 'adminpass', 'adminpass')
        user = User.query.filter_by(username='admin2').first()
        self.assertTrue(user.is_admin)

        self.logout_user()
        response = self.register_user('randomadmin', 'admin@example.com', 'adminpass', 'adminpass')
        user = User.query.filter_by(username='randomadmin').first()
        self.assertTrue(user.is_admin)

    def test_login_success(self):
        """Test successful login with username or email."""
        # Create standard user
        user = User(username='testuser', email='testuser@example.com')
        user.set_password('mysecret')
        db.session.add(user)
        db.session.commit()

        # Login using username
        response = self.login_user('testuser', 'mysecret')
        self.assertIn(b'Welcome back, testuser', response.data)

        # Logout
        self.logout_user()

        # Login using email
        response = self.login_user('testuser@example.com', 'mysecret')
        self.assertIn(b'Welcome back, testuser', response.data)

    def test_login_validation_failures(self):
        """Test login failures with invalid inputs."""
        # Non-existent user
        response = self.login_user('ghost', 'pass')
        self.assertIn(b'Invalid username/email or password', response.data)

        # Incorrect password
        user = User(username='user1', email='u1@example.com')
        user.set_password('pass1')
        db.session.add(user)
        db.session.commit()
        
        response = self.login_user('user1', 'wrongpass')
        self.assertIn(b'Invalid username/email or password', response.data)

        # Empty fields
        response = self.login_user('', 'pass1')
        self.assertIn(b'All fields are required', response.data)

    def test_logout(self):
        """Test logout clears session and redirects to landing page."""
        self.register_user('user1', 'u1@example.com', 'pass', 'pass')
        response = self.logout_user()
        self.assertIn(b'You have been logged out', response.data)
        
        # Verify page is index page
        self.assertIn(b'Carbon Neutrality', response.data)

    # 2. Page & Routing Tests
    def test_index_page_redirect_for_logged_in_user(self):
        """Test index page redirects to dashboard if user is logged in."""
        # Set up a user and make at least one calculation so dashboard rendering doesn't redirect
        user = User(username='testuser', email='test@example.com')
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
        
        calc = CarbonCalculation(user_id=user.id, transport_emissions=1.0, electricity_emissions=1.0, food_emissions=1.0, waste_emissions=1.0, total_emissions=4.0)
        db.session.add(calc)
        db.session.commit()

        self.login_user('testuser', 'pass')
        
        # Request index page
        response = self.client.get('/', follow_redirects=True)
        # Should redirect to dashboard
        self.assertIn(b'Dashboard', response.data)

    def test_dashboard_redirect_without_calculations(self):
        """Test dashboard redirects to calculator if user has no footprint logs."""
        self.register_user('newuser', 'new@example.com', 'pass', 'pass')
        
        # Access dashboard
        response = self.client.get('/dashboard', follow_redirects=True)
        # Should redirect to calculator
        self.assertIn(b'Please complete your first carbon calculation to initialize your dashboard', response.data)
        self.assertIn(b'Carbon Calculator', response.data)

    @patch('app.generate_sustainability_recommendations')
    def test_dashboard_rendering_with_calculations(self, mock_gen_recs):
        """Test dashboard displays metrics when calculations exist."""
        mock_gen_recs.return_value = {
            "summary": "You are doing okay.",
            "tips": [{"category": "Energy", "tip": "Use LEDs"}],
            "weekly_plan": ["Day 1: Audit home"]
        }
        
        # Register and submit calculation
        self.register_user('user1', 'u1@example.com', 'pass', 'pass')
        
        self.client.post('/calculator', data={
            'car_miles': '1000',
            'fuel_type': 'gasoline',
            'transit_miles': '50',
            'flight_hours': '10',
            'electricity_kwh': '200',
            'solar_panels': 'no',
            'diet': 'mixed',
            'recycle_pct': '50'
        }, follow_redirects=True)

        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)
        self.assertIn(b'You are doing okay', response.data)
        self.assertIn(b'Green Points', response.data)
        self.assertIn(b'Eco Novice', response.data)

    def test_calculator_rendering_and_submission(self):
        """Test calculator page submission and footprint computation logic."""
        self.register_user('user1', 'u1@example.com', 'pass', 'pass')
        
        # GET calculator
        response = self.client.get('/calculator')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Carbon Calculator', response.data)

        # POST calculator with custom values
        # Fuel factors: gasoline=0.00041, hybrid=0.00022, electric=0.00010
        # Car emissions = 1000 * 0.00041 = 0.41
        # Transit emissions = 100 * 0.00014 = 0.014
        # Flight emissions = 4 * 0.25 = 1.00
        # Transport total = 1.424
        
        # Electricity emissions = 200 kWh * 12 * 0.0007 = 1.68
        # Since solar panels = yes -> 1.68 * 0.2 = 0.336
        
        # Diet emissions: vegetarian = 2.0
        
        # Waste emissions: Base 0.5. Recycle pct = 80%.
        # Waste = 0.5 * (1.0 - (80/100)*0.6) = 0.5 * (1.0 - 0.48) = 0.5 * 0.52 = 0.26
        
        # Total emissions = 1.424 + 0.336 + 2.0 + 0.26 = 4.02 metric tons
        with patch('app.generate_sustainability_recommendations') as mock_recs:
            mock_recs.return_value = {
                "summary": "Summary text",
                "tips": [{"category": "Energy", "tip": "Tip"}],
                "weekly_plan": ["Day 1"]
            }
            
            response = self.client.post('/calculator', data={
                'car_miles': '1000',
                'fuel_type': 'gasoline',
                'transit_miles': '100',
                'flight_hours': '4',
                'electricity_kwh': '200',
                'solar_panels': 'yes',
                'diet': 'vegetarian',
                'recycle_pct': '80'
            }, follow_redirects=True)
            
            self.assertIn(b'Footprint successfully calculated', response.data)
            
            # Verify calculation record in DB
            user = User.query.filter_by(username='user1').first()
            calc = CarbonCalculation.query.filter_by(user_id=user.id).first()
            self.assertIsNotNone(calc)
            self.assertAlmostEqual(calc.transport_emissions, 1.424, places=3)
            self.assertAlmostEqual(calc.electricity_emissions, 0.336, places=3)
            self.assertAlmostEqual(calc.food_emissions, 2.0, places=3)
            self.assertAlmostEqual(calc.waste_emissions, 0.260, places=3)
            self.assertAlmostEqual(calc.total_emissions, 4.02, places=3)
            
            # Verify XP rewards: standard 100 points
            self.assertEqual(user.green_points, 100)
            self.assertEqual(user.current_level, 1)

    @patch('app.generate_sustainability_recommendations')
    def test_calculator_reduction_bonus(self, mock_recs):
        """Test that user receives a 150 points bonus if they reduce emissions."""
        mock_recs.return_value = {
            "summary": "Summary",
            "tips": [],
            "weekly_plan": []
        }
        self.register_user('user1', 'u1@example.com', 'pass', 'pass')

        # First calculation (high emissions)
        self.client.post('/calculator', data={
            'car_miles': '5000',
            'electricity_kwh': '1000',
            'diet': 'heavy_meat',
            'recycle_pct': '0'
        })
        
        user = User.query.filter_by(username='user1').first()
        self.assertEqual(user.green_points, 100)

        # Second calculation (lower emissions)
        response = self.client.post('/calculator', data={
            'car_miles': '500',
            'electricity_kwh': '100',
            'diet': 'vegan',
            'recycle_pct': '100'
        }, follow_redirects=True)

        self.assertIn(b'reduced your carbon emissions and earned a 150 Green Points bonus', response.data)
        # Total points should be 100 (first) + 100 (second) + 150 (bonus) = 350
        self.assertEqual(user.green_points, 350)

    def test_reports_page_rendering_and_redirects(self):
        """Test reports page renders correctly or redirects based on calculation existence."""
        self.register_user('user1', 'u1@example.com', 'pass', 'pass')
        user = User.query.filter_by(username='user1').first()

        # No calculations -> redirect
        response = self.client.get('/reports', follow_redirects=True)
        self.assertIn(b'Please calculate your carbon footprint first to view reports', response.data)

        # Create calculations
        c1 = CarbonCalculation(user_id=user.id, transport_emissions=1.0, electricity_emissions=1.0, food_emissions=1.0, waste_emissions=1.0, total_emissions=4.0)
        c2 = CarbonCalculation(user_id=user.id, transport_emissions=0.5, electricity_emissions=0.5, food_emissions=0.5, waste_emissions=0.5, total_emissions=2.0)
        db.session.add_all([c1, c2])
        db.session.commit()

        response = self.client.get('/reports')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Analytics & Reports', response.data)
        self.assertIn(b'decreasing', response.data) # 4.0 -> 2.0 is decreasing
        self.assertIn(b'50.0%', response.data)     # reduction is 50%

    def test_leaderboard_page(self):
        """Test leaderboard displays ranked users by carbon reduction percentage."""
        self.register_user('u1', 'u1@example.com', 'pass', 'pass')
        user1 = User.query.filter_by(username='u1').first()
        # Reduction: 8.0 -> 4.0 = 50% reduction
        c1_1 = CarbonCalculation(user_id=user1.id, transport_emissions=2.0, electricity_emissions=2.0, food_emissions=2.0, waste_emissions=2.0, total_emissions=8.0, calculated_at=datetime.utcnow() - timedelta(days=2))
        c1_2 = CarbonCalculation(user_id=user1.id, transport_emissions=1.0, electricity_emissions=1.0, food_emissions=1.0, waste_emissions=1.0, total_emissions=4.0, calculated_at=datetime.utcnow())
        db.session.add_all([c1_1, c1_2])
        user1.green_points = 200
        
        self.logout_user()
        self.register_user('u2', 'u2@example.com', 'pass', 'pass')
        user2 = User.query.filter_by(username='u2').first()
        # Reduction: 8.0 -> 2.0 = 75% reduction
        c2_1 = CarbonCalculation(user_id=user2.id, transport_emissions=2.0, electricity_emissions=2.0, food_emissions=2.0, waste_emissions=2.0, total_emissions=8.0, calculated_at=datetime.utcnow() - timedelta(days=2))
        c2_2 = CarbonCalculation(user_id=user2.id, transport_emissions=0.5, electricity_emissions=0.5, food_emissions=0.5, waste_emissions=0.5, total_emissions=2.0, calculated_at=datetime.utcnow())
        db.session.add_all([c2_1, c2_2])
        user2.green_points = 300
        db.session.commit()

        # Login and access leaderboard
        self.login_user('u1', 'pass')
        response = self.client.get('/leaderboard')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Global Carbon Reducers', response.data)
        
        # Verify rank ordering: u2 (75% reduction) should come before u1 (50% reduction)
        data_str = response.data.decode('utf-8')
        u2_idx = data_str.find('u2')
        u1_idx = data_str.find('u1')
        self.assertTrue(u2_idx < u1_idx)

    def test_profile_page_updates_and_reset(self):
        """Test profile page rendering, update requests, and reset operations."""
        self.register_user('user1', 'u1@example.com', 'pass', 'pass')
        user = User.query.filter_by(username='user1').first()

        # GET profile
        response = self.client.get('/profile')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Account Settings', response.data)

        # POST update username & email
        response = self.client.post('/profile', data={
            'username': 'updatedname',
            'email': 'updated@example.com',
            'avatar_index': '2'
        }, follow_redirects=True)
        self.assertIn(b'Profile updated successfully', response.data)
        self.assertEqual(user.username, 'updatedname')
        self.assertEqual(user.email, 'updated@example.com')
        self.assertEqual(user.avatar_index, 2)

        # POST duplicate username validation check
        User.query.filter_by(username='updatedname').first()
        other_user = User(username='other', email='other@example.com')
        other_user.set_password('pass')
        db.session.add(other_user)
        db.session.commit()

        response = self.client.post('/profile', data={
            'username': 'other',
            'email': 'updated@example.com'
        }, follow_redirects=True)
        self.assertIn(b'Username is already in use by another user', response.data)

        # POST reset history action
        # Seed calculations to delete
        c1 = CarbonCalculation(user_id=user.id, transport_emissions=1.0, electricity_emissions=1.0, food_emissions=1.0, waste_emissions=1.0, total_emissions=4.0)
        db.session.add(c1)
        user.green_points = 500
        user.current_level = 2
        db.session.commit()

        response = self.client.post('/profile', data={
            'action': 'reset_data'
        }, follow_redirects=True)

        self.assertIn(b'Your account carbon history and points have been completely reset', response.data)
        self.assertEqual(user.green_points, 0)
        self.assertEqual(user.current_level, 1)
        self.assertEqual(CarbonCalculation.query.filter_by(user_id=user.id).count(), 0)

    def test_admin_console_access_and_metrics(self):
        """Test admin console access authorization and correct calculation of platform metrics."""
        # Register a standard user
        self.register_user('standard', 'std@example.com', 'pass', 'pass')
        
        # Attempt standard user access -> Denied
        response = self.client.get('/admin', follow_redirects=True)
        self.assertIn(b'Access denied. Admin credentials required', response.data)

        # Logout standard user
        self.logout_user()

        # Login admin user
        self.login_user(self.admin_username, self.admin_password)

        # Seed some database records to verify metrics calculation in admin panel
        c1 = CarbonCalculation(user_id=1, transport_emissions=2.0, electricity_emissions=2.0, food_emissions=2.0, waste_emissions=2.0, total_emissions=8.0)
        c2 = CarbonCalculation(user_id=1, transport_emissions=1.0, electricity_emissions=1.0, food_emissions=1.0, waste_emissions=1.0, total_emissions=4.0)
        db.session.add_all([c1, c2])
        db.session.commit()

        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Platform Administrator Console', response.data)
        # Verify metrics exist (total users, average footprint)
        self.assertIn(b'6.0', response.data) # average footprint calculation is (8+4)/2 = 6.0

    # 3. API Route Tests
    def test_api_complete_challenge(self):
        """Test complete-challenge JSON endpoint behavior, validation, and points allocation."""
        self.register_user('user1', 'u1@example.com', 'pass', 'pass')
        user = User.query.filter_by(username='user1').first()

        # Try invalid challenge
        response = self.client.post('/api/complete-challenge', json={
            'challenge_id': 'invalid_id'
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()['success'])

        # Complete challenge successfully
        points_before = user.green_points
        challenge_points = CHALLENGES['no_meat_day']['points']
        
        response = self.client.post('/api/complete-challenge', json={
            'challenge_id': 'no_meat_day'
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(user.green_points, points_before + challenge_points)
        self.assertEqual(data['points'], user.green_points)

        # Repeat same challenge on same day -> Should be rejected
        response = self.client.post('/api/complete-challenge', json={
            'challenge_id': 'no_meat_day'
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()['success'])
        self.assertIn('already completed today', response.get_json()['message'])

    def test_api_emissions_history(self):
        """Test emissions-history JSON endpoint returns user's calculation history."""
        self.register_user('user1', 'u1@example.com', 'pass', 'pass')
        user = User.query.filter_by(username='user1').first()

        # Seed calculations
        dt1 = datetime.utcnow() - timedelta(days=2)
        dt2 = datetime.utcnow()
        c1 = CarbonCalculation(user_id=user.id, transport_emissions=1.0, electricity_emissions=1.1, food_emissions=1.2, waste_emissions=1.3, total_emissions=4.6, calculated_at=dt1)
        c2 = CarbonCalculation(user_id=user.id, transport_emissions=2.0, electricity_emissions=2.1, food_emissions=2.2, waste_emissions=2.3, total_emissions=8.6, calculated_at=dt2)
        db.session.add_all([c1, c2])
        db.session.commit()

        response = self.client.get('/api/emissions-history')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['total'], 4.6)
        self.assertEqual(data[1]['total'], 8.6)
        self.assertEqual(data[0]['date'], dt1.strftime('%Y-%b-%d'))

if __name__ == '__main__':
    unittest.main()
