"""
Main executable entry point for KRT Bookings Tracker Agent.
"""
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.agent import KRTTrackerAgent

def main():
    agent = KRTTrackerAgent()
    agent.start()

if __name__ == "__main__":
    main()
