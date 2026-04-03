# src/ui/screens/welcome.py

from src.UI.API.imports import *


# Create Title screen
class Title:
    def __init__(self, s_Mode, screen):
        # ===== CORE STATE =====
        self.s_Mode = s_Mode
        self.screen = screen
        self.screen_x, self.screen_y = screen.get_size()
        # ===== TIMING =====
        self.time = 5
        self.start_time_ms = pygame.time.get_ticks()
        # ===== SCREEN TEXT =====
        self.title_text = "WELCOME"
        self.subtitle_text = "This simulator is an independent academic project and is not affiliated with, endorsed by, or associated with Formula One Licensing B.V., the FIA Formula One World Championship™,"
        self.subtitle_text_2 = "or any Formula 1 teams. All trademarks, team names, and related marks are the property of their respective owners and are used for identification and educational purposes only."
        # ===== FADE SETTINGS =====
        self.alpha = 255
        self.fade_speed = 255 / (self.time * FPS)
        # ===== BACKGROUND =====
        self.dots = []
        self.dot_spacing = 40
        self.influence_radius = 150
        # ===== INITIAL UI BUILD =====
        self.create_dots()

    # ===== TEXT SURFACES =====
    def title(self):
        # Build the main welcome title
        title_font = pygame.font.Font(font_name, int(self.screen_x / 13.8375))
        title_text = title_font.render(self.title_text, True, text_colour_red)

        if self.alpha > 0:
            title_text.set_alpha(int(self.alpha))

        title_text_pos = title_text.get_rect(center=(self.screen_x / 2, self.screen_y / 3))
        return title_text, title_text_pos

    def subtitle(self):
        # Build the disclaimer text lines
        subtitle_font = pygame.font.Font(font_name, int(self.screen_x / 110.7))
        subtitle_text = subtitle_font.render(self.subtitle_text, True, grey)
        subtitle_text_2 = subtitle_font.render(self.subtitle_text_2, True, grey)

        if self.alpha > 0:
            subtitle_text.set_alpha(int(self.alpha))
            subtitle_text_2.set_alpha(int(self.alpha))

        subtitle_text_pos = subtitle_text.get_rect(center=(self.screen_x / 2, self.screen_y / 1.05))
        subtitle_text_pos_2 = subtitle_text_2.get_rect(center=(self.screen_x / 2, self.screen_y / 1.025))

        return subtitle_text, subtitle_text_pos, subtitle_text_2, subtitle_text_pos_2

    # ===== SCREEN TIMER =====
    def update_screen_timer(self):
        # Move to home screen once the welcome timer has finished
        elapsed_ms = pygame.time.get_ticks() - self.start_time_ms

        if elapsed_ms >= self.time * 1000:
            self.s_Mode = "Home"

    # ===== BACKGROUND =====
    def create_dots(self):
        self.dots.clear()

        for x in range(0, int(self.screen_x), self.dot_spacing):
            for y in range(0, int(self.screen_y), self.dot_spacing):
                self.dots.append({"pos": (x, y)})

    def update_dots(self):
        mouse_x, mouse_y = pygame.mouse.get_pos()

        for dot in self.dots:
            dot_x, dot_y = dot["pos"]
            dx = dot_x - mouse_x
            dy = dot_y - mouse_y
            distance = (dx**2 + dy**2) ** 0.5

            if distance < self.influence_radius:
                intensity = 1 - (distance / self.influence_radius)
                r = int(grey_2[0] + (red[0] - grey_2[0]) * intensity)
                g = int(grey_2[1] + (red[1] - grey_2[1]) * intensity)
                b = int(grey_2[2] + (red[2] - grey_2[2]) * intensity)
                color = (r, g, b)
                radius = 3 + (6 * intensity)

            else:
                color = grey_2
                radius = 3

            pygame.draw.circle(self.screen, color, (dot_x, dot_y), int(radius))

    # ===== RENDER =====
    def render(self, title_text, title_text_pos, subtitle_text, subtitle_text_pos, subtitle_text_2, subtitle_text_pos_2):
        # Background colour
        self.screen.fill(background_colour)

        # Update and draw dots
        self.update_dots()

        # Draw title and subtitle text
        self.screen.blit(title_text, title_text_pos)
        self.screen.blit(subtitle_text, subtitle_text_pos)
        self.screen.blit(subtitle_text_2, subtitle_text_pos_2)

    # ===== UPDATE =====
    def update(self):
        # Rebuild background dots if the window size changes
        new_w, new_h = self.screen.get_size()
        if new_w != self.screen_x or new_h != self.screen_y:
            self.screen_x, self.screen_y = new_w, new_h
            self.create_dots()

        # Check if user has quit screen
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.s_Mode = "Quit"

        # Update screen timer
        self.update_screen_timer()

        # Fade text out over time
        self.alpha = max(0, self.alpha - self.fade_speed)

        # Build text surfaces
        title_text, title_text_pos = self.title()
        subtitle_text, subtitle_text_pos, subtitle_text_2, subtitle_text_pos_2 = self.subtitle()

        # Render frame
        self.render(title_text, title_text_pos, subtitle_text, subtitle_text_pos, subtitle_text_2, subtitle_text_pos_2)

        pygame.display.flip()
        fpsClock.tick(FPS)

        return self.s_Mode, self.screen