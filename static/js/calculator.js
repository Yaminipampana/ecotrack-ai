document.addEventListener('DOMContentLoaded', () => {
    const wizardForm = document.getElementById('calc-form');
    if (!wizardForm) return;

    const steps = document.querySelectorAll('.wizard-step-pane');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const submitBtn = document.getElementById('submit-btn');
    const progressBar = document.querySelector('.wizard-progress-fill');
    const stepIndicators = document.querySelectorAll('.wizard-step-indicator');
    const loadingOverlay = document.getElementById('loading-overlay');
    
    let currentStep = 0;
    const totalSteps = steps.length;

    // Choice Cards Selection Logic (Radio buttons)
    const choiceCards = document.querySelectorAll('.choice-card');
    choiceCards.forEach(card => {
        card.addEventListener('click', () => {
            const radio = card.querySelector('input[type="radio"]');
            if (radio) {
                // Unselect others in the same group
                const groupName = radio.name;
                document.querySelectorAll(`input[name="${groupName}"]`).forEach(input => {
                    input.closest('.choice-card').classList.remove('selected');
                });
                
                // Select this card
                radio.checked = true;
                card.classList.add('selected');
                
                // Trigger real-time calculation update
                calculateRealtimeProjection();
            }
        });
    });

    // Form inputs monitoring for real-time projection
    const numericInputs = wizardForm.querySelectorAll('input[type="number"], input[type="range"]');
    numericInputs.forEach(input => {
        input.addEventListener('input', calculateRealtimeProjection);
        input.addEventListener('change', calculateRealtimeProjection);
    });
    
    // Checkboxes / Solar panel switch monitoring
    const selectInputs = wizardForm.querySelectorAll('select');
    selectInputs.forEach(input => {
        input.addEventListener('change', calculateRealtimeProjection);
    });

    // Navigation Click Handlers
    nextBtn.addEventListener('click', () => {
        if (validateStep(currentStep)) {
            currentStep++;
            updateWizard();
        }
    });

    prevBtn.addEventListener('click', () => {
        currentStep--;
        updateWizard();
    });

    // Handle form submission and show loading overlay
    wizardForm.addEventListener('submit', (e) => {
        if (!validateStep(currentStep)) {
            e.preventDefault();
            return;
        }
        
        // Show loading overlay
        if (loadingOverlay) {
            loadingOverlay.style.display = 'flex';
            document.body.style.overflow = 'hidden'; // Lock scrolling
        }
    });

    // Validate inputs of the current step
    function validateStep(stepIndex) {
        const activePane = steps[stepIndex];
        const requiredInputs = activePane.querySelectorAll('input[type="number"]');
        let isValid = true;

        requiredInputs.forEach(input => {
            const val = parseFloat(input.value);
            if (isNaN(val) || val < 0) {
                input.classList.add('invalid');
                isValid = false;
                
                // Show a quick warning styling
                input.style.borderColor = 'var(--danger)';
                input.style.boxShadow = '0 0 0 3px var(--danger-glow)';
            } else {
                input.classList.remove('invalid');
                input.style.borderColor = '';
                input.style.boxShadow = '';
            }
        });

        if (!isValid) {
            // Display an alert or toast
            let container = document.querySelector('.flash-container');
            if (!container) {
                container = document.createElement('div');
                container.className = 'flash-container';
                document.body.appendChild(container);
            }
            const toast = document.createElement('div');
            toast.className = 'flash-message error';
            toast.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i><span>Please enter positive numbers for all fields.</span>';
            container.appendChild(toast);
            setTimeout(() => {
                toast.classList.add('fade-out');
                toast.addEventListener('animationend', () => toast.remove());
            }, 3000);
        }

        return isValid;
    }

    // Refresh Wizard View
    function updateWizard() {
        // Hide all steps, show current step
        steps.forEach((pane, idx) => {
            if (idx === currentStep) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });

        // Update progress bar
        const progressPercentage = ((currentStep + 1) / totalSteps) * 100;
        if (progressBar) {
            progressBar.style.width = `${progressPercentage}%`;
        }

        // Update step indicators
        stepIndicators.forEach((ind, idx) => {
            if (idx <= currentStep) {
                ind.classList.add('active');
            } else {
                ind.classList.remove('active');
            }
        });

        // Toggle buttons visibility
        if (currentStep === 0) {
            prevBtn.style.display = 'none';
        } else {
            prevBtn.style.display = 'inline-flex';
        }

        if (currentStep === totalSteps - 1) {
            nextBtn.style.display = 'none';
            submitBtn.style.display = 'inline-flex';
        } else {
            nextBtn.style.display = 'inline-flex';
            submitBtn.style.display = 'none';
        }
    }

    // Realtime projection calculator
    function calculateRealtimeProjection() {
        // Gather inputs
        // 1. Transportation
        const carMiles = parseFloat(document.getElementById('car_miles').value) || 0;
        
        // Find checked fuel type
        const fuelRadio = document.querySelector('input[name="fuel_type"]:checked');
        const fuelType = fuelRadio ? fuelRadio.value : 'gasoline';
        const fuelFactors = {'gasoline': 0.00041, 'hybrid': 0.00022, 'electric': 0.00010};
        const carFactor = fuelFactors[fuelType] || 0.00041;
        
        const transitMiles = parseFloat(document.getElementById('transit_miles').value) || 0;
        const flightHours = parseFloat(document.getElementById('flight_hours').value) || 0;
        
        const transportEmissions = (carMiles * carFactor) + (transitMiles * 0.00014) + (flightHours * 0.25);

        // 2. Electricity
        const electricityKwh = parseFloat(document.getElementById('electricity_kwh').value) || 0;
        const solarPanels = document.getElementById('solar_panels').value === 'yes';
        let electricityEmissions = electricityKwh * 12 * 0.0007;
        if (solarPanels) {
            electricityEmissions *= 0.2;
        }

        // 3. Food
        const dietRadio = document.querySelector('input[name="diet"]:checked');
        const diet = dietRadio ? dietRadio.value : 'mixed';
        const dietFactors = {'heavy_meat': 4.5, 'mixed': 3.0, 'vegetarian': 2.0, 'vegan': 1.5};
        const foodEmissions = dietFactors[diet] || 3.0;

        // 4. Waste
        const recyclePct = parseFloat(document.getElementById('recycle_pct').value) || 0;
        const wasteEmissions = 0.5 * (1.0 - (recyclePct / 100.0) * 0.6);

        // Calculate total
        const total = transportEmissions + electricityEmissions + foodEmissions + wasteEmissions;

        // Render estimate
        const estimateVal = document.getElementById('projected-score');
        if (estimateVal) {
            estimateVal.innerText = `${total.toFixed(2)} tCO2e/yr`;
        }
    }

    // Initialize
    updateWizard();
    calculateRealtimeProjection();
});
