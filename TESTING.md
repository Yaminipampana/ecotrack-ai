# EcoTrack AI Testing Guide

This document outlines the testing strategy, test cases (both automated and manual), execution procedures, and coverage analysis for the **EcoTrack AI** platform.

---

## 1. Automated Test Suite

EcoTrack AI features a comprehensive automated testing suite utilizing Python's built-in `unittest` framework. The tests cover:
- **Unit Tests**: Verifying individual models, helper routines, password cryptography, gamification progression, and rule-based recommendation fallback algorithms.
- **Integration Tests**: Verifying view routing, authentication session management, calculator calculations cascades, point allocation, and admin authorization metrics.

### Test Structure

```
tests/
├── test_models.py          # Unit tests for User, CarbonCalculation, etc.
├── test_gemini_helper.py   # Unit tests for text cleaning and fallback recommendations
└── test_routes.py          # Integration tests for auth, dashboards, and API endpoints
```

### Automated Test Cases List

The automated test suite runs **33 test cases** checking critical logic:

| Test File | Test Case Name | Description |
| :--- | :--- | :--- |
| `test_models.py` | `test_user_password_hashing` | Verifies secure password hashing and verification methods. |
| | `test_user_add_points_and_leveling` | Validates point progression and automatic user leveling threshold triggers. |
| | `test_user_get_badges` | Asserts badge awards logic under correct milestones (*Eco Novice*, *Carbon Reducer*, etc.). |
| | `test_get_carbon_reduction_percentage` | Tests percentage calculations of historical footprint metrics. |
| | `test_database_cascades` | Ensures cascade deletion removes user records and child foreign tables cleanly. |
| `test_gemini_helper.py` | `test_clean_json_markdown` | Verifies cleaning of raw Markdown strings from LLM JSON responses. |
| | `test_generate_local_fallback` | Validates fallback recommendations logic if the Gemini API is offline. |
| | `test_generate_recommendations_success` | Tests successful API mocks returning valid recommendations structure. |
| | `test_generate_recommendations_network_error` | Verifies graceful fallback recovery during API network issues. |
| `test_routes.py` | `test_signup_success` | Tests signup registration redirects and session persistence. |
| | `test_signup_validation_failures` | Tests duplicate user validation, password mismatches, and empty inputs. |
| | `test_signup_admin_privileges` | Validates automatic elevation of admin accounts during registration. |
| | `test_login_success` | Tests logins with either username or registered email. |
| | `test_login_validation_failures` | Asserts error flashes for invalid credentials or empty payloads. |
| | `test_logout` | Verifies logout clears cookies and redirects to landing page. |
| | `test_index_redirect_logged_in` | Verifies active session redirects from landing page directly to dashboard. |
| | `test_dashboard_no_calculations` | Asserts redirection to calculator for first-time users lacking logs. |
| | `test_dashboard_with_calculations` | Verifies dashboard renders custom charts and active badges. |
| | `test_calculator_rendering` | Tests calculator page wizard rendering and input forms. |
| | `test_calculator_submission` | Verifies emissions calculation formulas and database persistence. |
| | `test_calculator_reduction_bonus` | Tests the 150 Green Points bonus awarded upon reducing emissions. |
| | `test_reports_rendering` | Asserts reports analytics graphs and percent comparison values. |
| | `test_leaderboard_page` | Validates user ranking order based on percentage emissions reduced. |
| | `test_profile_updates` | Tests avatar selections and profile username/email updates. |
| | `test_profile_reset_data` | Verifies the reset actions delete history logs and revert level stats. |
| | `test_admin_console_access` | Asserts authorization checks restrict admin console access from standard users. |
| | `test_admin_console_metrics` | Verifies calculations of average platform footprint and active metrics. |
| | `test_api_complete_challenge` | Tests API challenge completion, daily limits, and JSON responses. |
| | `test_api_emissions_history` | Tests endpoint output format for Chart.js integrations. |

---

## 2. Running Automated Tests Locally

To run the automated tests, ensure you have configured your environment.

### Run All Tests

From the project root directory, run:
```bash
python -m unittest discover -s tests
```

### Run Specific Test Modules

- **To run model unit tests**:
  ```bash
  python -m unittest tests/test_models.py
  ```
- **To run helper unit tests**:
  ```bash
  python -m unittest tests/test_gemini_helper.py
  ```
- **To run route integration tests**:
  ```bash
  python -m unittest tests/test_routes.py
  ```

---

## 3. Manual Testing Checklist

For verifying visual elements, animations, page transitions, and interactive features (e.g. downloads), perform the following manual test scenarios:

### Theme Switching & Design
1. **Scenario**: Switch Theme.
   - **Steps**: Click the sun/moon icon in the upper-right corner of the navbar on any page.
   - **Expectation**: Seamless transition between Deep Forest Dark Mode and Fresh Mint Light Mode. Chart colors, glass card backdrops, and gradient blobs should update appropriately.

### Multi-Step Calculator Wizard
2. **Scenario**: Real-time Estimate Calculation.
   - **Steps**: Go to the `/calculator` route. Enter values in Step 1 (Transit) and Step 2 (Energy).
   - **Expectation**: The "Estimated Carbon Footprint" box at the bottom should update dynamically in real-time as inputs change.
3. **Scenario**: Navigation Controls.
   - **Steps**: Fill fields and click **Next**; click **Previous** to review inputs.
   - **Expectation**: Navigation works smoothly, progress indicators active states move, and validation blocks going to the next step if inputs are invalid.

### PDF & CSV Exporting
4. **Scenario**: High-Fidelity PDF download.
   - **Steps**: Go to the `/reports` route. Click the **Download PDF Audit** button.
   - **Expectation**: An interactive PDF containing the full dashboard data and reports layout is generated client-side and downloaded immediately.
5. **Scenario**: CSV Log Exports.
   - **Steps**: Go to `/reports`. Click **Export CSV Data**.
   - **Expectation**: A `.csv` file formatted with column indices (`Date`, `Transit`, `Energy`, `Diet`, `Waste`, `Total`) is downloaded.

### Gamification & Interaction
6. **Scenario**: Check-off Daily Challenges.
   - **Steps**: Go to `/dashboard`. Click the checkmark circle next to any challenge in the sidebar.
   - **Expectation**: The circle fills with a green checkmark, a success toast popup appears notifying of point gains, and the XP progress bar and navbar level indicators update instantly without page reloads.

---

## 4. Test Results Summary

During the last validation, the full test suite ran successfully:

```
Ran 33 tests in 7.281s

OK
```

All integration points (including the sqlite3 in-memory engine and mock API contexts) behaved exactly as expected.
