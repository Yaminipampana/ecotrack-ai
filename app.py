import os
from functools import wraps
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from models import db, User, CarbonCalculation, CompletedChallenge, AiRecommendation
from gemini_helper import generate_sustainability_recommendations

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ecotrack_ai_secret_key_2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in or sign up to access EcoTrack AI.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Admin authentication required.', 'error')
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('Access denied. Admin credentials required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Before request hook
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)

# Challenge constants
CHALLENGES = {
    "no_meat_day": {"title": "Plant-Powered Day", "desc": "Eat a fully vegetarian or vegan diet today.", "points": 50, "icon": "carrot"},
    "public_transit": {"title": "Eco-Transit Commute", "desc": "Use public transit, bike, or walk instead of a personal car.", "points": 50, "icon": "bus"},
    "unplug_idle": {"title": "Vampire Power Hunt", "desc": "Unplug all idle electronic devices, chargers, and power strips.", "points": 50, "icon": "plug"},
    "compost_waste": {"title": "Zero Organic Waste", "desc": "Compost your kitchen scraps and food waste today.", "points": 50, "icon": "dumpster-fire"},
    "cold_wash": {"title": "Cold Water Wash", "desc": "Wash your laundry in cold water and air-dry them.", "points": 50, "icon": "wind"}
}

@app.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if g.user:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('signup.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')
            
        if User.query.filter_by(username=username).first():
            flash('Username is already taken.', 'error')
            return render_template('signup.html')
            
        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'error')
            return render_template('signup.html')
            
        # Create User
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        # Default Admin assignment for testing
        if username.lower() == 'admin' or email.lower().startswith('admin@'):
            new_user.is_admin = True
            
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        flash('Account created successfully! Welcome to EcoTrack AI.', 'success')
        return redirect(url_for('calculator'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email').strip()
        password = request.form.get('password')
        
        if not username_or_email or not password:
            flash('All fields are required.', 'error')
            return render_template('login.html')
            
        # Check by username or email
        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email.lower())).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username/email or password.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # If user hasn't calculated carbon footprint, redirect them to the calculator
    if not g.user.calculations:
        flash('Welcome! Please complete your first carbon calculation to initialize your dashboard.', 'info')
        return redirect(url_for('calculator'))
        
    # Get latest calculation and AI recommendations
    latest_calc = CarbonCalculation.query.filter_by(user_id=g.user.id).order_by(CarbonCalculation.calculated_at.desc()).first()
    latest_rec = AiRecommendation.query.filter_by(user_id=g.user.id, calculation_id=latest_calc.id).first()
    
    # Render fallback recommendations if missing
    recommendations = None
    if latest_rec:
        try:
            recommendations = {
                "summary": latest_rec.summary,
                "tips": json.loads(latest_rec.tips_json),
                "weekly_plan": json.loads(latest_rec.weekly_plan_json)
            }
        except Exception as e:
            print(f"Error parsing recommendations from DB: {e}")
            
    # Get completed challenges for today
    today = date.today()
    completed_today_objs = CompletedChallenge.query.filter_by(user_id=g.user.id, completed_at=today).all()
    completed_ids = [c.challenge_id for c in completed_today_objs]
    
    # Build challenges payload
    daily_challenges = []
    for cid, info in CHALLENGES.items():
        daily_challenges.append({
            "id": cid,
            "title": info["title"],
            "desc": info["desc"],
            "points": info["points"],
            "icon": info["icon"],
            "completed": cid in completed_ids
        })
        
    # Calculate carbon saving compared to standard average (say global average is 4.0 metric tons)
    co2_saved = max(0.0, 4.0 - latest_calc.total_emissions)
    
    # Gather badges
    badges = g.user.get_badges()
    
    return render_template('dashboard.html', 
                           calc=latest_calc, 
                           recommendations=recommendations, 
                           challenges=daily_challenges, 
                           co2_saved=co2_saved,
                           badges=badges)

@app.route('/calculator', methods=['GET', 'POST'])
@login_required
def calculator():
    if request.method == 'POST':
        try:
            # Inputs gathering
            # 1. Transportation
            car_miles = float(request.form.get('car_miles', 0))
            fuel_type = request.form.get('fuel_type', 'gasoline')
            transit_miles = float(request.form.get('transit_miles', 0))
            flight_hours = float(request.form.get('flight_hours', 0))
            
            # 2. Electricity
            electricity_kwh = float(request.form.get('electricity_kwh', 0))
            solar_panels = request.form.get('solar_panels') == 'yes'
            
            # 3. Food
            diet = request.form.get('diet', 'mixed')
            
            # 4. Waste
            recycle_pct = float(request.form.get('recycle_pct', 0))
            
            # Carbon calculations logic
            # Car factor: Gasoline=0.00041, Hybrid=0.00022, Electric=0.00010
            fuel_factors = {'gasoline': 0.00041, 'hybrid': 0.00022, 'electric': 0.00010}
            car_factor = fuel_factors.get(fuel_type, 0.00041)
            
            transport_emissions = (car_miles * car_factor) + (transit_miles * 0.00014) + (flight_hours * 0.25)
            
            # Electricity: 0.0007 metric tons of CO2 per kWh, multiplied by 12 months.
            # Solar panels give an 80% emissions reduction offset.
            electricity_emissions = electricity_kwh * 12 * 0.0007
            if solar_panels:
                electricity_emissions *= 0.2
                
            # Diet Factor (tons/year): heavy_meat=4.5, mixed=3.0, vegetarian=2.0, vegan=1.5
            diet_factors = {'heavy_meat': 4.5, 'mixed': 3.0, 'vegetarian': 2.0, 'vegan': 1.5}
            food_emissions = diet_factors.get(diet, 3.0)
            
            # Waste Factor (tons/year): Base is 0.5 tons/year. Recycling reduces up to 60% of this emission.
            waste_emissions = 0.5 * (1.0 - (recycle_pct / 100.0) * 0.6)
            
            total_emissions = transport_emissions + electricity_emissions + food_emissions + waste_emissions
            
            # Save Calculation
            new_calc = CarbonCalculation(
                user_id=g.user.id,
                transport_emissions=round(transport_emissions, 3),
                electricity_emissions=round(electricity_emissions, 3),
                food_emissions=round(food_emissions, 3),
                waste_emissions=round(waste_emissions, 3),
                total_emissions=round(total_emissions, 3)
            )
            
            db.session.add(new_calc)
            
            # Gamification Logic: Award Points
            points_gained = 100 # Standard points for completing a calculation
            
            # Check if user has previous calculations to check for reduction
            prev_calc = CarbonCalculation.query.filter_by(user_id=g.user.id).order_by(CarbonCalculation.calculated_at.desc()).first()
            if prev_calc and new_calc.total_emissions < prev_calc.total_emissions:
                points_gained += 150 # Bonus for reducing emissions!
                flash('Awesome! You reduced your carbon emissions and earned a 150 Green Points bonus!', 'success')
                
            g.user.add_points(points_gained)
            
            db.session.commit()
            
            # Trigger Gemini API recommendation (saving it to DB)
            recs = generate_sustainability_recommendations(
                new_calc.transport_emissions,
                new_calc.electricity_emissions,
                new_calc.food_emissions,
                new_calc.waste_emissions,
                new_calc.total_emissions
            )
            
            import json
            new_rec = AiRecommendation(
                user_id=g.user.id,
                calculation_id=new_calc.id,
                summary=recs["summary"],
                tips_json=json.dumps(recs["tips"]),
                weekly_plan_json=json.dumps(recs["weekly_plan"])
            )
            
            db.session.add(new_rec)
            db.session.commit()
            
            flash(f'Footprint successfully calculated! Earned {points_gained} Green Points.', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error computing footprint: {str(e)}', 'error')
            return render_template('calculator.html')
            
    return render_template('calculator.html')

@app.route('/reports')
@login_required
def reports():
    if not g.user.calculations:
        flash('Please calculate your carbon footprint first to view reports.', 'info')
        return redirect(url_for('calculator'))
        
    calcs = CarbonCalculation.query.filter_by(user_id=g.user.id).order_by(CarbonCalculation.calculated_at.asc()).all()
    latest_calc = calcs[-1]
    
    # Calculate stats
    avg_emissions = sum(c.total_emissions for c in calcs) / len(calcs)
    max_emissions = max(c.total_emissions for c in calcs)
    min_emissions = min(c.total_emissions for c in calcs)
    
    # Calculate savings trend if multiple calculations exist
    trend_direction = "neutral"
    trend_percentage = 0
    if len(calcs) >= 2:
        diff = calcs[-1].total_emissions - calcs[-2].total_emissions
        trend_percentage = round((abs(diff) / calcs[-2].total_emissions) * 100, 1)
        if diff < 0:
            trend_direction = "decreasing"
        elif diff > 0:
            trend_direction = "increasing"
            
    return render_template('reports.html', 
                           calcs=calcs, 
                           latest_calc=latest_calc, 
                           avg=avg_emissions, 
                           max=max_emissions, 
                           min=min_emissions,
                           trend_direction=trend_direction,
                           trend_percentage=trend_percentage)

@app.route('/leaderboard')
@login_required
def leaderboard():
    all_users = User.query.all()
    leaderboard_data = []
    
    for user in all_users:
        if not user.calculations:
            continue
            
        calcs = sorted(user.calculations, key=lambda c: c.calculated_at)
        first_score = calcs[0].total_emissions
        latest_score = calcs[-1].total_emissions
        reduction = user.get_carbon_reduction_percentage()
        
        leaderboard_data.append({
            "username": user.username,
            "avatar_index": user.avatar_index,
            "level": user.current_level,
            "green_points": user.green_points,
            "first_score": first_score,
            "latest_score": latest_score,
            "reduction": reduction
        })
        
    # Sort by reduction percentage desc, then by green points desc
    leaderboard_data.sort(key=lambda x: (x["reduction"], x["green_points"]), reverse=True)
    
    return render_template('leaderboard.html', leaderboard=leaderboard_data)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Check if doing profile reset or standard update
        if request.form.get('action') == 'reset_data':
            # Delete all calculations, recommendations, challenges, reset level & points
            try:
                CarbonCalculation.query.filter_by(user_id=g.user.id).delete()
                CompletedChallenge.query.filter_by(user_id=g.user.id).delete()
                AiRecommendation.query.filter_by(user_id=g.user.id).delete()
                g.user.green_points = 0
                g.user.current_level = 1
                db.session.commit()
                flash('Your account carbon history and points have been completely reset.', 'success')
                return redirect(url_for('calculator'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error resetting data: {str(e)}', 'error')
                return render_template('profile.html')
                
        # Handle profile updates
        username = request.form.get('username').strip()
        email = request.form.get('email').strip().lower()
        avatar_index = request.form.get('avatar_index')
        new_password = request.form.get('new_password')
        
        # User validations
        if not username or not email:
            flash('Username and email cannot be empty.', 'error')
            return render_template('profile.html')
            
        existing_user_name = User.query.filter(User.username == username, User.id != g.user.id).first()
        if existing_user_name:
            flash('Username is already in use by another user.', 'error')
            return render_template('profile.html')
            
        existing_user_email = User.query.filter(User.email == email, User.id != g.user.id).first()
        if existing_user_email:
            flash('Email is already registered to another user.', 'error')
            return render_template('profile.html')
            
        try:
            g.user.username = username
            g.user.email = email
            if avatar_index is not None:
                g.user.avatar_index = int(avatar_index)
                
            if new_password:
                g.user.set_password(new_password)
                
            db.session.commit()
            flash('Profile updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
            
    return render_template('profile.html')

@app.route('/admin')
@admin_required
def admin():
    # Platform metrics
    total_users = User.query.count()
    calculations_count = CarbonCalculation.query.count()
    challenges_count = CompletedChallenge.query.count()
    
    # Averages
    all_calcs = CarbonCalculation.query.all()
    avg_footprint = 0.0
    if all_calcs:
        avg_footprint = sum(c.total_emissions for c in all_calcs) / len(all_calcs)
        
    # Total Green Points
    total_points = db.session.query(db.func.sum(User.green_points)).scalar() or 0
    
    # List of users
    users = User.query.order_by(User.green_points.desc()).all()
    
    return render_template('admin.html',
                           total_users=total_users,
                           calc_count=calculations_count,
                           challenge_count=challenges_count,
                           avg_footprint=avg_footprint,
                           total_points=total_points,
                           users=users)

@app.route('/api/complete-challenge', methods=['POST'])
@login_required
def complete_challenge():
    data = request.json or {}
    challenge_id = data.get('challenge_id')
    
    if not challenge_id or challenge_id not in CHALLENGES:
        return jsonify({"success": False, "message": "Invalid challenge ID."}), 400
        
    today = date.today()
    existing = CompletedChallenge.query.filter_by(
        user_id=g.user.id,
        challenge_id=challenge_id,
        completed_at=today
    ).first()
    
    if existing:
        return jsonify({"success": False, "message": "Challenge already completed today."}), 400
        
    try:
        new_comp = CompletedChallenge(user_id=g.user.id, challenge_id=challenge_id, completed_at=today)
        db.session.add(new_comp)
        
        points = CHALLENGES[challenge_id]["points"]
        g.user.add_points(points)
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": f"Challenge completed! +{points} Green Points.", 
            "points": g.user.green_points, 
            "level": g.user.current_level
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@app.route('/api/emissions-history')
@login_required
def emissions_history():
    calcs = CarbonCalculation.query.filter_by(user_id=g.user.id).order_by(CarbonCalculation.calculated_at.asc()).all()
    history = []
    for c in calcs:
        history.append({
            "date": c.calculated_at.strftime('%Y-%b-%d'),
            "transport": c.transport_emissions,
            "electricity": c.electricity_emissions,
            "food": c.food_emissions,
            "waste": c.waste_emissions,
            "total": c.total_emissions
        })
    return jsonify(history)

import json

# Database Table Creation inside app context
with app.app_context():
    db.create_all()
    # Create default admin user if it doesn't exist
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin = User(username='admin', email='admin@ecotrack.ai', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Default admin user created: admin / admin123")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
