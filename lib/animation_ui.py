#!/usr/bin/env python3
"""
Animation UI components for QSO party visualizations
"""

class TimelineControls:
    """Play/pause/speed controls for animations"""

    @staticmethod
    def get_css():
        return '''
        .timeline-controls { display: flex; align-items: center; justify-content: center; gap: 15px; }
        .control-btn { padding: 12px 16px; border: none; border-radius: 6px; background: #3498db; color: white; cursor: pointer; font-size: 16px; }
        .control-btn:hover { background: #2980b9; }
        .control-btn:disabled { background: #7f8c8d; cursor: not-allowed; }
        .time-display { font-size: 18px; font-weight: bold; }
        .speed-control select { padding: 8px; border-radius: 4px; }
        '''

    @staticmethod
    def get_html():
        return '''
        <div class="timeline-controls">
            <button class="control-btn" id="playBtn" onclick="togglePlay()">▶ Play</button>
            <button class="control-btn" id="resetBtn" onclick="resetAnimation()">⏮ Reset</button>
            <span class="time-display" id="timeDisplay">00:00 UTC</span>
            <span class="speed-control">Speed:
                <select id="speedSelect" onchange="changeSpeed()">
                    <option value="1">1x</option>
                    <option value="5">5x</option>
                    <option value="10" selected>10x</option>
                    <option value="30">30x</option>
                    <option value="60">60x</option>
                </select>
            </span>
        </div>
        '''

    @staticmethod
    def get_javascript():
        return '''
        let isPlaying = false;
        let animationSpeed = 10;

        function togglePlay() {
            isPlaying = !isPlaying;
            const btn = document.getElementById('playBtn');
            btn.textContent = isPlaying ? '⏸ Pause' : '▶ Play';
        }

        function resetAnimation() {
            isPlaying = false;
            document.getElementById('playBtn').textContent = '▶ Play';
        }

        function changeSpeed() {
            animationSpeed = parseInt(document.getElementById('speedSelect').value);
        }
        '''

class ProgressBar:
    """Progress bar for animation timeline"""

    @staticmethod
    def get_css():
        return '''
        .progress-container { width: 300px; height: 8px; background: #34495e; border-radius: 4px; cursor: pointer; }
        .progress-bar { height: 100%; background: #e74c3c; border-radius: 4px; width: 0%; transition: width 0.1s; }
        '''

    @staticmethod
    def get_html():
        return '''
        <div class="progress-container" onclick="seekToPosition(event)">
            <div class="progress-bar" id="progressBar"></div>
        </div>
        '''

    @staticmethod
    def get_javascript():
        return '''
        function updateProgress(percent) {
            document.getElementById('progressBar').style.width = Math.min(percent, 100) + '%';
        }

        function seekToPosition(event) {
            const container = event.currentTarget;
            const rect = container.getBoundingClientRect();
            const percent = (event.clientX - rect.left) / rect.width * 100;
            updateProgress(percent);
        }
        '''

class StatusBar:
    """Status display for active stations, QSO counts, etc."""

    @staticmethod
    def get_css():
        return '''
        .status-bar { display: flex; align-items: center; justify-content: center; gap: 20px; font-size: 16px; }
        .status-item { padding: 8px 12px; background: #34495e; border-radius: 4px; }
        '''

    @staticmethod
    def get_html():
        return '''
        <div class="status-bar">
            <span class="status-item" id="activeStations">Active: 0</span>
            <span class="status-item" id="totalQSOs">QSOs: 0</span>
            <span class="status-item" id="currentTime">Time: --:--</span>
        </div>
        '''

    @staticmethod
    def get_javascript():
        return '''
        function updateStatus(active, qsos, time) {
            document.getElementById('activeStations').textContent = `Active: ${active}`;
            document.getElementById('totalQSOs').textContent = `QSOs: ${qsos}`;
            document.getElementById('currentTime').textContent = `Time: ${time}`;
        }
        '''

class Legend:
    """Legend for map colors and symbols"""

    @staticmethod
    def get_css():
        return '''
        .legend { position: absolute; top: 10px; right: 10px; background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); z-index: 1000; }
        .legend-title { font-weight: bold; margin-bottom: 10px; }
        .legend-item { display: flex; align-items: center; margin-bottom: 5px; }
        .legend-color { width: 20px; height: 20px; margin-right: 8px; border-radius: 3px; }
        '''

    @staticmethod
    def get_html(items):
        legend_items = ''.join([
            f'<div class="legend-item"><div class="legend-color" style="background: {color};"></div><span>{label}</span></div>'
            for color, label in items
        ])
        return f'''
        <div class="legend">
            <div class="legend-title">Legend</div>
            {legend_items}
        </div>
        '''

    @staticmethod
    def get_javascript():
        return '''
        // Legend is static, no JavaScript needed
        console.log('Legend component loaded');
        '''
