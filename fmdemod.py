import pyaudio
import struct
import math
import struct
import sys

# This is a simple FM demodulator which works on the principle of quadrature
# detection. (http://en.wikipedia.org/wiki/Detector_(radio)#Quadrature_detector)
# We assume that one is using the FunCube dongle, which samples at a rate at 96k
# and that the frequency of interest is tuned to 24kHz. (The Nyquist rate tells
# that since we are sampling at 96kSamples, the highest frequency that can be
# represented is 48kHz.) Quadrature demodulation works by multiplying the signal
# by a copy delayed by pi/2 (90 degress). If the frequency of interest is half
# the Nyquist rate, this is equivalent to delaying the original signal by 1
# sample.
# Then, the signal is low-pass filtered to remove the modulated signal around
# 24kHz.
# To robustly demodulate the FM signal, it should first be limited (to remove
# amplitude variations) and then de-emphasized (roll-off the high frequency
# signals).
# Also, note that although the dongle provides I/Q samples of the RF stream,
# this demodulator only uses the real samples (I).

# Samples from the FunCube come as 16 bit signed short integers.
# Utility functions to convert to normalized (-1.0 / 1.0) floats
def unpack(data):
    data_unpacked = struct.unpack('%sh' % (len(data)/2), data)
    data_float = ([],[])
    i = 0
    for sample in data_unpacked:
        sample = sample / (65536.0 / 2.0)
        data_float[i%2].append(sample)
        i+=1
    return data_float

def pack(data):
    data_ushort = []
    for i in range(len(data[0])):
        sample = data[0][i]
        sample = int(sample * 32768)
        if sample < -32768: sample = -32768
        if sample > 32767: sample = 32767
        data_ushort.append(sample)
        sample = data[1][i]
        sample = int(sample * 32768 + 32768)
        if sample < -32768: sample = -32768
        if sample > 32767: sample = 32767
        data_ushort.append(sample)
    data_packed = struct.pack('%sh' % len(data_ushort), *data_ushort)
    return data_packed


# FM quadrature demodulator
mem1 = 0.0
def demodulate(data):
    global mem1
    out = []
    for i in range(0,len(data)):        
        mul = mem1*data[i]
        mem1 = data[i]
        out.append(mul)
    return out

# FIR low pass filter (designed from http://t-filter.appspot.com/fir/index.html)
# with a passband of 0-7kHz and a stopband of 11kHz-48kHz.
# (Narrowband FM has a bandwidth of 20kHz or 15Khz, which would put lowest
# modulated frequency at 14kHz or 16.5kHz.)
coef = [
    -0.003751090021725844,
    -0.016457936753412384,
    -0.02294181624990546,
    -0.03409024368571728,
    -0.040497886062356034,
    -0.04050365821080267,
    -0.03036303211675522,
    -0.008740203839825258,
    0.02361683260953284,
    0.06325335897807506,
    0.10457588980440596,
    0.14085278715905142,
    0.1656876520146318,
    0.1745193485322739,
    0.1656876520146318,
    0.14085278715905142,
    0.10457588980440596,
    0.06325335897807506,
    0.02361683260953284,
    -0.008740203839825258,
    -0.03036303211675522,
    -0.04050365821080267,
    -0.040497886062356034,
    -0.03409024368571728,
    -0.02294181624990546,
    -0.016457936753412384,
    -0.003751090021725844
]
mem2 = [0]*len(coef)
def lpf(bitstream):
    out = []
    for i in range(len(bitstream)):
        mem2.append(bitstream[i])
        mem2.pop(0)
        sout = 0.0
        for j in range(len(coef)):
            sout += mem2[j] * coef[j]
        out.append(sout)
    return out

# Amplify the signal.
def amp(data):
    out = []
    for s in data:
        out.append(s*200.0)
    return out

# Read input from FunCube dongle and output demodulated audio.
CHUNK = 1024*10
WIDTH = 2
CHANNELS = 2
RATE = 96000

p = pyaudio.PyAudio()

stream = p.open(format=p.get_format_from_width(WIDTH),
                channels=CHANNELS,
                rate=RATE,
                input=True,
                output=True,
                frames_per_buffer=CHUNK)

while True:
    data = stream.read(CHUNK)
    l,r = unpack(data)
    ld = demodulate(l)
    lf = lpf(ld)
    la = amp(lf)
    p = pack((la,la))
    stream.write(p, CHUNK)

stream.stop_stream()
stream.close()

p.terminate()
