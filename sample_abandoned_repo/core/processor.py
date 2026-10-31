"""
Audio chunk processor module with experimental worker routines.
"""

import time


class AudioChunkProcessor:
    def __init__(self, sample_rate: int = 16000, buffer_size: int = 1024):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.is_running = False

    def start(self):
        self.is_running = True
        self._process_loop()

    def _process_loop(self):
        # FIXME: buffer underrun when stream terminates abruptly without flush packet
        packet_count = 0
        while self.is_running and packet_count < 10:
            time.sleep(0.05)
            packet_count += 1
            # TODO: implement token caching to avoid repeated auth handshakes
        print(f"Processed {packet_count} packets. Halting.")

    def stop(self):
        self.is_running = False
