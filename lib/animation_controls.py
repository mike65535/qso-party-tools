#!/usr/bin/env python3
"""
Animation Controls Library - Reusable HTML/CSS/JS components for QSO animations
"""

def get_controls_html(about_text=''):
    """Return HTML structure for animation controls.
    If about_text is provided, an ℹ button is shown that toggles a panel above the controls bar.
    """
    about_btn = ''
    about_panel = ''
    if about_text:
        about_btn = '<button class="control-btn" onclick="toggleAbout()">ℹ About</button>'
        about_panel = f'''
    <div id="aboutPanel" class="about-panel">
        <button class="about-close" onclick="toggleAbout()">✕</button>
        {about_text}
    </div>'''

    return f'''
    {about_panel}
    <div class="controls">
        <div class="top-controls">
            <button class="control-btn" id="playBtn" onclick="playPause()">▶ Play</button>
            <button class="control-btn" onclick="reset()">⏮ Reset</button>
            <button class="control-btn" id="speedBtn" onclick="changeSpeed(1)">Speed 1x</button>
            {about_btn}
        </div>
        <div class="middle-row">
            <div class="time-info">
                <span id="dateDisplay">2024-10-19</span> <span id="timeDisplay">12:00Z</span>
            </div>
            <div class="progress-section">
                <div class="progress-container" onclick="seekToPosition(event)">
                    <div class="progress-bar" id="progressBar"></div>
                </div>
            </div>
        </div>
        <div class="bottom-info">
            <span id="statusDisplay">Contest Activity | QSOs: 0 | Active: 0</span>
        </div>
    </div>'''


def get_controls_css():
    """Return CSS styling for animation controls"""
    return '''
        .controls { position: fixed; bottom: 0; left: 0; right: 0; background: #2c3e50; padding: 10px; z-index: 1000; }
        .top-controls { display: flex; justify-content: center; gap: 10px; margin-bottom: 8px; }
        .middle-row { display: flex; align-items: center; margin-bottom: 8px; }
        .time-info { width: 10%; color: white; font-weight: bold; display: flex; flex-direction: column; line-height: 1.2; }
        .progress-section { width: 85%; margin-left: 2%; }
        .progress-container { width: 100%; height: 8px; background: #34495e; border-radius: 4px; cursor: pointer; }
        .progress-bar { height: 100%; background: #e74c3c; border-radius: 4px; width: 0%; transition: width 0.1s; }
        .bottom-info { text-align: center; color: white; font-size: 12px; }
        .control-btn { background: #3498db; color: white; border: none; padding: 8px 12px; margin: 0 2px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .control-btn:hover { background: #2980b9; }
        .control-btn:disabled { background: #7f8c8d; cursor: not-allowed; }
        .about-panel { display: none; position: fixed; bottom: 90px; left: 0; right: 0; background: rgba(44,62,80,0.96); color: #ecf0f1; padding: 14px 48px 14px 20px; font-size: 13px; line-height: 1.6; z-index: 1001; }
        .about-panel.visible { display: block; }
        .about-close { position: absolute; top: 8px; right: 12px; background: none; border: none; color: #ecf0f1; font-size: 18px; cursor: pointer; line-height: 1; }
        .about-close:hover { color: white; }'''


def get_controls_js(animation_speeds="[1, 5, 10, 50]"):
    """Return JavaScript functions for animation controls"""
    return f'''
        let currentFrame = 0, isPlaying = false, speed = 1, animationInterval;

        function playPause() {{
            if (isPlaying) {{
                clearInterval(animationInterval);
                isPlaying = false;
                document.getElementById('playBtn').textContent = '▶ Play';
            }} else {{
                if (currentFrame >= animationData.frames.length - 1) currentFrame = 0;
                animationInterval = setInterval(() => {{
                    currentFrame++;
                    if (currentFrame >= animationData.frames.length) {{
                        currentFrame = animationData.frames.length - 1;
                        clearInterval(animationInterval);
                        isPlaying = false;
                        document.getElementById('playBtn').textContent = '▶ Play';
                    }}
                    updateFrame();
                }}, 1000 / speed);
                isPlaying = true;
                document.getElementById('playBtn').textContent = '⏸ Pause';
            }}
        }}

        function reset() {{
            clearInterval(animationInterval);
            isPlaying = false;
            currentFrame = 0;
            document.getElementById('playBtn').textContent = '▶ Play';
            updateFrame();
        }}

        function changeSpeed(delta) {{
            const speeds = {animation_speeds};
            let currentIndex = speeds.indexOf(speed);
            currentIndex = (currentIndex + 1) % speeds.length;
            speed = speeds[currentIndex];
            document.getElementById('speedBtn').textContent = `Speed ${{speed}}x`;
            if (isPlaying) {{
                clearInterval(animationInterval);
                animationInterval = setInterval(() => {{
                    currentFrame++;
                    if (currentFrame >= animationData.frames.length) {{
                        currentFrame = animationData.frames.length - 1;
                        clearInterval(animationInterval);
                        isPlaying = false;
                        document.getElementById('playBtn').textContent = '▶ Play';
                    }}
                    updateFrame();
                }}, 1000 / speed);
            }}
        }}

        function seekToPosition(event) {{
            const rect = event.currentTarget.getBoundingClientRect();
            const clickX = event.clientX - rect.left;
            const percentage = clickX / rect.width;
            currentFrame = Math.floor(percentage * (animationData.frames.length - 1));
            updateFrame();
        }}

        function toggleAbout() {{
            const panel = document.getElementById('aboutPanel');
            if (!panel) return;
            const controls = document.querySelector('.controls');
            if (controls) panel.style.bottom = controls.offsetHeight + 'px';
            panel.classList.toggle('visible');
        }}'''
