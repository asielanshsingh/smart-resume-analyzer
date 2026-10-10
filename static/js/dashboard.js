document.addEventListener('DOMContentLoaded', () => {
    let breakdownChartInstance = null;
    let currentResumeId = null;
    let rolesCatalog = [];

    const skeletonEl = document.getElementById('dashboard-skeleton');
    const emptyStateEl = document.getElementById('dashboard-empty-state');
    const contentEl = document.getElementById('dashboard-content');
    const errorBanner = document.getElementById('dashboard-error-banner');
    const errorCodeEl = document.getElementById('dash-error-code');
    const errorMessageEl = document.getElementById('dash-error-message');
    const retryBtn = document.getElementById('dash-retry-btn');
    const roleSwitchSelect = document.getElementById('role-switch-select');
    const roleSwitchSpinner = document.getElementById('role-switch-spinner');
    const printBtn = document.getElementById('print-btn');

    // Helper: Safely create DOM element with text content (XSS protection)
    function createEl(tag, className = '', text = '') {
        const el = document.createElement(tag);
        if (className) el.className = className;
        if (text !== undefined && text !== null) el.textContent = String(text);
        return el;
    }

    // Helper: get a display label from a skill that may be a string or an object
    function skillLabel(item) {
        if (item === null || item === undefined) return '';
        if (typeof item === 'string') return item;
        return String(item.skill ?? item.name ?? item.keyword ?? item.term ?? item.label ?? '');
    }

    // Helper: where a matched skill was found, if the API says so
    function skillSections(item) {
        if (!item || typeof item !== 'object') return '';
        const found = item.sections ?? item.found_in ?? item.locations ?? [];
        return Array.isArray(found) ? found.join(', ') : String(found || '');
    }

    // Helper: turn a breakdown entry (number or {points, max}) into a 0-100 value
    function categoryPercent(entry) {
        if (typeof entry === 'number') return entry;
        if (!entry || typeof entry !== 'object') return 0;
        const earned = Number(entry.points ?? entry.earned ?? entry.score ?? 0);
        const max = Number(entry.max_score ?? entry.max ?? entry.max_points ?? entry.maximum ?? 0);
        return max > 0 ? Math.round((earned / max) * 100) : Math.round(earned);
    }

    function showError(code, message) {
        if (errorCodeEl) errorCodeEl.textContent = `Error [${code}]`;
        if (errorMessageEl) errorMessageEl.textContent = message;
        if (errorBanner) errorBanner.classList.remove('hidden');
        if (skeletonEl) skeletonEl.classList.add('hidden');
    }

    function clearError() {
        if (errorBanner) errorBanner.classList.add('hidden');
    }

    if (retryBtn) {
        retryBtn.addEventListener('click', () => {
            clearError();
            loadDashboardData();
        });
    }

    if (printBtn) {
        printBtn.addEventListener('click', () => {
            window.print();
        });
    }

    // Load available roles into switcher dropdown
    async function loadRolesCatalog() {
        if (!roleSwitchSelect) return;
        try {
            const resp = await fetch('/api/roles');
            if (!resp.ok) return;
            const data = await resp.json();
            rolesCatalog = data.roles || [];

            roleSwitchSelect.innerHTML = '';
            const defaultOpt = createEl('option', '', 'Select target role...');
            defaultOpt.disabled = true;
            roleSwitchSelect.appendChild(defaultOpt);

            rolesCatalog.forEach(role => {
                const opt = createEl('option', '', `${role.title} (${role.category})`);
                opt.value = role.id;
                roleSwitchSelect.appendChild(opt);
            });
        } catch (err) {
            console.error('Failed to load roles catalog:', err);
        }
    }

    // Role switcher change handler
    if (roleSwitchSelect) {
        roleSwitchSelect.addEventListener('change', async (e) => {
            const newRoleId = e.target.value;
            if (!newRoleId || !currentResumeId) return;

            if (roleSwitchSpinner) roleSwitchSpinner.classList.remove('hidden');
            roleSwitchSelect.disabled = true;
            clearError();

            try {
                const resp = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        resume_id: currentResumeId,
                        role_id: newRoleId
                    })
                });

                const result = await resp.json();

                if (!resp.ok) {
                    const errCode = result.error?.code || 'ROLE_SWITCH_FAILED';
                    const errMessage = result.error?.message || 'Could not re-analyze for selected role.';
                    showError(errCode, errMessage);
                    return;
                }

                const newShareToken = result.share_token || result.analysis_id;
                sessionStorage.setItem('active_share_token', newShareToken);

                // Update URL without full page refresh
                history.pushState(null, '', `/result/${encodeURIComponent(newShareToken)}`);

                const fullResp = await fetch(`/api/analysis/${encodeURIComponent(newShareToken)}`);
                if (!fullResp.ok) throw new Error('Could not load the new analysis.');
                const fullData = await fullResp.json();
                currentResumeId = fullData.resume_id;
                renderDashboard(fullData);
            } catch (err) {
                console.error('Error switching role:', err);
                showError('NETWORK_ERROR', 'Failed to reach server when switching roles. Please try again.');
            } finally {
                if (roleSwitchSpinner) roleSwitchSpinner.classList.add('hidden');
                roleSwitchSelect.disabled = false;
            }
        });
    }

    // Main data loader function
    async function loadDashboardData() {
        clearError();
        if (skeletonEl) skeletonEl.classList.remove('hidden');
        if (contentEl) contentEl.classList.add('hidden');
        if (emptyStateEl) emptyStateEl.classList.add('hidden');

        // Extract identifier from URL path (/result/<identifier>) or query params or sessionStorage
        const pathSegments = window.location.pathname.split('/').filter(Boolean);
        let identifier = null;

        if (pathSegments.length >= 2 && pathSegments[0] === 'result') {
            identifier = pathSegments[1];
        } else {
            const urlParams = new URLSearchParams(window.location.search);
            identifier = urlParams.get('id') || urlParams.get('analysis_id') || urlParams.get('share_token');
        }

        if (!identifier) {
            identifier = sessionStorage.getItem('active_share_token') || sessionStorage.getItem('active_analysis_id');
        }

        if (!identifier) {
            if (skeletonEl) skeletonEl.classList.add('hidden');
            if (emptyStateEl) emptyStateEl.classList.remove('hidden');
            return;
        }

        try {
            const resp = await fetch(`/api/analysis/${encodeURIComponent(identifier)}`);
            if (resp.status === 404) {
                if (skeletonEl) skeletonEl.classList.add('hidden');
                if (emptyStateEl) emptyStateEl.classList.remove('hidden');
                return;
            }

            if (!resp.ok) {
                const errorData = await resp.json();
                throw new Error(errorData.error?.message || 'Failed to fetch analysis details.');
            }

            const data = await resp.json();
            currentResumeId = data.resume_id;

            renderDashboard(data);
        } catch (err) {
            console.error('Error loading dashboard data:', err);
            showError('FETCH_ERROR', err.message || 'An error occurred while loading the evaluation report.');
        } finally {
            if (skeletonEl) skeletonEl.classList.add('hidden');
        }
    }

    // Render full dashboard from API data
    function renderDashboard(data) {
        if (contentEl) contentEl.classList.remove('hidden');

        // 1. Role Badge & Filename Header
        const roleBadge = document.getElementById('role-badge');
        if (roleBadge) {
            const matchedRoleObj = rolesCatalog.find(r => r.id === data.role);
            roleBadge.textContent = matchedRoleObj ? matchedRoleObj.title : (data.role || 'Target Role').replace(/_/g, ' ').toUpperCase();
        }

        const filenameText = document.getElementById('filename-text');
        if (filenameText) {
            filenameText.textContent = data.filename || 'Uploaded Resume';
        }

        if (roleSwitchSelect && data.role) {
            roleSwitchSelect.value = data.role;
        }

        // 2. Score Gauges (Overall & ATS) - bands & labels from API config
        const resScore = Math.round(data.resume_score || 0);
        const resBand = data.resume_score_band || { label: 'Evaluated', stroke_color: '#2563eb', badge_bg: 'bg-blue-50', badge_text: 'text-blue-700', badge_border: 'border-blue-200' };

        const overallScoreText = document.getElementById('overall-score-text');
        const overallCircle = document.getElementById('overall-score-circle');
        const overallStatus = document.getElementById('overall-score-status');
        const overallSvg = document.getElementById('overall-score-svg');

        if (overallScoreText) overallScoreText.textContent = resScore;
        if (overallCircle) {
            overallCircle.setAttribute('stroke-dasharray', `${resScore}, 100`);
            overallCircle.setAttribute('stroke', resBand.stroke_color);
        }
        if (overallStatus) {
            overallStatus.textContent = resBand.label;
            overallStatus.className = `inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold ${resBand.badge_bg} ${resBand.badge_text} border ${resBand.badge_border}`;
        }
        if (overallSvg) {
            overallSvg.setAttribute('aria-label', `Overall Resume Score: ${resScore} out of 100. Category: ${resBand.label}`);
        }

        const atsScore = Math.round(data.ats_score || 0);
        const atsBand = data.ats_score_band || { label: 'ATS Evaluated', stroke_color: '#4f46e5', badge_bg: 'bg-indigo-50', badge_text: 'text-indigo-700', badge_border: 'border-indigo-200' };

        const atsScoreText = document.getElementById('ats-score-text');
        const atsCircle = document.getElementById('ats-score-circle');
        const atsStatus = document.getElementById('ats-score-status');
        const atsSvg = document.getElementById('ats-score-svg');

        if (atsScoreText) atsScoreText.textContent = `${atsScore}%`;
        if (atsCircle) {
            atsCircle.setAttribute('stroke-dasharray', `${atsScore}, 100`);
            atsCircle.setAttribute('stroke', atsBand.stroke_color);
        }
        if (atsStatus) {
            atsStatus.textContent = atsBand.label;
            atsStatus.className = `inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold ${atsBand.badge_bg} ${atsBand.badge_text} border ${atsBand.badge_border}`;
        }
        if (atsSvg) {
            atsSvg.setAttribute('aria-label', `ATS Compatibility Score: ${atsScore}%. Status: ${atsBand.label}`);
        }

        // 3. Matched and Missing Skills (DOM node building for XSS safety)
        const matchedContainer = document.getElementById('matched-skills-container');
        const matchedCountEl = document.getElementById('matched-count');
        const matchedSkills = (data.matched_missing?.matched_skills) || (data.matched_skills) || [];

        if (matchedCountEl) matchedCountEl.textContent = matchedSkills.length;
        if (matchedContainer) {
            matchedContainer.innerHTML = '';
            if (matchedSkills.length === 0) {
                matchedContainer.appendChild(createEl('p', 'text-xs text-slate-400 italic', 'No matched target skills detected.'));
            } else {
                matchedSkills.forEach(skill => {
                    const chip = createEl('span', 'inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 shadow-2xs', skillLabel(skill));
                    const where = skillSections(skill);
                    if (where) chip.title = `Found in: ${where}`;
                    matchedContainer.appendChild(chip);
                });
            }
        }

        const missingContainer = document.getElementById('missing-skills-container');
        const missingCountEl = document.getElementById('missing-count');
        const missingCritical = (data.matched_missing?.missing_critical_skills) || (data.missing_critical_skills) || [];
        const missingNiceToHave = (data.matched_missing?.missing_nice_to_have_skills) || (data.missing_nice_to_have_skills) || [];
        const totalMissing = missingCritical.length + missingNiceToHave.length;

        if (missingCountEl) missingCountEl.textContent = totalMissing;
        if (missingContainer) {
            missingContainer.innerHTML = '';
            if (totalMissing === 0) {
                missingContainer.appendChild(createEl('p', 'text-xs text-emerald-600 font-medium', 'All target role skills present!'));
            } else {
                // Highlight critical missing skills prominently
                missingCritical.forEach(skill => {
                    const chip = createEl('span', 'inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-800 border border-rose-300 shadow-2xs', `CRITICAL: ${skillLabel(skill)}`);
                    missingContainer.appendChild(chip);
                });

                missingNiceToHave.forEach(skill => {
                    const chip = createEl('span', 'inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200 shadow-2xs', skill);
                    missingContainer.appendChild(chip);
                });
            }
        }

        // 4. Render Breakdown Chart & Expandable Category Score Details dynamically
        renderChart(data.breakdown || {});
        renderBreakdownDetails(data.breakdown || {});

        // 5. Render ATS Compatibility Category Breakdown & Criteria Deductions
        const atsDet = data.ats_details || data.matched_missing?.ats_details || {};
        renderAtsBreakdown(atsDet);

        // 6. Render Contacts & Sections
        renderContactsAndSections(data);

        // 7. Render Prioritized Improvement Suggestions
        renderSuggestions(data.suggestions || []);
    }



    // Dynamic Chart.js category breakdown rendering
    function renderChart(breakdownObj) {
        const ctx = document.getElementById('breakdownChart')?.getContext('2d');
        if (!ctx) return;

        if (breakdownChartInstance) {
            breakdownChartInstance.destroy();
        }

        const rawKeys = Object.keys(breakdownObj);
        if (rawKeys.length === 0) return;

        const labels = rawKeys.map(k => k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()));
        const values = rawKeys.map(k => categoryPercent(breakdownObj[k]));

        const chartColors = [
            'rgba(37, 99, 235, 0.85)',
            'rgba(79, 70, 229, 0.85)',
            'rgba(16, 185, 129, 0.85)',
            'rgba(245, 158, 11, 0.85)',
            'rgba(139, 92, 246, 0.85)',
            'rgba(236, 72, 153, 0.85)'
        ];

        breakdownChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Score out of 100',
                    data: values,
                    backgroundColor: chartColors.slice(0, values.length),
                    borderRadius: 6,
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
                            label: (context) => {
                                const entry = breakdownObj[rawKeys[context.dataIndex]];
                                if (entry && typeof entry === 'object' && entry.max_score) {
                                    return ` ${entry.score} / ${entry.max_score} points (${context.parsed.x}%)`;
                                }
                                return ` ${context.parsed.x}%`;
                            }
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

    // Render accessible expandable details list for breakdown categories (XSS-safe textContent only)
    function renderBreakdownDetails(breakdownObj) {
        const container = document.getElementById('breakdown-details-container');
        if (!container) return;

        container.innerHTML = '';

        const rawKeys = Object.keys(breakdownObj);
        if (rawKeys.length === 0) {
            container.appendChild(createEl('p', 'text-xs text-slate-400 italic', 'No category breakdown details available.'));
            return;
        }

        rawKeys.forEach(catKey => {
            const entry = breakdownObj[catKey];
            const titleText = catKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

            let scoreVal = 0;
            let maxVal = 0;
            let reasonsList = [];

            if (typeof entry === 'number') {
                scoreVal = entry;
                maxVal = 100;
            } else if (entry && typeof entry === 'object') {
                scoreVal = Number(entry.score ?? entry.points ?? 0);
                maxVal = Number(entry.max_score ?? entry.max ?? 100);
                reasonsList = Array.isArray(entry.reasons) ? entry.reasons : [];
            }

            const detailsEl = document.createElement('details');
            detailsEl.className = 'group rounded-lg border border-slate-200 bg-white overflow-hidden text-xs';

            const summaryEl = document.createElement('summary');
            summaryEl.className = 'px-3 py-2 font-semibold text-slate-800 bg-slate-50 hover:bg-slate-100 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-between transition-colors';

            const leftSpan = createEl('span', 'font-bold text-slate-900', titleText);
            const rightSpan = createEl('span', 'font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200', `${scoreVal} / ${maxVal} pts`);

            summaryEl.appendChild(leftSpan);
            summaryEl.appendChild(rightSpan);
            detailsEl.appendChild(summaryEl);

            const contentDiv = createEl('div', 'p-3 space-y-1.5 bg-white text-slate-700 border-t border-slate-100');

            if (reasonsList.length > 0) {
                const listEl = createEl('ul', 'space-y-1 pl-4 list-disc text-slate-600');
                reasonsList.forEach(r => {
                    const li = createEl('li', 'leading-normal', r);
                    listEl.appendChild(li);
                });
                contentDiv.appendChild(listEl);
            } else {
                const noReasons = createEl('p', 'text-slate-400 italic', 'No specific notes for this category.');
                contentDiv.appendChild(noReasons);
            }

            detailsEl.appendChild(contentDiv);
            container.appendChild(detailsEl);
        });
    }

    // Render accessible expandable details list for ATS categories and deductions (XSS-safe textContent only)
    function renderAtsBreakdown(atsDetails) {
        const container = document.getElementById('ats-breakdown-container');
        if (!container) return;

        container.innerHTML = '';

        const catScores = (atsDetails && atsDetails.category_scores) || {};
        const deductions = (atsDetails && atsDetails.deductions) || [];

        const categories = [
            { key: 'keyword_match', title: 'Keyword Match', max: 40, kw: ['keyword', 'match rate'] },
            { key: 'standard_sections', title: 'Standard Section Headings', max: 20, kw: ['section'] },
            { key: 'contact_info', title: 'Parseable Contact Info', max: 15, kw: ['email', 'phone', 'contact'] },
            { key: 'text_extraction', title: 'Text Extraction Quality', max: 10, kw: ['text extraction', 'readability'] },
            { key: 'layout_formatting', title: 'Layout & Formatting Risk', max: 10, kw: ['layout', 'formatting'] },
            { key: 'length_suitability', title: 'Length Suitability', max: 5, kw: ['length', 'short', 'words'] }
        ];

        categories.forEach(cat => {
            const earnedPts = Number(catScores[cat.key] ?? cat.max);
            const maxPts = cat.max;

            // Filter deduction messages relevant to this category
            const catDeductions = deductions.filter(d => {
                const lower = d.toLowerCase();
                return cat.kw.some(k => lower.includes(k));
            });

            const detailsEl = document.createElement('details');
            detailsEl.className = 'group rounded-lg border border-slate-200 bg-white overflow-hidden text-xs';

            const summaryEl = document.createElement('summary');
            summaryEl.className = 'px-3 py-2 font-semibold text-slate-800 bg-slate-50 hover:bg-slate-100 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-between transition-colors';

            const leftSpan = createEl('span', 'font-bold text-slate-900', cat.title);
            
            const isFullScore = earnedPts >= maxPts;
            const badgeClass = isFullScore 
                ? 'font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200' 
                : 'font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200';

            const rightSpan = createEl('span', badgeClass, `${earnedPts} / ${maxPts} pts`);

            summaryEl.appendChild(leftSpan);
            summaryEl.appendChild(rightSpan);
            detailsEl.appendChild(summaryEl);

            const contentDiv = createEl('div', 'p-3 space-y-1.5 bg-white text-slate-700 border-t border-slate-100');

            if (catDeductions.length > 0) {
                const listEl = createEl('ul', 'space-y-1 pl-4 list-disc text-rose-700');
                catDeductions.forEach(d => {
                    const li = createEl('li', 'leading-normal font-medium', d);
                    listEl.appendChild(li);
                });
                contentDiv.appendChild(listEl);
            } else {
                const fullPtsNote = createEl('p', 'text-emerald-700 font-medium', 'Full points earned — no ATS deductions for this criterion.');
                contentDiv.appendChild(fullPtsNote);
            }

            detailsEl.appendChild(contentDiv);
            container.appendChild(detailsEl);
        });

        // Any leftover general deductions not captured by specific categories
        const unassignedDeductions = deductions.filter(d => {
            const lower = d.toLowerCase();
            return !categories.some(cat => cat.kw.some(k => lower.includes(k)));
        });

        if (unassignedDeductions.length > 0) {
            const generalCard = document.createElement('details');
            generalCard.className = 'group rounded-lg border border-rose-200 bg-rose-50/50 overflow-hidden text-xs';
            
            const generalSummary = document.createElement('summary');
            generalSummary.className = 'px-3 py-2 font-bold text-rose-900 bg-rose-100 hover:bg-rose-200 cursor-pointer focus:outline-none focus:ring-2 focus:ring-rose-500 flex items-center justify-between';
            
            const leftTitle = createEl('span', '', 'Additional ATS Deductions');
            const rightBadge = createEl('span', 'font-semibold text-rose-800 bg-rose-200 px-2 py-0.5 rounded border border-rose-300', `${unassignedDeductions.length} deduction(s)`);
            generalSummary.appendChild(leftTitle);
            generalSummary.appendChild(rightBadge);
            generalCard.appendChild(generalSummary);

            const genContent = createEl('div', 'p-3 bg-white text-rose-800 border-t border-rose-200');
            const genList = createEl('ul', 'space-y-1 pl-4 list-disc text-rose-700');
            unassignedDeductions.forEach(d => {
                genList.appendChild(createEl('li', 'leading-normal font-medium', d));
            });
            genContent.appendChild(genList);
            generalCard.appendChild(genContent);

            container.appendChild(generalCard);
        }
    }

    // Contacts & Sections DOM rendering
    function renderContactsAndSections(data) {


        const contactsContainer = document.getElementById('contacts-container');
        if (contactsContainer) {
            contactsContainer.innerHTML = '';
            const contacts = data.contacts || {};

            const items = [
                { label: 'Email', values: contacts.emails || [] },
                { label: 'Phone', values: contacts.phones || [] },
                { label: 'LinkedIn', values: contacts.linkedin || [] },
                { label: 'GitHub', values: contacts.github || [] }
            ];

            items.forEach(item => {
                const row = createEl('div', 'flex items-center justify-between py-1 border-b border-slate-100 last:border-0');
                const lbl = createEl('span', 'font-semibold text-slate-500', item.label + ':');
                row.appendChild(lbl);

                if (item.values.length > 0) {
                    const valSpan = createEl('span', 'font-medium text-slate-800 truncate max-w-[200px]', item.values.join(', '));
                    row.appendChild(valSpan);
                } else {
                    const noneSpan = createEl('span', 'text-slate-400 italic', 'Not detected');
                    row.appendChild(noneSpan);
                }
                contactsContainer.appendChild(row);
            });

            // Document Stats Row
            const statsRow = createEl('div', 'pt-2 mt-2 border-t border-slate-200 flex justify-between text-[11px] font-bold text-slate-500 uppercase');
            const pgSpan = createEl('span', '', `Page Count: ${data.page_count || 1}`);
            const wdSpan = createEl('span', '', `Word Count: ${data.word_count || 0}`);
            statsRow.appendChild(pgSpan);
            statsRow.appendChild(wdSpan);
            contactsContainer.appendChild(statsRow);
        }

        const sectionsContainer = document.getElementById('sections-container');
        if (sectionsContainer) {
            sectionsContainer.innerHTML = '';
            const detectedObj = data.detected_sections || {};
            const sectionKeys = Object.keys(detectedObj);

            if (sectionKeys.length === 0) {
                sectionsContainer.appendChild(createEl('p', 'text-xs text-slate-400 italic', 'No explicit sections detected.'));
            } else {
                sectionKeys.forEach(secKey => {
                    const secBadge = createEl('span', 'inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200', secKey.toUpperCase());
                    sectionsContainer.appendChild(secBadge);
                });
            }
        }
    }

    // Suggestions DOM rendering with expandable <details>
    function renderSuggestions(suggestionsList) {
        const container = document.getElementById('suggestions-container');
        if (!container) return;

        container.innerHTML = '';

        if (!suggestionsList || suggestionsList.length === 0) {
            container.appendChild(createEl('p', 'text-xs text-slate-500 italic', 'No specific improvement suggestions generated. Excellent job!'));
            return;
        }

        suggestionsList.forEach(s => {
            const card = createEl('div', 'p-4 rounded-xl border border-slate-200 bg-white hover:bg-slate-50/60 transition-all space-y-2 shadow-2xs');

            const headerRow = createEl('div', 'flex items-center justify-between gap-2');

            const prioUpper = (s.priority || 'Medium').toUpperCase();
            let badgeClass = 'bg-blue-100 text-blue-800 border-blue-200';
            if (prioUpper === 'HIGH') badgeClass = 'bg-rose-100 text-rose-800 border-rose-200 font-bold';
            else if (prioUpper === 'MEDIUM') badgeClass = 'bg-amber-100 text-amber-800 border-amber-200 font-semibold';
            else if (s.id === 'positive_strong_profile') badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-200 font-bold';

            const badge = createEl('span', `px-2 py-0.5 rounded text-[10px] uppercase tracking-wide border ${badgeClass}`, `${prioUpper} PRIORITY`);
            headerRow.appendChild(badge);

            if (s.category) {
                const catSpan = createEl('span', 'text-[11px] font-semibold text-slate-400 uppercase tracking-wider', s.category);
                headerRow.appendChild(catSpan);
            }
            card.appendChild(headerRow);

            const msgEl = createEl('h4', 'text-sm font-bold text-slate-900', s.message || s.title);
            card.appendChild(msgEl);

            if (s.how_to_fix || s.example) {
                const detailsEl = document.createElement('details');
                detailsEl.className = 'group pt-1';

                const summaryEl = createEl('summary', 'text-xs font-semibold text-blue-600 hover:text-blue-800 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 rounded p-0.5 inline-flex items-center space-x-1', 'How to fix this');
                detailsEl.appendChild(summaryEl);

                const fixContainer = createEl('div', 'mt-2 space-y-2 text-xs text-slate-700 bg-slate-50 p-3 rounded-lg border border-slate-200');

                if (s.how_to_fix) {
                    const fixText = createEl('p', 'leading-relaxed', s.how_to_fix);
                    fixContainer.appendChild(fixText);
                }

                if (s.example) {
                    const exBox = createEl('div', 'mt-2 p-2.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-900 font-mono text-[11px]', `Example: ${s.example}`);
                    fixContainer.appendChild(exBox);
                }

                detailsEl.appendChild(fixContainer);
                card.appendChild(detailsEl);
            }

            container.appendChild(card);
        });
    }

    // Initialize Dashboard
    loadRolesCatalog();
    loadDashboardData();
});
