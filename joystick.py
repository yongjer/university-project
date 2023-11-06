# A function to initialize a joystick and print its events
def joystick_events():
    import pygame

    pygame.init()
    pygame.joystick.init()

    joystick_count = pygame.joystick.get_count()
    if joystick_count == 0:
        print("No joysticks found.")
        return
    else:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        print("Initialized joystick: {}".format(joystick.get_name()))

        while True:
            for event in pygame.event.get():
                if event.type == pygame.JOYAXISMOTION:
                    print("Axis {} value: {}".format(event.axis, joystick.get_axis(event.axis)))
                elif event.type == pygame.JOYBUTTONDOWN:
                    print("Button {} down".format(event.button))
                elif event.type == pygame.JOYBUTTONUP:
                    print("Button {} up".format(event.button))

# Call the function
joystick_events()