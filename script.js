// ─── State ────────────────────────────────────────────────────────────────────
const state = {
    playlist: [],
    currentIndex: -1,
    zoom: 1,
    panX: 0,
    panY: 0,
    isPanning: false,
    panStart: { x: 0, y: 0 },
    isSliderDragging: false,
    isMuted: false,
    playbackRate: 1.0,
    subtitleTracks: [],
    currentSubtitleIndex: -1,
    subtitleCues: [],
    isFullscreen: false,
    savedPositions: JSON.parse(localStorage.getItem('videoPositions') || '{}'),
    controlsTimeout: null,
    lastVolume: 1,
};

// ─── DOM ──────────────────────────────────────────────────────────────────────
const video = document.getElementById('videoPlayer');
const fileLoader = document.getElementById('fileLoader');
const fileInput = document.getElementById('fileInput');
const folderInput = document.getElementById('folderInput');
const controls = document.getElementById('controls');
const progressBar = document.getElementById('progressBar');
const progressBuf = document.getElementById('progressBuffer');
const progressCont = document.getElementById('progressContainer');
const playBtn = document.getElementById('playPauseBtn');
const rewindBtn = document.getElementById('rewindBtn');
const forwardBtn = document.getElementById('forwardBtn');
const muteBtn = document.getElementById('muteBtn');
const volumeSlider = document.getElementById('volumeSlider');
const currentTimeEl = document.getElementById('currentTime');
const durationEl = document.getElementById('duration');
const zoomOutBtn = document.getElementById('zoomOutBtn');
const zoomInBtn = document.getElementById('zoomInBtn');
const resetZoomBtn = document.getElementById('resetZoomBtn');
const zoomLevelText = document.getElementById('zoomLevelText');
const fullscreenBtn = document.getElementById('fullscreenBtn');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const speedBtn = document.getElementById('speedBtn');
const speedMenu = document.getElementById('speedMenu');
const subtitleBtn = document.getElementById('subtitleBtn');
const subtitleMenu = document.getElementById('subtitleMenu');
const subtitleFile = document.getElementById('subtitleFileInput');
const subtitleDisp = document.getElementById('subtitleDisplay');
const playlistPanel = document.getElementById('playlistPanel');
const playlistList = document.getElementById('playlistList');
const playlistToggle = document.getElementById('playlistToggle');
const videoWrapper = document.getElementById('videoWrapper');
const container = document.getElementById('videoContainer');
const zoomHint = document.getElementById('zoomHint');
const statusBar = document.getElementById('statusBar');
const toastEl = document.getElementById('toast');
const resumeDialog = document.getElementById('resumeDialog');
const resumeYes = document.getElementById('resumeYes');
const resumeNo = document.getElementById('resumeNo');
const resumeTime = document.getElementById('resumeTime');
const loadingSpinner = document.getElementById('loadingSpinner');

// ─── Toast ────────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg, duration = 2000) {
    toastEl.textContent = msg;
    toastEl.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('visible'), duration);
}

function setStatus(msg) {
    statusBar.textContent = msg;
}

// ─── Time Format ──────────────────────────────────────────────────────────────
function formatTime(seconds) {
    if (isNaN(seconds)) return '00:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// ─── File Loading ─────────────────────────────────────────────────────────────
fileInput.addEventListener('change', e => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    const videoExts = ['mp4', 'webm', 'ogg', 'mkv', 'avi', 'mov', 'm4v', 'flv', 'wmv'];
    const videoFiles = files.filter(f => {
        const ext = f.name.split('.').pop().toLowerCase();
        return videoExts.includes(ext) || f.type.startsWith('video/');
    });
    if (!videoFiles.length) { showToast('Video dosyası bulunamadı'); return; }
    state.playlist = videoFiles;
    state.currentIndex = 0;
    loadVideo(videoFiles[0]);
    renderPlaylist();
});

folderInput && folderInput.addEventListener('change', e => {
    const files = Array.from(e.target.files);
    const videoExts = ['mp4', 'webm', 'ogg', 'mkv', 'avi', 'mov', 'm4v', 'flv', 'wmv'];
    const videoFiles = files.filter(f => {
        const ext = f.name.split('.').pop().toLowerCase();
        return videoExts.includes(ext) || f.type.startsWith('video/');
    }).sort((a, b) => a.name.localeCompare(b.name));
    if (!videoFiles.length) { showToast('Klasörde video bulunamadı'); return; }
    state.playlist = videoFiles;
    state.currentIndex = 0;
    loadVideo(videoFiles[0]);
    renderPlaylist();
    setStatus(`${videoFiles.length} video yüklendi`);
});

function loadVideo(file) {
    const url = URL.createObjectURL(file);
    video.src = url;
    fileLoader.classList.remove('active');
    controls.classList.add('active');
    loadingSpinner.style.display = 'flex';

    video.load();
    video.play().catch(() => { });

    document.title = `${file.name} — Video Oynatıcı`;
    setStatus(`Oynatılıyor: ${file.name}`);
    updatePlaylistHighlight();

    // Resume position?
    const key = file.name + '_' + file.size;
    const saved = state.savedPositions[key];
    if (saved && saved > 5) {
        state._pendingResume = { key, time: saved };
        resumeTime.textContent = formatTime(saved);
        resumeDialog.classList.add('active');
    } else {
        state._pendingResume = null;
    }
}

resumeYes && resumeYes.addEventListener('click', () => {
    if (state._pendingResume) {
        video.currentTime = state._pendingResume.time;
    }
    resumeDialog.classList.remove('active');
});
resumeNo && resumeNo.addEventListener('click', () => {
    resumeDialog.classList.remove('active');
});

// ─── Video Events ─────────────────────────────────────────────────────────────
video.addEventListener('loadedmetadata', () => {
    durationEl.textContent = formatTime(video.duration);
    loadingSpinner.style.display = 'none';
});

video.addEventListener('waiting', () => loadingSpinner.style.display = 'flex');
video.addEventListener('playing', () => loadingSpinner.style.display = 'none');
video.addEventListener('canplay', () => loadingSpinner.style.display = 'none');

video.addEventListener('timeupdate', () => {
    if (state.isSliderDragging) return;
    const pct = video.duration ? (video.currentTime / video.duration) * 100 : 0;
    progressBar.style.width = pct + '%';
    currentTimeEl.textContent = formatTime(video.currentTime);
    updateSubtitle();

    // Auto-save position every ~5s
    if (state.playlist.length && state.currentIndex >= 0) {
        const file = state.playlist[state.currentIndex];
        const key = file.name + '_' + file.size;
        if (video.currentTime > 5) {
            state.savedPositions[key] = video.currentTime;
            localStorage.setItem('videoPositions', JSON.stringify(state.savedPositions));
        }
    }
});

video.addEventListener('progress', () => {
    if (video.buffered.length) {
        const buffered = (video.buffered.end(video.buffered.length - 1) / video.duration) * 100;
        progressBuf.style.width = buffered + '%';
    }
});

video.addEventListener('play', () => { playBtn.innerHTML = '<i class="fas fa-pause"></i>'; });
video.addEventListener('pause', () => { playBtn.innerHTML = '<i class="fas fa-play"></i>'; });

video.addEventListener('ended', () => {
    if (state.currentIndex < state.playlist.length - 1) {
        state.currentIndex++;
        loadVideo(state.playlist[state.currentIndex]);
    } else {
        playBtn.innerHTML = '<i class="fas fa-play"></i>';
    }
});

video.addEventListener('error', () => {
    loadingSpinner.style.display = 'none';
    showToast('Video yüklenemedi: Desteklenmeyen format olabilir', 4000);
    setStatus('Hata: Video yüklenemedi');
});

// ─── Play / Pause ─────────────────────────────────────────────────────────────
function togglePlay() {
    if (!video.src) return;
    video.paused ? video.play() : video.pause();
}
playBtn.addEventListener('click', togglePlay);

// ─── Progress Bar ─────────────────────────────────────────────────────────────
progressCont.addEventListener('mousedown', e => {
    state.isSliderDragging = true;
    seekTo(e);
});
document.addEventListener('mousemove', e => {
    if (state.isSliderDragging) seekTo(e);
});
document.addEventListener('mouseup', () => { state.isSliderDragging = false; });

progressCont.addEventListener('touchstart', e => {
    state.isSliderDragging = true;
    seekTo(e.touches[0]);
}, { passive: true });
document.addEventListener('touchmove', e => {
    if (state.isSliderDragging) seekTo(e.touches[0]);
}, { passive: true });
document.addEventListener('touchend', () => { state.isSliderDragging = false; });

// Tooltip on hover
progressCont.addEventListener('mousemove', e => {
    if (video.duration) {
        const rect = progressCont.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        const t = pct * video.duration;
        const tip = document.getElementById('progressTooltip');
        if (tip) {
            tip.style.left = Math.min(Math.max(0, e.clientX - rect.left), rect.width) + 'px';
            tip.textContent = formatTime(t);
        }
    }
});

function seekTo(e) {
    const rect = progressCont.getBoundingClientRect();
    const pct = Math.min(Math.max(0, (e.clientX - rect.left) / rect.width), 1);
    video.currentTime = pct * video.duration;
    progressBar.style.width = (pct * 100) + '%';
}

// ─── Seek Relative ────────────────────────────────────────────────────────────
function seekRelative(seconds) {
    video.currentTime = Math.min(Math.max(0, video.currentTime + seconds), video.duration);
    showToast(seconds > 0 ? `+${seconds}s` : `${seconds}s`);
}
rewindBtn.addEventListener('click', () => seekRelative(-10));
forwardBtn.addEventListener('click', () => seekRelative(30));

// ─── Volume ───────────────────────────────────────────────────────────────────
volumeSlider.addEventListener('input', () => {
    video.volume = parseFloat(volumeSlider.value);
    state.lastVolume = video.volume;
    updateVolumeIcon();
});

function updateVolumeIcon() {
    const v = video.volume;
    const m = video.muted;
    if (m || v === 0) muteBtn.innerHTML = '<i class="fas fa-volume-xmark"></i>';
    else if (v < 0.3) muteBtn.innerHTML = '<i class="fas fa-volume-off"></i>';
    else if (v < 0.7) muteBtn.innerHTML = '<i class="fas fa-volume-low"></i>';
    else muteBtn.innerHTML = '<i class="fas fa-volume-high"></i>';
}

function toggleMute() {
    video.muted = !video.muted;
    if (video.muted) {
        volumeSlider.value = 0;
    } else {
        volumeSlider.value = state.lastVolume || 1;
        video.volume = state.lastVolume || 1;
    }
    updateVolumeIcon();
}
muteBtn.addEventListener('click', toggleMute);

// Volume scroll on button
muteBtn.addEventListener('wheel', e => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.05 : -0.05;
    video.volume = Math.min(1, Math.max(0, video.volume + delta));
    volumeSlider.value = video.volume;
    state.lastVolume = video.volume;
    updateVolumeIcon();
    showToast(`Ses: ${Math.round(video.volume * 100)}%`);
}, { passive: false });

// ─── Playlist ─────────────────────────────────────────────────────────────────
function renderPlaylist() {
    playlistList.innerHTML = '';
    state.playlist.forEach((file, i) => {
        const li = document.createElement('li');
        li.className = 'playlist-item' + (i === state.currentIndex ? ' active' : '');
        li.innerHTML = `<i class="fas fa-film"></i><span>${file.name}</span>`;
        li.addEventListener('click', () => {
            state.currentIndex = i;
            loadVideo(file);
        });
        playlistList.appendChild(li);
    });
}

function updatePlaylistHighlight() {
    document.querySelectorAll('.playlist-item').forEach((el, i) => {
        el.classList.toggle('active', i === state.currentIndex);
    });
}

playlistToggle && playlistToggle.addEventListener('click', () => {
    playlistPanel.classList.toggle('open');
    playlistToggle.classList.toggle('active');
});

prevBtn && prevBtn.addEventListener('click', () => {
    if (state.currentIndex > 0) {
        state.currentIndex--;
        loadVideo(state.playlist[state.currentIndex]);
    }
});
nextBtn && nextBtn.addEventListener('click', () => {
    if (state.currentIndex < state.playlist.length - 1) {
        state.currentIndex++;
        loadVideo(state.playlist[state.currentIndex]);
    }
});

// ─── Playback Speed ───────────────────────────────────────────────────────────
speedBtn && speedBtn.addEventListener('click', e => {
    speedMenu.classList.toggle('open');
    subtitleMenu.classList.remove('open');
    e.stopPropagation();
});

document.querySelectorAll('.speed-option').forEach(btn => {
    btn.addEventListener('click', () => {
        const rate = parseFloat(btn.dataset.speed);
        setPlaybackRate(rate);
        speedMenu.classList.remove('open');
    });
});

function setPlaybackRate(rate) {
    state.playbackRate = rate;
    video.playbackRate = rate;
    speedBtn.querySelector('span').textContent = rate + 'x';
    // highlight active
    document.querySelectorAll('.speed-option').forEach(b => {
        b.classList.toggle('active', parseFloat(b.dataset.speed) === rate);
    });
    showToast(`Hız: ${rate}x`);
}

// ─── Subtitles ────────────────────────────────────────────────────────────────
subtitleBtn && subtitleBtn.addEventListener('click', e => {
    subtitleMenu.classList.toggle('open');
    speedMenu.classList.remove('open');
    e.stopPropagation();
});

subtitleFile && subtitleFile.addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
        const ext = file.name.split('.').pop().toLowerCase();
        let cues = [];
        if (ext === 'srt') cues = parseSRT(ev.target.result);
        else if (ext === 'vtt') cues = parseVTT(ev.target.result);
        if (cues.length) {
            state.subtitleTracks.push({ name: file.name, cues });
            addSubtitleOption(file.name, state.subtitleTracks.length - 1);
            activateSubtitle(state.subtitleTracks.length - 1);
            showToast(`Altyazı yüklendi: ${file.name}`);
        } else {
            showToast('Altyazı ayrıştırılamadı');
        }
    };
    reader.readAsText(file, 'UTF-8');
});

function addSubtitleOption(name, index) {
    const btn = document.createElement('button');
    btn.className = 'subtitle-option';
    btn.textContent = name;
    btn.dataset.index = index;
    btn.addEventListener('click', () => {
        activateSubtitle(index);
        subtitleMenu.classList.remove('open');
    });
    const list = document.getElementById('subtitleList');
    if (list) list.appendChild(btn);
}

function activateSubtitle(index) {
    state.currentSubtitleIndex = index;
    state.subtitleCues = state.subtitleTracks[index].cues;
    document.querySelectorAll('.subtitle-option').forEach((b, i) => {
        b.classList.toggle('active', i === index);
    });
}

document.getElementById('subtitleOff') && document.getElementById('subtitleOff').addEventListener('click', () => {
    state.currentSubtitleIndex = -1;
    state.subtitleCues = [];
    subtitleDisp.textContent = '';
    document.querySelectorAll('.subtitle-option').forEach(b => b.classList.remove('active'));
    subtitleMenu.classList.remove('open');
});

function updateSubtitle() {
    if (!state.subtitleCues.length) { subtitleDisp.textContent = ''; return; }
    const t = video.currentTime;
    const cue = state.subtitleCues.find(c => t >= c.start && t <= c.end);
    subtitleDisp.innerHTML = cue ? cue.text : '';
}

function parseSRT(text) {
    const blocks = text.trim().split(/\n\s*\n/);
    return blocks.map(block => {
        const lines = block.trim().split('\n');
        if (lines.length < 2) return null;
        const timeMatch = lines[1].match(/(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)/);
        if (!timeMatch) return null;
        const toSec = (h, m, s, ms) => parseInt(h) * 3600 + parseInt(m) * 60 + parseInt(s) + parseInt(ms) / 1000;
        const start = toSec(timeMatch[1], timeMatch[2], timeMatch[3], timeMatch[4]);
        const end = toSec(timeMatch[5], timeMatch[6], timeMatch[7], timeMatch[8]);
        const text = lines.slice(2).join('<br>').replace(/<[^>]+>/g, '');
        return { start, end, text };
    }).filter(Boolean);
}

function parseVTT(text) {
    const lines = text.split('\n');
    const cues = [];
    let i = 0;
    while (i < lines.length) {
        const timeMatch = lines[i].match(/(\d+):(\d+)[.:](\d+)\s*-->\s*(\d+):(\d+)[.:](\d+)/);
        if (timeMatch) {
            const toSec = (m, s, ms) => parseInt(m) * 60 + parseInt(s) + parseInt(ms) / 1000;
            const start = toSec(timeMatch[1], timeMatch[2], timeMatch[3]);
            const end = toSec(timeMatch[4], timeMatch[5], timeMatch[6]);
            const textLines = [];
            i++;
            while (i < lines.length && lines[i].trim() !== '') {
                textLines.push(lines[i]);
                i++;
            }
            cues.push({ start, end, text: textLines.join('<br>') });
        } else { i++; }
    }
    return cues;
}

// ─── Zoom & Pan ───────────────────────────────────────────────────────────────
function applyTransform() {
    video.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
    zoomLevelText.textContent = Math.round(state.zoom * 100) + '%';
    zoomHint.classList.toggle('visible', state.zoom > 1);
}

function zoomIn() { state.zoom = Math.min(5, state.zoom * 1.2); applyTransform(); }
function zoomOut() { if (state.zoom > 1) { state.zoom = Math.max(1, state.zoom / 1.2); if (state.zoom <= 1) { state.panX = 0; state.panY = 0; } applyTransform(); } }
function resetZoom() { state.zoom = 1; state.panX = 0; state.panY = 0; applyTransform(); }

zoomInBtn.addEventListener('click', zoomIn);
zoomOutBtn.addEventListener('click', zoomOut);
resetZoomBtn.addEventListener('click', resetZoom);

// Ctrl+Wheel zoom
container.addEventListener('wheel', e => {
    if (e.ctrlKey) {
        e.preventDefault();
        e.deltaY < 0 ? zoomIn() : zoomOut();
    }
}, { passive: false });

// Pan
videoWrapper.addEventListener('mousedown', e => {
    if (state.zoom <= 1) return;
    state.isPanning = true;
    state.panStart = { x: e.clientX - state.panX, y: e.clientY - state.panY };
    videoWrapper.style.cursor = 'grabbing';
});
document.addEventListener('mousemove', e => {
    if (!state.isPanning) return;
    state.panX = e.clientX - state.panStart.x;
    state.panY = e.clientY - state.panStart.y;
    applyTransform();
});
document.addEventListener('mouseup', () => {
    state.isPanning = false;
    videoWrapper.style.cursor = state.zoom > 1 ? 'grab' : 'default';
});

// Touch pan
let touchPanStart = null;
videoWrapper.addEventListener('touchstart', e => {
    if (e.touches.length === 1 && state.zoom > 1) {
        touchPanStart = { x: e.touches[0].clientX - state.panX, y: e.touches[0].clientY - state.panY };
    }
}, { passive: true });
videoWrapper.addEventListener('touchmove', e => {
    if (touchPanStart && e.touches.length === 1) {
        state.panX = e.touches[0].clientX - touchPanStart.x;
        state.panY = e.touches[0].clientY - touchPanStart.y;
        applyTransform();
    }
}, { passive: true });
videoWrapper.addEventListener('touchend', () => { touchPanStart = null; });

// ─── Fullscreen ───────────────────────────────────────────────────────────────
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        container.requestFullscreen().catch(() => { });
    } else {
        document.exitFullscreen();
    }
}
fullscreenBtn.addEventListener('click', toggleFullscreen);
document.addEventListener('fullscreenchange', () => {
    state.isFullscreen = !!document.fullscreenElement;
    fullscreenBtn.innerHTML = state.isFullscreen
        ? '<i class="fas fa-compress"></i>'
        : '<i class="fas fa-expand"></i>';
});

// ─── Controls Auto-hide ───────────────────────────────────────────────────────
function showControls() {
    controls.classList.add('active');
    clearTimeout(state.controlsTimeout);
    if (!video.paused) {
        state.controlsTimeout = setTimeout(() => controls.classList.remove('active'), 3000);
    }
}

container.addEventListener('mousemove', showControls);
container.addEventListener('click', e => {
    if (e.target === video || e.target === videoWrapper) togglePlay();
});
container.addEventListener('dblclick', e => {
    if (e.target === video || e.target === videoWrapper) toggleFullscreen();
});
video.addEventListener('pause', () => { clearTimeout(state.controlsTimeout); controls.classList.add('active'); });
video.addEventListener('play', showControls);

// ─── Keyboard ─────────────────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
    const tag = document.activeElement.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;

    switch (e.code) {
        case 'Space': e.preventDefault(); togglePlay(); break;
        case 'ArrowLeft':
            e.ctrlKey ? (state.currentIndex > 0 && (state.currentIndex--, loadVideo(state.playlist[state.currentIndex])))
                : seekRelative(-10);
            break;
        case 'ArrowRight':
            e.ctrlKey ? (state.currentIndex < state.playlist.length - 1 && (state.currentIndex++, loadVideo(state.playlist[state.currentIndex])))
                : seekRelative(30);
            break;
        case 'ArrowUp':
            e.preventDefault();
            video.volume = Math.min(1, video.volume + 0.05);
            volumeSlider.value = video.volume;
            state.lastVolume = video.volume;
            updateVolumeIcon();
            showToast(`Ses: ${Math.round(video.volume * 100)}%`);
            break;
        case 'ArrowDown':
            e.preventDefault();
            video.volume = Math.max(0, video.volume - 0.05);
            volumeSlider.value = video.volume;
            state.lastVolume = video.volume;
            updateVolumeIcon();
            showToast(`Ses: ${Math.round(video.volume * 100)}%`);
            break;
        case 'KeyM': toggleMute(); break;
        case 'KeyF': case 'F11': e.preventDefault(); toggleFullscreen(); break;
        case 'Escape':
            if (state.isFullscreen) document.exitFullscreen();
            speedMenu.classList.remove('open');
            subtitleMenu.classList.remove('open');
            break;
        case 'Equal': case 'NumpadAdd':
            if (e.ctrlKey) { e.preventDefault(); zoomIn(); } break;
        case 'Minus': case 'NumpadSubtract':
            if (e.ctrlKey) { e.preventDefault(); zoomOut(); } break;
        case 'Digit0': case 'Numpad0':
            if (e.ctrlKey) { e.preventDefault(); resetZoom(); } break;
    }
});

// Close menus on outside click
document.addEventListener('click', () => {
    speedMenu.classList.remove('open');
    subtitleMenu.classList.remove('open');
});

// ─── Drag & Drop ─────────────────────────────────────────────────────────────
container.addEventListener('dragover', e => { e.preventDefault(); container.classList.add('drag-over'); });
container.addEventListener('dragleave', () => container.classList.remove('drag-over'));
container.addEventListener('drop', e => {
    e.preventDefault();
    container.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files);
    const videoExts = ['mp4', 'webm', 'ogg', 'mkv', 'avi', 'mov', 'm4v', 'flv', 'wmv'];
    const videoFiles = files.filter(f => {
        const ext = f.name.split('.').pop().toLowerCase();
        return videoExts.includes(ext) || f.type.startsWith('video/');
    }).sort((a, b) => a.name.localeCompare(b.name));
    if (videoFiles.length) {
        state.playlist = videoFiles;
        state.currentIndex = 0;
        loadVideo(videoFiles[0]);
        renderPlaylist();
    }
});

// ─── Init ─────────────────────────────────────────────────────────────────────
volumeSlider.value = 1;
video.volume = 1;
updateVolumeIcon();
applyTransform();