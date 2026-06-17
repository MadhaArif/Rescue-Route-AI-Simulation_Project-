from rescueroute.simulation import Simulation
import time
import signal
import sys

def main():
    print("Starting continuous headless simulation for dashboard updates...")
    sim = Simulation(seed=42)
    
    def signal_handler(sig, frame):
        print("\nStopping simulation...")
        sim.write_snapshot()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    dt = 0.5 # Fast forward a bit
    while True:
        sim.update(dt)
        # The Simulation class already handles writing snapshots based on SNAPSHOT_SECONDS
        time.sleep(0.1) # Small delay to not eat 100% CPU

if __name__ == "__main__":
    main()
