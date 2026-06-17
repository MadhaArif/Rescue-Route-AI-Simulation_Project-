from rescueroute.simulation import Simulation
import time

def main():
    print("Starting headless simulation to generate dashboard data...")
    sim = Simulation(seed=42)
    
    # Run for 1000 virtual steps (0.1s each)
    dt = 0.1
    for i in range(2000):
        sim.update(dt)
        if i % 100 == 0:
            print(f"Simulation step {i}/2000, time: {sim.sim_time:.1f}s")
            # Force snapshot every 10 seconds of virtual time
            sim.write_snapshot()
        
        # Randomly spawn emergencies if none active
        if len(sim.active_emergencies) < 3 and i % 50 == 0:
            sim.spawn_emergency(force=True)
            
    print("Headless simulation complete. Initial data generated.")

if __name__ == "__main__":
    main()
