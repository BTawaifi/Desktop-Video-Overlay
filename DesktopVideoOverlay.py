import os
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import pygame
import win32api
import win32con
import win32gui
import cv2
import numpy as np
from collections import Counter
import threading
from PIL import Image
import pystray  # Added missing import for system tray
from pystray import MenuItem as item
import vlc  # For audio playback

class DesktopVideoOverlay:
    def __init__(self):
        pygame.init()
        self.width = 400
        self.height = 600
        self.default_transparency_color = (255, 0, 255)  # Default magenta
        self.transparency_color = self.default_transparency_color
        self.default_color_tolerance = 30
        self.color_tolerance = self.default_color_tolerance
        self.screen = pygame.display.set_mode(
            (self.width, self.height),
            pygame.NOFRAME | pygame.RESIZABLE
        )
        pygame.display.set_caption("Desktop Video Overlay")
        self.scale_factor = 1.0
        self.scale_step = 0.1
        self.is_dragging = False
        self.drag_offset = (0, 0)
        self.color_picking_mode = False
        self.video = None
        self.video_path = None
        self.video_paths = []  # List of video file paths
        self.current_video_index = 0
        self.is_playing = False
        self.temp_surface = None
        self.scaled_surface = None
        self.last_frame_surface = None  # Store last frame for pause
        self.font = pygame.font.SysFont("Arial", 14)
        self.vlc_instance = vlc.Instance('--no-video')  # Disable video output
        self.vlc_player = None  # VLC media player for audio
        self.sound_playing = False
        self.running = True
        self.auto_chroma_enabled = False  # Flag to track auto-detect chroma state
        self.make_window_transparent()
        self.select_video()
        # Start system tray thread
        tray_thread = threading.Thread(target=self.setup_tray_icon, daemon=True)
        tray_thread.start()

    def reset_chroma(self):
        """Reset chroma key to default values and disable auto-detection."""
        self.transparency_color = self.default_transparency_color
        self.color_tolerance = self.default_color_tolerance
        self.auto_chroma_enabled = False  # Disable auto-detection
        self.make_window_transparent()
        self.scaled_surface = None  # Force re-scale
        print(f"Chroma reset to default: {self.transparency_color}, tolerance: {self.color_tolerance}")

    def auto_detect_chroma(self):
        """Automatically detect the most likely chroma key color."""
        if not self.video or not self.temp_surface:
            return
        # Draw current frame to temp surface
        ret, frame = self.video.read()
        if not ret:
            return
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_surface = pygame.surfarray.make_surface(np.rot90(frame_rgb))
        self.temp_surface.blit(frame_surface, (0, 0))
        
        # Convert surface to numpy array
        surf_array = pygame.surfarray.pixels3d(self.temp_surface)
        
        # Sample pixels from the edges of the frame
        edge_pixels = []
        edge_pixels.extend(surf_array[10:-10, 0].tolist())  # Top edge
        edge_pixels.extend(surf_array[10:-10, -1].tolist())  # Bottom edge
        edge_pixels.extend(surf_array[0, 10:-10].tolist())  # Left edge
        edge_pixels.extend(surf_array[-1, 10:-10].tolist())  # Right edge
        
        # Convert to tuples for counting
        edge_pixels = [tuple(pixel) for pixel in edge_pixels]
        
        # Find the most common color
        color_counts = Counter(edge_pixels)
        most_common_color = color_counts.most_common(1)[0][0]
        
        # Set as new transparency color
        self.transparency_color = most_common_color
        self.make_window_transparent()
        self.scaled_surface = None  # Force re-scale
        print(f"Auto-detected chroma color: {self.transparency_color}")

    def make_window_transparent(self):
        """Set the window to be transparent and always on top."""
        hwnd = pygame.display.get_wm_info()["window"]
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) |
            win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST
        )
        win32gui.SetLayeredWindowAttributes(
            hwnd,
            win32api.RGB(*self.transparency_color),
            0,
            win32con.LWA_COLORKEY
        )

    def get_video_size(self, video_path):
        """Get the dimensions of a video file."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Could not open video file")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        return width, height

    def select_transparency_color_from_screen(self):
        """Allow user to pick a transparency color from the video and disable auto-detection."""
        self.color_picking_mode = True
        print("Color picking mode: Click on a color in the video to make it transparent")
        while self.color_picking_mode:
            self.draw_frame()
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    x, y = event.pos
                    if 0 <= x < self.width and 0 <= y < self.height:
                        ret, frame = self.video.read()
                        if ret:
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            frame_surface = pygame.surfarray.make_surface(np.rot90(frame_rgb))
                            self.temp_surface.blit(frame_surface, (0, 0))
                            pixel_color = self.temp_surface.get_at((x, y))[:3]
                            self.transparency_color = pixel_color
                            self.auto_chroma_enabled = False  # Disable auto-detection
                            self.color_picking_mode = False
                            self.get_color_tolerance()
                            self.make_window_transparent()
                            self.scaled_surface = None  # Force re-scale
                            print(f"New transparency color: {self.transparency_color}")
                            print(f"Color tolerance: {self.color_tolerance}")
                            return
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.color_picking_mode = False
                    print("Color picking canceled")
                    return

    def get_color_tolerance(self):
        """Prompt user for color tolerance value."""
        root = tk.Tk()
        root.withdraw()
        tolerance = simpledialog.askinteger(
            "Color Tolerance",
            "Enter color tolerance (0-255):",
            initialvalue=self.color_tolerance,
            minvalue=0,
            maxvalue=255
        )
        if tolerance is not None:
            self.color_tolerance = tolerance
        root.destroy()

    def select_video(self):
        """Prompt user to select video files."""
        root = tk.Tk()
        root.withdraw()
        self.video_paths = filedialog.askopenfilenames(
            title="Select Video File(s)",
            filetypes=[
                ("Video files", "*.webm *.mp4 *.avi *.mov"),
                ("All files", "*.*")
            ]
        )
        if not self.video_paths:
            print("No video selected. Exiting.")
            pygame.quit()
            sys.exit()
        self.current_video_index = 0
        self.load_video()

    def load_video(self):
        """Load the current video from the video_paths list and reapply auto-chroma if enabled."""
        if not self.video_paths:
            return
        self.video_path = self.video_paths[self.current_video_index]
        try:
            if self.video:
                self.video.release()
            self.video = cv2.VideoCapture(self.video_path)
            self.original_width, self.original_height = self.get_video_size(self.video_path)
            self.update_window_size()  # Apply current scale factor
            self.temp_surface = pygame.Surface((self.original_width, self.original_height))
            self.scaled_surface = None  # Reset scaled surface
            self.last_frame_surface = None  # Reset last frame
            self.is_playing = True
            print(f"Loaded video: {os.path.basename(self.video_path)}")
            print(f"Video dimensions: {self.width}x{self.height}")
            self.load_sound()
            # Reapply auto-detected chroma if enabled
            if self.auto_chroma_enabled:
                self.auto_detect_chroma()
        except Exception as e:
            print(f"Error loading video: {e}")
            self.next_video()  # Try next video on error

    def load_sound(self):
        """Load and play the video's audio using VLC without video output."""
        try:
            if self.vlc_player:
                self.vlc_player.stop()
                self.vlc_player.release()
            # Create a new VLC media player instance for audio only
            self.vlc_player = self.vlc_instance.media_player_new()
            media = self.vlc_instance.media_new(self.video_path)
            self.vlc_player.set_media(media)
            self.vlc_player.audio_set_volume(100)  # Set volume (0-100)
            print(f"Loaded audio from video: {os.path.basename(self.video_path)}")
            self.sound_playing = True
            self.vlc_player.play()
            if not self.is_playing:
                self.vlc_player.pause()
                self.sound_playing = False
        except Exception as e:
            print(f"Error loading video audio with VLC: {e}")
            self.vlc_player = None
            self.sound_playing = False

    def next_video(self):
        """Switch to the next video in the list."""
        if not self.video_paths:
            return
        self.current_video_index = (self.current_video_index + 1) % len(self.video_paths)
        self.reset_playback(preserve_settings=True)
        self.load_video()

    def previous_video(self):
        """Switch to the previous video in the list."""
        if not self.video_paths:
            return
        self.current_video_index = (self.current_video_index - 1) % len(self.video_paths)
        self.reset_playback(preserve_settings=True)
        self.load_video()

    def reset_playback(self, preserve_settings=False):
        """Reset video and sound playback."""
        if self.video:
            self.video.release()
            self.video = None
        if self.vlc_player:
            self.vlc_player.stop()
            self.vlc_player.release()
            self.vlc_player = None
        self.is_playing = False
        self.sound_playing = False
        self.scaled_surface = None
        self.last_frame_surface = None  # Reset last frame
        if not preserve_settings:
            self.reset_chroma()

    def update_window_size(self):
        """Update window size based on scale factor."""
        new_width = int(self.original_width * self.scale_factor)
        new_height = int(self.original_height * self.scale_factor)
        self.width = max(50, new_width)
        self.height = max(50, new_height)
        self.screen = pygame.display.set_mode(
            (self.width, self.height),
            pygame.NOFRAME | pygame.RESIZABLE
        )
        self.scaled_surface = None  # Force re-scale
        self.last_frame_surface = None  # Reset last frame
        self.make_window_transparent()

    def handle_events(self):
        """Handle user input events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.color_picking_mode:
                        self.color_picking_mode = False
                        print("Color picking canceled")
                    else:
                        self.running = False
                        return False
                elif event.key == pygame.K_SPACE:
                    self.is_playing = not self.is_playing
                    if self.vlc_player:
                        if self.is_playing:
                            self.vlc_player.play()
                            self.sound_playing = True
                        else:
                            self.vlc_player.pause()
                            self.sound_playing = False
                elif event.key == pygame.K_o:
                    self.select_video()
                elif event.key == pygame.K_p:
                    self.select_transparency_color_from_screen()
                elif event.key == pygame.K_c:
                    self.reset_chroma()
                elif event.key == pygame.K_a:
                    self.auto_chroma_enabled = True  # Enable auto-detection
                    self.auto_detect_chroma()
                    self.get_color_tolerance()  # Prompt for tolerance only when enabling
                elif event.key == pygame.K_r:
                    self.scale_factor = 1.0
                    self.update_window_size()
                elif event.key == pygame.K_PLUS or event.key == pygame.K_KP_PLUS:
                    self.scale_factor += self.scale_step
                    self.update_window_size()
                elif event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS:
                    self.scale_factor = max(0.1, self.scale_factor - self.scale_step)
                    self.update_window_size()
                elif event.key == pygame.K_RIGHT:
                    self.next_video()
                elif event.key == pygame.K_LEFT:
                    self.previous_video()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.is_dragging = True
                    self.drag_offset = event.pos
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.is_dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if self.is_dragging:
                    x, y = win32gui.GetCursorPos()
                    win32gui.SetWindowPos(
                        pygame.display.get_wm_info()["window"],
                        win32con.HWND_TOPMOST,
                        x - self.drag_offset[0],
                        y - self.drag_offset[1],
                        0, 0,
                        win32con.SWP_NOSIZE
                    )
        return True

    def draw_frame(self):
        """Draw the current video frame with transparency, retaining last frame when paused."""
        self.screen.fill(self.transparency_color)
        if self.video:
            if self.is_playing:
                ret, frame = self.video.read()
                if not ret:
                    self.video.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.video.read()
                if ret:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_surface = pygame.surfarray.make_surface(np.rot90(frame_rgb))
                    self.temp_surface.fill(self.transparency_color)
                    self.temp_surface.blit(frame_surface, (0, 0))
                    
                    # Scale the surface if needed
                    if (self.scaled_surface is None or 
                        self.width != self.scaled_surface.get_width() or 
                        self.height != self.scaled_surface.get_height()):
                        self.scaled_surface = pygame.transform.scale(self.temp_surface, (self.width, self.height))
                    else:
                        pygame.transform.scale(self.temp_surface, (self.width, self.height), self.scaled_surface)
                    
                    # Apply transparency
                    transparent_surface = self.scaled_surface.copy()
                    surf_array = pygame.surfarray.pixels3d(transparent_surface)
                    tr = np.array(self.transparency_color)
                    mask = np.sqrt(np.sum((surf_array - tr) ** 2, axis=2)) <= self.color_tolerance
                    surf_array[mask] = self.transparency_color
                    del surf_array  # Release lock
                    
                    self.last_frame_surface = transparent_surface  # Store last frame
                    self.screen.blit(transparent_surface, (0, 0))
            elif self.last_frame_surface:  # When paused, draw the last frame
                self.screen.blit(self.last_frame_surface, (0, 0))
            
            if self.color_picking_mode:
                text = self.font.render("Click to select a color for transparency", True, (255, 255, 255))
                text_rect = text.get_rect(center=(self.width // 2, 20))
                self.screen.blit(text, text_rect)
                mouse_pos = pygame.mouse.get_pos()
                pygame.draw.circle(self.screen, (255, 255, 255), mouse_pos, 5, 1)

    def is_similar_color(self, c1, c2, tolerance):
        """Check if two colors are similar within tolerance."""
        return all(abs(c1[i] - c2[i]) <= tolerance for i in range(3))

    def setup_tray_icon(self):
        """Set up the system tray icon with menu."""
        def show_info():
            if self.video_path:
                info = f"Current Video: {os.path.basename(self.video_path)}\n" \
                       f"Dimensions: {self.width}x{self.height}\n" \
                       f"Scale Factor: {self.scale_factor:.2f}\n" \
                       f"Transparency Color: {self.transparency_color}\n" \
                       f"Color Tolerance: {self.color_tolerance}\n" \
                       f"Auto-Chroma Enabled: {self.auto_chroma_enabled}"
                messagebox.showinfo("Desktop Video Overlay Info", info)

        def set_tolerance():
            self.get_color_tolerance()

        def reset_chroma():
            self.reset_chroma()

        def auto_detect_chroma():
            self.auto_chroma_enabled = True  # Enable auto-detection
            self.auto_detect_chroma()
            self.get_color_tolerance()  # Prompt for tolerance only when enabling

        def quit_app():
            self.running = False
            if self.video:
                self.video.release()
            if self.vlc_player:
                self.vlc_player.stop()
                self.vlc_player.release()
            pygame.quit()
            self.icon.stop()
            sys.exit()

        menu = (
            item('Info', show_info),
            item('Settings', (
                item('Set Tolerance', set_tolerance),
                item('Reset Chroma', reset_chroma),
                item('Auto-detect Chroma', auto_detect_chroma),
            )),
            item('Quit', quit_app)
        )

        try:
            image = Image.open(os.path.join(sys._MEIPASS, "icon.png"))
        except AttributeError:
            image = Image.open("icon.png")  # Fallback for development

        self.icon = pystray.Icon("Desktop Video Overlay", image, "Desktop Video Overlay", menu)
        self.icon.run()

    def run(self):
        """Run the main application loop."""
        clock = pygame.time.Clock()
        while self.running:
            self.handle_events()
            self.draw_frame()
            pygame.display.flip()
            clock.tick(60)
        if self.video:
            self.video.release()
        if self.vlc_player:
            self.vlc_player.stop()
            self.vlc_player.release()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    try:
        print("Desktop Video Overlay starting...")
        print("Controls:")
        print("  Esc: Exit application or cancel color picking")
        print("  Space: Pause/Play video and sound")
        print("  O: Open a different video file(s)")
        print("  P: Pick a color from the video for transparency")
        print("  C: Reset chroma key to default")
        print("  A: Auto-detect chroma key color")
        print("  R: Reset video to original size")
        print("  +: Scale video up")
        print("  -: Scale video down")
        print("  Left Arrow: Previous video")
        print("  Right Arrow: Next video")
        print("  Click and drag: Move overlay around screen")
        
        app = DesktopVideoOverlay()
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        pygame.quit()
        sys.exit()