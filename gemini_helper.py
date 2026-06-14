import os
import json
import requests
import re
from dotenv import load_dotenv

# Load local environment variables from .env file
load_dotenv()

def clean_obfuscated_text(text):
    if not isinstance(text, str):
        return text
    
    # We only clean if colons make up a substantial part of the string (e.g. > 15%)
    # or if we have at least 5 colons and their density is high.
    if text.count(':') > max(3, len(text) * 0.15):
        # Extract Day X: prefix if present
        day_match = re.match(r'^(Day \d+:)\s*(.*)$', text, re.IGNORECASE)
        if day_match:
            prefix = day_match.group(1)
            rest = day_match.group(2)
            cleaned_rest = re.sub(r':(.)', r'\1', rest)
            return f"{prefix} {cleaned_rest}".strip()
        else:
            return re.sub(r':(.)', r'\1', text)
    return text

def generate_sustainability_recommendations(transport, electricity, food, waste, total):
    """
    Generates personalized carbon reduction suggestions, weekly recommendations,
    and environmental impact summaries using Gemini API (with local rule-based fallback).
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    
    prompt = f"""
    The user has completed their carbon footprint calculator on EcoTrack AI. 
    Here are their annual emissions in metric tons of CO2 equivalent per year (tCO2e/yr):
    - Transportation: {transport:.2f} tCO2e/yr
    - Electricity/Energy: {electricity:.2f} tCO2e/yr
    - Food Habits: {food:.2f} tCO2e/yr
    - Waste & Recycling: {waste:.2f} tCO2e/yr
    - Total Footprint Score: {total:.2f} tCO2e/yr
 
    The average carbon footprint for an individual globally is about 4.0 tCO2e/yr, while in high-emissions countries it can exceed 15.0 tCO2e/yr.
 
    Analyze their footprint and generate:
    1. A concise environmental impact summary (2-3 sentences) reflecting on how their footprint compares and highlighting their primary source of emissions.
    2. Exactly 3 highly personalized, actionable sustainability tips targeted at their highest emission categories.
    3. A weekly 7-day green plan (one actionable step per day, from Day 1 to Day 7) to guide them.
 
    You must return a raw JSON object matching the following structure:
    {{
      "summary": "Your environmental impact summary here.",
      "tips": [
        {{"category": "Transportation", "tip": "Personalized transit tip here."}},
        {{"category": "Energy", "tip": "Personalized energy conservation tip here."}},
        {{"category": "Food/Waste", "tip": "Personalized food/waste tip here."}}
      ],
      "weekly_plan": [
        "Day 1: Actionable task for Monday",
        "Day 2: Actionable task for Tuesday",
        "Day 3: Actionable task for Wednesday",
        "Day 4: Actionable task for Thursday",
        "Day 5: Actionable task for Friday",
        "Day 6: Actionable task for Saturday",
        "Day 7: Actionable task for Sunday"
      ]
    }}
    Do not wrap the response in markdown blocks (like ```json). Return ONLY the raw JSON string.
    """
    
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                text_content = data['candidates'][0]['content']['parts'][0]['text'].strip()
                
                # Robust cleaning of markdown code wrappers if present
                if text_content.startswith("```"):
                    lines = text_content.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    text_content = "\n".join(lines).strip()
                
                recommendations = json.loads(text_content)
                
                # Validate schema keys
                required_keys = ["summary", "tips", "weekly_plan"]
                if all(key in recommendations for key in required_keys):
                    # Validate tips structure
                    if isinstance(recommendations["tips"], list) and len(recommendations["tips"]) > 0:
                        # Clean obfuscated text fields
                        recommendations["summary"] = clean_obfuscated_text(recommendations["summary"])
                        for tip in recommendations["tips"]:
                            if isinstance(tip, dict):
                                tip["category"] = clean_obfuscated_text(tip.get("category", ""))
                                tip["tip"] = clean_obfuscated_text(tip.get("tip", ""))
                        if isinstance(recommendations["weekly_plan"], list):
                            recommendations["weekly_plan"] = [
                                clean_obfuscated_text(day) for day in recommendations["weekly_plan"]
                            ]
                        return recommendations
                
                print("Gemini response is missing required keys or structured differently. Falling back.")
        except Exception as e:
            print(f"Error calling Gemini API: {e}. Falling back to local model.")
            
    # Local rule-based fallback system if API key is not present or failed
    return get_local_recommendations(transport, electricity, food, waste, total)

def get_local_recommendations(transport, electricity, food, waste, total):
    """
    Generates structured recommendations locally based on emission characteristics.
    """
    # Find the highest emissions source
    sources = [
        ("Transportation", transport),
        ("Home Energy", electricity),
        ("Dietary Choices", food),
        ("Waste & Recycling", waste)
    ]
    highest_name, highest_val = max(sources, key=lambda x: x[1])
    
    # 1. Summary
    if total < 4.0:
        status_text = "excellent, well below the global average of 4.0 tCO2e/yr"
    elif total < 10.0:
        status_text = "moderate, but higher than the sustainable global target of 2.0 tCO2e/yr"
    else:
        status_text = "high, significantly above the global average. Urgent reductions are recommended"
        
    summary = (
        f"Your annual carbon footprint is {total:.2f} tCO2e/yr, which is {status_text}. "
        f"Your primary source of emissions is {highest_name} at {highest_val:.2f} tCO2e/yr. "
        f"Focusing on this sector will yield the most significant carbon reductions."
    )
    
    # 2. Tips based on categories
    tips = []
    
    # Transit Tip
    if transport > 3.0:
        tips.append({
            "category": "Transportation",
            "tip": "Transition to public transit or carpooling for your daily commute. Consider switching to an electric or hybrid vehicle, which can reduce your transit footprint by up to 75%."
        })
    else:
        tips.append({
            "category": "Transportation",
            "tip": "Combine errands into single trips and keep tires properly inflated to optimize fuel economy. For distances under 2 miles, try walking or cycling."
        })
        
    # Energy Tip
    if electricity > 2.0:
        tips.append({
            "category": "Energy",
            "tip": "Install a smart thermostat to optimize heating and cooling schedules. Unplug 'vampire' electronics when not in use, and consider upgrading old appliances to ENERGY STAR certified models."
        })
    else:
        tips.append({
            "category": "Energy",
            "tip": "Replace standard light bulbs with highly efficient LEDs, wash laundry in cold water, and air-dry clothing when possible to save electricity."
        })
        
    # Food/Waste Tip
    if food > waste:
        tips.append({
            "category": "Food & Diet",
            "tip": "Incorporate more plant-based meals into your diet. Reducing red meat consumption and participating in 'Meatless Mondays' can lower your food emissions by 20-30%."
        })
    else:
        tips.append({
            "category": "Waste & Recycling",
            "tip": "Initiate home composting for organic waste to reduce methane production in landfills. Minimize single-use plastics by carrying reusable bags and bottles."
        })
        
    # 3. Weekly plan based on highest category
    if highest_name == "Transportation":
        weekly_plan = [
            "Day 1: Leave the car at home. Walk, bike, or use transit for at least one trip.",
            "Day 2: Map out public transit routes for your regular commute to check options.",
            "Day 3: Check and adjust your car's tire pressure to optimize fuel efficiency.",
            "Day 4: Plan your weekly shopping list to consolidate all errands into a single trip.",
            "Day 5: Research hybrid/EV options or carpooling groups in your neighborhood.",
            "Day 6: Clean out any heavy items in your car's trunk to reduce vehicle weight.",
            "Day 7: Commit to a low-emission weekend—explore nearby parks by foot or bike."
        ]
    elif highest_name == "Home Energy":
        weekly_plan = [
            "Day 1: Audit your home for drafts around windows and doors; seal any air leaks.",
            "Day 2: Switch off and unplug all non-essential electronics before sleeping.",
            "Day 3: Set your water heater temperature to a highly efficient 120°F (49°C).",
            "Day 4: Lower your home heating thermostat by 2 degrees or raise the AC by 2 degrees.",
            "Day 5: Wash a full load of laundry on the cold water setting and hang dry.",
            "Day 6: Replace at least 3 high-use incandescent bulbs with LED alternatives.",
            "Day 7: Explore local green power utility options to see if you can switch to solar/wind energy."
        ]
    elif highest_name == "Dietary Choices":
        weekly_plan = [
            "Day 1: Go 100% plant-based for all meals today (try a new vegan recipe!).",
            "Day 2: Audit your refrigerator to identify items nearing expiration and cook them first.",
            "Day 3: Buy groceries locally or choose organic, locally-grown produce at the market.",
            "Day 4: Swap out dairy milk for oat, almond, or soy milk in your coffee or cereal.",
            "Day 5: Avoid buying individually packaged foods; opt for bulk items instead.",
            "Day 6: Prepare a meal using only leftover ingredients to eliminate food waste.",
            "Day 7: Pack your lunch in reusable containers rather than using plastic wrap or foil."
        ]
    else: # Waste & Recycling
        weekly_plan = [
            "Day 1: Set up dedicated recycling bins for paper, plastic, and glass in your kitchen.",
            "Day 2: Refuse single-use plastics today—carry a reusable water bottle and canvas bag.",
            "Day 3: Research local recycling guidelines to understand what plastics are accepted.",
            "Day 4: Start an organic kitchen waste collector box to begin composting.",
            "Day 5: Cancel paper billing statements and switch to digital alternatives.",
            "Day 6: Repair or repurpose an old item instead of purchasing a replacement.",
            "Day 7: Shop package-free at a local market or bulk store to avoid packaging waste."
        ]
        
    return {
        "summary": summary,
        "tips": tips,
        "weekly_plan": weekly_plan
    }
