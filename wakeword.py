# wakeword.py – neues Hintergrund-Thread
import pvporcupine
import pyaudio
import struct

porcupine = pvporcupine.create(keywords=["pia"])
audio_stream = pyaudio.PyAudio().open(...)

while True:
    pcm = audio_stream.read(porcupine.frame_length)
    if porcupine.process(struct.unpack_from("h" * porcupine.frame_length, pcm)) >= 0:
        print("Hey Pia erkannt!")
        start_listening()  # Deine Browser-Speech-Funktion