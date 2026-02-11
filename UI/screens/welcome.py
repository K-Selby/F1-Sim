# screens/welcome.py

from API.imports import *

# Create Title screen
class Title:
    def __init__(self, s_Mode, screen):
        self.s_Mode = s_Mode
        self.screen = screen
        self.screen_x, self.screen_y = screen.get_size()
        self.time = 5
        self.count = 0
        self.title_text = "WELCOME"
        self.subtitle_text = "This simulator is an independent academic project and is not affiliated with, endorsed by, or associated with Formula One Licensing B.V., the FIA Formula One World Championship™,"
        self.subtitle_text_2 = "or any Formula 1 teams. All trademarks, team names, and related marks are the property of their respective owners and are used for identification and educational purposes only."
        self.alpha = 255
        self.fade_speed = 255 / (self.time * FPS)
        self.dots = []
        self.dot_spacing = 40
        self.influence_radius = 150
        self.create_dots()
           
    def title(self):
        # Text settings for title
        title_font = pygame.font.Font(font_name, int(self.screen_x / 13.8375))
        title_text = title_font.render(self.title_text, True, text_colour_red)
        
        if self.alpha > 0:
            title_text.set_alpha(int(self.alpha))
            
        title_text_pos = title_text.get_rect()
        title_text_pos.center = ((self.screen_x / 2), self.screen_y / 3)
        return title_text, title_text_pos
    
    def subtitle(self):
        # Text settings for subtitle
        subtitle_font = pygame.font.Font(font_name, int(self.screen_x / 110.7))
        subtitle_text = subtitle_font.render(self.subtitle_text, True, grey)
        
        # Text settings for subtitle 2
        subtitle_font_2 = pygame.font.Font(font_name, int(self.screen_x / 110.7))
        subtitle_text_2 = subtitle_font_2.render(self.subtitle_text_2, True, grey)
        
        if self.alpha > 0:
            subtitle_text.set_alpha(int(self.alpha))
            subtitle_text_2.set_alpha(int(self.alpha))
        
        subtitle_text_pos = subtitle_text.get_rect()
        subtitle_text_pos_2 = subtitle_text_2.get_rect()
        subtitle_text_pos.center = ((self.screen_x / 2), self.screen_y / 1.05)
        subtitle_text_pos_2.center = ((self.screen_x / 2), self.screen_y / 1.025)
        return subtitle_text, subtitle_text_pos, subtitle_text_2, subtitle_text_pos_2
    
    def timer(self):
        # Checks to see if its past the first call
        if self.count > 0:
            self.s_Mode = 'Home'

    def create_dots(self):
        self.dots.clear()

        for x in range(0, int(self.screen_x), self.dot_spacing):
            for y in range(0, int(self.screen_y), self.dot_spacing):
                self.dots.append({
                    "pos": (x, y),
                    "radius": 3
                })
             
    def update_dots(self):
        mouse_x, mouse_y = pygame.mouse.get_pos()

        for dot in self.dots:
            dot_x, dot_y = dot["pos"]
            dx = dot_x - mouse_x
            dy = dot_y - mouse_y
            distance = (dx**2 + dy**2) ** 0.5

            if distance < self.influence_radius:
                intensity = 1 - (distance / self.influence_radius)
                r = int(dot_colour[0] + (red[0] - dot_colour[0]) * intensity)
                g = int(dot_colour[1] + (red[1] - dot_colour[1]) * intensity)
                b = int(dot_colour[2] + (red[2] - dot_colour[2]) * intensity)
                color = (r, g, b)

                radius = 3 + (6 * intensity)
            else:
                color = dot_colour
                radius = 3
            
            pygame.draw.circle(self.screen, color, (dot_x, dot_y), int(radius))
                
    def render(self, title_text,title_text_pos, subtitle_text, subtitle_text_pos, subtitle_text_2, subtitle_text_pos_2):
        # Background colour
        self.screen.fill(background_colour)
        
        # Update and draw dots
        self.update_dots()
        
        # Draws the text onto the surface
        self.screen.blit(title_text, title_text_pos)
        
        # Draws the text onto the surface
        self.screen.blit(subtitle_text, subtitle_text_pos)
        self.screen.blit(subtitle_text_2, subtitle_text_pos_2)

    def update(self):
        self.screen_x, self.screen_y = self.screen.get_size()
        
        # Checks to make sure its only ran once 
        if self.count == 0:
            # Calls timer function every 5 seconds
            Timer(self.time, self.timer, args=()).start()
            self.count += 1
            
        # Checks if user has quit screen
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.s_Mode = 'Quit'
                
        self.alpha -= self.fade_speed
        
        # Calls functions in the title class
        title_text,title_text_pos = self.title()
        subtitle_text, subtitle_text_pos, subtitle_text_2, subtitle_text_pos_2 = self.subtitle()
        self.render(title_text, title_text_pos, subtitle_text, subtitle_text_pos, subtitle_text_2, subtitle_text_pos_2)
        
        # Updates display
        pygame.display.flip()
        fpsClock.tick(FPS)            
        
        return self.s_Mode, self.screen
    