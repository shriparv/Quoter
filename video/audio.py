import struct
import math
import random
import wave
from pathlib import Path


class AudioGenerator:
    def __init__(self, sample_rate: int = 44100, channels: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels

    def generate_background(self, output_path: str | Path, duration: float = 10.0, volume: float = 0.15) -> str:
        n_samples = int(self.sample_rate * duration)
        samples = []
        notes = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
        base_note = random.choice(notes)
        octave_notes = [n * (2 ** random.randint(0, 2)) for n in notes]

        for i in range(n_samples):
            t = i / self.sample_rate
            val = 0.0
            chord = [base_note, base_note * 1.25, base_note * 1.5]
            for freq in chord:
                val += math.sin(2 * math.pi * freq * t) * 0.3
            fade = min(1.0, max(0.0, (t / 2.0), 1.0 - (t - duration + 2.0) / 2.0))
            val *= volume * fade
            val = max(-1.0, min(1.0, val))
            sample = int(val * 32767)
            samples.append(sample)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            for s in samples:
                wav.writeframes(struct.pack("<h", s))
                if self.channels == 2:
                    wav.writeframes(struct.pack("<h", s))
        return str(output_path)

    def generate_ambient(self, output_path: str | Path, duration: float = 15.0, volume: float = 0.1) -> str:
        n_samples = int(self.sample_rate * duration)
        samples = []
        drone_freq = random.choice([55.0, 65.41, 73.42, 82.41, 98.00, 110.0, 130.81])
        for i in range(n_samples):
            t = i / self.sample_rate
            val = math.sin(2 * math.pi * drone_freq * t) * 0.4
            val += math.sin(2 * math.pi * drone_freq * 2 * t) * 0.25
            val += math.sin(2 * math.pi * drone_freq * 0.5 * t) * 0.15
            modulation = math.sin(2 * math.pi * 0.25 * t)
            val *= (1.0 + modulation * 0.3)
            fade = min(1.0, max(0.0, (t / 2.0), 1.0 - (t - duration + 2.0) / 2.0))
            val *= volume * fade
            val = max(-1.0, min(1.0, val))
            sample = int(val * 32767)
            samples.append(sample)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            for s in samples:
                wav.writeframes(struct.pack("<h", s))
                if self.channels == 2:
                    wav.writeframes(struct.pack("<h", s))
        return str(output_path)
