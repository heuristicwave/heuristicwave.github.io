/**
 * Theme Toggle System
 * Handles light/dark mode switching with localStorage persistence
 * and system preference detection
 */

(function() {
    'use strict';
    
    // Theme constants
    const THEMES = {
        LIGHT: 'light',
        DARK: 'dark'
    };
    
    const STORAGE_KEY = 'heuristic-wave-theme';
    
    // Get DOM elements
    const html = document.documentElement;
    
    /**
     * Get the current theme from localStorage or system preference
     */
    function getCurrentTheme() {
        // Check localStorage first
        const savedTheme = localStorage.getItem(STORAGE_KEY);
        if (savedTheme && Object.values(THEMES).includes(savedTheme)) {
            return savedTheme;
        }
        
        // Fall back to system preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return THEMES.DARK;
        }
        
        return THEMES.LIGHT;
    }
    
    /**
     * Apply theme to the document
     */
    function applyTheme(theme) {
        html.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_KEY, theme);
        
        // Dispatch custom event for other scripts to listen to
        window.dispatchEvent(new CustomEvent('themechange', {
            detail: { theme: theme }
        }));
        
        console.log('Theme applied:', theme);
    }
    
    /**
     * Toggle between light and dark themes
     */
    function toggleTheme() {
        const currentTheme = getCurrentTheme();
        const newTheme = currentTheme === THEMES.LIGHT ? THEMES.DARK : THEMES.LIGHT;
        applyTheme(newTheme);
        return newTheme;
    }
    
    /**
     * Create and inject theme toggle button
     */
    function createThemeToggle() {
        // Check if toggle already exists
        if (document.getElementById('theme-toggle')) {
            return document.getElementById('theme-toggle');
        }
        
        const button = document.createElement('button');
        button.id = 'theme-toggle';
        button.className = 'theme-toggle';
        button.setAttribute('aria-label', 'Toggle dark mode');
        button.setAttribute('title', 'Toggle dark mode');
        
        // SVG icons for light and dark modes
        const lightIcon = `
            <svg class="theme-icon theme-icon--light" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/>
                <line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/>
                <line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
        `;
        
        const darkIcon = `
            <svg class="theme-icon theme-icon--dark" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
        `;
        
        button.innerHTML = lightIcon + darkIcon;
        
        // Add click handler
        button.addEventListener('click', function() {
            const newTheme = toggleTheme();
            updateButtonState(button, newTheme);
        });
        
        // Add to navigation - try multiple locations
        const navRight = document.querySelector('.site-nav-right');
        const nav = document.querySelector('.site-nav');
        const socialLinks = document.querySelector('.social-links');
        
        if (navRight) {
            navRight.appendChild(button);
        } else if (socialLinks) {
            socialLinks.appendChild(button);
        } else if (nav) {
            nav.appendChild(button);
        } else {
            // Fallback: add to body
            document.body.appendChild(button);
            button.style.position = 'fixed';
            button.style.top = '20px';
            button.style.right = '20px';
            button.style.zIndex = '1000';
        }
        
        console.log('Theme toggle button created and added to:', navRight ? 'nav-right' : socialLinks ? 'social-links' : nav ? 'nav' : 'body');
        
        return button;
    }
    
    /**
     * Update button state based on current theme
     */
    function updateButtonState(button, theme) {
        const lightIcon = button.querySelector('.theme-icon--light');
        const darkIcon = button.querySelector('.theme-icon--dark');
        
        if (theme === THEMES.DARK) {
            button.setAttribute('aria-label', 'Switch to light mode');
            button.setAttribute('title', 'Switch to light mode');
            if (lightIcon) lightIcon.style.display = 'block';
            if (darkIcon) darkIcon.style.display = 'none';
        } else {
            button.setAttribute('aria-label', 'Switch to dark mode');
            button.setAttribute('title', 'Switch to dark mode');
            if (lightIcon) lightIcon.style.display = 'none';
            if (darkIcon) darkIcon.style.display = 'block';
        }
    }
    
    /**
     * Listen for system theme changes
     */
    function setupSystemThemeListener() {
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addEventListener('change', function(e) {
                // Only apply system theme if user hasn't manually set a preference
                if (!localStorage.getItem(STORAGE_KEY)) {
                    const theme = e.matches ? THEMES.DARK : THEMES.LIGHT;
                    applyTheme(theme);
                    
                    const button = document.getElementById('theme-toggle');
                    if (button) {
                        updateButtonState(button, theme);
                    }
                }
            });
        }
    }
    
    /**
     * Initialize theme system
     */
    function init() {
        console.log('Initializing theme system...');
        
        // Apply initial theme immediately
        const initialTheme = getCurrentTheme();
        applyTheme(initialTheme);
        
        // Create toggle button when DOM is ready
        function setupButton() {
            const button = createThemeToggle();
            if (button) {
                updateButtonState(button, initialTheme);
            }
        }
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', setupButton);
        } else {
            setupButton();
        }
        
        // Setup system theme listener
        setupSystemThemeListener();
    }
    
    // Expose public API
    window.ThemeToggle = {
        getCurrentTheme: getCurrentTheme,
        applyTheme: applyTheme,
        toggleTheme: toggleTheme,
        THEMES: THEMES
    };
    
    // Initialize immediately
    init();
})();