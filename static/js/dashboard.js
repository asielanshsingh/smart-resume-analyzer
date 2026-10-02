document.addEventListener('DOMContentLoaded', () => {
    let breakdownChartInstance = null;

    async function loadDashboardData() {
        const urlParams = new URLSearchParams(window.location.search);
        const roleParam = urlParams.get('role');
        const filenameParam = urlParams.get('filename');

        try {
            const response = await fetch('/api/placeholder-analysis');
            if (!response.ok) {
                throw new Error('Failed to fetch dashboard data');
            }
            const data = await response.json();

            // Override with query params if available
            if (roleParam) {
                data.role = roleParam.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
            }
            if (filenameParam) {
                data.filename = filenameParam;
            }

            renderDashboard(data);
        } catch (err) {
            console.error('Error loading dashboard:', err);
        }
    }

    function renderDashboard(data) {
        // Set Header Info
        const roleBadge = document.getElementById('role-badge');
        if (roleBadge) roleBadge.textContent = data.role || 'Software Engineer';

        const filenameDisplay = document.getElementById('resume-filename-display');
        if (filenameDisplay && data.filename) {
            filenameDisplay.innerHTML = `Analyzed Document: <span class="font-medium text-slate-700">${escapeHtml(data.filename)}</span>`;
        }

        // Set Scores
        const overallScoreText = document.getElementById('overall-score-text');
        const overallCircle = document.getElementById('overall-score-circle');
        if (overallScoreText) overallScoreText.textContent = data.resume_score;
        if (overallCircle) overallCircle.setAttribute('stroke-dasharray', `${data.resume_score}, 100`);

        const atsScoreText = document.getElementById('ats-score-text');
        const atsCircle = document.getElementById('ats-score-circle');
        if (atsScoreText) atsScoreText.textContent = `${data.ats_score}%`;
        if (atsCircle) atsCircle.setAttribute('stroke-dasharray', `${data.ats_score}, 100`);

        // Render Skill Chips
        const matchedContainer = document.getElementById('matched-skills-container');
        const matchedCount = document.getElementById('matched-count');
        const matchedSkills = data.matched_missing?.matched_skills || [];
        
        if (matchedCount) matchedCount.textContent = matchedSkills.length;
        if (matchedContainer) {
            matchedContainer.innerHTML = matchedSkills.map(skill => `
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 shadow-2xs">
                    <svg class="w-3.5 h-3.5 text-emerald-600 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
                    </svg>
                    ${escapeHtml(skill)}
                </span>
            `).join('') || '<p class="text-xs text-slate-400">No matched skills detected.</p>';
        }

        const missingContainer = document.getElementById('missing-skills-container');
        const missingCount = document.getElementById('missing-count');
        const missingSkills = data.matched_missing?.missing_skills || [];

        if (missingCount) missingCount.textContent = missingSkills.length;
        if (missingContainer) {
            missingContainer.innerHTML = missingSkills.map(skill => `
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200 shadow-2xs">
                    <svg class="w-3.5 h-3.5 text-rose-500 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                    </svg>
                    ${escapeHtml(skill)}
                </span>
            `).join('') || '<p class="text-xs text-slate-400">No missing skills identified.</p>';
        }

        // Render Suggestions List
        const suggestionsContainer = document.getElementById('suggestions-container');
        const suggestions = data.suggestions || [];
        if (suggestionsContainer) {
            suggestionsContainer.innerHTML = suggestions.map(s => {
                const severityClasses = {
                    'High': 'bg-rose-100 text-rose-800 border-rose-200',
                    'Medium': 'bg-amber-100 text-amber-800 border-amber-200',
                    'Low': 'bg-blue-100 text-blue-800 border-blue-200'
                };
                const badgeClass = severityClasses[s.severity] || 'bg-slate-100 text-slate-800 border-slate-200';

                return `
                    <div class="p-4 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-colors flex items-start space-x-3">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border flex-shrink-0 mt-0.5 ${badgeClass}">
                            ${escapeHtml(s.severity)} Impact
                        </span>
                        <div class="flex-grow">
                            <h4 class="text-sm font-bold text-slate-900">${escapeHtml(s.title)}</h4>
                            <p class="text-xs text-slate-600 mt-1">${escapeHtml(s.description)}</p>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // Render Chart.js Breakdown Chart
        renderChart(data.breakdown || {});
    }

    function renderChart(breakdown) {
        const ctx = document.getElementById('breakdownChart')?.getContext('2d');
        if (!ctx) return;

        if (breakdownChartInstance) {
            breakdownChartInstance.destroy();
        }

        const labels = ['Required Skills', 'Preferred Skills', 'Section Structure', 'Formatting & Length'];
        const values = [
            breakdown.required_skills_score || 85,
            breakdown.preferred_skills_score || 70,
            breakdown.section_presence_score || 90,
            breakdown.formatting_length_score || 80
        ];

        breakdownChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Score out of 100',
                    data: values,
                    backgroundColor: [
                        'rgba(37, 99, 235, 0.85)',
                        'rgba(79, 70, 229, 0.85)',
                        'rgba(16, 185, 129, 0.85)',
                        'rgba(245, 158, 11, 0.85)'
                    ],
                    borderRadius: 8,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => ` Score: ${context.parsed.x} / 100`
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: '#f1f5f9' },
                        ticks: { font: { size: 11, family: 'sans-serif' }, color: '#64748b' }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: { size: 11, weight: '600', family: 'sans-serif' }, color: '#334155' }
                    }
                }
            }
        });
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    loadDashboardData();
});
