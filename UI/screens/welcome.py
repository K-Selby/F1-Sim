# screens/welcome.py
from API.imports import *

# Create Title screen
class Title:
    def __init__(self, s_Mode, screen):
        self.s_Mode = s_Mode
        self.screen = screen
        self.screen_x, self.screen_y = screen.get_size()
        self.time = 3
        self.count = 0
        self.font = pygame.font.SysFont("arial", 64, bold=True)
        self.title_text = self.font.render('WELCOME', True, red)
        self.alpha = 255
        self.fade_speed = 255 / (self.time * FPS)
        
   
    def title(self):
        # Text settings for title
        if self.alpha > 0:
            self.title_text.set_alpha(int(self.alpha))
            
        title_text_pos = self.title_text.get_rect()
        title_text_pos.center = ((self.screen_x / 2), self.screen_y / 2)
        return title_text_pos
    
    def timer(self):
        # Checks to see if its past the first call
        if self.count > 0:
            self.s_Mode = 'Quit'

    def render(self, title_text_pos):
        # Background colour
        self.screen.fill(black)

        # Draws the text onto the surface
        self.screen.blit(self.title_text, title_text_pos)

    def update(self):
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
        title_text_pos = self.title()
        self.render(title_text_pos)
        
        # Updates display
        pygame.display.flip()
        fpsClock.tick(FPS)            
        
        return self.s_Mode
    