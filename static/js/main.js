document.addEventListener('DOMContentLoaded', () => {
    const roleSelect = document.getElementById('role-select');
    const rolesLoadingIndicator = document.getElementById('roles-loading-indicator');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const dropZonePrompt = document.getElementById('drop-zone-prompt');
    const filePreview = document.getElementById('file-preview');
    const fileNameEl = document.getElementById('file-name');
    const fileSizeEl = document.getElementById('file-size');
    const fileIconEl = document.getElementById('file-icon');
    const removeFileBtn = document.getElementById('remove-file-btn');
    const uploadForm = document.getElementById('upload-form');
    const submitBtn = document.getElementById('submit-btn');
    const loadingOverlay = document.getElementById('loading-overlay');
    const errorBanner = document.getElementById('error-banner');
    const errorCodeEl = document.getElementById('error-code');
    const errorMessageEl = document.getElementById('error-message');
    const dismissErrorBtn = document.getElementById('dismiss-error');

    let selectedFile = null;

    // Fetch Roles from Backend API
    async function loadRoles() {
        if (rolesLoadingIndicator) rolesLoadingIndicator.classList.remove('hidden');
        try {
            const response = await fetch('/api/roles');
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error?.message || 'Failed to fetch roles');
            }
            const data = await response.json();
            populateRolesDropdown(data.roles || []);
        } catch (err) {
            console.error('Error loading roles:', err);
            showError('ROLE_FETCH_ERROR', 'Could not load job roles. Please refresh the page or try again later.');
            roleSelect.innerHTML = '<option value="" disabled selected>Error loading roles</option>';
        } finally {
            if (rolesLoadingIndicator) rolesLoadingIndicator.classList.add('hidden');
        }
    }

    function populateRolesDropdown(roles) {
        roleSelect.innerHTML = '<option value="" disabled selected>Select a target job role...</option>';
        roles.forEach(role => {
            const option = document.createElement('option');
            option.value = role.id;
            option.textContent = `${role.title} (${role.category})`;
            roleSelect.appendChild(option);
        });
    }

    // Helper functions for UI Error Handling
    function showError(code, message) {
        errorCodeEl.textContent = `Error [${code}]:`;
        errorMessageEl.textContent = message;
        errorBanner.classList.remove('hidden');
        errorBanner.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function clearError() {
        errorBanner.classList.add('hidden');
        errorCodeEl.textContent = '';
        errorMessageEl.textContent = '';
    }

    if (dismissErrorBtn) {
        dismissErrorBtn.addEventListener('click', clearError);
    }

    // Drag & Drop handlers
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('drag-over');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            handleFileSelection(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFileSelection(fileInput.files[0]);
        }
    });

    function handleFileSelection(file) {
        clearError();
        const allowedExtensions = ['pdf', 'docx'];
        const ext = file.name.split('.').pop().toLowerCase();
        
        if (!allowedExtensions.includes(ext)) {
            showError('UNSUPPORTED_MEDIA_TYPE', 'Invalid file format. Please upload a PDF (.pdf) or Word document (.docx).');
            resetFileSelection();
            return;
        }

        const maxSizeBytes = 16 * 1024 * 1024; // 16 MB
        if (file.size > maxSizeBytes) {
            showError('PAYLOAD_TOO_LARGE', 'File size exceeds the 16 MB limit. Please select a smaller file.');
            resetFileSelection();
            return;
        }

        selectedFile = file;
        fileNameEl.textContent = file.name;
        fileSizeEl.textContent = formatBytes(file.size);
        fileIconEl.textContent = ext.toUpperCase();
        fileIconEl.className = `w-10 h-10 rounded-lg flex items-center justify-center font-bold text-xs flex-shrink-0 ${
            ext === 'pdf' ? 'bg-rose-100 text-rose-700' : 'bg-blue-100 text-blue-700'
        }`;

        dropZonePrompt.classList.add('hidden');
        filePreview.classList.remove('hidden');
    }

    function resetFileSelection() {
        selectedFile = null;
        fileInput.value = '';
        dropZonePrompt.classList.remove('hidden');
        filePreview.classList.add('hidden');
    }

    removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        resetFileSelection();
    });

    function formatBytes(bytes, decimals = 1) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // Form Submission
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearError();

        const roleValue = roleSelect.value;
        if (!roleValue) {
            showError('BAD_REQUEST', 'Please select a target job role before continuing.');
            return;
        }

        if (!selectedFile) {
            showError('BAD_REQUEST', 'Please choose or drop a resume file to analyze.');
            return;
        }

        // Show Loading Overlay & Disable Submit
        loadingOverlay.classList.remove('hidden');
        submitBtn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('file', selectedFile);

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                const errCode = result.error?.code || 'UPLOAD_FAILED';
                const errMessage = result.error?.message || 'Failed to upload and parse resume.';
                showError(errCode, errMessage);
                return;
            }

            // Store resume_id and navigate to dashboard with role and resume_id
            const resumeId = result.resume_id;
            sessionStorage.setItem('active_resume_id', resumeId);
            window.location.href = `/dashboard?role=${encodeURIComponent(roleValue)}&resume_id=${resumeId}`;

        } catch (err) {
            console.error('Upload error:', err);
            showError('NETWORK_ERROR', 'Network error or server unreachable. Please check your connection and try again.');
        } finally {
            loadingOverlay.classList.add('hidden');
            submitBtn.disabled = false;
        }
    });


    // Initialize Page
    loadRoles();
});
