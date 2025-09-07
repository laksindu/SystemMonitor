import time

class FPSCounter:
    def __init__(self):
        self.frame_count = 0
        self.start_time = time.time()
        self.fps = 0

    def tick(self):
        """Call this once per frame"""
        self.frame_count += 1
        elapsed = time.time() - self.start_time
        if elapsed >= 1.0:  # update every second
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.start_time = time.time()
        return self.fps

# Example usage
fps_counter = FPSCounter()

for i in range(200):  # simulate 200 frames
    time.sleep(0.016)  # ~60 FPS
    print("FPS:", fps_counter.tick())
