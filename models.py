from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    green_points = db.Column(db.Integer, default=0)
    current_level = db.Column(db.Integer, default=1)
    avatar_index = db.Column(db.Integer, default=0)
    
    # Relationships
    calculations = db.relationship('CarbonCalculation', backref='user', lazy=True, cascade="all, delete-orphan")
    challenges = db.relationship('CompletedChallenge', backref='user', lazy=True, cascade="all, delete-orphan")
    recommendations = db.relationship('AiRecommendation', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def add_points(self, points):
        self.green_points += points
        # Level equation: Level = 1 + floor(Points / 500)
        self.current_level = 1 + (self.green_points // 500)
        
    def get_badges(self):
        badges = []
        # Badge 1: Eco Novice (Completed first calculation)
        if len(self.calculations) > 0:
            badges.append({
                "id": "eco_novice",
                "title": "Eco Novice",
                "description": "Completed your first carbon footprint calculation.",
                "icon": "leaf"
            })
            
        # Badge 2: Carbon Reducer (Second calculation emissions < first calculation)
        if len(self.calculations) >= 2:
            sorted_calcs = sorted(self.calculations, key=lambda c: c.calculated_at)
            if sorted_calcs[-1].total_emissions < sorted_calcs[-2].total_emissions:
                badges.append({
                    "id": "carbon_reducer",
                    "title": "Carbon Reducer",
                    "description": "Reduced your carbon emissions in your latest calculation.",
                    "icon": "arrow-down"
                })
                
        # Badge 3: Challenge Champion (Completed at least 5 challenges)
        if len(self.challenges) >= 5:
            badges.append({
                "id": "challenge_champion",
                "title": "Challenge Champion",
                "description": "Completed 5 or more eco challenges.",
                "icon": "trophy"
            })
            
        # Badge 4: Solar Pioneer (Check if energy has solar panel - we can check calculations)
        has_solar = False
        for calc in self.calculations:
            # We will store notes or calculations. If any calculations have solar (we can check if electricity is below 1.0 or if they marked it)
            # Actually, let's look at calculations or check if they've ever logged solar. We can save a flag or check database logs.
            pass
            
        # Let's check user level for specific badges
        if self.current_level >= 3:
            badges.append({
                "id": "green_guardian",
                "title": "Green Guardian",
                "description": "Reached Level 3 in sustainability achievements.",
                "icon": "shield-halved"
            })
            
        if self.is_admin:
            badges.append({
                "id": "green_admin",
                "title": "Green Admin",
                "description": "EcoTrack platform administrator.",
                "icon": "crown"
            })
            
        return badges

    def get_carbon_reduction_percentage(self):
        """
        Calculates the carbon footprint reduction percentage between the user's
        very first calculation and their latest calculation.
        """
        calcs = sorted(self.calculations, key=lambda c: c.calculated_at)
        if len(calcs) < 2:
            return 0.0
        first_val = calcs[0].total_emissions
        latest_val = calcs[-1].total_emissions
        if first_val <= 0:
            return 0.0
        reduction = ((first_val - latest_val) / first_val) * 100
        return round(reduction, 1)


class CarbonCalculation(db.Model):
    __tablename__ = 'carbon_calculations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    transport_emissions = db.Column(db.Float, nullable=False)      # tCO2e/yr
    electricity_emissions = db.Column(db.Float, nullable=False)    # tCO2e/yr
    food_emissions = db.Column(db.Float, nullable=False)           # tCO2e/yr
    waste_emissions = db.Column(db.Float, nullable=False)          # tCO2e/yr
    total_emissions = db.Column(db.Float, nullable=False)          # tCO2e/yr
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Optional raw values if needed, but the emissions aggregates are most important
    recommendations = db.relationship('AiRecommendation', backref='calculation', lazy=True, cascade="all, delete-orphan")


class CompletedChallenge(db.Model):
    __tablename__ = 'completed_challenges'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    challenge_id = db.Column(db.String(50), nullable=False)
    completed_at = db.Column(db.Date, default=date.today)


class AiRecommendation(db.Model):
    __tablename__ = 'ai_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    calculation_id = db.Column(db.Integer, db.ForeignKey('carbon_calculations.id', ondelete='CASCADE'), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    tips_json = db.Column(db.Text, nullable=False)                 # JSON array of tips
    weekly_plan_json = db.Column(db.Text, nullable=False)           # JSON array/object of weekly recommendations
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
