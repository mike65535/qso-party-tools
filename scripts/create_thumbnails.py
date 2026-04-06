#!/usr/bin/env python3
"""
Create thumbnail images for the chart gallery.
Discovers all PNG files in the charts directory automatically.
"""

import argparse
from pathlib import Path
from PIL import Image


def create_thumbnails(charts_dir, thumbs_dir, thumb_size=(300, 200)):
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    chart_files = list(charts_dir.glob('*.png'))

    if not chart_files:
        print(f"No PNG files found in {charts_dir}")
        return

    for chart_path in sorted(chart_files):
        thumb_path = thumbs_dir / f"thumb_{chart_path.name}"
        try:
            with Image.open(chart_path) as img:
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                img.save(thumb_path, 'PNG')
                print(f"Created {thumb_path.name}")
        except Exception as e:
            print(f"Error creating thumbnail for {chart_path.name}: {e}")

    print(f"\nThumbnails saved to: {thumbs_dir}")


def main():
    parser = argparse.ArgumentParser(description='Create chart thumbnails')
    parser.add_argument('--charts-dir', required=True, help='Directory containing PNG chart files')
    parser.add_argument('--output-dir', help='Thumbnail output directory (default: <charts-dir>/thumbnails)')
    parser.add_argument('--width', type=int, default=300)
    parser.add_argument('--height', type=int, default=200)
    args = parser.parse_args()

    charts_dir = Path(args.charts_dir)
    thumbs_dir = Path(args.output_dir) if args.output_dir else charts_dir / 'thumbnails'

    create_thumbnails(charts_dir, thumbs_dir, thumb_size=(args.width, args.height))


if __name__ == '__main__':
    main()
