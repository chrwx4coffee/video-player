document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('videoPlayer');
    const videoWrapper = document.getElementById('videoWrapper');
    const fileInput = document.getElementById('fileInput');
    const fileLoader = document.getElementById('fileLoader');
    const controls = document.getElementById('controls');

    // Control elements
    const playPauseBtn = document.getElementById('playPauseBtn');
    const rewindBtn = document.getElementById('rewindBtn');
    const forwardBtn = document.getElementById('forwardBtn');
    const muteBtn = document.getElementById('muteBtn');
    const volumeSlider = document.getElementById('volumeSlider');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const currentTimeEl = document.getElementById('currentTime');
    const durationEl = document.getElementById('duration');
    const fullscreenBtn = document.getElementById('fullscreenBtn');

    // Zoom control elements
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const resetZoomBtn = document.getElementById('resetZoomBtn');
    const zoomLevelText = document.getElementById('zoomLevelText');
    const zoomHint = document.getElementById('zoomHint');

    let currentZoom = 1;
    let isDragging = false;
    let startX, startY;
    let translateX = 0, translateY = 0;

    // Dosya okuma (Ekle)
    fileInput.addEventListener('change', function (e) {
        const file = e.target.files[0];
        if (file) {
            const fileURL = URL.createObjectURL(file);
            video.src = fileURL;
            fileLoader.classList.add('hidden');
            controls.classList.remove('active');

            // Sıfırlamalar
            currentZoom = 1;
            translateX = 0;
            translateY = 0;
            updateTransform();

            video.load();
            video.play();
            updatePlayIcon();
        }
    });

    // Saniye çevirici
    function formatTime(seconds) {
        if (isNaN(seconds)) return "00:00";
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    video.addEventListener('loadedmetadata', () => {
        durationEl.textContent = formatTime(video.duration);
    });

    video.addEventListener('timeupdate', () => {
        currentTimeEl.textContent = formatTime(video.currentTime);
        const progressPercent = (video.currentTime / video.duration) * 100;
        progressBar.style.width = `${progressPercent}%`;
    });

    // Oynat / Duraklat
    function togglePlay() {
        if (video.paused) {
            video.play();
        } else {
            video.pause();
        }
        updatePlayIcon();
    }

    function updatePlayIcon() {
        const icon = playPauseBtn.querySelector('i');
        if (video.paused) {
            icon.classList.replace('fa-pause', 'fa-play');
        } else {
            icon.classList.replace('fa-play', 'fa-pause');
        }
    }

    playPauseBtn.addEventListener('click', togglePlay);
    videoWrapper.addEventListener('click', (e) => {
        // Kontrol kutusuna veya iç tıklamalara duyarlı yapma işlemi
        if (!wasDragging && e.target === videoWrapper) {
            togglePlay();
        }
    });

    // Sarma İşlemleri (10sn geri, 30sn ileri)
    function rewind() {
        video.currentTime = Math.max(0, video.currentTime - 10);
    }

    function forward() {
        video.currentTime = Math.min(video.duration, video.currentTime + 30);
    }

    rewindBtn.addEventListener('click', rewind);
    forwardBtn.addEventListener('click', forward);

    // İlerleme Çubuğu Scrubbing (Sürükleme) İşlemleri
    let isDraggingProgress = false;
    let wasPlayingBeforeDrag = false;

    function updateProgress(e) {
        const rect = progressContainer.getBoundingClientRect();
        let pos = (e.clientX - rect.left) / rect.width;
        pos = Math.max(0, Math.min(1, pos));
        video.currentTime = pos * video.duration;
        progressBar.style.width = `${pos * 100}%`;
    }

    progressContainer.addEventListener('mousedown', (e) => {
        isDraggingProgress = true;
        wasPlayingBeforeDrag = !video.paused;
        video.pause();
        updateProgress(e);
    });

    window.addEventListener('mousemove', (e) => {
        if (isDraggingProgress) {
            updateProgress(e);
        }
    });

    window.addEventListener('mouseup', () => {
        if (isDraggingProgress) {
            isDraggingProgress = false;
            if (wasPlayingBeforeDrag) video.play();
        }
    });

    // Ses ve Sessiz
    function toggleMute() {
        video.muted = !video.muted;
        if (video.muted) {
            volumeSlider.value = 0;
        } else {
            volumeSlider.value = Math.max(0.1, video.volume);
        }
        updateVolumeIcon();
    }

    function updateVolumeIcon() {
        const icon = muteBtn.querySelector('i');
        icon.className = '';
        if (video.muted || video.volume === 0 || volumeSlider.value == 0) {
            icon.classList.add('fas', 'fa-volume-xmark');
        } else if (volumeSlider.value < 0.5) {
            icon.classList.add('fas', 'fa-volume-low');
        } else {
            icon.classList.add('fas', 'fa-volume-high');
        }
    }

    muteBtn.addEventListener('click', toggleMute);

    volumeSlider.addEventListener('input', (e) => {
        video.volume = e.target.value;
        video.muted = false;
        updateVolumeIcon();
    });

    // Tam Ekran
    fullscreenBtn.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    });

    document.addEventListener('fullscreenchange', () => {
        const icon = fullscreenBtn.querySelector('i');
        if (document.fullscreenElement) {
            icon.classList.replace('fa-expand', 'fa-compress');
        } else {
            icon.classList.replace('fa-compress', 'fa-expand');
        }
    });

    // Yakınlaştırma (Zoom) ve Kaydırma (Pan)
    function updateTransform() {
        video.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentZoom})`;
        zoomLevelText.textContent = `${Math.round(currentZoom * 100)}%`;

        if (currentZoom > 1) {
            zoomHint.classList.add('show');
            setTimeout(() => zoomHint.classList.remove('show'), 2000);
            videoWrapper.style.cursor = 'grab';
        } else {
            zoomHint.classList.remove('show');
            videoWrapper.style.cursor = 'default';
        }
    }

    function changeZoom(delta) {
        let oldZoom = currentZoom;
        currentZoom += delta;
        currentZoom = Math.max(0.5, Math.min(10, currentZoom)); // Min x0.5, Max x10.0

        if (currentZoom !== oldZoom && currentZoom === 1) {
            translateX = 0;
            translateY = 0;
        }
        updateTransform();
    }

    zoomInBtn.addEventListener('click', () => changeZoom(0.2));
    zoomOutBtn.addEventListener('click', () => changeZoom(-0.2));
    resetZoomBtn.addEventListener('click', () => {
        currentZoom = 1;
        translateX = 0;
        translateY = 0;
        updateTransform();
    });

    // Mouse Tekerleği ile Zoom
    videoWrapper.addEventListener('wheel', (e) => {
        e.preventDefault();
        const zoomDelta = e.deltaY < 0 ? 0.1 : -0.1;
        changeZoom(zoomDelta);
    });

    // Sürükleme (Pan) İşlemleri
    let wasDragging = false;

    videoWrapper.addEventListener('mousedown', (e) => {
        if (currentZoom > 1 && e.button === 0) { // Sol tık
            isDragging = true;
            wasDragging = false;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
            videoWrapper.style.cursor = 'grabbing';
            e.preventDefault(); // Metin seçimini engelle
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        wasDragging = true;

        translateX = e.clientX - startX;
        translateY = e.clientY - startY;

        updateTransform();
    });

    window.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            if (currentZoom > 1) {
                videoWrapper.style.cursor = 'grab';
            }
            // Sürükleme sonrası tık almaması için ufak timeout
            setTimeout(() => {
                wasDragging = false;
            }, 50);
        }
    });

    // Klavye Kısayolları (30sn İleri, 10sn Geri vs.)
    document.addEventListener('keydown', (e) => {
        // Eğer input gibi yerlerdeysek, kısayolları ezme
        if (e.target.tagName.toLowerCase() === 'input') return;

        switch (e.code) {
            case 'Space':
            case 'KeyK': // YouTube Play/Pause standardı
                e.preventDefault();
                togglePlay();
                break;
            case 'ArrowRight':
                e.preventDefault();
                forward(); // 30s İleri
                break;
            case 'ArrowLeft':
                e.preventDefault();
                rewind(); // 10s Geri
                break;
            case 'ArrowUp':
                e.preventDefault();
                video.volume = Math.min(1, video.volume + 0.1);
                volumeSlider.value = video.volume;
                video.muted = false;
                updateVolumeIcon();
                break;
            case 'ArrowDown':
                e.preventDefault();
                video.volume = Math.max(0, video.volume - 0.1);
                volumeSlider.value = video.volume;
                updateVolumeIcon();
                break;
            case 'KeyM':
                e.preventDefault();
                toggleMute();
                break;
            case 'KeyF':
                e.preventDefault();
                fullscreenBtn.click();
                break;
            case 'Equal': // Klavyedeki +
            case 'NumpadAdd':
                changeZoom(0.2);
                break;
            case 'Minus': // Klavyedeki -
            case 'NumpadSubtract':
                changeZoom(-0.2);
                break;
        }
    });
});
