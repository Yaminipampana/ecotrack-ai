document.addEventListener('DOMContentLoaded', () => {
    // Theme Switcher Logic
    const themeToggleBtn = document.getElementById('theme-toggle');
    const themeIcon = themeToggleBtn ? themeToggleBtn.querySelector('i') : null;
    
    // Check local storage or system preference
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'light' || (!savedTheme && !systemPrefersDark)) {
        document.documentElement.setAttribute('data-theme', 'light');
        if (themeIcon) {
            themeIcon.className = 'fa-solid fa-moon';
        }
    } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        if (themeIcon) {
            themeIcon.className = 'fa-solid fa-sun';
        }
    }
    
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            let newTheme = 'dark';
            
            if (currentTheme === 'dark') {
                newTheme = 'light';
                themeIcon.className = 'fa-solid fa-moon';
            } else {
                themeIcon.className = 'fa-solid fa-sun';
            }
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }

    // Mobile Navigation Toggle
    const mobileToggle = document.getElementById('mobile-toggle');
    const navLinks = document.getElementById('nav-links');
    
    if (mobileToggle && navLinks) {
        mobileToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            // Change menu icon
            const icon = mobileToggle.querySelector('i');
            if (navLinks.classList.contains('active')) {
                icon.className = 'fa-solid fa-xmark';
            } else {
                icon.className = 'fa-solid fa-bars';
            }
        });
    }

    // Auto-dismiss Flash Messages
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(msg => {
        // Set timeout to start fade-out after 4 seconds
        setTimeout(() => {
            msg.classList.add('fade-out');
            // Remove from DOM after fade-out transition completes
            msg.addEventListener('animationend', (e) => {
                if (e.animationName === 'fadeOut') {
                    msg.remove();
                }
            });
        }, 4000);
        
        // Manual close click
        msg.addEventListener('click', () => {
            msg.classList.add('fade-out');
        });
    });

    // AI Tab Switching on Dashboard
    const aiTabs = document.querySelectorAll('.ai-tab');
    const aiPanes = document.querySelectorAll('.ai-content-pane');
    
    if (aiTabs.length > 0 && aiPanes.length > 0) {
        aiTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.getAttribute('data-target');
                
                // Toggle tabs active state
                aiTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                // Toggle content panes active state
                aiPanes.forEach(pane => {
                    if (pane.id === target) {
                        pane.classList.add('active');
                    } else {
                        pane.classList.remove('active');
                    }
                });
            });
        });
    }

    // Daily Challenges AJAX completion
    const challengeItems = document.querySelectorAll('.challenge-item');
    challengeItems.forEach(item => {
        const checkBtn = item.querySelector('.challenge-check-btn');
        if (!checkBtn) return;
        
        checkBtn.addEventListener('click', async () => {
            // If already completed, do nothing
            if (item.classList.contains('completed')) return;
            
            const challengeId = item.getAttribute('data-id');
            
            try {
                const response = await fetch('/api/complete-challenge', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ challenge_id: challengeId })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    // Visual updates
                    item.classList.add('completed');
                    
                    // Show a points animation in check button
                    checkBtn.innerHTML = '<i class="fa-solid fa-check"></i>';
                    
                    // Show custom toast notification
                    showToast(data.message, 'success');
                    
                    // Update user level and points UI
                    updateXPProgress(data.points, data.level);
                } else {
                    showToast(data.message || 'Failed to complete challenge.', 'error');
                }
            } catch (err) {
                console.error('Challenge completion error:', err);
                showToast('A network error occurred. Please try again.', 'error');
            }
        });
    });

    // Helper to dynamically show toasts
    function showToast(message, type) {
        let container = document.querySelector('.flash-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'flash-container';
            document.body.appendChild(container);
        }
        
        const toast = document.createElement('div');
        toast.className = `flash-message ${type}`;
        
        let iconClass = 'fa-circle-info';
        if (type === 'success') iconClass = 'fa-circle-check';
        if (type === 'error') iconClass = 'fa-circle-exclamation';
        if (type === 'warning') iconClass = 'fa-triangle-exclamation';
        
        toast.innerHTML = `<i class="fa-solid ${iconClass}"></i><span>${message}</span>`;
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('fade-out');
            toast.addEventListener('animationend', () => toast.remove());
        }, 4000);
    }

    // Helper to update XP bar and Level indicators
    function updateXPProgress(totalPoints, level) {
        // Update level text
        const levelValElements = document.querySelectorAll('.level-circle .val, .user-nav-badge span');
        levelValElements.forEach(el => {
            el.innerText = level;
        });
        
        // Update points text
        const pointsElements = document.querySelectorAll('.metric-mini-card.points-card .metric-mini-val');
        pointsElements.forEach(el => {
            el.innerText = totalPoints;
        });
        
        // Calculate progress percentage inside level
        // Level equation: Level = 1 + floor(Points / 500)
        // Remainder points = totalPoints % 500
        const remainder = totalPoints % 500;
        const pct = (remainder / 500) * 100;
        
        // Update progress bar
        const fillBar = document.querySelector('.xp-progress-fill');
        if (fillBar) {
            fillBar.style.width = `${pct}%`;
        }
        
        // Update text descriptor
        const progressMetaText = document.querySelector('.xp-progress-meta span:first-child');
        if (progressMetaText) {
            progressMetaText.innerText = `${remainder} / 500 XP`;
        }
    }
});
