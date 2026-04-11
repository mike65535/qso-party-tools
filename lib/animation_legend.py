#!/usr/bin/env python3
"""
Animation Legend Library - Reusable legend components for QSO animations
"""

def get_legend_html():
    """Return HTML structure for animation legend"""
    return '<div class="legend" id="legend"></div>'

def get_legend_css():
    """Return CSS styling for animation legend"""
    return '''
        .legend { position: absolute; top: 20px; right: 20px; z-index: 1000; background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.3); min-width: 150px; font-family: Arial, sans-serif; }
        .legend-title { font-size: 13px; font-weight: bold; text-align: center; margin: 0 0 8px 0; padding: 0; color: #333; }
        .legend-item { display: flex; align-items: center; margin: 3px 0; }
        .legend-color { width: 20px; height: 15px; margin-right: 8px; border: 1px solid #ccc; flex-shrink: 0; }'''

def get_legend_js(color_thresholds, color_palette, title="QSOs per County"):
    """Return JavaScript functions for legend management"""
    return f'''
        function roundNice(val) {{
            if (val <= 0) return 0;
            const mag = Math.pow(10, Math.floor(Math.log10(val)));
            const step = mag / 2;
            return Math.round(val / step) * step;
        }}

        function getThresholds(maxCount) {{
            return {color_thresholds}.map(t => t === 0 ? 0 : Math.max(1, Math.round(roundNice(t * maxCount))));
        }}

        function getColor(count, maxCount) {{
            const thresholds = getThresholds(maxCount);
            const colors = {color_palette};

            for (let i = 0; i < thresholds.length; i++) {{
                if (count <= thresholds[i]) {{
                    return colors[i];
                }}
            }}
            return colors[colors.length - 1];
        }}

        function updateLegend(maxCount) {{
            if (maxCount === 0) {{
                document.getElementById('legend').innerHTML =
                    '<div class="legend-title">{title}</div>' +
                    '<div class="legend-item"><div class="legend-color" style="background-color:{color_palette[0]}"></div>' +
                    '<span style="font-size:12px;">0</span></div>';
                return;
            }}
            const thresholds = getThresholds(maxCount);
            const colors = {color_palette};

            let legendHtml = '<div class="legend-title">{title}</div>';
            for (let i = colors.length - 1; i >= 0; i--) {{
                const min = i === 0 ? 0 : thresholds[i - 1] + 1;
                const max = i < thresholds.length ? thresholds[i] : maxCount;
                legendHtml += `<div class="legend-item">
                    <div class="legend-color" style="background-color: ${{colors[i]}}"></div>
                    <span style="font-size: 12px;">${{min}} – ${{max}}</span>
                </div>`;
            }}
            document.getElementById('legend').innerHTML = legendHtml;
        }}'''
