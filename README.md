# Desktop Video Overlay

A Windows desktop overlay app that plays videos with chroma key (green screen) transparency, allowing you to place animated characters or effects on your desktop. Features advanced chroma keying, color picking, scaling, and system tray controls.

## Features
- **Chroma Key (Green Screen) Transparency:** Remove backgrounds from videos using chroma keying. Supports manual color picking and automatic chroma detection.
- **Color Tolerance Control:** Fine-tune the chroma key effect for best results.
- **Multiple Video Support:** Load and switch between multiple video files (webm, mp4, avi, mov).
- **Audio Playback:** Plays video audio using VLC (audio only, no video window).
- **Scaling & Positioning:** Resize and drag the overlay anywhere on your desktop.
- **System Tray Integration:** Quick access to settings, chroma controls, and quit from the tray icon.

## Installation
1. Install Python 3.8+ (Windows only).
2. Install dependencies:
   ```bash
   pip install pygame opencv-python numpy pillow pystray python-vlc pywin32
   ```
3. Download or clone this repository.
4. Place an `icon.png` in the project folder for the tray icon (optional).

## Usage
Run the app:
```bash
python "Desktop Dancer.py"
```

### Controls
- **O**: Open video file(s)
- **P**: Pick a chroma key color from the video (click on the video)
- **A**: Auto-detect chroma key color (from video edges)
- **C**: Reset chroma key to default (magenta)
- **Space**: Pause/Play video and audio
- **+ / -**: Scale overlay up/down
- **Arrow keys**: Switch videos
- **Click & drag**: Move overlay
- **System Tray**: Access settings, chroma controls, and quit

## Chroma Keying Details
- **Manual Color Picking:** Press `P` and click on the video to select the color to make transparent.
- **Auto Chroma Detection:** Press `A` to automatically detect the most common edge color as the chroma key.
- **Tolerance:** Adjust how similar a color must be to the chroma key to be made transparent (via tray or after picking color).

## License
MIT 