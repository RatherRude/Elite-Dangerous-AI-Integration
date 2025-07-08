import numpy as np

class RollingAudioBuffer:
    def __init__(self, max_samples: int):
        self.max_samples = max_samples
        self.buffer = np.zeros(max_samples, dtype=np.float32)
        self.current_size = 0

    def add_chunk(self, chunk: np.ndarray):
        chunk_len = len(chunk)
        if chunk_len >= self.max_samples:
            # If chunk is longer than buffer, just keep the last part
            self.buffer = chunk[-self.max_samples:]
            self.current_size = self.max_samples
        else:
            # Shift and insert new chunk
            shift_len = min(self.max_samples - chunk_len, self.current_size)
            self.buffer[:shift_len] = self.buffer[self.current_size - shift_len:self.current_size]
            self.buffer[shift_len:shift_len + chunk_len] = chunk
            self.current_size = min(self.current_size + chunk_len, self.max_samples)

    def get(self, length: int) -> np.ndarray:
        """Get the most recent `length` samples"""
        if self.current_size < length:
            return self.buffer[:self.current_size]
        return self.buffer[self.current_size - length:self.current_size]

    def get_all(self) -> np.ndarray:
        """Get all current samples in buffer"""
        return self.buffer[:self.current_size]
