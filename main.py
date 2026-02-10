# main.py

from src.sim.RaceManager import RaceManager


def main():
    """
    Entry point for the MAS-based race simulation.

    main.py is intentionally thin:
    - It wires everything together
    - It does NOT contain race logic
    - All decisions live inside agents
    """

    ###rm = RaceManager(
        #total_laps=57,            # example: Bahrain
        #base_lap_time=96.0,       # baseline clean-air lap
        #track_deg_multiplier=1.0  # global degradation scaling
   ## ##)

    #rm.run()


if __name__ == "__main__":
    main()