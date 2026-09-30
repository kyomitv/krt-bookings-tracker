"""
Main executable entry point for KRT Bookings Tracker Agent.
Enforces single-instance execution and initializes the agent controller.
"""
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.single_instance import SingleInstanceManager
from agent.agent import KRTTrackerAgent
from agent.logger import logger


def main():
    lock = SingleInstanceManager()
    if not lock.acquire():
        logger.warning("Une autre instance de KRT Bookings Tracker est déjà en cours d'exécution. Fermeture.")
        sys.exit(0)

    try:
        agent = KRTTrackerAgent(single_instance_lock=lock)
        agent.start()
    finally:
        lock.release()


if __name__ == "__main__":
    main()
